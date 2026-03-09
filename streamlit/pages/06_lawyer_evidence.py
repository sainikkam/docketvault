import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_attorney, get_matter_id
from lib.api_client import api_get
from lib.theme import setup_page, page_header

setup_page()
require_attorney()
matter_id = get_matter_id()

page_header("Evidence Viewer", "Browse and inspect approved evidence")

try:
    evidence = api_get(f"/matters/{matter_id}/evidence")
    artifacts = evidence.get("artifacts", [])

    if not artifacts:
        st.info("No approved evidence yet. The client needs to approve sharing first.")
        st.stop()

    st.write(f"**{evidence.get('total', len(artifacts))} approved artifacts**")

    for artifact in artifacts:
        with st.expander(f"{artifact['filename']} ({artifact.get('mime_type', '')})"):
            st.write(f"**Status:** {artifact.get('status', '')}")
            st.write(f"**Uploaded:** {artifact.get('uploaded_at', '')}")

            # Load AI extraction results
            try:
                ext = api_get(f"/artifacts/{artifact['id']}/extraction")

                if ext.get("summary"):
                    st.subheader("Summary")
                    st.write(ext["summary"])

                if ext.get("doc_type_guess") and ext["doc_type_guess"] != "unknown":
                    st.write(f"**Document Type:** {ext['doc_type_guess']}")

                if ext.get("overall_summary"):
                    st.subheader("Audio Summary")
                    st.write(ext["overall_summary"])

                if ext.get("transcript"):
                    st.subheader("Transcript")
                    for seg in ext["transcript"]:
                        start = seg.get("start_ms", 0)
                        text = seg.get("text", "")
                        st.caption(f"[{start}ms] {text}")

                if ext.get("key_moments"):
                    st.subheader("Key Moments")
                    for moment in ext["key_moments"]:
                        st.write(
                            f"- **{moment.get('title', '')}**: "
                            f"{moment.get('summary', '')}"
                        )

                if ext.get("structured_claims"):
                    st.subheader("Extracted Claims")
                    st.json(ext["structured_claims"])

                if ext.get("sensitivity_flags"):
                    flags = ext["sensitivity_flags"]
                    active = [k for k, v in flags.items() if v]
                    if active:
                        st.warning(f"Sensitivity flags: {', '.join(active)}")

            except Exception:
                st.caption("No AI extraction available for this artifact.")

except Exception as e:
    st.error(f"Could not load evidence: {e}")
