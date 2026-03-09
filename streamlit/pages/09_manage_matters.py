from lib.theme import setup_page, page_header
from lib.api_client import api_get, api_post
from lib.session import require_attorney
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

setup_page()
require_attorney()

page_header("Manage Matters", "Set up your firm and cases")

# ── Section 1: Firm Setup ──────────────────────────────────────

st.subheader("1. Your Firms")

# Fetch existing firms
try:
    firms = api_get("/firms")
except Exception:
    firms = []

if firms:
    # Show existing firms in a table
    for f in firms:
        st.write(f"- **{f['name']}** (`{f['id'][:8]}...`)")
else:
    st.info("No firms yet. Create one below to get started.")

# Create new firm
with st.expander("Create New Firm", expanded=not firms):
    firm_name = st.text_input("Firm Name", key="new_firm_name")
    if st.button("Create Firm"):
        if not firm_name.strip():
            st.warning("Please enter a firm name.")
        else:
            try:
                firm = api_post("/firms", json={"name": firm_name.strip()})
                st.success(f"Firm '{firm['name']}' created!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to create firm: {e}")

st.divider()

if not firms:
    st.warning("Create a firm first (above) before continuing.")
    st.stop()

# Firm selector (shared by sections below)
firm_options = {f"{f['name']} ({f['id'][:8]}...)": f["id"] for f in firms}
selected_firm_label = st.selectbox("Select Firm", list(
    firm_options.keys()), key="template_firm")
selected_firm_id = firm_options[selected_firm_label]

# ── Section 2: Create a Matter ─────────────────────────────────

st.subheader("2. Create a Matter (Case)")

matter_title = st.text_input(
    "Matter Title", placeholder="e.g. Smith v. Jones", key="new_matter_title")

if st.button("Create Matter"):
    if not matter_title.strip():
        st.warning("Please enter a matter title.")
    else:
        try:
            matter = api_post("/matters", json={
                "firm_id": selected_firm_id,
                "title": matter_title.strip(),
            })
            # Auto-select the new matter
            st.session_state.matter_id = matter["id"]
            st.success(f"Matter '{matter['title']}' created and selected!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to create matter: {e}")

st.divider()

# ── Section 3: Your Matters ────────────────────────────────────

st.subheader("3. Your Matters")

try:
    matters = api_get("/matters")
except Exception:
    matters = []

if matters:
    for m in matters:
        col1, col2 = st.columns([3, 1])
        is_selected = st.session_state.matter_id == m["id"]
        col1.write(f"**{m['title']}** — Status: {m['status']}")
        if is_selected:
            col2.success("Selected")
        else:
            if col2.button("Select", key=f"select_{m['id']}"):
                st.session_state.matter_id = m["id"]
                st.rerun()
else:
    st.info("No matters yet. Create one above.")

st.divider()

# ── Section 4: Evidence Requests (before inviting client) ─────

st.subheader("4. Set Up Evidence Requests")
st.caption(
    "Create evidence requests with checklists **before** inviting the client. "
    "When the client joins, they'll immediately see what evidence to provide."
)

if not st.session_state.matter_id:
    st.warning("Select a matter first (above) before creating evidence requests.")
else:
    from lib.request_form import render_existing_requests, render_request_form

    render_existing_requests(st.session_state.matter_id)
    render_request_form(matter_id=st.session_state.matter_id, key_prefix="mm_")

st.divider()

# ── Section 5: Invite Client (final step) ─────────────────────

st.subheader("5. Invite the Client")
st.caption(
    "Once your evidence requests are ready, generate an invitation token "
    "and share it with your client."
)

if not st.session_state.matter_id:
    st.warning("Select a matter first (above) before inviting clients.")
else:
    invite_role = st.selectbox(
        "Invitation Role",
        ["primary_client", "contributor_client"],
        key="invite_role",
    )
    if st.button("Generate Invitation Link"):
        try:
            invite = api_post(
                f"/matters/{st.session_state.matter_id}/invitations",
                json={"role": invite_role},
            )
            st.success("Invitation created!")
            st.code(invite["token"], language=None)
            st.caption(
                "Share this token with the client. "
                "They can accept it on the login page after registering."
            )
        except Exception as e:
            st.error(f"Failed to create invitation: {e}")
