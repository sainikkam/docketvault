"""Gmail Evidence Search.

Lets clients search their connected Gmail for emails matching
attorney evidence requests. Results are previewed, then imported
as Records (email body) and Artifacts (attachments).
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_client, get_matter_id
from lib.api_client import api_get, api_post
from lib.theme import setup_page, page_header

setup_page()
require_client()
matter_id = get_matter_id()

page_header("Gmail Search", "Find evidence in your email")

# ── Page-specific CSS ─────────────────────────────────────────

st.markdown(
    """<style>
    .gmail-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #EA4335;
        border-radius: 8px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
    }
    .gmail-card .subject {
        font-weight: 600;
        color: #0F172A;
        margin: 0;
        font-size: 0.95rem;
    }
    .gmail-card .meta {
        font-size: 0.8rem;
        color: #64748B;
        margin: 0.2rem 0;
    }
    .gmail-card .snippet {
        font-size: 0.85rem;
        color: #475569;
        margin: 0.3rem 0 0 0;
    }
    .gmail-att-badge {
        display: inline-block;
        background: #FEF3C7;
        color: #92400E;
        border-radius: 12px;
        padding: 0.1rem 0.5rem;
        font-size: 0.7rem;
        font-weight: 600;
        margin-left: 0.4rem;
    }
    .gmail-query-box {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 0.7rem 1rem;
        font-family: monospace;
        font-size: 0.85rem;
        color: #334155;
        margin-bottom: 1rem;
    }
    </style>""",
    unsafe_allow_html=True,
)


# ── Check Google connection ───────────────────────────────────

def _check_connected():
    """Show connect button if Google isn't linked yet."""
    try:
        # Quick check: try listing drive files (reuses the same token)
        api_get("/oauth/google/drive/files")
        return True
    except Exception:
        return False


if not _check_connected():
    st.warning("Connect your Google account to search Gmail.")
    st.caption(
        "This gives DocketVault read-only access to search your emails. "
        "We never modify or delete anything."
    )
    if st.button("Connect Google Account", type="primary"):
        try:
            data = api_get("/oauth/google/authorize")
            st.markdown(
                f"[Click here to authorize]({data['authorize_url']})"
            )
        except Exception as e:
            st.error(f"Failed to start OAuth: {e}")
    st.stop()

st.success("Google account connected", icon="✅")

# ── Search mode selector ──────────────────────────────────────

search_mode = st.radio(
    "How do you want to search?",
    ["From attorney request", "Custom search"],
    horizontal=True,
)

# ── Mode 1: Search based on attorney evidence request ─────────

if search_mode == "From attorney request":
    try:
        requests = api_get(f"/matters/{matter_id}/requests")
        open_reqs = [r for r in requests if r.get("status") == "open"]
    except Exception:
        open_reqs = []

    if not open_reqs:
        st.info("No open evidence requests. Ask your attorney to create one.")
        st.stop()

    # Let client pick which request to search for
    req_titles = {r["title"]: r for r in open_reqs}
    selected_title = st.selectbox("Select a request", list(req_titles.keys()))
    selected_req = req_titles[selected_title]

    # Show what the attorney is asking for
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

# ── Mode 2: Custom free-text search ──────────────────────────

else:
    raw_query = st.text_input(
        "Gmail search query",
        placeholder="e.g. rent payment receipt after:2024/01/01",
    )
    if not raw_query:
        st.caption(
            "Use Gmail search syntax: `from:`, `subject:`, "
            "`after:YYYY/MM/DD`, `has:attachment`, etc."
        )
        st.stop()

    search_payload = {"raw_query": raw_query, "max_results": 25}

# ── Run search ────────────────────────────────────────────────

if st.button("Search Gmail", type="primary"):
    with st.spinner("Searching your Gmail..."):
        try:
            result = api_post(
                f"/matters/{matter_id}/gmail/search",
                json=search_payload,
            )
        except Exception as e:
            st.error(f"Search failed: {e}")
            st.stop()

    # Store results in session so they persist after button clicks
    st.session_state["gmail_results"] = result
    st.session_state["gmail_selected"] = set()

# ── Display results ───────────────────────────────────────────

result = st.session_state.get("gmail_results")
if not result:
    st.stop()

# Show the generated query so the client can see what was searched
st.markdown(
    f'<div class="gmail-query-box">Query: {result["query"]}</div>',
    unsafe_allow_html=True,
)

messages = result.get("messages", [])
if not messages:
    st.info("No matching emails found. Try adjusting your search.")
    st.stop()

st.markdown(f"**{len(messages)}** matching emails found")

# Render each email as a selectable card
selected_ids = []
for msg in messages:
    att_badge = ""
    if msg.get("has_attachments"):
        att_badge = (
            f'<span class="gmail-att-badge">'
            f'{msg["attachment_count"]} attachment(s)</span>'
        )

    st.markdown(
        f"""<div class="gmail-card">
            <p class="subject">{msg['subject']}{att_badge}</p>
            <p class="meta">From: {msg['sender']}
            &nbsp;·&nbsp; {msg.get('date', '')}</p>
            <p class="snippet">{msg['snippet']}</p>
        </div>""",
        unsafe_allow_html=True,
    )

    # Checkbox to select this email for import
    if st.checkbox(
        f"Import: {msg['subject'][:60]}",
        key=f"gmail_sel_{msg['message_id']}",
    ):
        selected_ids.append(msg["message_id"])

# ── Import selected ───────────────────────────────────────────

if not selected_ids:
    st.caption("Select emails above to import them as evidence.")
    st.stop()

st.divider()

include_attachments = st.checkbox("Include attachments", value=True)

if st.button(
    f"Import {len(selected_ids)} email(s)",
    type="primary",
):
    with st.spinner("Importing emails and attachments..."):
        try:
            import_result = api_post(
                f"/matters/{matter_id}/gmail/import",
                json={
                    "message_ids": selected_ids,
                    "include_attachments": include_attachments,
                },
            )
            st.success(
                f"Imported {import_result['imported_emails']} email(s) "
                f"and {import_result['imported_attachments']} attachment(s)!"
            )
            # Clear search results after successful import
            st.session_state.pop("gmail_results", None)
        except Exception as e:
            st.error(f"Import failed: {e}")
