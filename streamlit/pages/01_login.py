import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.api_client import api_post, api_get

st.title("Login / Register")

tab_login, tab_register = st.tabs(["Login", "Register"])

with tab_login:
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login"):
        try:
            data = api_post("/auth/login", json={"email": email, "password": password})
            st.session_state.access_token = data["access_token"]
            st.session_state.role = data["user"]["role"]
            st.session_state.user_id = data["user"]["id"]
            st.session_state.user_email = data["user"]["email"]
            st.success("Logged in!")

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
    reg_password = st.text_input("Password", type="password", key="reg_password")
    reg_role = st.selectbox("Role", ["primary_client", "attorney", "paralegal"])
    if st.button("Register"):
        try:
            data = api_post("/auth/register", json={
                "email": reg_email,
                "password": reg_password,
                "role": reg_role,
                "display_name": reg_name,
            })
            st.session_state.access_token = data["access_token"]
            st.session_state.role = reg_role
            st.session_state.user_id = data.get("user_id") or data.get("id")
            st.session_state.user_email = reg_email
            st.success("Registered and logged in!")
            st.rerun()
        except Exception as e:
            st.error(f"Registration failed: {e}")
