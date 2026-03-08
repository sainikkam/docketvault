import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_client, get_matter_id
from lib.api_client import api_post_files, api_get, api_post

require_client()
matter_id = get_matter_id()

st.title("Upload Evidence")

# --- File Upload ---
st.subheader("Upload Export Files")
st.caption("Supported: ZIP, PDF, images (PNG/JPG), audio (MP3/WAV/M4A)")

uploaded_files = st.file_uploader(
    "Drop files here", accept_multiple_files=True,
    type=["zip", "pdf", "png", "jpg", "jpeg", "mp3", "wav", "m4a", "csv", "jsonl"],
)

if uploaded_files and st.button("Upload All"):
    files_data = [(f.name, f.read(), f.type or "application/octet-stream") for f in uploaded_files]
    try:
        result = api_post_files(f"/matters/{matter_id}/evidence/upload", files_data)
        st.success(f"Uploaded {result.get('uploaded', len(files_data))} files!")
    except Exception as e:
        st.error(f"Upload failed: {e}")

st.divider()

# --- Current Artifacts ---
st.subheader("Uploaded Evidence")
try:
    artifacts = api_get(f"/matters/{matter_id}/artifacts")
    if artifacts:
        for a in artifacts:
            st.write(f"- **{a['original_filename']}** ({a['mime_type']}) -- Status: {a['status']}")
    else:
        st.info("No evidence uploaded yet.")
except Exception as e:
    st.warning(f"Could not load artifacts: {e}")

st.divider()

# --- Google Drive Import ---
st.subheader("Import from Google Drive")
if st.button("Connect Google Drive"):
    try:
        data = api_get("/oauth/google/authorize")
        st.markdown(f"[Click here to authorize Google Drive]({data['authorize_url']})")
    except Exception as e:
        st.error(f"Failed to start OAuth: {e}")
