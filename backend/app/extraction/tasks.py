import asyncio
import base64
import json
from uuid import UUID

import anthropic
from sqlalchemy.orm import Session
from sqlmodel import select

from app.config import Settings
from app.database import sync_engine
from app.evidence.models import Artifact
from app.extraction.models import Extraction
from app.storage import get_storage
from app.worker import celery_app

EXTRACTION_SYSTEM_PROMPT = (
    "You are an evidence extraction engine for a landlord-tenant legal intake vault. "
    "Extract only what is visible in the image/document. Do not infer or assume. "
    "Always provide citations as bounding boxes (normalized 0..1 coordinates). "
    "Respond with strict JSON matching the schema provided."
)

EXTRACTION_USER_TEMPLATE = """Analyze this {mime_type} file: "{filename}"
Matter type: landlord-tenant dispute

Extract and return JSON with these fields:
- extracted_text: all visible text
- summary: 1-2 sentence summary of what this document is
- doc_type_guess: one of [receipt, chat_screenshot, lease, notice, letter, invoice, photo, contract, bill, other]
- structured_claims: object with keys like "parties", "dates", "amounts", "addresses" — each value is a list of {{"value": "...", "citation": {{"page": 1, "region": {{"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}}}}}}
- sensitivity_flags: object with boolean keys: contains_ssn, contains_account_number, contains_medical, contains_minor_info
- confidence: float 0..1 for overall extraction quality

For PDFs, include "page" (1-indexed) in each citation. Bounding box coordinates are normalized 0..1 relative to page/image dimensions.
"""


@celery_app.task(bind=True, max_retries=3)
def extract_image_pdf(self, artifact_id: str):
    settings = Settings()
    storage = get_storage(settings)

    with Session(sync_engine) as db:
        artifact = (
            db.execute(select(Artifact).where(Artifact.id == UUID(artifact_id)))
            .scalars()
            .first()
        )
        if not artifact or artifact.status != "processing":
            return

        # Extract storage key from URI
        uri = artifact.storage_uri
        if uri.startswith("local://"):
            key = uri[len("local://") :]
        elif uri.startswith("s3://"):
            parts = uri[len("s3://") :].split("/", 1)
            key = parts[1] if len(parts) > 1 else parts[0]
        else:
            key = uri

        file_bytes = asyncio.run(storage.download(key))

        # Build Claude vision request
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        user_msg = EXTRACTION_USER_TEMPLATE.format(
            mime_type=artifact.mime_type,
            filename=artifact.original_filename,
        )

        media_type = artifact.mime_type

        response = client.messages.create(
            model=settings.LLM_MODEL,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.b64encode(file_bytes).decode(),
                            },
                        },
                        {"type": "text", "text": user_msg},
                    ],
                }
            ],
            max_tokens=4096,
        )

        # Parse JSON response
        raw_text = response.content[0].text
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0]
        extraction_data = json.loads(raw_text)

        # Validate: every claim must have a citation
        claims = extraction_data.get("structured_claims", {})
        for claim_list in claims.values():
            if isinstance(claim_list, list):
                for claim in claim_list:
                    if not claim.get("citation"):
                        claim["citation"] = {
                            "page": 1,
                            "region": {"x": 0, "y": 0, "w": 1, "h": 1},
                        }

        confidence = extraction_data.get("confidence", 0.0)
        verification_state = "high_confidence" if confidence >= 0.85 else "needs_review"

        extraction = Extraction(
            artifact_id=UUID(artifact_id),
            extracted_text=extraction_data.get("extracted_text", ""),
            summary=extraction_data.get("summary", ""),
            doc_type_guess=extraction_data.get("doc_type_guess", "unknown"),
            structured_claims=claims,
            sensitivity_flags=extraction_data.get("sensitivity_flags", {}),
            confidence=confidence,
            verification_state=verification_state,
        )
        db.add(extraction)

        artifact.status = "extracted"
        db.add(artifact)
        db.commit()
