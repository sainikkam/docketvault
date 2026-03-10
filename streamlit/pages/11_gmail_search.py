"""Gmail Evidence Search.

Lets clients search their connected Gmail for emails matching
attorney evidence requests. Results are previewed, then imported
as Records (email body) and Artifacts (attachments).

This page delegates to the reusable gmail_search_widget, which is
also embedded on the Upload Evidence page.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_client, get_matter_id
from lib.api_client import api_get, is_google_connected
from lib.theme import setup_page, page_header
from lib.gmail_widget import gmail_search_widget

setup_page()
require_client()
matter_id = get_matter_id()

page_header("Gmail Search", "Find evidence in your email")

# Check Google connection (shared helper)
google_ok = is_google_connected()

if not google_ok:
    st.warning("Connect your Google account to search Gmail.")
    st.caption(
        "This gives DocketVault read-only access to search your emails. "
        "We never modify or delete anything."
    )
    if st.button("Connect Google Account", type="primary"):
        try:
            data = api_get("/oauth/google/authorize")
            st.markdown(f"[Click here to authorize]({data['authorize_url']})")
        except Exception as e:
            st.error(f"Failed to start OAuth: {e}")
    st.stop()

st.success("Google account connected — Drive and Gmail are ready", icon="✅")

# Render the full Gmail search + import widget
gmail_search_widget(matter_id, google_connected=True)
