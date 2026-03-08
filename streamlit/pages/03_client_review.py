import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_client, get_matter_id
from lib.api_client import api_get

require_client()
matter_id = get_matter_id()

st.title("Evidence Review")

# --- Timeline ---
st.subheader("Key Timeline")
try:
    events = api_get(f"/matters/{matter_id}/timeline")
    if events:
        for event in events:
            col1, col2 = st.columns([1, 4])
            with col1:
                st.caption(str(event.get("event_ts", "Unknown date")))
            with col2:
                st.markdown(f"**{event['title']}**")
                if event.get("actors"):
                    st.caption(f"Actors: {', '.join(event['actors'])}")
                st.caption(f"Confidence: {event.get('confidence', 0):.0%} | {event.get('verification_state', '')}")
    else:
        st.info("No timeline events yet. Upload evidence and wait for processing.")
except Exception as e:
    st.warning(f"Could not load timeline: {e}")

st.divider()

# --- Evidence ---
st.subheader("Evidence")
try:
    evidence = api_get(f"/matters/{matter_id}/evidence")
    if evidence.get("artifacts"):
        for a in evidence["artifacts"]:
            st.write(f"- **{a['filename']}** ({a.get('mime_type', '')}) -- Status: {a.get('status', '')}")
    else:
        st.info("No evidence uploaded yet.")
except Exception as e:
    st.warning(f"Could not load evidence: {e}")

st.divider()

# --- Missing Items ---
st.subheader("Missing Items")
try:
    items = api_get(f"/matters/{matter_id}/missing-items")
    if items:
        for item in items:
            st.warning(f"**{item['missing_type']}** ({item['priority']}) -- {item.get('description', '')}")
    else:
        st.success("No missing items detected!")
except Exception as e:
    st.warning(f"Could not load missing items: {e}")
