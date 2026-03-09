import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_attorney, get_matter_id
from lib.api_client import api_get_bytes
from lib.theme import setup_page, page_header

setup_page()
require_attorney()
matter_id = get_matter_id()

page_header("Evidence Pack Export", "Download the complete Evidence Pack for this matter")

st.markdown("""
The Evidence Pack contains:
- **intake_summary.json** -- AI-assisted intake summary with citations
- **evidence_index.csv** -- Full index of approved evidence
- **approved_records.jsonl** -- Structured record data
- **approved_artifacts/** -- Approved files (images, PDFs, audio)
- **hash_manifest.csv** -- SHA-256 hashes for integrity verification
- **audit_excerpt.jsonl** -- Audit trail for this matter
""")

if st.button("Generate & Download Evidence Pack", type="primary"):
    with st.spinner("Generating Evidence Pack..."):
        try:
            zip_bytes = api_get_bytes(f"/matters/{matter_id}/export")
            st.download_button(
                label="Download Evidence Pack (ZIP)",
                data=zip_bytes,
                file_name=f"evidence_pack_{matter_id}.zip",
                mime="application/zip",
            )
            st.success("Evidence Pack ready!")
        except Exception as e:
            st.error(f"Failed to generate Evidence Pack: {e}")
