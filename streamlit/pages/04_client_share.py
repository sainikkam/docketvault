import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_client, get_matter_id
from lib.api_client import api_get, api_post

require_client()
matter_id = get_matter_id()

st.title("Share Preview & Consent")
st.caption("Review what will be shared with your attorney. Nothing is shared until you approve.")

try:
    preview = api_get(f"/matters/{matter_id}/share-preview")
    categories = preview.get("categories", {})

    if not categories:
        st.info("No evidence to share yet. Upload and process evidence first.")
        st.stop()

    # Flatten items for stats
    all_items = []
    for items in categories.values():
        all_items.extend(items)

    total = len(all_items)
    sensitive = sum(1 for i in all_items if i.get("is_sensitive"))
    approved = sum(1 for i in all_items if i.get("state") == "approved")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Items", total)
    col2.metric("Sensitive Items", sensitive)
    col3.metric("Currently Approved", approved)

    st.divider()

    # Per-category display
    for cat, items in categories.items():
        with st.expander(f"{cat} ({len(items)} items)"):
            for item in items:
                cols = st.columns([1, 3, 1, 1])
                with cols[0]:
                    st.write(item.get("state", "pending"))
                with cols[1]:
                    st.write(item.get("filename", item["artifact_id"][:8]))
                with cols[2]:
                    st.write(item.get("mime_type", ""))
                with cols[3]:
                    if item.get("is_sensitive"):
                        st.warning("Sensitive")

    st.divider()

    col_approve, col_revoke = st.columns(2)

    with col_approve:
        if st.button("Approve All & Share", type="primary"):
            try:
                result = api_post(f"/matters/{matter_id}/share-preview/approve-all")
                st.success(f"Approved {result.get('approved', 0)} items!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    with col_revoke:
        if st.button("Revoke All Sharing"):
            try:
                result = api_post(f"/matters/{matter_id}/revoke")
                st.warning(f"Revoked {result.get('revoked', 0)} items.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

except Exception as e:
    st.error(f"Could not load share preview: {e}")
