"""Join a Matter — accept an invitation token from your attorney.

Login and registration are handled on the main landing page.
This page is for clients who already have an account and need
to join a matter using an invitation token.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.theme import setup_page, page_header
from lib.session import require_login
from lib.api_client import api_post

setup_page()
require_login()

page_header("Join a Matter", "Use an invitation token to join a case")

st.caption("Paste the invitation token your attorney shared with you.")

invite_token = st.text_input("Invitation Token", key="invite_token")
if st.button("Join Matter", type="primary"):
    if not invite_token.strip():
        st.warning("Please paste the invitation token.")
    else:
        try:
            member = api_post(f"/invitations/{invite_token.strip()}/accept")
            st.session_state.matter_id = member["matter_id"]
            st.success("You've joined the matter!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to join matter: {e}")
