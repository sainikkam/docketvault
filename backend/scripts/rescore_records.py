"""One-time script: set varied relevance scores on existing records
using keyword matching (no LLM calls, no API cost).

Clears existing record_share_states so they get recreated
with the new scores on next share-preview load.
"""
import sys
sys.path.insert(0, ".")

from sqlmodel import select, Session
from app.database import sync_engine
from app.evidence.models import Record
from app.sharing.models import RecordShareState
import app.auth.models  # noqa: registers users table
import app.matters.models  # noqa: registers matters table

MATTER_ID = "9f1d2c96-77db-4fbd-9a47-a0c63026623a"

# Keywords that indicate high relevance to an emotional distress / workplace case
HIGH_KEYWORDS = [
    "therapy", "therapist", "dr. kim", "anxiety", "stress", "distress",
    "harassment", "complaint", "hostile", "discrimination", "hr ",
    "human resources", "incident", "retaliation", "medical", "diagnosis",
    "medication", "panic", "depression", "leave of absence", "fmla",
    "eeoc", "lawyer", "attorney", "legal",
]
MED_KEYWORDS = [
    "manager", "performance", "review", "meeting", "deadline",
    "workload", "overtime", "schedule", "conflict", "feedback",
    "promotion", "director", "roadmap", "sprint", "team",
]
LOW_KEYWORDS = [
    "dinner", "fitbit", "marathon", "training run", "recipe",
    "netflix", "spotify", "gym", "restaurant", "birthday",
    "vacation", "holiday", "shopping", "unsubscribe", "newsletter",
    "statement ready", "weekly report", "spam",
]


def score_record(text: str) -> float:
    lower = text.lower()
    for kw in HIGH_KEYWORDS:
        if kw in lower:
            return 0.85
    for kw in MED_KEYWORDS:
        if kw in lower:
            return 0.55
    for kw in LOW_KEYWORDS:
        if kw in lower:
            return 0.15
    return 0.3  # default: slightly below threshold


with Session(sync_engine) as db:
    records = list(
        db.execute(select(Record).where(Record.matter_id == MATTER_ID))
        .scalars().all()
    )
    print(f"Scoring {len(records)} records by keywords...")

    high = med = low = 0
    for rec in records:
        new_score = score_record(rec.text)
        rec.relevance_score = new_score
        db.add(rec)
        if new_score >= 0.7:
            high += 1
        elif new_score >= 0.4:
            med += 1
        else:
            low += 1

    # Clear existing record share states so they regenerate
    # with the new scores on next share-preview load
    existing = list(
        db.execute(select(RecordShareState)).scalars().all()
    )
    for rss in existing:
        db.delete(rss)

    db.commit()
    print(f"Done! High: {high}, Medium: {med}, Low: {low}")
    print("Record share states cleared — will regenerate on next page load.")
