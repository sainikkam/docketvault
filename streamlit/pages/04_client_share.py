import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_client, get_matter_id
from lib.api_client import api_get, api_post
from lib.theme import setup_page, page_header, step_indicator

setup_page()
require_client()
matter_id = get_matter_id()

step_indicator(2)
page_header("Share Preview & Consent", "Review what will be shared with your attorney — nothing is shared until you approve")

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
    excluded = sum(1 for i in all_items if i.get("state") == "excluded")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Items", total)
    col2.metric("Approved", approved)
    col3.metric("Excluded", excluded)
    col4.metric("Sensitive", sensitive)

    st.divider()

    # ── Per-category display with individual controls ─────────

    for cat, items in categories.items():
        st.subheader(f"{cat} ({len(items)} items)")
        for item in items:
            col_status, col_name, col_type, col_flag, col_approve, col_exclude = st.columns(
                [1, 3, 1, 1, 1, 1]
            )
            aid = item["artifact_id"]
            state = item.get("state", "pending")
            is_sens = item.get("is_sensitive", False)

            with col_status:
                if state == "approved":
                    st.success("Approved")
                elif state == "excluded":
                    st.error("Excluded")
                else:
                    st.info("Pending")
            with col_name:
                st.write(item.get("filename", aid[:8]))
            with col_type:
                st.caption(item.get("mime_type", ""))
            with col_flag:
                if is_sens:
                    st.warning("Sensitive")
            with col_approve:
                if state != "approved":
                    if st.button("Approve", key=f"approve_{aid}"):
                        try:
                            api_post(
                                f"/matters/{matter_id}/share-preview/update",
                                json={"updates": [{
                                    "artifact_id": aid,
                                    "state": "approved",
                                    "acknowledge_sensitive": is_sens,
                                }]},
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
            with col_exclude:
                if state != "excluded":
                    if st.button("Exclude", key=f"exclude_{aid}"):
                        try:
                            api_post(
                                f"/matters/{matter_id}/share-preview/update",
                                json={"updates": [{
                                    "artifact_id": aid,
                                    "state": "excluded",
                                    "acknowledge_sensitive": False,
                                }]},
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")

    st.divider()

    # ── Bulk actions ──────────────────────────────────────────

    col_approve_all, col_revoke_all = st.columns(2)

    with col_approve_all:
        if st.button("Approve All & Share", type="primary"):
            try:
                result = api_post(f"/matters/{matter_id}/share-preview/approve-all")
                st.success(f"Approved {result.get('approved', 0)} items!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    with col_revoke_all:
        if st.button("Revoke All Sharing"):
            try:
                result = api_post(f"/matters/{matter_id}/revoke")
                st.warning(f"Revoked {result.get('revoked', 0)} items.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

except Exception as e:
    st.error(f"Could not load share preview: {e}")
