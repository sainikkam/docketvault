import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_attorney, get_matter_id
from lib.api_client import api_get
from lib.theme import setup_page, page_header

setup_page()
require_attorney()
matter_id = get_matter_id()

page_header("Evidence Viewer", "Browse approved evidence sorted by relevance")

CATEGORY_LABELS = {
    "lease_documents": "Lease & Legal Documents",
    "communications": "Communications",
    "financial_records": "Financial Records",
    "notices": "Notices & Letters",
    "photos_evidence": "Photos & Visual Evidence",
    "calendar_events": "Calendar & Scheduling",
    "medical_records": "Medical Records",
    "personal_journal": "Personal Journal & Reflections",
    "ai_conversations": "AI Assistant Conversations",
    "social_media": "Social Media",
    "other": "Other",
    "uncategorized": "Uncategorized",
}


def _render_approved_records(artifact_id: str):
    """Fetch and display the individual approved records within a multi-item artifact.

    Only records the client marked as "included" are returned by the API
    for attorney/paralegal users.
    """
    try:
        data = api_get(f"/artifacts/{artifact_id}/records")
        records = data.get("records", [])
        total = data.get("total", len(records))

        if not records:
            st.caption("No individual items shared from this file.")
            return

        st.write(f"**{total} shared items from this file:**")
        for rec in records:
            rec_score = rec.get("relevance_score", 0.0)
            with st.container(border=True):
                meta_col, text_col = st.columns([1, 4])
                with meta_col:
                    if rec.get("type"):
                        st.caption(rec["type"])
                    if rec.get("ts"):
                        st.caption(rec["ts"][:10])
                    if rec_score >= 0.7:
                        st.success(f"{rec_score:.0%}")
                    elif rec_score >= 0.4:
                        st.info(f"{rec_score:.0%}")
                    else:
                        st.caption(f"{rec_score:.0%}")
                with text_col:
                    st.write(rec.get("text", ""))
    except Exception:
        st.caption("Could not load individual items.")


def render_artifact(artifact: dict):
    """Render a single artifact with its extraction details."""
    score = artifact.get("relevance_score", 0.0)
    tags = artifact.get("tags", [])
    rationale = artifact.get("relevance_rationale", "")

    with st.expander(
        f"{artifact['filename']} ({artifact.get('mime_type', '')}) — {score:.0%} relevance"
    ):
        info_col, score_col = st.columns([3, 1])
        with info_col:
            st.write(f"**Status:** {artifact.get('status', '')}")
            st.write(f"**Uploaded:** {artifact.get('uploaded_at', '')}")
            if rationale:
                st.write(f"**Why relevant:** {rationale}")
            if tags:
                st.write(f"**Tags:** {', '.join(tags)}")
        with score_col:
            if score >= 0.7:
                st.success(f"Relevance: {score:.0%}")
            elif score >= 0.4:
                st.info(f"Relevance: {score:.0%}")
            else:
                st.warning(f"Relevance: {score:.0%}")

        # Load AI extraction results
        try:
            ext = api_get(f"/artifacts/{artifact['id']}/extraction")

            if ext.get("summary"):
                st.subheader("Summary")
                st.write(ext["summary"])

            if ext.get("doc_type_guess") and ext["doc_type_guess"] != "unknown":
                st.write(f"**Document Type:** {ext['doc_type_guess']}")

            if ext.get("overall_summary"):
                st.subheader("Audio Summary")
                st.write(ext["overall_summary"])

            if ext.get("transcript"):
                st.subheader("Transcript")
                for seg in ext["transcript"]:
                    start = seg.get("start_ms", 0)
                    text = seg.get("text", "")
                    st.caption(f"[{start}ms] {text}")

            if ext.get("key_moments"):
                st.subheader("Key Moments")
                for moment in ext["key_moments"]:
                    st.write(
                        f"- **{moment.get('title', '')}**: "
                        f"{moment.get('summary', '')}"
                    )

            if ext.get("structured_claims"):
                st.subheader("Extracted Claims")
                st.json(ext["structured_claims"])

            if ext.get("sensitivity_flags"):
                flags = ext["sensitivity_flags"]
                active = [k for k, v in flags.items() if v]
                if active:
                    st.warning(f"Sensitivity flags: {', '.join(active)}")

        except Exception:
            st.caption("No AI extraction available for this artifact.")

        # Show individual approved records for multi-item artifacts
        # (e.g. emails from a JSONL export where the client chose specific items)
        if artifact.get("mime_type") in (
            "application/jsonl", "application/x-ndjson", "text/jsonl",
        ) or (artifact.get("filename", "").endswith(".jsonl")):
            st.divider()
            _render_approved_records(artifact["id"])


# ── Main content ─────────────────────────────────────────────

try:
    evidence = api_get(f"/matters/{matter_id}/evidence?sort_by=relevance")
    artifacts = evidence.get("artifacts", [])

    if not artifacts:
        st.info("No approved evidence yet. The client needs to approve sharing first.")
        st.stop()

    st.write(f"**{evidence.get('total', len(artifacts))} approved artifacts**")

    # ── Filter controls ──────────────────────────────────────

    filter_col, sort_col = st.columns(2)
    with filter_col:
        cats = sorted(set(a.get("category", "uncategorized") for a in artifacts))
        cat_options = ["All"] + cats
        selected_cat = st.selectbox(
            "Filter by category",
            cat_options,
            format_func=lambda c: (
                CATEGORY_LABELS.get(c, c.replace("_", " ").title())
                if c != "All" else "All Categories"
            ),
        )
    with sort_col:
        sort_choice = st.selectbox(
            "Sort by",
            ["Relevance (highest first)", "Upload date (newest first)"],
        )

    filtered = artifacts
    if selected_cat != "All":
        filtered = [a for a in artifacts if a.get("category") == selected_cat]

    if "Upload date" in sort_choice:
        filtered = sorted(
            filtered, key=lambda x: x.get("uploaded_at", ""), reverse=True
        )

    st.divider()

    # ── Display ──────────────────────────────────────────────

    if selected_cat == "All":
        # Group by category
        by_cat: dict[str, list] = {}
        for a in filtered:
            cat = a.get("category", "uncategorized")
            by_cat.setdefault(cat, []).append(a)

        for cat_key, cat_items in by_cat.items():
            label = CATEGORY_LABELS.get(cat_key, cat_key.replace("_", " ").title())
            st.subheader(f"{label} ({len(cat_items)})")
            for artifact in cat_items:
                render_artifact(artifact)
    else:
        for artifact in filtered:
            render_artifact(artifact)

except Exception as e:
    st.error(f"Could not load evidence: {e}")
