from lib.theme import setup_page, page_header
from lib.api_client import api_get
from lib.session import require_attorney, get_matter_id
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

setup_page()
require_attorney()
matter_id = get_matter_id()

page_header("Matter Dashboard", "Overview of your active case")

try:
    dashboard = api_get(f"/matters/{matter_id}/dashboard")

    # ── Key Metrics ───────────────────────────────────────────

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", dashboard.get("status", "active"))
    col2.metric("Timeline Events", len(dashboard.get("timeline_events", [])))
    col3.metric("Missing Items", len(dashboard.get("missing_items", [])))
    col4.metric("Recent Activity", len(dashboard.get("recent_activity", [])))

    st.divider()

    # ── Timeline ──────────────────────────────────────────────

    st.subheader("Key Timeline")
    events = dashboard.get("timeline_events", [])
    if events:
        for event in events:
            col_date, col_desc = st.columns([1, 4])
            with col_date:
                st.caption(str(event.get("event_ts", "?")))
            with col_desc:
                st.markdown(f"**{event['title']}**")
                if event.get("summary"):
                    st.caption(event["summary"])
                if event.get("actors"):
                    st.caption(f"Actors: {', '.join(event['actors'])}")
    else:
        st.info("No timeline events yet.")

    st.divider()

    # ── Evidence by Category ──────────────────────────────────

    st.subheader("Evidence by Category")
    cat_counts = dashboard.get("category_counts", {})
    if cat_counts:
        for cat, count in cat_counts.items():
            st.write(f"- **{cat}**: {count} items")
    else:
        st.info("No evidence categorized yet.")

    st.divider()

    # ── Missing Items ─────────────────────────────────────────

    st.subheader("Missing Items")
    missing = dashboard.get("missing_items", [])
    if missing:
        for item in missing:
            st.warning(
                f"**{item['missing_type']}** ({item['priority']}) — "
                f"{item.get('description', '')}"
            )
    else:
        st.success("All expected evidence present.")

    st.divider()

    # ── Evidence Requests ─────────────────────────────────────

    st.subheader("Evidence Requests")
    st.caption(
        "Request specific documents from the client using structured RFP forms.")

    from lib.request_form import render_existing_requests, render_request_form

    render_existing_requests(matter_id)
    render_request_form(
        matter_id=matter_id,
        key_prefix="db_",
    )

    st.divider()

    # ── Recent Activity ───────────────────────────────────────

    st.subheader("Recent Activity")
    activity = dashboard.get("recent_activity", [])
    if activity:
        for entry in activity[:10]:
            st.caption(
                f"{entry.get('created_at', '')} — {entry.get('action', '')}")
    else:
        st.info("No recent activity.")

except Exception as e:
    st.error(f"Could not load dashboard: {e}")
