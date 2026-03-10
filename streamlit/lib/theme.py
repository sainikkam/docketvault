"""DocketVault UI theme — CSS injection, sidebar navigation, and shared components.

Color palette derived from the DocketVault brand logos (navy blue + grey).
Every page should call setup_page() at the top, then optionally use
page_header() and step_indicator() for consistent styling.
"""

import streamlit as st
import os


# ── Brand colors (from logo) ─────────────────────────────────

NAVY = "#1E3A5F"
BLUE = "#2563EB"
BLUE_LIGHT = "#3B82F6"
BLUE_50 = "#EFF6FF"
BLUE_100 = "#DBEAFE"
BLUE_200 = "#BFDBFE"
GREY_600 = "#475569"
GREY_500 = "#64748B"
GREY_400 = "#94A3B8"
GREY_200 = "#E2E8F0"
GREEN = "#10B981"
WHITE = "#FFFFFF"


# ── Asset helpers ─────────────────────────────────────────────

def _root():
    """Project root: two levels up from this file (lib/ -> streamlit/ -> root)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def logo_path():
    """Absolute path to the icon logo."""
    return os.path.join(_root(), "docketlogo.png")


def wordlogo_path():
    """Absolute path to the word logo."""
    return os.path.join(_root(), "docketvaultwordlogo.png")


# ── CSS ───────────────────────────────────────────────────────

_CSS = """<style>
/* Hide the auto-generated sidebar page list */
[data-testid="stSidebarNav"] { display: none; }

/* Landing page typography */
.landing-tagline {
    text-align: center;
    font-size: 1.5rem;
    color: #0F172A;
    font-weight: 500;
    letter-spacing: 0.02em;
    margin: 0.25rem 0 0.5rem 0;
}
.landing-desc {
    text-align: center;
    font-size: 0.95rem;
    color: #475569;
    max-width: 800px;
    margin-left: auto;
    margin-right: auto;
    margin-top: 0;
    margin-bottom: 2.5rem;
    line-height: 1.6;
}

/* 3-step progress indicator for client workflow */
.step-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    margin: 1rem 0 1.5rem;
}
.step-item {
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
.step-circle {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.8rem;
}
.step-active .step-circle { background: #2563EB; color: #fff; box-shadow: 0 0 0 3px #DBEAFE; }
.step-done   .step-circle { background: #10B981; color: #fff; }
.step-future .step-circle { background: #E2E8F0; color: #94A3B8; }

.step-label { font-size: 0.85rem; font-weight: 500; }
.step-active .step-label { color: #2563EB; }
.step-done   .step-label { color: #10B981; }
.step-future .step-label { color: #94A3B8; }

.step-line { width: 48px; height: 2px; margin: 0 0.6rem; }
.step-line-done    { background: #10B981; }
.step-line-pending { background: #E2E8F0; }

/* Page subtitle (used by page_header) */
.page-subtitle {
    color: #64748B;
    font-size: 0.95rem;
    margin-top: -0.5rem;
    margin-bottom: 1rem;
}
</style>"""

_HIDE_SIDEBAR_CSS = """<style>
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}
</style>"""


# ── Public API ────────────────────────────────────────────────

def inject_css():
    """Inject the global DocketVault CSS. Safe to call multiple times."""
    st.markdown(_CSS, unsafe_allow_html=True)


def hide_sidebar():
    """Completely hide the sidebar (used on the login/landing screen)."""
    st.markdown(_HIDE_SIDEBAR_CSS, unsafe_allow_html=True)


def setup_sidebar():
    """Build the custom sidebar: logo, user info, role-based nav, matter selector, logout.

    Only renders content when the user is logged in.
    """
    if not st.session_state.get("access_token"):
        return

    role = st.session_state.get("role", "")
    email = st.session_state.get("user_email", "")

    # Logo
    lp = logo_path()
    if os.path.exists(lp):
        st.sidebar.image(lp, width=60)
    st.sidebar.caption("**DocketVault**")
    st.sidebar.divider()

    # User info
    st.sidebar.markdown(f"**{email}**")
    role_map = {
        "primary_client": "Client",
        "contributor_client": "Contributor",
        "attorney": "Attorney",
        "paralegal": "Paralegal",
    }
    st.sidebar.caption(role_map.get(role, role))
    st.sidebar.divider()

    # Role-based navigation links
    if role in ("primary_client", "contributor_client"):
        st.sidebar.page_link("streamlit_app.py", label="Home")
        st.sidebar.page_link("pages/02_client_upload.py", label="Upload Evidence")
        st.sidebar.page_link("pages/10_client_requests.py", label="Attorney Requests")
        st.sidebar.page_link("pages/03_client_review.py", label="Review & Timeline")
        st.sidebar.page_link("pages/04_client_share.py", label="Share & Approve")
        st.sidebar.page_link("pages/08_audit_log.py", label="Audit Log")
    elif role in ("attorney", "paralegal"):
        st.sidebar.page_link("streamlit_app.py", label="Home")
        st.sidebar.page_link("pages/09_manage_matters.py", label="Manage Matters")
        st.sidebar.page_link("pages/05_lawyer_dashboard.py", label="Matter Dashboard")
        st.sidebar.page_link("pages/13_intake_summary.py", label="Intake Summary")
        st.sidebar.page_link("pages/06_lawyer_evidence.py", label="Evidence Viewer")
        st.sidebar.page_link("pages/07_lawyer_export.py", label="Export Pack")
        st.sidebar.page_link("pages/08_audit_log.py", label="Audit Log")

    st.sidebar.divider()

    # Matter selector
    _matter_selector()

    # Notification badge
    _notification_badge()

    st.sidebar.divider()

    # Logout — clear session state AND the refresh-token cookie
    if st.sidebar.button("Logout", use_container_width=True):
        from lib.cookies import clear_refresh_token
        clear_refresh_token()
        for k in ["access_token", "role", "user_id", "matter_id", "user_email", "login_mode"]:
            st.session_state[k] = None
        st.rerun()


def setup_page():
    """Inject CSS and set up sidebar navigation.

    Call this at the top of every page, before any auth guards.
    """
    inject_css()
    setup_sidebar()


def page_header(title, subtitle=None):
    """Render a styled page title with an optional grey subtitle."""
    st.title(title)
    if subtitle:
        st.markdown(
            f'<p class="page-subtitle">{subtitle}</p>',
            unsafe_allow_html=True,
        )


_STEPS = ["Upload", "Review", "Share"]


def step_indicator(current: int):
    """Render a 3-step progress bar for the client workflow.

    Args:
        current: 0-indexed step number (0=Upload, 1=Review, 2=Share).
    """
    html = '<div class="step-bar">'
    for i, label in enumerate(_STEPS):
        if i < current:
            cls, char = "step-done", "&#10003;"
        elif i == current:
            cls, char = "step-active", str(i + 1)
        else:
            cls, char = "step-future", str(i + 1)

        html += (
            f'<div class="step-item {cls}">'
            f'<div class="step-circle">{char}</div>'
            f'<span class="step-label">{label}</span>'
            f'</div>'
        )
        if i < len(_STEPS) - 1:
            lcls = "step-line-done" if i < current else "step-line-pending"
            html += f'<div class="step-line {lcls}"></div>'

    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ── Private helpers ───────────────────────────────────────────

def _matter_selector():
    """Render the Active Matter dropdown in the sidebar."""
    from lib.api_client import api_get

    try:
        matters = api_get("/matters")
    except Exception:
        matters = []

    if matters:
        labels = {m["title"]: m["id"] for m in matters}
        names = list(labels.keys())
        current = st.session_state.get("matter_id")
        idx = 0
        for i, n in enumerate(names):
            if labels[n] == current:
                idx = i
                break
        sel = st.sidebar.selectbox("Active Matter", names, index=idx, key="_sb_matter")
        st.session_state.matter_id = labels[sel]
    else:
        st.sidebar.info("No matters yet")


def _notification_badge():
    """Show unread notification count in the sidebar."""
    from lib.api_client import api_get

    try:
        data = api_get("/notifications", params={"limit": 5, "unread_only": True})
        unread = data.get("unread_count", 0)
        if unread:
            st.sidebar.info(f"{unread} unread notification(s)")
    except Exception:
        pass
