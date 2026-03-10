import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_client, get_matter_id
from lib.api_client import api_get, api_patch, api_post
from lib.theme import setup_page, page_header, step_indicator

setup_page()
require_client()
matter_id = get_matter_id()

step_indicator(1)
page_header(
    "Evidence Review",
    "Preview how your evidence is organized before sharing with your attorney",
)

# ── Load organized evidence preview ──────────────────────────

try:
    preview = api_get(f"/matters/{matter_id}/evidence-preview")
except Exception as e:
    st.warning(f"Could not load evidence preview: {e}")
    st.info("Upload evidence first, then wait for AI processing to complete.")
    st.stop()

total = preview.get("total", 0)
relevant_count = preview.get("relevant_count", 0)
sensitive_count = preview.get("sensitive_count", 0)
low_count = preview.get("low_relevance_count", 0)

if total == 0:
    st.info("No evidence uploaded yet. Go to the Upload page to add files.")
    st.stop()

# ── Processing status check ──────────────────────────────────
# If everything is still at 0% relevance, the AI hasn't processed yet.

all_unscored = (relevant_count == 0 and low_count == total)
if all_unscored:
    st.warning(
        "Your evidence hasn't been analyzed by AI yet. "
        "Click below to start processing."
    )
    if st.button("Analyze My Evidence", type="primary"):
        try:
            result = api_post(f"/matters/{matter_id}/enrich")
            st.info(result.get("message", "Processing started..."))
            st.caption("This takes 15-30 seconds. Refresh the page after a moment.")
        except Exception as e:
            st.error(f"Could not start processing: {e}")
    st.divider()

# ── Summary metrics ──────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Items", total)
col2.metric("Relevant", relevant_count)
col3.metric("Sensitive", sensitive_count)
col4.metric("Needs Review", low_count)

st.divider()

# ── Helper: render a single evidence item ────────────────────


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


def render_item(item: dict, show_relevance: bool = True):
    """Render a single evidence item with its details."""
    filename = item.get("filename", "Unknown file")
    mime = item.get("mime_type", "")
    summary = item.get("summary", "")
    score = item.get("relevance_score", 0.0)
    rationale = item.get("relevance_rationale", "")
    doc_type = item.get("doc_type", "")
    tags = item.get("tags", [])
    is_sensitive = item.get("is_sensitive", False)

    # Build header with sensitivity badge
    header = f"**{filename}**"
    if is_sensitive:
        header += "  —  :warning: Contains Sensitive Info"

    with st.container(border=True):
        # Top row: filename, doc type, relevance
        top_left, top_right = st.columns([3, 1])
        with top_left:
            st.markdown(header)
            if doc_type and doc_type != "unknown":
                st.caption(f"Type: {doc_type}  |  {mime}")
            else:
                st.caption(mime)
        with top_right:
            if show_relevance:
                if score >= 0.7:
                    st.success(f"Relevance: {score:.0%}")
                elif score >= 0.4:
                    st.info(f"Relevance: {score:.0%}")
                else:
                    st.warning(f"Relevance: {score:.0%}")

        # Summary from AI extraction
        if summary:
            st.write(summary)

        # Relevance explanation
        if rationale:
            st.caption(f"Why: {rationale}")

        # Tags
        if tags:
            st.caption(f"Tags: {', '.join(tags)}")

        # Sensitivity details
        if is_sensitive:
            flags = item.get("sensitivity_flags", {})
            active_flags = [k.replace("contains_", "").replace("_", " ").title()
                           for k, v in flags.items() if v]
            if active_flags:
                st.warning(f"Detected: {', '.join(active_flags)}")


# ── Section 1: Relevant Evidence (grouped by category) ───────

st.subheader("Relevant Evidence")
st.caption(
    "These items were identified as relevant to your case, "
    "organized by category and sorted by importance."
)

relevant_by_cat = preview.get("relevant_by_category", {})
if relevant_by_cat:
    for cat_key, items in relevant_by_cat.items():
        label = CATEGORY_LABELS.get(cat_key, cat_key.replace("_", " ").title())
        st.markdown(f"#### {label} ({len(items)} items)")
        for item in items:
            render_item(item)
else:
    st.info(
        "No relevant items identified yet. "
        "This happens when AI processing hasn't completed. "
        "Check back shortly."
    )

st.divider()

# ── Section 2: Sensitive Items ───────────────────────────────

st.subheader("Sensitive Items")
st.caption(
    "These documents may contain sensitive information (SSN, account numbers, "
    "medical data, etc.). Review carefully before sharing with your attorney."
)

sensitive_items = preview.get("sensitive_items", [])
if sensitive_items:
    st.warning(
        f"**{len(sensitive_items)} item(s)** contain potentially sensitive information. "
        "You will be asked to explicitly acknowledge each one before sharing."
    )
    for item in sensitive_items:
        render_item(item, show_relevance=False)
else:
    st.success("No sensitive information detected in your uploads.")

st.divider()

# ── Section 3: Low Relevance Items ───────────────────────────

low_items = preview.get("low_relevance_items", [])
if low_items:
    with st.expander(
        f"Potentially Not Relevant ({len(low_items)} items)", expanded=False
    ):
        st.caption(
            "These items scored low on relevance. They won't be excluded "
            "automatically — you can still include them when sharing."
        )
        for item in low_items:
            render_item(item)

st.divider()

# ── Timeline ─────────────────────────────────────────────────

st.subheader("Key Timeline")
st.caption("Events extracted from your evidence, sorted chronologically.")

try:
    events = api_get(f"/matters/{matter_id}/timeline")
    if events:
        for event in events:
            col_date, col_desc, col_action = st.columns([1, 3, 1])
            with col_date:
                ts = event.get("event_ts")
                st.caption(str(ts) if ts else "Unknown date")
            with col_desc:
                st.markdown(f"**{event['title']}**")
                if event.get("summary"):
                    st.caption(event["summary"])
                if event.get("actors"):
                    st.caption(f"Actors: {', '.join(event['actors'])}")
                st.caption(
                    f"Confidence: {event.get('confidence', 0):.0%} | "
                    f"{event.get('verification_state', 'needs_review')}"
                )
            with col_action:
                state = event.get("verification_state", "needs_review")
                if state == "verified":
                    st.success("Verified")
                else:
                    if st.button("Verify", key=f"verify_event_{event['id']}"):
                        try:
                            api_patch(f"/timeline-events/{event['id']}/verify")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
    else:
        st.info("No timeline events yet. Upload evidence and wait for AI processing.")
except Exception as e:
    st.warning(f"Could not load timeline: {e}")

st.divider()

# ── Missing Items ────────────────────────────────────────────

st.subheader("Missing Items")
st.caption("Items the AI identified as gaps in your case.")
try:
    items = api_get(f"/matters/{matter_id}/missing-items")
    if items:
        for item in items:
            col_info, col_status = st.columns([4, 1])
            with col_info:
                st.warning(
                    f"**{item['missing_type']}** ({item['priority']}) — "
                    f"{item.get('description', '')}"
                )
            with col_status:
                if item.get("status") == "open":
                    st.caption("Open")
                else:
                    st.caption(item.get("status", ""))
    else:
        st.success("No missing items detected!")
except Exception as e:
    st.warning(f"Could not load missing items: {e}")

# ── Next step ────────────────────────────────────────────────

st.divider()
st.page_link(
    "pages/04_client_share.py",
    label="Next: Share with your lawyer  \u2192",
)
