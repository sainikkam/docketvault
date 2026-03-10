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
from app.matters.models import EvidenceRequest, Matter
from app.worker import celery_app

# Import all table models so SQLAlchemy resolves foreign keys correctly
import app.auth.models  # noqa: F401 — registers users table
import app.sharing.models  # noqa: F401 — registers share_policies table
import app.notifications.models  # noqa: F401

CATEGORIZE_TIMELINE_SYSTEM = (
    "You are a legal intake assistant that works across all case types "
    "(employment, personal injury, landlord-tenant, family law, etc.). "
    "Given a list of evidence items (records and artifacts with extraction summaries), do two things:\n"
    "1. Categorize EVERY item and assign a relevance score (0.0 = not relevant, 1.0 = critical)\n"
    "2. Build a chronological timeline of key events\n"
    "Score relevance based on how useful the item is for the specific legal matter described. "
    "Pay close attention to the matter title and case type — they define what counts as relevant. "
    "Items that are clearly unrelated (spam, generic docs) should get low scores. "
    "Extract only what is supported by the evidence. Cite item IDs for every claim."
)

CATEGORIZE_TIMELINE_USER = """Matter: {matter_title}
Case type: {case_type}

Evidence items:
{items_text}

Return JSON with:
- categorizations: list of {{"item_id": str, "item_type": "record"|"artifact", "category": str, "tags": [str], "relevance_score": float, "relevance_rationale": str}}
  Categories: legal_documents, communications, financial_records, official_notices, photos_evidence, calendar_events, medical_records, employment_records, personal_journal, ai_conversations, social_media, other
  relevance_rationale: 1 sentence explaining why this item is or isn't relevant to this specific case type
- timeline_events: list of {{"event_type": str, "title": str, "event_ts": str|null, "actors": [str], "summary": str, "confidence": float, "citations": [{{"item_id": str, "excerpt": str}}], "related_item_ids": [str]}}
  Event types: agreement_signed, notice_received, payment_made, complaint_filed, legal_action, medical_event, therapy_session, workplace_event, communication_sent, relationship_event, milestone, other
"""

MISSING_SUMMARY_SYSTEM = (
    "You are a legal intake assistant that works across all case types. "
    "Given categorized evidence and a checklist of required items, do two things:\n"
    "1. Identify what's missing from the checklist\n"
    "2. Draft a concise intake summary for the attorney\n"
    "Tailor your analysis to the specific case type described. "
    "Be specific about what's missing and why it matters for this type of case."
)

MISSING_SUMMARY_USER = """Matter: {matter_title}
Case type: {case_type}

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


REQUEST_MATCH_SYSTEM = (
    "You are a legal evidence matching engine. Given a list of attorney evidence "
    "requests (with optional checklists) and a list of uploaded artifacts with "
    "their extraction summaries, do two things:\n"
    "1. Determine which artifacts satisfy which requests.\n"
    "2. For requests that have checklists, determine which checklist items are "
    "satisfied by the uploaded evidence.\n"
    "Match based on: category alignment, keyword presence in extracted text/claims, "
    "date range overlap, and source system match.\n"
    "Only report confident matches. Do not guess."
)

REQUEST_MATCH_USER = """Open evidence requests:
{requests_text}

Uploaded artifacts with extractions:
{artifacts_text}

Return JSON with:
- matches: list of {{
    "request_id": str,
    "artifact_ids": [str],
    "confidence": float (0..1),
    "reason": str (brief explanation of why these artifacts match)
  }}
- checklist_updates: list of {{
    "request_id": str,
    "completed_indices": [int] (0-based indices of checklist items satisfied by uploaded evidence),
    "reasons": [str] (brief explanation for each completed item, same order as indices)
  }}

Only include matches with confidence >= 0.7.
If no artifacts match a request, omit that request from the matches list.
Only mark a checklist item as completed if there is clear evidence for it.
"""


MAX_SAMPLE_PER_SOURCE = 5
MAX_RECORD_TEXT_LEN = 300
# Per-record scoring: max records sent per LLM call
MAX_RECORDS_PER_SCORING_BATCH = 50
MAX_RECORD_PREVIEW_LEN = 400

RECORD_SCORING_SYSTEM = (
    "You are a legal evidence relevance scorer. "
    "Given a legal matter description and a list of individual records "
    "(emails, messages, transactions, etc.) from a single file, "
    "score each record's relevance to the matter on a 0.0-1.0 scale.\n"
    "0.0 = completely unrelated (spam, personal, off-topic)\n"
    "0.4 = marginally relevant (tangential mention)\n"
    "0.7 = clearly relevant (directly discusses the matter)\n"
    "1.0 = critical evidence (key document for the case)\n"
    "Be discriminating — most records in a bulk file are NOT relevant."
)

RECORD_SCORING_USER = """Matter: {matter_title}
{matter_context}
Records from file "{source_file}":
{records_text}

Return JSON with:
- scores: list of {{"index": int, "relevance_score": float, "relevance_rationale": str}}

Score EVERY record listed above using its index number. Keep rationale to one short sentence.
"""


def _summarize_records_for_llm(records: list) -> str:
    """Build a compact summary of records grouped by source file.

    Instead of sending every record to the LLM (which can be 1000+),
    we group by source file and send: count, date range, types found,
    and a sample of representative text entries.
    """
    from collections import defaultdict

    by_source: dict[str, list] = defaultdict(list)
    for rec in records:
        source_file = ""
        if rec.metadata_ and isinstance(rec.metadata_, dict):
            source_file = rec.metadata_.get("source_file", rec.source)
        else:
            source_file = rec.source
        by_source[source_file].append(rec)

    lines = []
    for source_file, recs in by_source.items():
        count = len(recs)
        types = set(r.type for r in recs if r.type)
        sources = set(r.source for r in recs if r.source)

        # Date range
        dates = [r.ts for r in recs if r.ts]
        date_range = ""
        if dates:
            earliest = min(dates).strftime("%Y-%m-%d")
            latest = max(dates).strftime("%Y-%m-%d")
            date_range = f" | date_range={earliest} to {latest}"

        # Sample entries — take first few representative records
        samples = []
        for r in recs[:MAX_SAMPLE_PER_SOURCE]:
            text_preview = r.text[:MAX_RECORD_TEXT_LEN].replace("\n", " ")
            samples.append(f"    sample: [{r.type}] {text_preview}")

        lines.append(
            f"- source_file={source_file} | {count} records | "
            f"types={','.join(types)} | sources={','.join(sources)}{date_range}"
        )
        lines.extend(samples)

    return "\n".join(lines) + "\n" if lines else ""


def _parse_json_response(raw_text: str) -> dict:
    """Strip markdown code fences and parse JSON."""
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw_text)


def _build_matter_context(matter_id: UUID, db: Session) -> str:
    """Build a concise description of the matter for the scoring LLM.

    Pulls from intake summary and evidence requests so the LLM
    understands what the case is actually about (the matter title
    alone is often uninformative, e.g. "Joe Vs Schmoe").
    """
    from app.enrichment.models import IntakeSummary

    lines = []

    summary = (
        db.execute(
            select(IntakeSummary).where(IntakeSummary.matter_id == matter_id)
        )
        .scalars()
        .first()
    )
    if summary and summary.case_overview:
        # Truncate to keep prompt size reasonable
        lines.append(f"Case overview: {summary.case_overview[:500]}")

    reqs = list(
        db.execute(
            select(EvidenceRequest).where(
                EvidenceRequest.matter_id == matter_id
            )
        )
        .scalars()
        .all()
    )
    for req in reqs[:3]:
        parts = [f"Evidence request: {req.title}"]
        if req.description:
            parts.append(req.description[:200])
        if req.keywords:
            parts.append(f"Keywords: {', '.join(req.keywords[:20])}")
        lines.append(" | ".join(parts))

    return "\n".join(lines) if lines else ""


def _score_individual_records(
    matter_title: str,
    artifacts: list,
    records: list,
    client,
    settings,
    db: Session,
):
    """Score individual records within multi-item artifacts.

    After the main categorization pass (which scores at the artifact level
    and propagates uniformly), this does a focused second pass on each
    multi-item artifact to give each record its own relevance score.
    This enables per-record pre-selection in the sharing UI.
    """
    from collections import defaultdict

    # Gather context about the matter so the LLM knows what the
    # case is actually about (matter title alone is often vague)
    matter_id_val = artifacts[0].matter_id if artifacts else None
    matter_context = ""
    if matter_id_val:
        matter_context = _build_matter_context(matter_id_val, db)

    # Group records by their source artifact filename
    by_source: dict[str, list] = defaultdict(list)
    for rec in records:
        source_file = ""
        if rec.metadata_ and isinstance(rec.metadata_, dict):
            source_file = rec.metadata_.get("source_file", "")
        if source_file:
            by_source[source_file].append(rec)

    # Only process artifacts that actually have child records
    art_filename_set = {a.original_filename for a in artifacts}
    sources_with_records = [sf for sf in by_source if sf in art_filename_set]

    for source_file in sources_with_records:
        recs = by_source[source_file]
        if len(recs) <= 1:
            continue  # single-record files don't need individual scoring

        # Process in batches to stay within token limits
        for batch_start in range(0, len(recs), MAX_RECORDS_PER_SCORING_BATCH):
            batch = recs[batch_start:batch_start + MAX_RECORDS_PER_SCORING_BATCH]

            # Use simple integer indices instead of UUIDs. LLMs reliably
            # return small numbers but frequently mangle 36-char UUIDs.
            records_text = ""
            for i, rec in enumerate(batch):
                preview = rec.text[:MAX_RECORD_PREVIEW_LEN].replace("\n", " ")
                ts_str = rec.ts.isoformat() if rec.ts else "no date"
                records_text += (
                    f"- index={i} | type={rec.type} | "
                    f"date={ts_str} | text: {preview}\n"
                )

            try:
                response = client.messages.create(
                    model=settings.LLM_MODEL,
                    system=RECORD_SCORING_SYSTEM,
                    messages=[{
                        "role": "user",
                        "content": RECORD_SCORING_USER.format(
                            matter_title=matter_title,
                            matter_context=matter_context,
                            source_file=source_file,
                            records_text=records_text,
                        ),
                    }],
                    max_tokens=4096,
                )
                data = _parse_json_response(response.content[0].text)

                # Map integer indices back to actual records
                for score_entry in data.get("scores", []):
                    idx = score_entry.get("index")
                    if idx is None or not isinstance(idx, int):
                        continue
                    if 0 <= idx < len(batch):
                        batch[idx].relevance_score = score_entry.get(
                            "relevance_score", 0.0
                        )
                        db.add(batch[idx])

            except Exception:
                # Per-record scoring is best-effort; don't fail enrichment
                pass

        db.flush()


def _propagate_artifact_scores_to_records(
    artifacts: list, records: list, db: Session
):
    """Fallback: copy artifact relevance_score to child records still at 0.0.

    Per-record scoring via LLM can silently fail (UUID mismatches, rate
    limits, etc.). When that happens records are left at the default 0.0,
    which causes everything to show as 0% on the share preview. This
    fallback gives each unscored record its parent artifact's score so the
    relevance-based pre-selection in the sharing UI works correctly.
    """
    # Build artifact filename -> score map
    art_score_map: dict[str, float] = {}
    for art in artifacts:
        if art.relevance_score > 0:
            art_score_map[art.original_filename] = art.relevance_score

    if not art_score_map:
        return

    updated = 0
    for rec in records:
        if rec.relevance_score > 0:
            continue  # already scored individually
        source_file = ""
        if rec.metadata_ and isinstance(rec.metadata_, dict):
            source_file = rec.metadata_.get("source_file", "")
        parent_score = art_score_map.get(source_file)
        if parent_score:
            rec.relevance_score = parent_score
            db.add(rec)
            updated += 1

    if updated:
        db.flush()


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

        # Load matter template early so both LLM calls get the case type.
        # Falls back to "General" if no template is linked.
        template = (
            db.execute(
                select(MatterTemplate).where(MatterTemplate.id == matter.template_id)
            )
            .scalars()
            .first()
        ) if matter.template_id else None
        case_type = template.name if template else "General"

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

        # Build a compact items list for the LLM.
        # For large record sets, summarize by source file instead of listing
        # every record — avoids exceeding token limits.
        items_text = ""
        extraction_map: dict[str, Extraction] = {}

        items_text += _summarize_records_for_llm(records)

        for art in artifacts:
            extraction = (
                db.execute(
                    select(Extraction).where(Extraction.artifact_id == art.id)
                )
                .scalars()
                .first()
            )
            if extraction:
                extraction_map[str(art.id)] = extraction
                ext_summary = extraction.summary or extraction.overall_summary or ""
                claims_str = json.dumps(extraction.structured_claims) if extraction.structured_claims else "{}"
                items_text += (
                    f"- item_id={art.id} | item_type=artifact | filename={art.original_filename} "
                    f"| type={art.mime_type} | Extraction: {ext_summary} | Claims: {claims_str}\n"
                )
            else:
                items_text += (
                    f"- item_id={art.id} | item_type=artifact | filename={art.original_filename} "
                    f"| type={art.mime_type} | status={art.status}\n"
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
                        case_type=case_type,
                        items_text=items_text,
                    ),
                }
            ],
            max_tokens=8192,
        )
        data1 = _parse_json_response(response1.content[0].text)

        # Apply categorizations to both records and artifacts.
        # Build lookup maps: artifact filename -> artifact, for propagating
        # categories from artifacts to their child records.
        rec_id_set = {str(r.id) for r in records}
        art_id_set = {str(a.id) for a in artifacts}
        art_map = {str(a.id): a for a in artifacts}
        art_filename_map = {a.original_filename: a for a in artifacts}

        for cat in data1.get("categorizations", []):
            item_id = cat.get("item_id", cat.get("record_id", ""))
            category = cat.get("category", "uncategorized")
            tags = cat.get("tags", [])
            score = cat.get("relevance_score", 0.0)
            rationale = cat.get("relevance_rationale", "")

            if item_id in rec_id_set:
                rec = next((r for r in records if str(r.id) == item_id), None)
                if rec:
                    rec.category = category
                    rec.tags = tags
                    rec.relevance_score = score
                    db.add(rec)
            elif item_id in art_id_set:
                art = art_map.get(item_id)
                if art:
                    art.category = category
                    art.tags = tags
                    art.relevance_score = score
                    art.relevance_rationale = rationale
                    db.add(art)

                    # Propagate category and tags to child records.
                    # Relevance scores are set individually by
                    # _score_individual_records() below.
                    for rec in records:
                        source_file = ""
                        if rec.metadata_ and isinstance(rec.metadata_, dict):
                            source_file = rec.metadata_.get("source_file", "")
                        if source_file == art.original_filename:
                            rec.category = category
                            rec.tags = tags
                            db.add(rec)

        # Per-record relevance scoring for multi-item artifacts.
        # Gives each record its own score instead of inheriting the
        # artifact-level score, enabling relevance-based pre-selection
        # in the sharing UI.
        _score_individual_records(
            matter_title=matter.title,
            artifacts=artifacts,
            records=records,
            client=client,
            settings=settings,
            db=db,
        )

        # Fallback: if per-record scoring left records at 0.0 (e.g. due
        # to LLM errors or UUID mismatches), inherit the parent artifact's
        # score so the share preview has reasonable defaults.
        _propagate_artifact_scores_to_records(artifacts, records, db)

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
                related_record_ids=evt.get("related_item_ids", evt.get("related_record_ids", [])),
            )
            db.add(te)
        db.commit()

        # --- Build context for Call 2 ---
        categorized_lines = [
            f"- {rec.id}: [{rec.category}] tags={rec.tags} relevance={rec.relevance_score}"
            for rec in records
        ]
        for art in artifacts:
            categorized_lines.append(
                f"- {art.id}: [{art.category}] file={art.original_filename} "
                f"relevance={art.relevance_score}"
            )
        categorized_text = "\n".join(categorized_lines)
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

        # Get checklist from the template loaded earlier
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
                        case_type=case_type,
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

        # --- LLM Call 3: Auto-match artifacts to open evidence requests ---
        _try_auto_match_requests(
            matter_id=UUID(matter_id),
            matter_title=matter.title,
            artifacts=artifacts,
            items_text=items_text,
            client=client,
            settings=settings,
            db=db,
        )

        # Update matter status
        matter.status = "enriched"
        db.add(matter)
        db.commit()


def _try_auto_match_requests(
    matter_id: UUID,
    matter_title: str,
    artifacts: list,
    items_text: str,
    client,
    settings,
    db: Session,
):
    """Best-effort: match uploaded artifacts to open evidence requests via LLM.

    Runs after categorization + missing-items enrichment. If the LLM finds
    high-confidence matches (>= 0.85), it auto-marks the request as fulfilled
    and notifies attorneys. Lower-confidence matches are logged but left open.
    """
    try:
        # Load open requests for this matter
        open_requests = list(
            db.execute(
                select(EvidenceRequest).where(
                    EvidenceRequest.matter_id == matter_id,
                    EvidenceRequest.status == "open",
                )
            )
            .scalars()
            .all()
        )

        if not open_requests:
            return

        # Build request descriptions for the LLM, including checklists
        requests_text = ""
        for req in open_requests:
            parts = [f"request_id={req.id}", f"title={req.title}"]
            if req.category:
                parts.append(f"category={req.category}")
            if req.keywords:
                parts.append(f"keywords={json.dumps(req.keywords)}")
            if req.date_range_start or req.date_range_end:
                parts.append(
                    f"date_range={req.date_range_start} to {req.date_range_end}"
                )
            if req.source_system:
                parts.append(f"source_system={req.source_system}")
            if req.description:
                parts.append(f"description={req.description[:200]}")
            requests_text += f"- {' | '.join(parts)}\n"

            # Include checklist items so the LLM can determine which
            # are satisfied by the uploaded evidence
            if req.checklist:
                for idx, item in enumerate(req.checklist):
                    item_text = item.get("item", str(item))
                    done = item.get("completed", False)
                    status = "DONE" if done else "TODO"
                    requests_text += f"    checklist[{idx}] ({status}): {item_text}\n"

        response = client.messages.create(
            model=settings.LLM_MODEL,
            system=REQUEST_MATCH_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": REQUEST_MATCH_USER.format(
                        requests_text=requests_text,
                        artifacts_text=items_text,
                    ),
                }
            ],
            max_tokens=2048,
        )
        match_data = _parse_json_response(response.content[0].text)

        # Process artifact-to-request matches
        req_map = {str(r.id): r for r in open_requests}
        for match in match_data.get("matches", []):
            req_id = match.get("request_id")
            confidence = match.get("confidence", 0.0)
            if req_id not in req_map:
                continue

            req = req_map[req_id]
            if confidence >= 0.85:
                # High confidence: auto-fulfill and notify attorneys
                req.status = "fulfilled"
                db.add(req)

                from app.matters.models import AuditLog

                audit = AuditLog(
                    matter_id=matter_id,
                    user_id=req.created_by,
                    action="request_auto_fulfilled",
                    target_type="request",
                    target_id=req.id,
                    metadata_={
                        "confidence": confidence,
                        "reason": match.get("reason", ""),
                        "matched_artifact_ids": match.get("artifact_ids", []),
                    },
                )
                db.add(audit)

        # Process checklist auto-completion. The LLM identifies which
        # checklist items are satisfied by the uploaded evidence. We mark
        # those items as completed and tag them as "auto_detected" so the
        # UI can distinguish manual vs automatic check-offs.
        for cl_update in match_data.get("checklist_updates", []):
            req_id = cl_update.get("request_id")
            if req_id not in req_map:
                continue

            req = req_map[req_id]
            if not req.checklist:
                continue

            indices = cl_update.get("completed_indices", [])
            reasons = cl_update.get("reasons", [])
            checklist = list(req.checklist)  # copy to avoid mutation issues
            changed = False

            for i, idx in enumerate(indices):
                if not isinstance(idx, int) or idx < 0 or idx >= len(checklist):
                    continue
                if checklist[idx].get("completed"):
                    continue  # already checked, don't overwrite
                checklist[idx]["completed"] = True
                checklist[idx]["auto_detected"] = True
                if i < len(reasons):
                    checklist[idx]["auto_reason"] = reasons[i]
                changed = True

            if changed:
                req.checklist = checklist
                db.add(req)

        db.commit()

    except Exception:
        # Auto-matching is best-effort; don't fail the whole enrichment
        pass
