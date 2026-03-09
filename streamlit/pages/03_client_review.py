import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_client, get_matter_id
from lib.api_client import api_get, api_patch
from lib.theme import setup_page, page_header, step_indicator

setup_page()
require_client()
matter_id = get_matter_id()

step_indicator(1)
page_header("Evidence Review", "Review your timeline and AI-extracted evidence")

# ── Timeline ──────────────────────────────────────────────────

st.subheader("Key Timeline")
try:
    events = api_get(f"/matters/{matter_id}/timeline")
    if events:
        for event in events:
            col_date, col_desc, col_action = st.columns([1, 3, 1])
            with col_date:
                st.caption(str(event.get("event_ts", "Unknown date")))
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
                # Let the client verify/confirm each event
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

# ── Evidence with Extractions ─────────────────────────────────

st.subheader("Extracted Evidence")
try:
    evidence = api_get(f"/matters/{matter_id}/evidence")
    artifacts = evidence.get("artifacts", [])
    if artifacts:
        for a in artifacts:
            with st.expander(f"{a['filename']} ({a.get('mime_type', '')}) — {a.get('status', '')}"):
                st.write(f"**Uploaded:** {a.get('uploaded_at', '')}")

                # Show AI extraction results if available
                try:
                    ext = api_get(f"/artifacts/{a['id']}/extraction")
                    if ext.get("summary"):
                        st.write(f"**Summary:** {ext['summary']}")
                    if ext.get("doc_type_guess") and ext["doc_type_guess"] != "unknown":
                        st.write(f"**Document Type:** {ext['doc_type_guess']}")
                    if ext.get("overall_summary"):
                        st.write(f"**Audio Summary:** {ext['overall_summary']}")
                    if ext.get("structured_claims"):
                        st.write("**Extracted Claims:**")
                        st.json(ext["structured_claims"])
                    if ext.get("transcript"):
                        st.write("**Transcript:**")
                        for seg in ext["transcript"]:
                            st.caption(f"[{seg.get('start_ms', 0)}ms] {seg.get('text', '')}")
                except Exception:
                    st.caption("No AI extraction available yet.")
    else:
        st.info("No evidence uploaded yet.")
except Exception as e:
    st.warning(f"Could not load evidence: {e}")

st.divider()

# ── Missing Items ─────────────────────────────────────────────

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

# ── Next step ─────────────────────────────────────────────────

st.divider()
st.page_link(
    "pages/04_client_share.py",
    label="Next: Share with your lawyer  \u2192",
)
