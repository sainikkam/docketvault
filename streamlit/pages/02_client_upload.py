import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_client, get_matter_id
from lib.api_client import api_post_files, api_get, api_post, api_patch, is_google_connected
from lib.theme import setup_page, page_header, step_indicator
from lib.gmail_widget import gmail_search_widget

setup_page()
require_client()
matter_id = get_matter_id()

step_indicator(0)
page_header("Upload Evidence", "Add files to your private vault")

# ── Pending Evidence Requests from Attorney ───────────────────

# Category labels for display
CATEGORY_LABELS = {
    "email": "Email",
    "browser_history": "Browser History",
    "social_media": "Social Media",
    "chat_logs": "Chat / Text Messages",
    "files": "Files / Documents",
    "photos": "Photos / Videos",
    "financial": "Financial Records",
    "medical": "Medical Records",
    "other": "Other",
}

# Priority badge styling
PRIORITY_ICONS = {"high": "🔴", "medium": "🟡", "low": "🟢"}

try:
    requests = api_get(f"/matters/{matter_id}/requests")
    open_reqs = [r for r in requests if r.get("status") == "open"]
    if open_reqs:
        st.subheader("Requested by Your Attorney")
        st.caption(
            "Your attorney needs the following items. "
            "Please read each request carefully and upload the requested files below."
        )

        for req in open_reqs:
            priority_icon = PRIORITY_ICONS.get(req.get("priority", "medium"), "")
            cat_label = CATEGORY_LABELS.get(req.get("category", ""), "")
            header = f"{priority_icon} **{req['title']}**"
            if cat_label:
                header += f"  —  _{cat_label}_"

            with st.expander(header, expanded=True):
                # Description / main instructions
                if req.get("description"):
                    st.markdown(req["description"])

                # Structured details in columns
                col1, col2 = st.columns(2)

                with col1:
                    # Date range
                    if req.get("date_range_start") or req.get("date_range_end"):
                        start = req.get("date_range_start", "earliest")
                        end = req.get("date_range_end", "present")
                        st.markdown(f"**Date range:** {start} → {end}")

                    # Source system
                    if req.get("source_system"):
                        st.markdown(f"**Where to look:** {req['source_system']}")

                with col2:
                    # Keywords
                    if req.get("keywords"):
                        kw_display = ", ".join(
                            f"`{k}`" for k in req["keywords"]
                        )
                        st.markdown(f"**Search for:** {kw_display}")

                # Format instructions
                if req.get("format_instructions"):
                    st.info(f"**Format:** {req['format_instructions']}")

                # Preservation warning — most important, shown prominently
                if req.get("preservation_note"):
                    st.warning(f"**⚠ Preservation Notice:** {req['preservation_note']}")

                # Checklist — actionable items for the client to work through
                checklist = req.get("checklist", [])
                if checklist:
                    st.markdown("**Your to-do list:**")
                    for idx, item in enumerate(checklist):
                        item_text = item.get("item", "")
                        is_done = item.get("completed", False)
                        is_auto = item.get("auto_detected", False)

                        # Show auto-detected badge next to items the
                        # system found evidence for automatically
                        label = item_text
                        if is_auto and is_done:
                            label += "  *(auto-detected from your uploads)*"

                        checked = st.checkbox(
                            label,
                            value=is_done,
                            key=f"cl_{req['id']}_{idx}",
                        )
                        # Show the reason the system auto-checked this item
                        if is_auto and is_done and item.get("auto_reason"):
                            st.caption(f"  Evidence found: {item['auto_reason']}")

                        # Update the item if the client toggles it
                        if checked != is_done:
                            try:
                                api_patch(
                                    f"/requests/{req['id']}/checklist"
                                    f"?item_index={idx}&completed={str(checked).lower()}"
                                )
                                st.rerun()
                            except Exception:
                                pass

                    done_count = sum(1 for c in checklist if c.get("completed"))
                    st.caption(f"{done_count}/{len(checklist)} items completed")

                # Mark fulfilled button
                if st.button("Mark as Fulfilled", key=f"fulfill_{req['id']}"):
                    try:
                        api_patch(f"/requests/{req['id']}?status=fulfilled")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

        st.divider()
except Exception:
    pass

# ── File Upload ───────────────────────────────────────────────

st.subheader("Upload Export Files")
st.caption("Supported: ZIP, PDF, images (PNG/JPG), audio (MP3/WAV/M4A)")

uploaded_files = st.file_uploader(
    "Drop files here", accept_multiple_files=True,
    type=["zip", "pdf", "png", "jpg", "jpeg", "mp3", "wav", "m4a", "csv", "jsonl"],
    key="evidence_uploader",
)

if uploaded_files and st.button("Upload All"):
    files_data = [(f.name, f.read(), f.type or "application/octet-stream") for f in uploaded_files]
    try:
        result = api_post_files(f"/matters/{matter_id}/evidence/upload", files_data)
        count = result.get("uploaded", len(files_data))
        st.success(
            f"Uploaded {count} files! "
            "AI is now analyzing your evidence for relevance and categorization. "
            "Go to Evidence Review to see results (takes ~30 seconds)."
        )
    except Exception as e:
        st.error(f"Upload failed: {e}")

st.divider()

# ── Current Artifacts ─────────────────────────────────────────

st.subheader("Uploaded Evidence")
try:
    artifacts = api_get(f"/matters/{matter_id}/artifacts")
    if artifacts:
        for a in artifacts:
            status = a.get("status", "unknown")
            score = a.get("relevance_score", 0.0)
            cat = a.get("category", "uncategorized")

            # Show status with relevance if scored
            if score > 0:
                st.write(
                    f"- **{a['original_filename']}** ({a['mime_type']}) — "
                    f"{cat} | Relevance: {score:.0%}"
                )
            else:
                label = "processing" if status == "processing" else status
                st.write(f"- **{a['original_filename']}** ({a['mime_type']}) — {label}")
    else:
        st.info("No evidence uploaded yet.")
except Exception as e:
    st.warning(f"Could not load artifacts: {e}")

st.divider()

# ── Google Import (Drive + Gmail) ─────────────────────────────

st.subheader("Import from Google")

# Single connection check shared by both tabs
google_ok = is_google_connected()

if google_ok:
    st.success("Google account connected — Drive and Gmail are ready", icon="✅")
else:
    st.info("Connect your Google account to import from Drive or search Gmail.")
    if st.button("Connect Google Account", type="primary"):
        try:
            data = api_get("/oauth/google/authorize")
            st.markdown(f"[Click here to authorize]({data['authorize_url']})")
        except Exception as e:
            st.error(f"Failed to start OAuth: {e}")

drive_tab, gmail_tab = st.tabs(["📁 Google Drive", "✉️ Gmail Search"])

with drive_tab:
    if not google_ok:
        st.caption("Connect your Google account above to browse Drive files.")
    else:
        try:
            files = api_get("/oauth/google/drive/files").get("files", [])
            if files:
                for f in files:
                    st.write(f"- **{f['name']}** ({f.get('mimeType', '')})")
            else:
                st.info("No files found in your Google Drive.")
        except Exception as e:
            st.warning(f"Could not list Drive files: {e}")

with gmail_tab:
    gmail_search_widget(matter_id, google_connected=google_ok)

# ── Next step ─────────────────────────────────────────────────

st.divider()
st.page_link(
    "pages/03_client_review.py",
    label="Next: Review your evidence  \u2192",
)
