import streamlit as st


def require_login():
    """Redirect to login if not authenticated."""
    if not st.session_state.get("access_token"):
        st.warning("Please log in first.")
        st.stop()


def require_client():
    """Stop page if user is not a client."""
    require_login()
    if st.session_state.get("role") not in ("primary_client", "contributor_client"):
        st.error("This page requires client access.")
        st.stop()


def require_attorney():
    """Stop page if user is not an attorney/paralegal."""
    require_login()
    if st.session_state.get("role") not in ("attorney", "paralegal"):
        st.error("This page requires attorney access.")
        st.stop()


def get_matter_id():
    """Get current matter ID from session."""
    matter_id = st.session_state.get("matter_id")
    if not matter_id:
        st.warning("No matter selected. Please select a matter first.")
        st.stop()
    return matter_id
