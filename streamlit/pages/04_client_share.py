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
page_header(
    "Share Preview & Consent",
    "Review what will be shared with your attorney — nothing is shared until you approve",
)

CATEGORY_LABELS = {
    "lease_documents": "Lease & Legal Documents",
    "communications": "Communications",
    "financial_records": "Financial Records",
    "notices": "Notices & Letters",
    "photos_evidence": "Photos & Visual Evidence",
    "calendar_events": "Calendar & Scheduling",
    "medical_records": "Medical Records",
    "personal_journal": "Personal Journal & Reflections",
    "ai_conversations": "AI Assistant Conversations",
    "social_media": "Social Media",
    "other": "Other",
    "uncategorized": "Uncategorized",
}

try:
    preview = api_get(f"/matters/{matter_id}/share-preview")
    categories = preview.get("categories", {})

    if not categories:
        st.info("No evidence to share yet. Upload and process evidence first.")
        st.stop()

    # Flatten all items for stats
    all_items = []
    for items in categories.values():
        all_items.extend(items)

    total = len(all_items)
    sensitive_items = preview.get("sensitive_items", [])
    sensitive_count = len(sensitive_items)
    approved = sum(1 for i in all_items if i.get("state") == "approved")
    excluded = sum(1 for i in all_items if i.get("state") == "excluded")
    pending = sum(1 for i in all_items if i.get("state") == "pending")

    # ── Summary metrics ──────────────────────────────────────

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Items", total)
    col2.metric("Pending", pending)
    col3.metric("Approved", approved)
    col4.metric("Excluded", excluded)
    col5.metric("Sensitive", sensitive_count)

    st.divider()

    # ── Sensitive items section (shown first for visibility) ──

    if sensitive_items:
        st.subheader("Items Containing Sensitive Information")
        st.warning(
            f"**{sensitive_count} item(s)** contain potentially sensitive data. "
            "You must explicitly acknowledge each one to include it in sharing."
        )
        for item in sensitive_items:
            aid = item["artifact_id"]
            state = item.get("state", "pending")
            flags = item.get("sensitivity_flags", {})
            active_flags = [
                k.replace("contains_", "").replace("_", " ").title()
                for k, v in flags.items() if v
            ]

            with st.container(border=True):
                c_name, c_flags, c_summary = st.columns([2, 2, 1])
                with c_name:
                    st.markdown(f"**{item.get('filename', aid[:8])}**")
                    st.caption(item.get("mime_type", ""))
                with c_flags:
                    st.error(f"Contains: {', '.join(active_flags)}")
                with c_summary:
                    if state == "approved":
                        st.success("Approved")
                    elif state == "excluded":
                        st.error("Excluded")
                    else:
                        st.info("Pending")

                if item.get("summary"):
                    st.caption(item["summary"])

                # Action buttons for sensitive items
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if state != "approved":
                        if st.button(
                            "Acknowledge & Approve",
                            key=f"ack_approve_{aid}",
                            type="primary",
                        ):
                            try:
                                api_post(
                                    f"/matters/{matter_id}/share-preview/update",
                                    json={"updates": [{
                                        "artifact_id": aid,
                                        "state": "approved",
                                        "acknowledge_sensitive": True,
                                    }]},
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                with btn_col2:
                    if state != "excluded":
                        if st.button("Exclude", key=f"sens_exclude_{aid}"):
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

    # ── Per-category display sorted by relevance ─────────────

    st.subheader("All Evidence by Category")
    st.caption(
        "Items are sorted by relevance within each category. "
        "Approve items to share them, or exclude items you don't want your attorney to see."
    )

    def _render_record_selector(item: dict, matter_id: str):
        """Show expandable per-record selection for multi-item artifacts.

        Each record gets a checkbox pre-set by the relevance-based default.
        Changes are sent to the record share state update endpoint.
        """
        records = item.get("records", [])
        record_count = item.get("record_count", len(records))
        aid = item["artifact_id"]
        included_count = sum(1 for r in records if r.get("state") == "included")

        st.caption(
            f"This file contains **{record_count} items** — "
            f"**{included_count}** selected for sharing"
        )

        # Bulk select/deselect buttons
        sel_col, desel_col = st.columns(2)
        with sel_col:
            if st.button("Select All", key=f"selall_{aid}"):
                try:
                    updates = [
                        {"record_id": r["record_id"], "state": "included"}
                        for r in records
                    ]
                    api_post(
                        f"/matters/{matter_id}/share-preview/records/update",
                        json={"artifact_id": aid, "updates": updates},
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
        with desel_col:
            if st.button("Deselect All", key=f"deselall_{aid}"):
                try:
                    updates = [
                        {"record_id": r["record_id"], "state": "excluded"}
                        for r in records
                    ]
                    api_post(
                        f"/matters/{matter_id}/share-preview/records/update",
                        json={"artifact_id": aid, "updates": updates},
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

        # Individual record checkboxes
        for rec in records:
            rid = rec["record_id"]
            is_included = rec.get("state") == "included"
            rec_score = rec.get("relevance_score", 0.0)

            # Build a concise label: type + date + text preview
            label_parts = []
            if rec.get("type"):
                label_parts.append(f"[{rec['type']}]")
            if rec.get("ts"):
                label_parts.append(rec["ts"][:10])
            preview = rec.get("text", "")[:120].replace("\n", " ")
            if preview:
                label_parts.append(preview)
            label = " ".join(label_parts) or rid[:8]

            # Score badge inline
            if rec_score >= 0.7:
                score_label = f" ({rec_score:.0%})"
            elif rec_score >= 0.4:
                score_label = f" ({rec_score:.0%})"
            else:
                score_label = f" ({rec_score:.0%})"

            new_val = st.checkbox(
                label + score_label,
                value=is_included,
                key=f"rec_{aid}_{rid}",
            )

            # Update on toggle
            if new_val != is_included:
                new_state = "included" if new_val else "excluded"
                try:
                    api_post(
                        f"/matters/{matter_id}/share-preview/records/update",
                        json={
                            "artifact_id": aid,
                            "updates": [{"record_id": rid, "state": new_state}],
                        },
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    for cat_key, items in categories.items():
        label = CATEGORY_LABELS.get(cat_key, cat_key.replace("_", " ").title())

        # Sort items by relevance within category
        sorted_items = sorted(
            items, key=lambda x: x.get("relevance_score", 0), reverse=True
        )

        with st.expander(f"{label} ({len(sorted_items)} items)", expanded=True):
            for item in sorted_items:
                aid = item["artifact_id"]
                state = item.get("state", "pending")
                is_sens = item.get("is_sensitive", False)
                score = item.get("relevance_score", 0.0)
                has_records = item.get("has_records", False)

                with st.container(border=True):
                    c_status, c_name, c_rel, c_approve, c_exclude = st.columns(
                        [1, 3, 1, 1, 1]
                    )

                    with c_status:
                        if state == "approved":
                            st.success("Approved")
                        elif state == "excluded":
                            st.error("Excluded")
                        else:
                            st.info("Pending")

                    with c_name:
                        name_text = item.get("filename", aid[:8])
                        if is_sens:
                            name_text += " :warning:"
                        if has_records:
                            name_text += f" ({item.get('record_count', 0)} items)"
                        st.write(name_text)
                        if item.get("summary"):
                            st.caption(item["summary"])
                        if item.get("relevance_rationale"):
                            st.caption(f"Why: {item['relevance_rationale']}")

                    with c_rel:
                        if score >= 0.7:
                            st.success(f"{score:.0%}")
                        elif score >= 0.4:
                            st.info(f"{score:.0%}")
                        else:
                            st.caption(f"{score:.0%}")

                    with c_approve:
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

                    with c_exclude:
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

                    # Per-record selection for multi-item artifacts
                    if has_records and item.get("records"):
                        with st.expander(
                            f"Review {item.get('record_count', 0)} individual items",
                            expanded=False,
                        ):
                            _render_record_selector(item, matter_id)

    st.divider()

    # ── Bulk actions ─────────────────────────────────────────

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
