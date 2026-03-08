import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_login, get_matter_id
from lib.api_client import api_get

require_login()
matter_id = get_matter_id()

st.title("Audit Log")
st.caption("Complete, append-only audit trail for this matter.")

try:
    entries = api_get(f"/matters/{matter_id}/audit-log")

    if not entries:
        st.info("No audit entries yet.")
        st.stop()

    # Filter by action type
    actions = sorted(set(e.get("action", "") for e in entries))
    selected_action = st.selectbox("Filter by action", ["All"] + actions)

    filtered = entries if selected_action == "All" else [
        e for e in entries if e.get("action") == selected_action
    ]

    # Display as table
    for entry in filtered:
        col_time, col_action, col_user = st.columns([2, 2, 2])
        with col_time:
            st.caption(str(entry.get("created_at", "")))
        with col_action:
            st.write(entry.get("action", ""))
        with col_user:
            st.caption(str(entry.get("user_id", ""))[:8] + "...")

except Exception as e:
    st.error(f"Could not load audit log: {e}")
