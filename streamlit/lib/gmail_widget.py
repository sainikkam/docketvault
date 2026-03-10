"""Reusable Gmail search widget.

Renders a self-contained Gmail search + import UI that can be
embedded on any Streamlit page. Used on the Upload Evidence page
and the standalone Gmail Search page.
"""

import streamlit as st
from lib.api_client import api_get, api_post, is_google_connected


# ── Gmail card styles (scoped via class prefix) ──────────────

_GMAIL_CSS = """<style>
.gmail-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 4px solid #EA4335;
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.6rem;
}
.gmail-card.accepted {
    border-left-color: #10B981;
    background: #F0FDF4;
}
.gmail-card.rejected {
    border-left-color: #D1D5DB;
    background: #F9FAFB;
    opacity: 0.55;
}
.gmail-card .subject {
    font-weight: 600; color: #0F172A;
    margin: 0; font-size: 0.95rem;
}
.gmail-card .meta {
    font-size: 0.8rem; color: #64748B; margin: 0.2rem 0;
}
.gmail-card .snippet {
    font-size: 0.85rem; color: #475569; margin: 0.3rem 0 0 0;
}
.gmail-att-badge {
    display: inline-block;
    background: #FEF3C7; color: #92400E;
    border-radius: 12px; padding: 0.1rem 0.5rem;
    font-size: 0.7rem; font-weight: 600; margin-left: 0.4rem;
}
.gmail-query-box {
    background: #F8FAFC; border: 1px solid #E2E8F0;
    border-radius: 8px; padding: 0.7rem 1rem;
    font-family: monospace; font-size: 0.85rem;
    color: #334155; margin-bottom: 1rem;
}
</style>"""


def _get_decisions() -> dict:
    """Return the accept/reject decisions dict from session state."""
    if "gmail_decisions" not in st.session_state:
        st.session_state["gmail_decisions"] = {}
    return st.session_state["gmail_decisions"]


def _render_results(matter_id: str):
    """Display search results with accept/reject buttons and import controls."""
    result = st.session_state.get("gmail_results")
    if not result:
        return

    # Show the generated query
    st.markdown(
        f'<div class="gmail-query-box">Query: {result["query"]}</div>',
        unsafe_allow_html=True,
    )

    messages = result.get("messages", [])
    if not messages:
        st.info("No matching emails found. Try adjusting your search.")
        return

    decisions = _get_decisions()

    # Tally for the summary line
    accepted = [m for m in messages if decisions.get(m["message_id"]) == "accepted"]
    rejected = [m for m in messages if decisions.get(m["message_id"]) == "rejected"]
    pending  = len(messages) - len(accepted) - len(rejected)

    st.markdown(
        f"**{len(messages)}** emails found — "
        f"✅ {len(accepted)} accepted · ❌ {len(rejected)} rejected · "
        f"{pending} remaining"
    )

    # Render each email card with accept / reject buttons
    for msg in messages:
        mid = msg["message_id"]
        decision = decisions.get(mid)

        # Card CSS class based on decision
        card_cls = "gmail-card"
        if decision == "accepted":
            card_cls += " accepted"
        elif decision == "rejected":
            card_cls += " rejected"

        att_badge = ""
        if msg.get("has_attachments"):
            att_badge = (
                f'<span class="gmail-att-badge">'
                f'{msg["attachment_count"]} attachment(s)</span>'
            )

        # Status label shown inside the card
        status_label = ""
        if decision == "accepted":
            status_label = " — ✅ Accepted"
        elif decision == "rejected":
            status_label = " — ❌ Rejected"

        st.markdown(
            f"""<div class="{card_cls}">
                <p class="subject">{msg['subject']}{att_badge}{status_label}</p>
                <p class="meta">From: {msg['sender']}
                &nbsp;·&nbsp; {msg.get('date', '')}</p>
                <p class="snippet">{msg['snippet']}</p>
            </div>""",
            unsafe_allow_html=True,
        )

        # Accept / Reject / Undo buttons
        btn_cols = st.columns([1, 1, 2])
        with btn_cols[0]:
            if decision == "accepted":
                if st.button("Undo", key=f"gmail_undo_{mid}"):
                    decisions.pop(mid, None)
                    st.rerun()
            else:
                if st.button("✅ Relevant", key=f"gmail_acc_{mid}", type="primary"):
                    decisions[mid] = "accepted"
                    st.rerun()
        with btn_cols[1]:
            if decision == "rejected":
                if st.button("Undo", key=f"gmail_undox_{mid}"):
                    decisions.pop(mid, None)
                    st.rerun()
            else:
                if st.button("❌ Not relevant", key=f"gmail_rej_{mid}"):
                    decisions[mid] = "rejected"
                    st.rerun()

    # Import controls — only when at least one email is accepted
    if not accepted:
        if pending > 0:
            st.caption("Review each email above, then import the accepted ones.")
        else:
            st.info("No emails accepted. Adjust your search or re-review.")
        return

    st.divider()
    include_attachments = st.checkbox("Include attachments", value=True)

    if st.button(
        f"Import {len(accepted)} accepted email(s)",
        type="primary",
        key="gmail_import_btn",
    ):
        accepted_ids = [m["message_id"] for m in accepted]
        with st.spinner("Importing emails and attachments..."):
            try:
                import_result = api_post(
                    f"/matters/{matter_id}/gmail/import",
                    json={
                        "message_ids": accepted_ids,
                        "include_attachments": include_attachments,
                    },
                )
                st.success(
                    f"Imported {import_result['imported_emails']} email(s) "
                    f"and {import_result['imported_attachments']} attachment(s)!"
                )
                # Clear results and decisions after successful import
                st.session_state.pop("gmail_results", None)
                st.session_state.pop("gmail_decisions", None)
            except Exception as e:
                st.error(f"Import failed: {e}")


def gmail_search_widget(matter_id: str, google_connected: bool | None = None):
    """Render the full Gmail search + import widget.

    Args:
        matter_id: Active matter UUID.
        google_connected: Pre-checked connection status. If None the
            widget calls is_google_connected() itself (used when
            rendered on the standalone Gmail Search page).
    """
    st.markdown(_GMAIL_CSS, unsafe_allow_html=True)

    # Use the caller's check if provided, otherwise check ourselves
    connected = google_connected if google_connected is not None else is_google_connected()

    if not connected:
        st.caption("Connect your Google account above to search Gmail.")
        return

    # Search mode: attorney request vs custom query
    search_mode = st.radio(
        "How do you want to search?",
        ["From attorney request", "Custom search"],
        horizontal=True,
        key="gmail_search_mode",
    )

    # Mode 1 — search from an open evidence request
    if search_mode == "From attorney request":
        try:
            requests = api_get(f"/matters/{matter_id}/requests")
            open_reqs = [r for r in requests if r.get("status") == "open"]
        except Exception:
            open_reqs = []

        if not open_reqs:
            st.info("No open evidence requests. Ask your attorney to create one.")
            return

        req_titles = {r["title"]: r for r in open_reqs}
        selected_title = st.selectbox(
            "Select a request", list(req_titles.keys()), key="gmail_req_sel"
        )
        selected_req = req_titles[selected_title]

        with st.expander("Request details", expanded=False):
            if selected_req.get("description"):
                st.markdown(selected_req["description"])
            if selected_req.get("keywords"):
                st.markdown(
                    "**Keywords:** "
                    + ", ".join(f"`{k}`" for k in selected_req["keywords"])
                )
            if selected_req.get("date_range_start") or selected_req.get("date_range_end"):
                start = selected_req.get("date_range_start", "any")
                end = selected_req.get("date_range_end", "present")
                st.markdown(f"**Date range:** {start} → {end}")

        search_payload = {"request_id": selected_req["id"], "max_results": 25}

    # Mode 2 — custom free-text query
    else:
        raw_query = st.text_input(
            "Gmail search query",
            placeholder="e.g. rent payment receipt after:2024/01/01",
            key="gmail_raw_query",
        )
        if not raw_query:
            st.caption(
                "Use Gmail search syntax: `from:`, `subject:`, "
                "`after:YYYY/MM/DD`, `has:attachment`, etc."
            )
            return

        search_payload = {"raw_query": raw_query, "max_results": 25}

    # Execute search
    if st.button("Search Gmail", type="primary", key="gmail_search_btn"):
        with st.spinner("Searching your Gmail..."):
            try:
                result = api_post(
                    f"/matters/{matter_id}/gmail/search",
                    json=search_payload,
                )
            except Exception as e:
                st.error(f"Search failed: {e}")
                return

        st.session_state["gmail_results"] = result
        # Reset decisions for the new result set
        st.session_state["gmail_decisions"] = {}

    # Show results and import controls
    _render_results(matter_id)
