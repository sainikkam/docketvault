import asyncio
import base64
import json
import tempfile
from uuid import UUID

import anthropic
import openai
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

        # Check if all artifacts extracted → trigger enrichment
        _try_trigger_enrichment(artifact.matter_id, db)


def _try_trigger_enrichment(matter_id, db):
    """Best-effort: trigger enrichment if all artifacts are done."""
    try:
        from app.enrichment.tasks import check_and_trigger_enrichment

        check_and_trigger_enrichment(matter_id, db)
    except Exception:
        pass


# --- Audio extraction (Chunk 7) ---

AUDIO_SYSTEM_PROMPT = (
    "You are an evidence analysis engine for a landlord-tenant legal intake vault. "
    "Given a transcript of an audio recording, extract key moments, structured claims, "
    "and sensitivity flags. Do not infer beyond what is stated. Cite with time ranges."
)

AUDIO_USER_TEMPLATE = """Analyze this transcript from audio file: "{filename}"
Matter type: landlord-tenant dispute

Transcript segments:
{transcript_text}

Extract and return JSON with these fields:
- key_moments: list of {{"title": str, "summary": str, "start_ms": int, "end_ms": int, "confidence": float}}
- structured_claims: object with keys like "parties", "dates", "amounts", "promises", "threats" — each value is a list of {{"value": str, "citation": {{"start_ms": int, "end_ms": int}}}}
- sensitivity_flags: object with boolean keys: contains_ssn, contains_account_number, contains_medical, contains_minor_info, contains_threat
- confidence: float 0..1 for overall extraction quality
- overall_summary: 2-3 sentence summary of the recording
"""


def _audio_ext(mime_type: str) -> str:
    """Map MIME type to file extension for Whisper API."""
    return {
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
    }.get(mime_type, ".mp3")


@celery_app.task(bind=True, max_retries=3)
def extract_audio(self, artifact_id: str):
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
            key = uri[len("local://"):]
        elif uri.startswith("s3://"):
            parts = uri[len("s3://"):].split("/", 1)
            key = parts[1] if len(parts) > 1 else parts[0]
        else:
            key = uri

        file_bytes = asyncio.run(storage.download(key))

        # Step 1: Transcribe via OpenAI Whisper API
        oai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        with tempfile.NamedTemporaryFile(
            suffix=_audio_ext(artifact.mime_type), delete=True
        ) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            with open(tmp.name, "rb") as audio_file:
                whisper_response = oai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )

        # Parse transcript segments: [{start_ms, end_ms, text}]
        transcript_segments = []
        for seg in whisper_response.segments:
            transcript_segments.append({
                "start_ms": int(seg["start"] * 1000),
                "end_ms": int(seg["end"] * 1000),
                "text": seg["text"].strip(),
            })

        # Build transcript text for LLM
        transcript_text = "\n".join(
            f"[{s['start_ms']}ms - {s['end_ms']}ms] {s['text']}"
            for s in transcript_segments
        )

        # Step 2: Send transcript to Claude for key moment extraction
        claude_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        user_msg = AUDIO_USER_TEMPLATE.format(
            filename=artifact.original_filename,
            transcript_text=transcript_text,
        )
        response = claude_client.messages.create(
            model=settings.LLM_MODEL,
            system=AUDIO_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=4096,
        )

        # Parse JSON response
        raw_text = response.content[0].text
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0]
        extraction_data = json.loads(raw_text)

        confidence = extraction_data.get("confidence", 0.0)

        # Step 3: Persist Extraction
        extraction = Extraction(
            artifact_id=UUID(artifact_id),
            extracted_text="\n".join(s["text"] for s in transcript_segments),
            transcript=transcript_segments,
            key_moments=extraction_data.get("key_moments", []),
            overall_summary=extraction_data.get("overall_summary", ""),
            structured_claims=extraction_data.get("structured_claims", {}),
            sensitivity_flags=extraction_data.get("sensitivity_flags", {}),
            confidence=confidence,
            verification_state="high_confidence" if confidence >= 0.85 else "needs_review",
        )
        db.add(extraction)

        artifact.status = "extracted"
        db.add(artifact)
        db.commit()

        # Check if all artifacts extracted → trigger enrichment
        _try_trigger_enrichment(artifact.matter_id, db)
