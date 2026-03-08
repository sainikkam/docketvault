import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_attorney, get_matter_id
from lib.api_client import api_get, api_post

require_attorney()
matter_id = get_matter_id()

st.title("Matter Dashboard")

try:
    dashboard = api_get(f"/matters/{matter_id}/dashboard")

    # --- Key Metrics ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", dashboard.get("status", "active"))
    col2.metric("Timeline Events", len(dashboard.get("timeline_events", [])))
    col3.metric("Missing Items", len(dashboard.get("missing_items", [])))
    col4.metric("Recent Activity", len(dashboard.get("recent_activity", [])))

    st.divider()

    # --- Timeline ---
    st.subheader("Key Timeline")
    for event in dashboard.get("timeline_events", []):
        col_date, col_desc = st.columns([1, 4])
        with col_date:
            st.caption(str(event.get("event_ts", "?")))
        with col_desc:
            st.markdown(f"**{event['title']}**")
            if event.get("actors"):
                st.caption(f"Actors: {', '.join(event['actors'])}")

    st.divider()

    # --- Categories ---
    st.subheader("Evidence by Category")
    for cat, count in dashboard.get("category_counts", {}).items():
        st.write(f"- **{cat}**: {count} items")

    st.divider()

    # --- Missing Items ---
    st.subheader("Missing Items")
    missing = dashboard.get("missing_items", [])
    if missing:
        for item in missing:
            st.warning(f"**{item['missing_type']}** ({item['priority']}) -- {item.get('description', '')}")
    else:
        st.success("All expected evidence present.")

    st.divider()

    # --- Evidence Requests ---
    st.subheader("Evidence Requests")
    try:
        requests = api_get(f"/matters/{matter_id}/requests")
        for req in requests:
            status_icon = "+" if req["status"] == "fulfilled" else "?"
            st.write(f"{status_icon} **{req['title']}** -- {req['status']} ({req['priority']})")
    except Exception:
        st.info("No requests yet.")

    with st.expander("Create New Request"):
        title = st.text_input("Request title")
        desc = st.text_area("Description (optional)")
        priority = st.selectbox("Priority", ["medium", "high", "low"])
        if st.button("Send Request to Client"):
            if title:
                try:
                    api_post(f"/matters/{matter_id}/requests", json={
                        "title": title, "description": desc, "priority": priority,
                    })
                    st.success("Request sent!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

except Exception as e:
    st.error(f"Could not load dashboard: {e}")
