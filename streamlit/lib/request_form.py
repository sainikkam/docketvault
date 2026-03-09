"""Shared evidence request form component.

Used by both the Manage Matters page (initial setup)
and the Lawyer Dashboard (ongoing case management).
"""

import streamlit as st
from lib.api_client import api_get, api_post

# Category labels — used when displaying existing requests
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


def render_existing_requests(matter_id: str):
    """Display existing evidence requests for a matter."""
    try:
        requests = api_get(f"/matters/{matter_id}/requests")
        if requests:
            for req in requests:
                col_info, col_status = st.columns([4, 1])
                with col_info:
                    cat_label = CATEGORY_LABELS.get(
                        req.get("category", ""), "")
                    prefix = f"[{cat_label}] " if cat_label else ""
                    st.write(f"**{prefix}{req['title']}** ({req['priority']})")
                    if req.get("description"):
                        st.caption(req["description"])
                    if req.get("date_range_start") or req.get("date_range_end"):
                        dr = f"{req.get('date_range_start', '...')} → {req.get('date_range_end', 'present')}"
                        st.caption(f"Date range: {dr}")
                    if req.get("keywords"):
                        st.caption(f"Keywords: {', '.join(req['keywords'])}")
                    # Show checklist summary if present
                    checklist = req.get("checklist", [])
                    if checklist:
                        done = sum(1 for c in checklist if c.get("completed"))
                        st.caption(f"Checklist: {done}/{len(checklist)} items")
                with col_status:
                    if req["status"] == "fulfilled":
                        st.success(req["status"])
                    elif req["status"] == "open":
                        st.info(req["status"])
                    else:
                        st.caption(req["status"])
        else:
            st.info("No evidence requests yet.")
    except Exception:
        st.info("No requests yet.")


def _generate_checklist(parsed: dict) -> list:
    """Call the checklist generation endpoint with parsed letter fields."""
    result = api_post("/requests/generate-checklist", json={
        "title": parsed.get("title", ""),
        "category": parsed.get("category"),
        "date_range_start": parsed.get("date_range_start"),
        "date_range_end": parsed.get("date_range_end"),
        "keywords": parsed.get("keywords", []),
        "source_system": parsed.get("source_system"),
        "description": parsed.get("description", ""),
        "format_instructions": parsed.get("format_instructions"),
        "preservation_note": parsed.get("preservation_note"),
    })
    return result.get("checklist", [])


def render_request_form(matter_id: str, key_prefix: str = ""):
    """Render the evidence request creation form.

    Lawyers can either upload a formal letter (AI extracts all fields
    and auto-generates a checklist) or fill in the form manually.
    Uses key_prefix to avoid widget ID conflicts when the form
    appears on multiple pages.
    """
    kp = key_prefix

    with st.expander("Create New Document Request"):
        # Optional letter upload — parses fields AND generates checklist
        letter_file = st.file_uploader(
            "Upload a formal letter (optional)",
            type=["pdf", "png", "jpg", "jpeg", "docx", "txt"],
            key=f"{kp}letter_upload",
            help="Upload an existing RFP letter and we'll extract all fields and generate a checklist.",
        )

        if letter_file and st.button("Parse uploaded letter", key=f"{kp}parse_letter_btn"):
            with st.spinner("Parsing letter and generating checklist..."):
                try:
                    from lib.api_client import get_client
                    with get_client() as c:
                        resp = c.post(
                            "/requests/parse-letter",
                            files={"file": (letter_file.name, letter_file.read(), letter_file.type)},
                        )
                        resp.raise_for_status()
                        parsed = resp.json()
                    st.session_state[f"{kp}parsed_letter"] = parsed

                    # Auto-generate checklist from the parsed fields
                    checklist = _generate_checklist(parsed)
                    st.session_state[f"{kp}draft_checklist"] = checklist

                    st.success("Letter parsed and checklist generated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to parse letter: {e}")

        parsed = st.session_state.get(f"{kp}parsed_letter", {})

        st.divider()

        # -- Form fields (pre-filled from parsed letter if available) --
        req_title = st.text_input(
            "Request title *",
            value=parsed.get("title", ""),
            key=f"{kp}new_req_title",
        )

        col_start, col_end = st.columns(2)
        with col_start:
            req_date_start = st.date_input(
                "Date range start", value=None, key=f"{kp}new_req_date_start")
        with col_end:
            req_date_end = st.date_input(
                "Date range end", value=None, key=f"{kp}new_req_date_end")

        parsed_kw = parsed.get("keywords", [])
        kw_default = ", ".join(parsed_kw) if parsed_kw else ""
        req_keywords = st.text_input(
            "Keywords (comma-separated)", value=kw_default,
            placeholder="contract, Smith, invoice", key=f"{kp}new_req_keywords",
        )
        req_source = st.text_input(
            "Source system",
            value=parsed.get("source_system", "") or "",
            placeholder="Gmail, WhatsApp, Company laptop...",
            key=f"{kp}new_req_source",
        )
        req_desc = st.text_area(
            "Additional instructions",
            value=parsed.get("description", "") or "",
            key=f"{kp}new_req_desc",
        )
        req_format = st.text_area(
            "Format instructions",
            value=parsed.get("format_instructions", "") or "",
            placeholder="e.g. Provide in native format, do not convert to PDF",
            key=f"{kp}new_req_format",
        )
        req_preservation = st.text_area(
            "Preservation notice",
            value=parsed.get("preservation_note", "") or "",
            placeholder="e.g. Do not delete, modify, or clear any data",
            key=f"{kp}new_req_preservation",
        )

        priority_options = ["medium", "high", "low"]
        parsed_priority = parsed.get("priority", "medium")
        priority_idx = priority_options.index(
            parsed_priority) if parsed_priority in priority_options else 0
        req_priority = st.selectbox(
            "Priority", priority_options, index=priority_idx,
            key=f"{kp}new_req_priority",
        )

        st.divider()

        # ── Checklist generation and review ──
        st.markdown("**Client checklist**")
        st.caption(
            "Generate an actionable checklist from the fields above. "
            "Review and edit it before sending to the client."
        )

        if st.button("Generate Checklist", key=f"{kp}gen_checklist_btn"):
            kw_list = [k.strip() for k in req_keywords.split(
                ",") if k.strip()] if req_keywords else []
            with st.spinner("Generating checklist..."):
                try:
                    result = api_post("/requests/generate-checklist", json={
                        "title": req_title,
                        "category": parsed.get("category"),
                        "date_range_start": str(req_date_start) if req_date_start else None,
                        "date_range_end": str(req_date_end) if req_date_end else None,
                        "keywords": kw_list, "source_system": req_source,
                        "description": req_desc, "format_instructions": req_format,
                        "preservation_note": req_preservation,
                    })
                    st.session_state[f"{kp}draft_checklist"] = result.get(
                        "checklist", [])
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate checklist: {e}")

        # Show editable checklist if we have one
        draft_checklist = st.session_state.get(f"{kp}draft_checklist", [])
        updated_items = []
        if draft_checklist:
            st.markdown(
                "**Review checklist** — edit or remove items before sending:")
            for i, item in enumerate(draft_checklist):
                col_text, col_remove = st.columns([5, 1])
                with col_text:
                    edited = st.text_input(
                        f"Item {i + 1}", value=item.get("item", ""),
                        key=f"{kp}checklist_item_{i}", label_visibility="collapsed",
                    )
                with col_remove:
                    remove = st.checkbox("Remove", key=f"{kp}checklist_rm_{i}")
                if not remove and edited.strip():
                    updated_items.append(
                        {"item": edited.strip(), "completed": False})

            new_item = st.text_input(
                "Add a custom checklist item",
                placeholder="e.g. Include all attachments",
                key=f"{kp}checklist_add_item",
            )
            if new_item.strip():
                updated_items.append(
                    {"item": new_item.strip(), "completed": False})
            st.caption(f"{len(updated_items)} checklist items")

        st.divider()

        # -- Send button --
        if st.button("Send Request to Client", key=f"{kp}send_req_btn"):
            if not req_title.strip():
                st.warning("Please enter a request title.")
            else:
                kw_list = [k.strip() for k in req_keywords.split(
                    ",") if k.strip()] if req_keywords else []
                final_checklist = updated_items if draft_checklist else []

                payload = {
                    "title": req_title.strip(), "description": req_desc,
                    "priority": req_priority,
                    "category": parsed.get("category"),
                    "keywords": kw_list, "source_system": req_source or None,
                    "format_instructions": req_format or None,
                    "preservation_note": req_preservation or None,
                    "checklist": final_checklist,
                }
                if req_date_start:
                    payload["date_range_start"] = str(req_date_start)
                if req_date_end:
                    payload["date_range_end"] = str(req_date_end)

                try:
                    api_post(f"/matters/{matter_id}/requests", json=payload)
                    st.session_state.pop(f"{kp}parsed_letter", None)
                    st.session_state.pop(f"{kp}draft_checklist", None)
                    st.success("Request created!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
