import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_login, get_matter_id
from lib.api_client import api_get
from lib.theme import setup_page, page_header

setup_page()
require_login()
matter_id = get_matter_id()

page_header("Audit Log", "Complete, append-only audit trail for this matter")

try:
    entries = api_get(f"/matters/{matter_id}/audit-log")

    if not entries:
        st.info("No audit entries yet.")
        st.stop()

    # Filter by action type
    actions = sorted(set(e.get("action", "") for e in entries))
    selected_action = st.selectbox(
        "Filter by action", ["All"] + actions, key="audit_action_filter"
    )

    filtered = entries if selected_action == "All" else [
        e for e in entries if e.get("action") == selected_action
    ]

    st.write(f"Showing {len(filtered)} of {len(entries)} entries")

    # Display as table
    for entry in filtered:
        col_time, col_action, col_target, col_user = st.columns([2, 2, 1, 1])
        with col_time:
            st.caption(str(entry.get("created_at", "")))
        with col_action:
            st.write(entry.get("action", ""))
        with col_target:
            target = entry.get("target_type", "")
            if target:
                st.caption(target)
        with col_user:
            user_id = str(entry.get("user_id", ""))
            st.caption(f"{user_id[:8]}..." if user_id else "")

except Exception as e:
    st.error(f"Could not load audit log: {e}")
