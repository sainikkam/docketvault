import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_attorney, get_matter_id
from lib.api_client import api_get

require_attorney()
matter_id = get_matter_id()

st.title("Evidence Viewer")

try:
    evidence = api_get(f"/matters/{matter_id}/evidence")
    artifacts = evidence.get("artifacts", [])

    if not artifacts:
        st.info("No approved evidence yet. The client needs to approve sharing first.")
        st.stop()

    st.write(f"**{evidence.get('total', len(artifacts))} approved artifacts**")

    for artifact in artifacts:
        with st.expander(f"{artifact['filename']} ({artifact.get('mime_type', '')})"):
            st.write(f"Status: {artifact.get('status', '')}")
            st.write(f"Uploaded: {artifact.get('uploaded_at', '')}")

            # Try to load extraction
            try:
                extraction = api_get(f"/artifacts/{artifact['id']}/extraction")
                if extraction:
                    if extraction.get("summary"):
                        st.write(f"**Summary:** {extraction['summary']}")
                    if extraction.get("doc_type_guess"):
                        st.write(f"**Type:** {extraction['doc_type_guess']}")
                    if extraction.get("overall_summary"):
                        st.write(f"**Audio Summary:** {extraction['overall_summary']}")
                    if extraction.get("transcript"):
                        st.subheader("Transcript")
                        for seg in extraction["transcript"]:
                            st.write(f"[{seg['start_ms']}ms] {seg['text']}")
                    if extraction.get("key_moments"):
                        st.subheader("Key Moments")
                        for moment in extraction["key_moments"]:
                            st.write(f"- **{moment.get('title', '')}**: {moment.get('summary', '')}")
                    if extraction.get("structured_claims"):
                        st.subheader("Extracted Claims")
                        st.json(extraction["structured_claims"])
            except Exception:
                pass  # No extraction available

except Exception as e:
    st.error(f"Could not load evidence: {e}")
