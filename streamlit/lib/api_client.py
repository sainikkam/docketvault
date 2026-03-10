import httpx
import streamlit as st


def get_client() -> httpx.Client:
    """Return an httpx client with auth header from session."""
    headers = {}
    token = st.session_state.get("access_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    base_url = st.secrets.get("API_BASE_URL", "http://localhost:8000")
    return httpx.Client(base_url=base_url, headers=headers, timeout=60.0)


def api_get(path: str, **kwargs):
    with get_client() as c:
        r = c.get(path, **kwargs)
        r.raise_for_status()
        return r.json()


def api_post(path: str, **kwargs):
    with get_client() as c:
        r = c.post(path, **kwargs)
        r.raise_for_status()
        return r.json()


def api_patch(path: str, **kwargs):
    with get_client() as c:
        r = c.patch(path, **kwargs)
        r.raise_for_status()
        return r.json()


def api_post_files(path: str, files_data: list[tuple[str, bytes, str]]):
    """Upload multiple files. files_data: [(filename, bytes, content_type), ...]"""
    with get_client() as c:
        files = [("files", (name, data, ct)) for name, data, ct in files_data]
        r = c.post(path, files=files)
        r.raise_for_status()
        return r.json()


def api_get_bytes(path: str) -> bytes:
    with get_client() as c:
        r = c.post(path)  # export is POST
        r.raise_for_status()
        return r.content


def is_google_connected() -> bool:
    """Check if the current user has a Google account linked.

    Calls the lightweight /oauth/google/status endpoint and caches
    the result in session state for the current page render so
    multiple UI sections (Drive tab, Gmail tab) share one check.
    """
    # Return cached value if we already checked this render cycle
    cached = st.session_state.get("_google_connected")
    if cached is not None:
        return cached

    try:
        data = api_get("/oauth/google/status")
        connected = data.get("connected", False)
    except Exception:
        connected = False

    st.session_state["_google_connected"] = connected
    return connected
