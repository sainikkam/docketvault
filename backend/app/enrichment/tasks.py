import json
from uuid import UUID

import anthropic
from sqlalchemy.orm import Session
from sqlmodel import select

from app.config import Settings
from app.database import sync_engine
from app.enrichment.models import IntakeSummary, MissingItem, TimelineEvent
from app.evidence.models import Artifact, Record
from app.extraction.models import Extraction
from app.firms.models import MatterTemplate
from app.matters.models import Matter
from app.worker import celery_app

CATEGORIZE_TIMELINE_SYSTEM = (
    "You are a legal intake assistant for landlord-tenant disputes. "
    "Given a list of evidence items (records with extraction summaries), do two things:\n"
    "1. Categorize each item and suggest tags\n"
    "2. Build a chronological timeline of key events\n"
    "Extract only what is supported by the evidence. Cite record IDs for every claim."
)

CATEGORIZE_TIMELINE_USER = """Matter: {matter_title}

Evidence items:
{items_text}

Return JSON with:
- categorizations: list of {{"record_id": str, "category": str, "tags": [str], "relevance_score": float}}
  Categories: lease_documents, communications, financial_records, notices, photos_evidence, calendar_events, other
- timeline_events: list of {{"event_type": str, "title": str, "event_ts": str|null, "actors": [str], "summary": str, "confidence": float, "citations": [{{"record_id": str, "excerpt": str}}], "related_record_ids": [str]}}
  Event types: lease_signed, notice_received, rent_paid, repair_requested, complaint_filed, eviction_notice, deposit_dispute, other
"""

MISSING_SUMMARY_SYSTEM = (
    "You are a legal intake assistant for landlord-tenant disputes. "
    "Given categorized evidence and a checklist of required items, do two things:\n"
    "1. Identify what's missing from the checklist\n"
    "2. Draft a concise intake summary for the attorney\n"
    "Be specific about what's missing and why it matters."
)

MISSING_SUMMARY_USER = """Matter: {matter_title}

Categorized evidence:
{categorized_text}

Timeline:
{timeline_text}

Required checklist items:
{checklist_text}

Return JSON with:
- missing_items: list of {{"missing_type": str, "description": str, "priority": "low"|"medium"|"high"}}
- intake_summary: {{
    "case_overview": str (2-3 paragraphs, cite record IDs in brackets like [rec_xxx]),
    "key_timeline": [{{"bullet": str, "citations": [{{"record_id": str}}]}}],
    "open_questions": [{{"question": str, "why": str}}]
  }}
"""


def _parse_json_response(raw_text: str) -> dict:
    """Strip markdown code fences and parse JSON."""
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw_text)


def check_and_trigger_enrichment(matter_id: UUID, db: Session):
    """After each extraction completes, check if all artifacts are done. If so, enrich."""
    pending = (
        db.execute(
            select(Artifact)
            .where(Artifact.matter_id == matter_id)
            .where(Artifact.status.in_(["uploading", "processing"]))
        )
        .scalars()
        .first()
    )
    if not pending:
        enrich_matter.delay(str(matter_id))


@celery_app.task(bind=True, max_retries=2)
def enrich_matter(self, matter_id: str):
    settings = Settings()
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    with Session(sync_engine) as db:
        matter = (
            db.execute(select(Matter).where(Matter.id == UUID(matter_id)))
            .scalars()
            .first()
        )
        if not matter:
            return

        # Gather all records + their extractions
        records = list(
            db.execute(select(Record).where(Record.matter_id == UUID(matter_id)))
            .scalars()
            .all()
        )

        # Also gather artifact extractions (for items without records)
        artifacts = list(
            db.execute(select(Artifact).where(Artifact.matter_id == UUID(matter_id)))
            .scalars()
            .all()
        )

        items_text = ""
        for rec in records:
            items_text += (
                f"- record_id={rec.id} | source={rec.source} | type={rec.type} "
                f"| ts={rec.ts} | text={rec.text[:500]}\n"
            )

        # Include artifact extractions
        for art in artifacts:
            extraction = (
                db.execute(
                    select(Extraction).where(Extraction.artifact_id == art.id)
                )
                .scalars()
                .first()
            )
            if extraction:
                ext_summary = extraction.summary or extraction.overall_summary or ""
                claims_str = json.dumps(extraction.structured_claims) if extraction.structured_claims else "{}"
                items_text += (
                    f"- artifact_id={art.id} | filename={art.original_filename} "
                    f"| type={art.mime_type} | Extraction: {ext_summary} | Claims: {claims_str}\n"
                )

        # --- LLM Call 1: Categorize + Timeline ---
        response1 = client.messages.create(
            model=settings.LLM_MODEL,
            system=CATEGORIZE_TIMELINE_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": CATEGORIZE_TIMELINE_USER.format(
                        matter_title=matter.title,
                        items_text=items_text,
                    ),
                }
            ],
            max_tokens=4096,
        )
        data1 = _parse_json_response(response1.content[0].text)

        # Apply categorizations to records
        cat_map = {c["record_id"]: c for c in data1.get("categorizations", [])}
        for rec in records:
            cat = cat_map.get(str(rec.id))
            if cat:
                rec.category = cat.get("category", "uncategorized")
                rec.tags = cat.get("tags", [])
                rec.relevance_score = cat.get("relevance_score", 0.0)
                db.add(rec)

        # Persist timeline events
        for evt in data1.get("timeline_events", []):
            te = TimelineEvent(
                matter_id=UUID(matter_id),
                event_type=evt.get("event_type", "unknown"),
                title=evt["title"],
                event_ts=evt.get("event_ts"),
                actors=evt.get("actors", []),
                summary=evt.get("summary", ""),
                confidence=evt.get("confidence", 0.0),
                verification_state=(
                    "high_confidence" if evt.get("confidence", 0) >= 0.85 else "needs_review"
                ),
                citations=evt.get("citations", []),
                related_record_ids=evt.get("related_record_ids", []),
            )
            db.add(te)
        db.commit()

        # --- Build context for Call 2 ---
        categorized_text = "\n".join(
            f"- {rec.id}: [{rec.category}] tags={rec.tags} relevance={rec.relevance_score}"
            for rec in records
        )
        timeline_events = list(
            db.execute(
                select(TimelineEvent)
                .where(TimelineEvent.matter_id == UUID(matter_id))
                .order_by(TimelineEvent.event_ts)
            )
            .scalars()
            .all()
        )
        timeline_text = "\n".join(
            f"- {te.event_ts}: {te.title} ({te.event_type})" for te in timeline_events
        )

        # Get checklist from matter template
        template = (
            db.execute(
                select(MatterTemplate).where(MatterTemplate.id == matter.template_id)
            )
            .scalars()
            .first()
        )
        checklist_text = json.dumps(template.checklist, indent=2) if template else "[]"

        # --- LLM Call 2: Missing Items + Intake Summary ---
        response2 = client.messages.create(
            model=settings.LLM_MODEL,
            system=MISSING_SUMMARY_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": MISSING_SUMMARY_USER.format(
                        matter_title=matter.title,
                        categorized_text=categorized_text,
                        timeline_text=timeline_text,
                        checklist_text=checklist_text,
                    ),
                }
            ],
            max_tokens=4096,
        )
        data2 = _parse_json_response(response2.content[0].text)

        # Persist missing items
        for mi in data2.get("missing_items", []):
            item = MissingItem(
                matter_id=UUID(matter_id),
                missing_type=mi["missing_type"],
                description=mi["description"],
                priority=mi.get("priority", "medium"),
            )
            db.add(item)

        # Persist intake summary (upsert)
        existing_summary = (
            db.execute(
                select(IntakeSummary).where(
                    IntakeSummary.matter_id == UUID(matter_id)
                )
            )
            .scalars()
            .first()
        )
        summary_data = data2.get("intake_summary", {})
        if existing_summary:
            existing_summary.case_overview = summary_data.get("case_overview", "")
            existing_summary.key_timeline = summary_data.get("key_timeline", [])
            existing_summary.open_questions = summary_data.get("open_questions", [])
            db.add(existing_summary)
        else:
            summary = IntakeSummary(
                matter_id=UUID(matter_id),
                case_overview=summary_data.get("case_overview", ""),
                key_timeline=summary_data.get("key_timeline", []),
                open_questions=summary_data.get("open_questions", []),
            )
            db.add(summary)

        # Update matter status
        matter.status = "enriched"
        db.add(matter)
        db.commit()
