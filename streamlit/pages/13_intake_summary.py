"""Intake Summary — AI-generated case narrative for attorneys.

Visualises the intake summary produced by the enrichment pipeline:
  - Case overview (narrative paragraphs citing evidence)
  - Key timeline bullets with citations
  - Open questions the attorney should follow up on
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.theme import setup_page, page_header, NAVY, BLUE, BLUE_50, BLUE_100, GREY_500
from lib.api_client import api_get
from lib.session import require_attorney, get_matter_id

setup_page()
require_attorney()
matter_id = get_matter_id()

page_header("Intake Summary", "AI-drafted case narrative — verify against source evidence")


# ── Fetch data ────────────────────────────────────────────────

try:
    summary = api_get(f"/matters/{matter_id}/intake-summary")
except Exception:
    summary = None

if not summary:
    st.info(
        "No intake summary available yet. "
        "Run the enrichment pipeline from the Matter Dashboard to generate one."
    )
    st.page_link("pages/05_lawyer_dashboard.py", label="Go to Matter Dashboard")
    st.stop()


# ── Helpers ───────────────────────────────────────────────────


def _format_overview(text: str) -> str:
    """Convert plain-text overview to HTML paragraphs.

    Splits on double-newlines for paragraphs. Highlights bracketed
    record citations like [rec_xxx] with a styled badge.
    """
    import re

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    html_parts = []
    for p in paragraphs:
        # Turn [rec_xxx] citations into styled badges
        styled = re.sub(
            r'\[([^\]]+)\]',
            f'<span style="'
            f"background: {BLUE_50}; color: {BLUE}; "
            f"padding: 1px 6px; border-radius: 10px; "
            f'font-size: 0.85em;">'
            r'\1</span>',
            p,
        )
        html_parts.append(f"<p style='margin-bottom: 1rem;'>{styled}</p>")

    return "".join(html_parts)


# ── AI disclaimer banner ─────────────────────────────────────

st.markdown(
    f"""<div style="
        background: {BLUE_50};
        border-left: 4px solid {BLUE};
        padding: 0.75rem 1rem;
        border-radius: 0 6px 6px 0;
        margin-bottom: 1.5rem;
        font-size: 0.9rem;
        color: {NAVY};
    ">
        <strong>AI-Assisted Draft</strong> — This narrative was generated
        automatically from uploaded evidence. All claims should be verified
        against the original source documents before use.
    </div>""",
    unsafe_allow_html=True,
)

# ── Tabs for the three sections ───────────────────────────────

tab_overview, tab_timeline, tab_questions = st.tabs([
    "Case Overview",
    "Key Timeline",
    "Open Questions",
])


# ── Tab 1: Case Overview ─────────────────────────────────────

with tab_overview:
    case_overview = summary.get("case_overview", "")
    if case_overview:
        # Render the narrative paragraphs with styled container
        st.markdown(
            f"""<div style="
                background: white;
                border: 1px solid {BLUE_100};
                border-radius: 8px;
                padding: 1.5rem 2rem;
                line-height: 1.8;
                font-size: 1rem;
                color: #1E293B;
            ">{_format_overview(case_overview)}</div>""",
            unsafe_allow_html=True,
        )
    else:
        st.caption("No case overview generated.")


# ── Tab 2: Key Timeline ──────────────────────────────────────

with tab_timeline:
    timeline = summary.get("key_timeline", [])
    if timeline:
        # Render a vertical timeline with styled bullets
        for i, entry in enumerate(timeline):
            bullet_text = entry if isinstance(entry, str) else entry.get("bullet", "")
            citations = [] if isinstance(entry, str) else entry.get("citations", [])

            # Connector line (skip for last item)
            border_style = f"border-left: 3px solid {BLUE};" if i < len(timeline) - 1 else "border-left: 3px solid transparent;"

            # Citation badges
            cite_html = ""
            if citations:
                badges = "".join(
                    f'<span style="'
                    f"background: {BLUE_50}; color: {BLUE}; "
                    f"padding: 2px 8px; border-radius: 12px; "
                    f'font-size: 0.75rem; margin-right: 4px;">'
                    f'{c.get("record_id", c) if isinstance(c, dict) else c}</span>'
                    for c in citations
                )
                cite_html = f'<div style="margin-top: 4px;">{badges}</div>'

            st.markdown(
                f"""<div style="
                    {border_style}
                    padding: 0 0 1.25rem 1.25rem;
                    position: relative;
                    margin-left: 8px;
                ">
                    <div style="
                        width: 14px; height: 14px;
                        background: {BLUE};
                        border: 3px solid {BLUE_100};
                        border-radius: 50%;
                        position: absolute;
                        left: -8.5px; top: 2px;
                    "></div>
                    <div style="
                        font-size: 0.95rem;
                        color: #1E293B;
                        line-height: 1.6;
                    ">{bullet_text}</div>
                    {cite_html}
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No timeline bullets generated.")


# ── Tab 3: Open Questions ────────────────────────────────────

with tab_questions:
    questions = summary.get("open_questions", [])
    if questions:
        for i, q in enumerate(questions):
            question = q if isinstance(q, str) else q.get("question", "")
            why = "" if isinstance(q, str) else q.get("why", "")

            st.markdown(
                f"""<div style="
                    background: white;
                    border: 1px solid {BLUE_100};
                    border-radius: 8px;
                    padding: 1rem 1.25rem;
                    margin-bottom: 0.75rem;
                ">
                    <div style="
                        font-weight: 600;
                        color: {NAVY};
                        font-size: 0.95rem;
                        margin-bottom: 0.25rem;
                    ">{i + 1}. {question}</div>
                    <div style="
                        color: {GREY_500};
                        font-size: 0.85rem;
                        line-height: 1.5;
                    ">{why}</div>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No open questions identified.")
