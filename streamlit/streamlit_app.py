"""DocketVault — main entry point.

Shows a branded landing page with login when not authenticated,
and a role-appropriate home dashboard when logged in.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="DocketVault",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize session state with defaults
for key in ["access_token", "role", "user_id", "matter_id", "user_email", "login_mode"]:
    if key not in st.session_state:
        st.session_state[key] = None

from lib.theme import (
    inject_css, hide_sidebar, setup_sidebar,
    logo_path, wordlogo_path, page_header, step_indicator,
)
from lib.api_client import api_post, api_get
from lib.session import try_restore_session
from lib.cookies import save_refresh_token
import base64

# Try to restore session from refresh-token cookie before anything else.
# This is what keeps users logged in across browser refreshes.
try_restore_session()

# If a logout is pending, clear the refresh-token cookie now.
# This runs during a normal render (no st.rerun() afterwards) so the
# injected JavaScript actually executes in the browser.
# NOTE: We keep _pending_logout in session_state (don't delete it)
# because st.context.cookies is a stale snapshot from the initial HTTP
# connection — it won't reflect the JS cookie deletion until the user
# does a full browser refresh. The flag prevents try_restore_session()
# from re-authenticating via that stale cookie on every rerun.
if st.session_state.get("_pending_logout"):
    from lib.cookies import clear_refresh_token
    clear_refresh_token()


# ── Join-matter form (used by client home + landing) ──────────

def _join_matter_form():
    """Input for clients to paste an invitation token and join a matter."""
    st.caption("Paste the invitation token your attorney shared with you.")
    token = st.text_input("Invitation Token", key="invite_token_home")
    if st.button("Join Matter"):
        if not token.strip():
            st.warning("Please paste the token.")
        else:
            try:
                member = api_post(f"/invitations/{token.strip()}/accept")
                st.session_state.matter_id = member["matter_id"]
                st.success("You've joined the matter!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")


# ── Landing page (not logged in) ─────────────────────────────

def _render_landing():
    """Branded landing page with logos, tagline, and role-based login.

    Designed to fit entirely within the viewport without scrolling.
    """
    hide_sidebar()

    # Collapse Streamlit's default padding and gaps for a tight landing layout
    st.markdown(
        """<style>
        .block-container { padding-top: 0.5rem !important; padding-bottom: 0 !important; }
        header[data-testid="stHeader"] { display: none !important; }
        footer { display: none !important; }
        /* Pull every element block closer together */
        .block-container .stVerticalBlock > div { margin-top: -0.5rem; }
        </style>""",
        unsafe_allow_html=True,
    )

    lp, wlp = logo_path(), wordlogo_path()

    # Picture logo pinned to top-left corner
    if os.path.exists(lp):
        st.image(lp, width=80)

    # Word logo centered and pushed up
    if os.path.exists(wlp):
        _, wl_center, _ = st.columns([1, 2, 1])
        with wl_center:
            st.image(wlp, width="stretch")

    # Tagline + description — wrapped in a centered div
    st.markdown(
        '<div style="display:flex; flex-direction:column; align-items:center; width:100%;">'
        '<p class="landing-tagline">Consent-Aware Legal Intake Vault</p>'
        '<p class="landing-desc">'
        "DocketVault turns your scattered personal data exports into a "
        "lawyer-ready Evidence Pack &mdash; organized, searchable, and "
        "shareable only after your explicit approval."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Role selection buttons
    _, center, _ = st.columns([1, 2, 1])
    with center:
        col_c, col_l = st.columns(2, gap="large")
        with col_c:
            if st.button("Client Login", use_container_width=True, type="primary"):
                st.session_state.login_mode = "client"
                st.rerun()
            st.caption("Upload and manage your evidence")
        with col_l:
            if st.button("Lawyer Login", use_container_width=True):
                st.session_state.login_mode = "lawyer"
                st.rerun()
            st.caption("Review evidence and manage cases")


# ── Sign-in page (client or lawyer) ──────────────────────────

def _render_signin():
    """Dedicated sign-in screen: logo top-left, form centered, no word logo.

    Rendered within the same app (no page navigation) to avoid
    a flash of the sidebar / logged-in UI during page transitions.
    """
    hide_sidebar()
    mode = st.session_state.login_mode
    role_label = "Client" if mode == "client" else "Lawyer"

    # Build a base64 data-URL for the logo so we can position it
    # fixed in the top-left with CSS (outside normal Streamlit flow).
    lp = logo_path()
    logo_html = ""
    if os.path.exists(lp):
        with open(lp, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        logo_html = (
            f'<div class="dv-logo-fixed">'
            f'<img src="data:image/png;base64,{b64}" />'
            f'</div>'
        )

    st.markdown(
        f"""<style>
        /* Hide Streamlit chrome */
        header[data-testid="stHeader"] {{ display: none !important; }}
        footer {{ display: none !important; }}

        /* Vertically + horizontally center all content */
        .block-container {{
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            min-height: 100vh !important;
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            max-width: 480px !important;
        }}

        /* Logo pinned to top-left, outside normal flow */
        .dv-logo-fixed {{
            position: fixed;
            top: 1rem;
            left: 1.5rem;
            z-index: 999;
        }}
        .dv-logo-fixed img {{
            width: 80px;
            height: auto;
        }}
        </style>
        {logo_html}""",
        unsafe_allow_html=True,
    )

    # Back button
    if st.button("← Back to role selection"):
        st.session_state.login_mode = None
        st.rerun()

    st.markdown(f"#### {role_label} Access")
    tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Sign In", type="primary", use_container_width=True):
            try:
                data = api_post("/auth/login", json={"email": email, "password": password})
                st.session_state.access_token = data["access_token"]
                # Persist refresh token in browser cookie for session survival
                save_refresh_token(data["refresh_token"])
                user = api_get("/users/me")
                st.session_state.role = user["role"]
                st.session_state.user_id = user["id"]
                st.session_state.user_email = user["email"]
                st.session_state.login_mode = None
                # Clear logout guard so future session restores work
                st.session_state.pop("_pending_logout", None)
                # Auto-select first matter
                try:
                    matters = api_get("/matters")
                    if matters:
                        st.session_state.matter_id = matters[0]["id"]
                except Exception:
                    pass
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")

    with tab_register:
        reg_email = st.text_input("Email", key="reg_email")
        reg_name = st.text_input("Display Name", key="reg_name")
        reg_pw = st.text_input("Password", type="password", key="reg_pw")
        if mode == "client":
            roles = ["primary_client", "contributor_client"]
            labels = {"primary_client": "Primary Client", "contributor_client": "Contributor"}
        else:
            roles = ["attorney", "paralegal"]
            labels = {"attorney": "Attorney", "paralegal": "Paralegal"}
        reg_role = st.selectbox("Role", roles, format_func=lambda r: labels[r])
        if st.button("Create Account", type="primary", use_container_width=True):
            try:
                data = api_post("/auth/register", json={
                    "email": reg_email,
                    "password": reg_pw,
                    "role": reg_role,
                    "display_name": reg_name,
                })
                st.session_state.access_token = data["access_token"]
                # Persist refresh token in browser cookie for session survival
                save_refresh_token(data["refresh_token"])
                # Clear logout guard so future session restores work
                st.session_state.pop("_pending_logout", None)
                user = api_get("/users/me")
                st.session_state.role = user["role"]
                st.session_state.user_id = user["id"]
                st.session_state.user_email = user["email"]
                st.session_state.login_mode = None
                st.rerun()
            except Exception as e:
                st.error(f"Registration failed: {e}")


# ── Client home dashboard ────────────────────────────────────

def _render_client_home():
    """Dashboard for logged-in clients: progress, quick actions, join matter."""
    page_header("Welcome back", st.session_state.user_email)

    matter_id = st.session_state.get("matter_id")
    if not matter_id:
        st.info("You haven't joined a matter yet. Use an invitation token below.")
        _join_matter_form()
        return

    # Gather quick stats (fail gracefully)
    n_files, n_events = 0, 0
    try:
        artifacts = api_get(f"/matters/{matter_id}/artifacts")
        n_files = len(artifacts) if artifacts else 0
    except Exception:
        pass
    try:
        events = api_get(f"/matters/{matter_id}/timeline")
        n_events = len(events) if events else 0
    except Exception:
        pass

    col1, col2, col3 = st.columns(3)
    col1.metric("Files Uploaded", n_files)
    col2.metric("Timeline Events", n_events)
    col3.metric("Matter Status", "Active")

    st.divider()

    # Workflow progress — determine current step from data
    st.subheader("Your Workflow")
    current_step = 0
    if n_files > 0:
        current_step = 1
    if n_events > 0:
        current_step = 2

    step_indicator(current_step)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.page_link("pages/02_client_upload.py", label="Upload Evidence")
    with c2:
        st.page_link("pages/10_client_requests.py", label="Attorney Requests")
    with c3:
        st.page_link("pages/03_client_review.py", label="Review & Timeline")
    with c4:
        st.page_link("pages/04_client_share.py", label="Share & Approve")

    st.divider()

    with st.expander("Join another matter"):
        _join_matter_form()


# ── Lawyer home dashboard ────────────────────────────────────

def _render_lawyer_home():
    """Dashboard for logged-in lawyers: matters overview and quick actions."""
    page_header("Welcome back", st.session_state.user_email)

    try:
        matters = api_get("/matters")
    except Exception:
        matters = []

    role_label = "Attorney" if st.session_state.role == "attorney" else "Paralegal"
    col1, col2 = st.columns(2)
    col1.metric("Active Matters", len(matters))
    col2.metric("Role", role_label)

    st.divider()

    st.subheader("Quick Actions")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.page_link("pages/09_manage_matters.py", label="Manage Matters")
    with c2:
        st.page_link("pages/05_lawyer_dashboard.py", label="Dashboard")
    with c3:
        st.page_link("pages/06_lawyer_evidence.py", label="Evidence")
    with c4:
        st.page_link("pages/07_lawyer_export.py", label="Export Pack")

    st.divider()

    # Active matters list
    if matters:
        st.subheader("Your Matters")
        for m in matters:
            is_selected = st.session_state.matter_id == m["id"]
            col_name, col_status, col_action = st.columns([3, 1, 1])
            with col_name:
                st.markdown(f"**{m['title']}**")
            with col_status:
                st.caption(m.get("status", "active"))
            with col_action:
                if is_selected:
                    st.success("Active")
                else:
                    if st.button("Select", key=f"sel_{m['id']}"):
                        st.session_state.matter_id = m["id"]
                        st.rerun()
    else:
        st.info("No matters yet. Go to **Manage Matters** to create one.")


# ── Main routing ─────────────────────────────────────────────

inject_css()

if not st.session_state.access_token:
    if st.session_state.login_mode:
        _render_signin()
    else:
        _render_landing()
else:
    setup_sidebar()
    role = st.session_state.role
    if role in ("primary_client", "contributor_client"):
        _render_client_home()
    elif role in ("attorney", "paralegal"):
        _render_lawyer_home()
    else:
        st.warning("Unknown role. Please log out and log in again.")
