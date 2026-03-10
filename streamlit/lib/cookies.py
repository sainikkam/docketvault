"""Browser cookie helpers for persisting auth across page refreshes.

Uses JavaScript injection to set cookies (via st.components.v1.html)
and st.context.cookies to read them back on subsequent page loads.
Requires Streamlit >= 1.37 for st.context.cookies.
"""

import streamlit as st
import streamlit.components.v1 as components

# Cookie name for the refresh token
_COOKIE_NAME = "dv_refresh_token"

# Cookie lifetime in days (matches backend JWT_REFRESH_TOKEN_EXPIRE_DAYS)
_MAX_AGE_DAYS = 30


def save_refresh_token(refresh_token: str):
    """Save the refresh token as a browser cookie via JavaScript.

    The cookie is HttpOnly-free (needed for JS access) but restricted
    to SameSite=Strict to prevent CSRF. It persists across refreshes.
    """
    max_age = _MAX_AGE_DAYS * 86400
    components.html(
        f"""<script>
        document.cookie = "{_COOKIE_NAME}={refresh_token}; path=/; max-age={max_age}; SameSite=Strict";
        </script>""",
        height=0,
    )


def clear_refresh_token():
    """Remove the refresh token cookie by setting max-age to 0."""
    components.html(
        f"""<script>
        document.cookie = "{_COOKIE_NAME}=; path=/; max-age=0; SameSite=Strict";
        </script>""",
        height=0,
    )


def get_refresh_token() -> str | None:
    """Read the refresh token from the browser cookie.

    Uses st.context.cookies which reads cookies sent with the
    initial HTTP request (available on page load / refresh).
    Returns None if the cookie is missing or Streamlit is too old.
    """
    try:
        return st.context.cookies.get(_COOKIE_NAME)
    except Exception:
        return None
