"""Client Request Matching View.

Shows the lawyer's evidence requests alongside matching records from
the client's vault, organized by data type with parsed visual displays.
The client can review what's relevant, then approve items for sharing.
"""

import re
from datetime import datetime

import streamlit as st
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.session import require_client, get_matter_id
from lib.api_client import api_get, api_patch, api_post
from lib.theme import setup_page, page_header

setup_page()
require_client()
matter_id = get_matter_id()

page_header(
    "Attorney Requests",
    "See what your attorney needs and which of your records match",
)

# ── Inject page-specific CSS for the rich card layouts ────────

st.markdown(
    """<style>
    .rq-hero {
        background: linear-gradient(135deg, #1E3A5F 0%, #2563EB 100%);
        border-radius: 12px;
        padding: 1.5rem 2rem;
        color: #fff;
        margin-bottom: 1rem;
    }
    .rq-hero h3 { margin: 0 0 0.5rem 0; color: #fff; font-size: 1.3rem; }
    .rq-hero p  { margin: 0 0 0.4rem 0; color: #CBD5E1; font-size: 0.9rem; }
    .rq-chip {
        display: inline-block;
        background: rgba(255,255,255,0.18);
        border-radius: 20px;
        padding: 0.2rem 0.7rem;
        margin: 0.15rem 0.2rem;
        font-size: 0.8rem;
        color: #E0F2FE;
    }
    .rq-badge {
        display: inline-block;
        border-radius: 6px;
        padding: 0.15rem 0.6rem;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .rq-badge-high   { background: #FEE2E2; color: #991B1B; }
    .rq-badge-medium { background: #FEF3C7; color: #92400E; }
    .rq-badge-low    { background: #DBEAFE; color: #1E40AF; }
    .rq-stat-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .rq-stat-card .num {
        font-size: 2rem;
        font-weight: 700;
        color: #1E3A5F;
        margin: 0;
    }
    .rq-stat-card .label {
        font-size: 0.8rem;
        color: #64748B;
        margin: 0;
    }
    .rq-email-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #2563EB;
        border-radius: 8px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
    }
    .rq-email-card .subject { font-weight: 600; color: #0F172A; margin: 0; }
    .rq-email-card .meta    { font-size: 0.8rem; color: #64748B; margin: 0.2rem 0; }
    .rq-email-card .preview { font-size: 0.85rem; color: #475569; margin: 0.3rem 0 0 0; }
    .rq-kw-hl {
        background: #FEF08A;
        padding: 0 3px;
        border-radius: 3px;
        font-weight: 600;
    }
    </style>""",
    unsafe_allow_html=True,
)


# ── Helpers ───────────────────────────────────────────────────


def _fetch_all_records(mid):
    """Fetch all records via pagination (endpoint caps at 100 per call)."""
    all_recs = []
    offset = 0
    while True:
        batch = api_get(
            f"/matters/{mid}/records", params={"limit": 100, "offset": offset}
        )
        if not batch:
            break
        all_recs.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
    return all_recs


def _match_records(request, records):
    """Score each record against a request. Returns matches sorted by score."""
    keywords = [kw.lower() for kw in request.get("keywords", [])]
    category = (request.get("category") or "").lower()
    date_start = request.get("date_range_start")
    date_end = request.get("date_range_end")

    matches = []
    for rec in records:
        score = 0
        matched_kws = []

        text_lower = rec.get("text", "").lower()
        tags_lower = [t.lower() for t in rec.get("tags", [])]

        # Keyword matching: check text and tags
        for kw in keywords:
            if kw in text_lower or any(kw in t for t in tags_lower):
                score += 2
                matched_kws.append(kw)

        # Category matching: compare to source, type, and tags
        if category:
            source_lower = rec.get("source", "").lower()
            type_lower = rec.get("type", "").lower()
            if (
                category in source_lower
                or category in type_lower
                or any(category in t for t in tags_lower)
            ):
                score += 1

        # Date range matching
        if (date_start or date_end) and rec.get("ts"):
            ts_str = str(rec["ts"])[:10]
            in_range = True
            if date_start and ts_str < str(date_start):
                in_range = False
            if date_end and ts_str > str(date_end):
                in_range = False
            if in_range:
                score += 1

        if score > 0:
            matches.append({**rec, "_score": score, "_kws": matched_kws})

    return sorted(matches, key=lambda x: -x["_score"])


def _highlight_keywords(text, keywords):
    """Wrap matched keywords in a highlight span."""
    result = text
    for kw in keywords:
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        result = pattern.sub(
            lambda m: f'<span class="rq-kw-hl">{m.group()}</span>', result
        )
    return result


def _parse_transaction(text):
    """Parse '$85.00 - Easy Tiger - social' into amount, vendor, category."""
    m = re.match(r"\$([0-9,]+\.?\d*)\s*-\s*(.+?)\s*-\s*(.+)", text)
    if m:
        return {
            "amount": m.group(1).replace(",", ""),
            "vendor": m.group(2).strip(),
            "category": m.group(3).strip(),
        }
    return None


def _parse_email(text):
    """Parse pipe-delimited email text into structured fields."""
    parts = {}
    for segment in text.split(" | "):
        if ": " in segment:
            key, val = segment.split(": ", 1)
            parts[key.strip().lower()] = val.strip()
    return parts


def _format_date(ts_str):
    """Format an ISO timestamp into a readable date."""
    if not ts_str:
        return "—"
    try:
        dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return str(ts_str)[:10]


# ── Load data ─────────────────────────────────────────────────

try:
    requests = api_get(f"/matters/{matter_id}/requests")
except Exception:
    requests = []

if not requests:
    st.info(
        "Your attorney hasn't sent any evidence requests yet. "
        "Check back later or ask them to create a request."
    )
    st.stop()

# Only show open/pending requests
open_requests = [r for r in requests if r.get("status") == "open"]
if not open_requests:
    st.success("All requests have been fulfilled!")
    st.stop()

# ── Request selector ──────────────────────────────────────────

request_titles = {r["title"]: r for r in open_requests}
selected_title = st.selectbox(
    "Select a request to review",
    list(request_titles.keys()),
    index=0,
)
request = request_titles[selected_title]

# ── Hero card: what the lawyer is asking for ──────────────────

priority_cls = f"rq-badge-{request.get('priority', 'medium')}"
keywords_html = "".join(
    f'<span class="rq-chip">{kw}</span>' for kw in request.get("keywords", [])
)
date_range_str = ""
if request.get("date_range_start") or request.get("date_range_end"):
    ds = request.get("date_range_start", "any")
    de = request.get("date_range_end", "present")
    date_range_str = f'<p>📅 Date range: <strong>{ds}</strong> → <strong>{de}</strong></p>'

st.markdown(
    f"""<div class="rq-hero">
        <h3>{request['title']}</h3>
        <p>{request.get('description', '')}</p>
        {f'<p>🔍 Keywords: {keywords_html}</p>' if keywords_html else ''}
        {date_range_str}
        <span class="rq-badge {priority_cls}">{request.get('priority', 'medium')} priority</span>
    </div>""",
    unsafe_allow_html=True,
)

# ── Checklist (if present) ────────────────────────────────────

checklist = request.get("checklist", [])
if checklist:
    done_count = sum(1 for c in checklist if c.get("completed"))
    with st.expander(
        f"Evidence checklist from your attorney ({done_count}/{len(checklist)} complete)",
        expanded=False,
    ):
        for i, item in enumerate(checklist):
            label = item.get("item", str(item))
            done = item.get("completed", False)
            is_auto = item.get("auto_detected", False)

            # Show auto-detected badge for items found automatically
            if is_auto and done:
                label += "  *(auto-detected)*"

            st.checkbox(label, value=done, disabled=True, key=f"ck_{i}")

            if is_auto and done and item.get("auto_reason"):
                st.caption(f"  Evidence found: {item['auto_reason']}")

# ── Fetch records and match ───────────────────────────────────

with st.spinner("Scanning your vault for matching records..."):
    all_records = _fetch_all_records(matter_id)

matches = _match_records(request, all_records)

if not matches:
    st.warning(
        "No matching records found yet. Upload evidence that matches "
        "your attorney's request, or try searching your Gmail."
    )
    # Direct link to Gmail search for this request
    if st.button("Search My Gmail", type="primary", key="gmail_no_match"):
        st.session_state["gmail_prefill_request"] = request["id"]
        st.switch_page("pages/11_gmail_search.py")
    st.stop()

# ── Summary stats ─────────────────────────────────────────────

# Group matches by source type
by_source = {}
for m in matches:
    src = m.get("source", "other")
    by_source.setdefault(src, []).append(m)

# Count financial totals
total_amount = 0.0
for m in by_source.get("bank", []):
    parsed = _parse_transaction(m.get("text", ""))
    if parsed:
        try:
            total_amount += float(parsed["amount"])
        except ValueError:
            pass

stat_cols = st.columns(4)
with stat_cols[0]:
    st.markdown(
        f'<div class="rq-stat-card"><p class="num">{len(matches)}</p>'
        f'<p class="label">Matching Records</p></div>',
        unsafe_allow_html=True,
    )
with stat_cols[1]:
    st.markdown(
        f'<div class="rq-stat-card"><p class="num">{len(by_source)}</p>'
        f'<p class="label">Source Types</p></div>',
        unsafe_allow_html=True,
    )
with stat_cols[2]:
    amt_display = f"${total_amount:,.2f}" if total_amount > 0 else "—"
    st.markdown(
        f'<div class="rq-stat-card"><p class="num">{amt_display}</p>'
        f'<p class="label">Financial Total</p></div>',
        unsafe_allow_html=True,
    )
with stat_cols[3]:
    top_score = matches[0]["_score"] if matches else 0
    st.markdown(
        f'<div class="rq-stat-card"><p class="num">{top_score}</p>'
        f'<p class="label">Top Match Score</p></div>',
        unsafe_allow_html=True,
    )

st.divider()

# ── Tabbed display by source type ─────────────────────────────

source_labels = {
    "bank": "💰 Financial Records",
    "email": "✉️ Emails",
    "calendar": "📅 Calendar",
    "ai_chat": "🤖 AI Conversations",
    "lifelog": "📝 Life Log",
    "social": "📱 Social Posts",
    "files": "📁 Files",
    "export": "📦 Other",
}

active_sources = [s for s in source_labels if s in by_source]
# Add any unlabeled sources
for s in by_source:
    if s not in active_sources:
        active_sources.append(s)

tab_labels = [source_labels.get(s, f"📄 {s.title()}") for s in active_sources]
tabs = st.tabs(tab_labels)

matched_keywords = request.get("keywords", [])

for tab, source_key in zip(tabs, active_sources):
    source_matches = by_source[source_key]
    with tab:
        st.caption(f"{len(source_matches)} matching records")

        # ── Financial records: parsed table ──
        if source_key == "bank":
            rows = []
            for m in source_matches:
                parsed = _parse_transaction(m.get("text", ""))
                if parsed:
                    rows.append({
                        "Date": _format_date(m.get("ts")),
                        "Amount": f"${float(parsed['amount']):,.2f}",
                        "Vendor": parsed["vendor"],
                        "Category": parsed["category"],
                        "Match Score": m["_score"],
                    })
                else:
                    rows.append({
                        "Date": _format_date(m.get("ts")),
                        "Amount": "—",
                        "Vendor": m.get("text", "")[:60],
                        "Category": "—",
                        "Match Score": m["_score"],
                    })
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
                if total_amount > 0:
                    st.markdown(
                        f"**Total: ${total_amount:,.2f}** across "
                        f"{len(rows)} transactions"
                    )

        # ── Emails: styled cards ──
        elif source_key == "email":
            for m in source_matches:
                parsed = _parse_email(m.get("text", ""))
                subject = parsed.get("subject", "No subject")
                sender = parsed.get("from", "Unknown")
                body = parsed.get("body summary", "")
                date_str = _format_date(m.get("ts"))

                # Highlight keywords in subject and body
                subject_hl = _highlight_keywords(subject, matched_keywords)
                body_hl = _highlight_keywords(body, matched_keywords)

                st.markdown(
                    f"""<div class="rq-email-card">
                        <p class="subject">{subject_hl}</p>
                        <p class="meta">From: {sender} &nbsp;·&nbsp; {date_str}
                        &nbsp;·&nbsp; Score: {m['_score']}</p>
                        <p class="preview">{body_hl}</p>
                    </div>""",
                    unsafe_allow_html=True,
                )

        # ── Calendar / conversations / other: timeline cards ──
        else:
            for m in source_matches:
                text = m.get("text", "")
                text_hl = _highlight_keywords(text[:300], matched_keywords)
                tags = m.get("tags", [])
                tag_chips = " ".join(
                    f'<span class="rq-chip" style="background:#E2E8F0;color:#334155;">'
                    f"{t}</span>"
                    for t in tags[:5]
                )
                date_str = _format_date(m.get("ts"))

                st.markdown(
                    f"""<div class="rq-email-card"
                         style="border-left-color: #64748B;">
                        <p class="meta">{date_str} &nbsp;·&nbsp;
                        {m.get('type', '')} &nbsp;·&nbsp;
                        Score: {m['_score']}</p>
                        <p class="preview">{text_hl}</p>
                        <p style="margin-top:0.3rem;">{tag_chips}</p>
                    </div>""",
                    unsafe_allow_html=True,
                )

# ── Actions ───────────────────────────────────────────────────

st.divider()
col_gmail, col_share, col_fulfill = st.columns(3)

with col_gmail:
    if st.button("Search My Gmail", key="gmail_bottom"):
        st.session_state["gmail_prefill_request"] = request["id"]
        st.switch_page("pages/11_gmail_search.py")

with col_share:
    st.page_link(
        "pages/04_client_share.py",
        label="Go to Share & Approve →",
    )

with col_fulfill:
    if st.button("Mark Request as Fulfilled", type="primary"):
        try:
            api_patch(
                f"/requests/{request['id']}",
                params={"status": "fulfilled"},
            )
            st.success("Request marked as fulfilled!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")
