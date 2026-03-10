import streamlit as st


def try_restore_session() -> bool:
    """Attempt to restore a logged-in session from the refresh-token cookie.

    Called on every page load. If the session already has an access_token
    this is a no-op. Otherwise it reads the browser cookie, exchanges the
    refresh token for new tokens via the backend, and populates session_state.

    Returns True if the session is authenticated after the attempt.
    """
    # A pending logout means the user just clicked Logout. Don't restore
    # from the cookie — it will be cleared during this render cycle.
    if st.session_state.get("_pending_logout"):
        return False

    if st.session_state.get("access_token"):
        return True

    from lib.cookies import get_refresh_token, save_refresh_token, clear_refresh_token
    from lib.api_client import api_post, api_get

    refresh_token = get_refresh_token()
    if not refresh_token:
        return False

    try:
        # Exchange refresh token for a fresh access + refresh token pair
        data = api_post("/auth/refresh", json={"refresh_token": refresh_token})
        st.session_state.access_token = data["access_token"]

        # Persist the new refresh token so the cookie stays fresh
        save_refresh_token(data["refresh_token"])

        # Populate user profile info
        user = api_get("/users/me")
        st.session_state.role = user["role"]
        st.session_state.user_id = user["id"]
        st.session_state.user_email = user["email"]

        # Auto-select the first matter so dashboards work immediately
        try:
            matters = api_get("/matters")
            if matters:
                st.session_state.matter_id = matters[0]["id"]
        except Exception:
            pass

        return True
    except Exception:
        # Refresh token is invalid or expired — clear the stale cookie
        clear_refresh_token()
        return False


def require_login():
    """Redirect to the landing/login page if not authenticated.

    First tries to restore the session from a refresh-token cookie
    so that browser refreshes don't log the user out.
    """
    if not st.session_state.get("access_token"):
        try_restore_session()
    if not st.session_state.get("access_token"):
        st.switch_page("streamlit_app.py")


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
