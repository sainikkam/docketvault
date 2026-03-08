import streamlit as st

st.set_page_config(
    page_title="DocketVault",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
for key in ["access_token", "role", "user_id", "matter_id", "user_email"]:
    if key not in st.session_state:
        st.session_state[key] = None

st.sidebar.title("DocketVault")

if st.session_state.access_token:
    st.sidebar.success(f"Logged in as {st.session_state.user_email} ({st.session_state.role})")
    if st.sidebar.button("Logout"):
        for key in ["access_token", "role", "user_id", "matter_id", "user_email"]:
            st.session_state[key] = None
        st.rerun()

    # Matter selector
    if st.session_state.matter_id:
        st.sidebar.info(f"Matter: {st.session_state.matter_id[:8]}...")
else:
    st.sidebar.info("Not logged in")

st.title("Welcome to DocketVault")
st.markdown("""
**Consent-Aware Legal Intake Vault**

DocketVault turns your scattered personal data exports into a lawyer-ready Evidence Pack --
organized, searchable, and shareable only after your explicit approval.

Use the sidebar to navigate between pages.
""")
