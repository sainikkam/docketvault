# TRACK1_OVERVIEW

### DocketVault — Consent-Aware Legal Intake Vault (Portable Personal Data → Evidence Pack)
**Track 1: Memory Infrastructure | March 2026**

---

## 0) One-sentence pitch
DocketVault is a **mobile-first, consent-gated evidence vault** that ingests a client’s **portable data exports** and **Google OAuth** sources (Drive/Gmail/Calendar), applies an **X‑LLM-style multimodal understanding layer** (images/audio/video + bounding boxes/timestamps), and generates a **lawyer-ready Evidence Pack**—shareable only after explicit client approval.

---

## 1) What this project is
DocketVault is a **permissioned data pipeline** + **secure vault** purpose-built for legal intake. It converts scattered personal data (messages, emails, receipts, screenshots, scanned PDFs, audio notes, short videos) into a structured, searchable “case memory”:

- **Client-private vault** (imports are private by default)
- **Model-assisted enrichment** (multimodal extraction + timeline + categorization)
- **Consent-gated sharing** (client approves subset; lawyer gets access)
- **Evidence Pack output** (PDF summary + indexes + approved record subset + audit excerpt)

**Key Track 1 alignment:** user-controlled personal data becomes **portable, permissioned, and interoperable** across systems/parties—without breaking consent.

---

## 2) Project goal (what we’re optimizing for)
1) **Reduce intake latency** from days/weeks → minutes/hours  
2) **Eliminate document chase** via completeness checks + targeted requests  
3) **Increase trust** via least-privilege access, explicit consent, audit logs  
4) **Make multimodal evidence usable** with X‑LLM-style extraction + citations  
5) **Produce defensible outputs** (evidence index + provenance + “what changed”)

---

## 3) Who we serve (two consumers)

### Client value
- **Minimal effort**: capture/import once; no manual sorting
- **Clear control**: Share Preview with include/exclude + revoke
- **Lower anxiety**: sensitive-content detection + transparent access
- **Faster outcomes**: lawyer acts sooner with organized materials

### Lawyer value
- **Fewer follow-ups**: “missing items” surfaced up front
- **Higher-quality intake**: timeline + categorized evidence w/ citations
- **Reduced risk**: consent tracking, least-privilege, audit trail
- **Operational leverage**: less staff time; faster time-to-file

---

## 4) Data sources we support (MVP)

### A) Portable exports (exports-first)
- ZIP/JSONL/CSV/PDF/images/audio/video
- Competition dataset-compatible “record streams” (schema-tolerant)
- LinkedIn / X / AI chat exports: **upload export ZIP** → parse → normalize

### B) Official Google OAuth connectors (read-only)
- **Drive**: import only user-selected files/folders
- **Gmail**: read-only import of relevant threads + attachments (query/date-bounded)
- **Calendar**: read-only import of events for timeline

> **Import ≠ share.** OAuth import fills client-private vault; lawyer sees nothing until client approves.

---

## 5) Security posture (lawyer-safe defaults)
- Read-only OAuth scopes (no send mail, no edit files/events)
- Per-matter role-based access (client vs lawyer)
- Signed, expiring download links for exports
- Append-only audit log (view/export/share/revoke)
- Sensitive-item gating (client must explicitly include)
- Retention/deletion controls aligned to competition constraints

---

## 6) X‑LLM-style multimodal layer (core differentiator)
We implement the **X‑LLM architectural idea**: treat each modality as a “foreign language,” convert it into language-aligned representations, then extract structured annotations that power downstream workflows.

### Inputs
- Images: screenshots, receipts, scans, photos of documents
- PDFs: both native text and scanned PDFs
- Audio: voice notes/voicemails
- Video: short clips (property damage, incident recording)

### Outputs (stored as annotations, not overwriting originals)
- **Extracted text** + short summary
- **Structured claims JSON** (dates, amounts, parties, identifiers, key quotes)
- **Sensitivity flags**
- **Citations**
  - Images/PDFs: **bounding boxes** for each extracted field
  - Audio/Video: **timestamps** for transcript segments and “key moments”

> **Rule:** every surfaced claim must cite its underlying artifact region/time.

---

## 7) LLM uses included in MVP (maximize impact; minimize risk)

**Principle:** LLM outputs are *annotations*; all facts shown to users include citations.

1) **Matter-aware categorization + tagging**
   - Communications / Documents / Financial / Calendar / Media / Audio / Video / Narrative
2) **Timeline extraction + key event summarization**
   - structured events with record/artifact citations
3) **Checklist gap detection (“missing items”)**
   - matter template requirements → prompts + structured requests
4) **Sensitive content detection**
   - PII/health/banking identifiers → gating in Share Preview
5) **Attorney-ready Intake Summary drafting**
   - one-page draft w/ citations + “needs confirmation” notes

---

## 8) Core user flows

### Client flow (mobile-first)
1) Join matter via invite
2) Connect Google + import exports
3) Add evidence from phone (scan/upload/audio/video/share sheet)
4) Review extracted highlights (bboxes/timestamps)
5) Share Preview (exclude sensitive items)
6) Approve & Share → lawyer gains access
7) Revoke at any time

### Lawyer flow (mobile + optional web)
1) Onboard to firm profile
2) Create matter templates
3) Create matter + invite client
4) Review timeline + evidence index + highlights
5) Send targeted requests for missing items
6) Export Evidence Pack (PDF + indexes + approved subset)

---

## 9) Mobile UI plan (exact screens + navigation)

### Design system (classy tri-chrome)
- **Base:** warm off-white (paper-like)
- **Primary accent:** burgundy (primary CTA, key highlights)
- **Ink:** charcoal/black (text/icons)
- **Neutrals:** cool grays for dividers, secondary text, chips
Accessibility:
- 44×44 touch targets, high contrast, labels not color-only, dynamic type

---

### Client app: screens (exact list)

#### Onboarding/Auth stack
1. Welcome  
2. Sign In / Create Account  
3. Verify Email + MFA Setup  
4. Join Matter (Invite Link deep link)  
5. Permissions & Privacy Promise (Import ≠ Share; retention; audit)  
6. Connect Sources (Google + Uploads)

#### Main tabs (Matter / Add / Review / Account)

**Tab: Matter**
7. Matter Home  
8. Case Timeline  
9. Evidence Categories  
10. Evidence Item Detail  
11. Viewer: Document/Image with Bounding-Box Highlights  
12. Viewer: Audio Transcript + Key Moments  
13. Viewer: Video + Key Moments  

**Tab: Add**
14. Add Evidence Hub  
15. Camera Scan (Multi-page PDF)  
16. Upload from Files/Photos  
17. Record Audio Note  
18. Import from Google (Drive/Gmail/Calendar)  
19. Import Exports from Drive Folder (ZIPs)  

**Tab: Review**
20. Share Preview (Category + Item toggles)  
21. Sensitive Items Review  
22. Confirm Key Timeline Events  
23. Approve & Share Confirmation  
24. Share Status + Activity Log  

**Tab: Account**
25. Profile & Security  
26. Connected Accounts  
27. Access & Revocation  
28. Retention / Delete Data  
29. Help / Support  

Client nav (happy path): Auth → Join Matter → Connect Sources → Matter Home → Add evidence/import → Review → Approve & Share.

---

### Lawyer app: screens (exact list)

#### Onboarding/Auth stack (explicitly included)
1. Welcome (Lawyer)  
2. Sign In  
3. MFA Setup  
4. **Firm Profile** (name, logo, practice areas, retention defaults)  
5. **Create Matter Templates** (required checklists + request templates)

#### Main tabs (Matters / Review / Requests / Account)

**Tab: Matters**
6. Matters List  
7. Matter Dashboard  
8. Evidence Index (Categories + Filters)  
9. Timeline (Key Events)  
10. Evidence Item Detail  
11. Viewer: Document/Image with Bounding-Box Highlights  
12. Viewer: Audio Transcript + Key Moments  
13. Viewer: Video + Key Moments  

**Tab: Review**
14. What’s New Feed (newly shared items)  
15. Sensitive Items Queue (view-only unless shared)  
16. Draft Intake Summary (AI-assisted; citations)

**Tab: Requests**
17. Missing Items Checklist  
18. Send Request to Client (structured request)  
19. Request Status Tracking  

**Tab: Account**
20. Profile & Security  
21. Firm Settings  
22. Audit Log Viewer  
23. Export Settings  

Lawyer nav (happy path): Auth → Firm Profile → Create Template → Create Matter → Invite Client → Review → Request missing → Export Evidence Pack.

---

## 10) High-level system architecture (implementation strategy)

### Frontend
- Mobile: React Native or Flutter
- Role-based router: Client vs Lawyer
- Viewers:
  - image/PDF viewer with bbox overlays
  - audio player w/ transcript sync
  - video player w/ key-moment markers

### Backend services
1) **API Service**
   - auth, RBAC, matters, sharing, requests, audit
2) **Ingestion Service**
   - import portable exports
   - Google OAuth import (Drive/Gmail/Calendar)
3) **Processing Workers (async jobs)**
   - X‑LLM multimodal extraction (images/PDF/audio/video)
   - LLM enrichment (categorize/timeline/missing items/summary)
4) **Evidence Pack Generator**
   - PDF summary + CSV index + approved subset export ZIP
5) **Search/Index**
   - full-text search over raw text + extracted text + tags

### Storage
- Object storage for blobs (images/pdf/audio/video/export zips)
- Postgres for metadata/records/annotations/audit logs
- Optional: vector index for semantic search (nice-to-have)

---

## 11) Data model (minimal, but complete)

### Core entities
- `User` (client or lawyer)
- `Firm` (lawyer org)
- `Matter` (case workspace)
- `MatterTemplate` (checklists + request templates)
- `Record` (normalized structured record: email/message/calendar/transaction/etc.)
- `Artifact` (blob: image/pdf/audio/video)
- `Extraction` (multimodal outputs: text/claims + bboxes/timestamps)
- `Annotation` (LLM outputs: category/tags/timeline items/sensitivity)
- `SharePolicy` (what’s approved for lawyer access)
- `Request` (lawyer→client missing item request)
- `AuditLog` (append-only events)

---

## 12) Step-by-step implementation plan (meticulous, high-level)

### Phase 1 — Foundations
- Implement Auth + MFA
- Create Firm + Matter + Invite links (deep links)
- Implement RBAC for client/lawyer
- Create Matter Templates (checklists + request prompts)
- Build object storage + blob upload pipeline
- Add audit logging for key actions

### Phase 2 — Ingestion
- Portable export ingestion:
  - upload ZIP → unpack → adapter parse → normalize to `Record`/`Artifact`
  - unknown formats stored as `Artifact` + “Needs Review”
- Google OAuth:
  - Drive picker import → download blobs
  - Gmail query-based import → store message metadata + attachments
  - Calendar date-range import → store events as records

### Phase 3 — X‑LLM multimodal extraction
- For each new Artifact (image/pdf/audio/video):
  - run extraction job
  - persist `Extraction`:
    - extracted text
    - structured claims
    - sensitivity flags
    - **bboxes** (image/pdf) / **timestamps** (audio/video)
  - index extracted text for search

### Phase 4 — LLM enrichment + “case memory”
- Categorize + tag all records/artifacts
- Build cited timeline (events reference record IDs + artifact regions/timestamps)
- Run completeness engine:
  - template requirements → “missing items” + suggested questions

### Phase 5 — Client review + share
- Share Preview screen:
  - category and item toggles
  - sensitive gating (explicit include/exclude)
- Approve & Share:
  - materialize `SharePolicy` for lawyer
  - log events (audit)
- Revoke:
  - immediately remove lawyer access; log event

### Phase 6 — Lawyer workflow + exports
- Matter dashboard:
  - key timeline
  - evidence index
  - missing items checklist
- Request missing items:
  - structured request + status tracking
- Evidence Pack export:
  - PDF summary (timeline + evidence index + gaps)
  - CSV index
  - approved JSONL subset
  - audit excerpt
  - ZIP bundle

---

## 13) Demo checklist (what must be visible)
- Connect Google (read-only scopes) **and** import exports from Drive folder
- Evidence item viewer with:
  - **bounding-box highlights** (image/PDF)
  - **transcript + key moments** (audio)
  - **key moments markers** (video)
- Share Preview with sensitive gating
- Lawyer dashboard + missing-items requests
- Evidence Pack export + audit log + revoke

---

## 14) What to say if asked “does it work for any person?”
Yes—if the person can provide **portable exports** in common formats (ZIP/JSONL/CSV/PDF/media) and/or connect supported sources via **official OAuth**. The internal model is schema-tolerant and adapter-based, so new export formats plug in cleanly.

---

# APPENDIX A — FULL PRD + TECHNICAL SPEC (DROP-IN)

# DOCKETVAULT_PRD_TECH_SPEC

### DocketVault — Consent-Aware Legal Intake Vault (Portable Personal Data → Evidence Pack)
**Track 1: Memory Infrastructure | March 2026**

---

## 1) Product overview

### 1.1 One-sentence pitch
**DocketVault** is a **mobile-first, consent-gated evidence vault** for **Landlord–Tenant matters** that ingests a client’s **portable exports** and **Google OAuth sources** (Drive/Gmail/Calendar), applies an **X-LLM-style multimodal understanding layer** (image/audio/video with bounding boxes/timestamps), and generates a **lawyer-ready Evidence Pack** with **chain-of-custody (SHA-256 hash manifest + source IDs + audit logs)**—shareable only after explicit client approval.

### 1.2 Target environment
- Demo at **UT Austin Law School**
- Competition “Memory Infrastructure” (data portability + user-controlled consent)

### 1.3 Core value proposition
- **Client**: minimal effort, clear control, sensitive-data safety, faster legal action
- **Lawyer**: less doc chase, better evidence quality, defensible provenance, faster case readiness

---

## 2) Users, roles, and permissions

### 2.1 User roles
**Client-side**
- **Primary Client**: can invite other clients; sharing approvals are per-item owner overall
- **Contributor Client**: can upload/import evidence; can approve sharing only for their own items

**Firm-side**
- **Attorney**: full access within firm; can create templates; create matters; invite clients; request items; export; propose edits
- **Paralegal**: can review evidence and propose edits/requests; export if allowed by attorney policy; cannot change firm settings

### 2.2 Multi-user matter rules (decided)
- **Multiple clients per matter**
- **Per-item owner approval** required for sharing that item to the firm
- Sensitive items: **included by default**, but require an **explicit approval prompt** to keep included
- Lawyer edits require **client confirmation** before becoming “final/shared truth”

### 2.3 Permission matrix (MVP)
| Action | Primary Client | Contributor Client | Paralegal | Attorney |
|---|---:|---:|---:|---:|
| Upload/import evidence | ✅ | ✅ | ❌ | ❌ |
| View own vault items | ✅ | ✅ | ❌ | ❌ |
| View shared-to-firm items | ✅ | ✅ | ✅ | ✅ |
| Approve sharing (own items) | ✅ | ✅ | ❌ | ❌ |
| Revoke sharing (own items) | ✅ | ✅ | ❌ | ❌ |
| Create matter | ❌ | ❌ | ✅ (optional) | ✅ |
| Invite clients | ❌ | ❌ | ✅ (optional) | ✅ |
| Request missing items | ❌ | ❌ | ✅ | ✅ |
| Edit categories/timeline | view + propose | view + propose | ✅ propose | ✅ propose |
| Finalize edits | confirm required | confirm required | ❌ | ❌ |
| Generate lawyer Evidence Pack | ❌ | ❌ | ✅ (configurable) | ✅ |
| Generate client export pack | ✅ | ✅ | ❌ | ❌ |
| Firm settings/templates | ❌ | ❌ | ❌ | ✅ |

---

## 3) Primary use case (Landlord–Tenant) and scope

### 3.1 Matter template: Landlord–Tenant
Evidence categories DocketVault must support:
- **Lease & notices**: lease PDF, notice to vacate, repair notices, demand letters
- **Communications**: emails with landlord/property manager, chat screenshots, formal letters
- **Payments & receipts**: rent payment receipts, bank statements (export), invoices
- **Condition evidence**: photos/videos of damage, mold, leaks, pests; inspection reports
- **Timeline**: repair request, notice received, inspection, payment, court date
- **Witnesses**: roommates, neighbors, maintenance staff (extracted from communications)

### 3.2 Ongoing updates (decided)
- Daily auto-refresh with notifications + manual refresh
- New items go to **client vault** but **not shared** until approval

---

## 4) Functional requirements

### 4.1 Onboarding & authentication
- Email-based accounts for clients and firm users
- MFA required (TOTP preferred)
- Firm settings page shows **“SSO (coming soon)”** as enterprise roadmap item

### 4.2 Firm onboarding (required)
- **Firm Profile screen**: firm name, logo, practice areas, default retention policy, export watermarking toggle (optional), paralegal export permission toggle
- **Create Matter Template screen**: checklist requirements + request templates + default Gmail query patterns + recommended Drive folder structure

### 4.3 Matter creation & invitations
- Attorney creates matter from template
- Invite links (deep links to mobile; web fallback)
- Add clients: Primary + Contributors
- Add staff: Attorney + Paralegal

### 4.4 Data ingestion

#### 4.4.1 Portable exports ingestion
- Upload ZIP/JSONL/CSV/PDF/images/audio/video
- Parse with “adapter” framework:
  - `LinkedInAdapter`, `XAdapter`, `AIChatAdapter`, `GenericZipAdapter`
- If unknown format: store as Artifact, mark “Needs Review”, allow include as raw file

#### 4.4.2 Google OAuth ingestion (two-step consent required)
Connect → Preview Import → Import
- **Drive**: user selects files/folders; import only selection
- **Gmail**: query- and date-bounded import of threads + attachments
- **Calendar**: date-bounded import of events
- Store **source IDs** (Drive/Gmail/Calendar)

#### 4.4.3 Offline capture mode (client)
- Client can scan/upload/record audio/video offline
- Items queue locally and upload when network available
- UI shows queued vs uploaded vs processed

### 4.5 Multimodal understanding (X-LLM-style layer)
Artifacts processed:
- Images (receipts/screenshots/scans), PDFs, audio, video
Outputs (annotations):
- extracted text, structured claims, sensitivity flags
- citations: **bboxes** (image/pdf) and **timestamps** (audio/video)
- video clips generated around key moments stored as derived artifacts

### 4.6 LLM enrichment layer
- Categorization + tags + relevance scoring
- Timeline extraction (events with citations)
- Missing items suggestions from template checklist
- Draft intake summary generation (AI-assisted; citations)
- States: **Verified / High confidence / Needs review**

### 4.7 Client review & consent gating
- Share Preview:
  - category-level toggles, item-level toggles
  - sensitive inclusion requires explicit approval prompt
- Per-item owner approval required to share item to firm
- Item-level revocation removes firm access to item and derived redacted copies

### 4.8 Lawyer editing workflow (with client confirmation)
- Lawyers propose edits (categories/timeline)
- Edits remain “Proposed” until owners confirm
- Audit log records proposals and confirmations

### 4.9 Requests workflow (“doc chase killer”)
- Missing Items checklist auto-generated per template
- Structured requests (due date, priority, accepted types)
- Client can fulfill in 1–2 taps; status tracking included

### 4.10 Redaction
- In-app redaction (blur/blackout) for images/PDFs
- Applies only to **shared-to-firm copy**
- Client retains original; client previews redacted view
- Redacted artifact has its own hash; references original

### 4.11 Malware scanning
- Scan ZIP/PDF/docs on upload/import
- If suspicious: **quarantine** (inaccessible), notify uploader + firm, allow delete/appeal

### 4.12 Evidence Pack export (both sides)
- Lawyer exports **approved shared subset** only
- Client exports vault pack and/or approved-for-firm pack
- Export includes: PDF, CSV, approved JSONL, audit excerpt, **hash manifest + source IDs**, artifacts (redacted where applicable)

### 4.13 Evidence Manifest UI
- Page showing per-item: SHA-256, source ID, original + import timestamps, owner, share state, chain-of-custody events

### 4.14 Notifications (MVP)
Channels: **in-app + email + push**
Triggers: refresh, approvals, requests, edits, exports, quarantine, processing states

---

## 5) Non-functional requirements
- Security: TLS, encryption at rest, MFA, least-privilege OAuth, RBAC, signed URLs, audit logs
- Reliability: async jobs, retries/DLQ, chunked uploads, dedupe-by-hash, rate limiting
- Explainability: citations for claims; verification states; pack distinguishes verified vs model-suggested

---

## 6) UX requirements (mobile + web)
- Tri-chrome theme: off-white base, burgundy accent, charcoal ink; neutral grays
- Accessibility: 44×44 targets, high contrast, dynamic type, labels not color-only
- Web dashboard required for lawyers; mobile required for clients

---

## 7) Technical architecture (recommended)
- Mobile: React Native (or Flutter)
- Web: Next.js
- Backend: FastAPI + Postgres + S3 storage
- Queue/Workers: Redis + Celery/RQ
- Search: Postgres FTS (optional vectors later)

---

## 8) Data model (detailed)
See main spec sections for tables:
- users, firms, templates, matters, members
- records, artifacts, extractions, annotations
- share approvals, edit proposals, requests
- audit log, notifications

---

## 9) Key APIs (high-level)
Auth, Firm/Templates, Matters/Members, Ingestion, Evidence/Processing, Sharing/Approvals, Edits, Requests, Exports, Manifest/Audit.

---

## 10) Job pipeline (async)
Upload/import → hash → malware scan → extraction (bbox/timestamps/clips) → enrichment → notify → review/verify → share gating → export.

---

## 11) Google OAuth (MVP)
Scopes:
- Drive: `https://www.googleapis.com/auth/drive.file`
- Gmail: `https://www.googleapis.com/auth/gmail.readonly`
- Calendar: `https://www.googleapis.com/auth/calendar.events.readonly`
Two-step consent: connect → preview → import; import ≠ share.

---

## 12) Evidence Pack content (lawyer pack)
- `intake_summary.pdf`
- `evidence_index.csv`
- `approved_records.jsonl`
- `approved_artifacts/` (redacted shared copies)
- `hash_manifest.csv` (SHA-256 + source IDs + timestamps)
- `audit_excerpt.jsonl`

---

## 13) Acceptance criteria (demo-critical)
- Landlord–Tenant template + requests
- Client mobile: offline capture; bbox viewer; audio transcript; video key moments + clips
- Lawyer web: dashboard; viewer; export; manifest page
- Consent gating: per-item owner approvals; sensitive explicit approval prompt
- Redaction (shared-copy only)
- Malware quarantine flow
- Evidence Pack includes manifest + audit trail
- Lawyer edits require client confirmation

---

# APPENDIX B — EXECUTION PLAN (DISCRETIZED DELIVERABLE CHUNKS)

# DOCKETVAULT_EXECUTION_PLAN (Deliverable Chunks)

## Chunk 1 — Foundations (Auth + RBAC + Matter scaffolding)
**Deliverables**
- Email auth + MFA (TOTP)
- Role router (Client / Attorney / Paralegal)
- Firm Profile (Attorney onboarding)
- Matter Template builder (Landlord–Tenant)
- Matter creation + invitations (deep links)
- Core DB schema + S3 storage + audit logging

**Demo check**
- Attorney creates firm + template + matter, generates invite link.

---

## Chunk 2 — Evidence ingestion (Portable exports + Google OAuth)
**Deliverables**
- Export upload (ZIP/JSONL/CSV/PDF/media) with adapter framework + “Needs Review”
- Google OAuth Connect → Preview → Import
  - Drive selection import
  - Gmail query/date import + attachments
  - Calendar date-range import
- Offline capture queue on mobile (scan/upload/audio/video)
- Source IDs + original timestamps captured

**Demo check**
- Client imports Drive folder and uploads a video offline then syncs.

---

## Chunk 3 — Trust pipeline (Hashing + malware quarantine)
**Deliverables**
- SHA-256 hashing at ingest + dedupe-by-hash
- Malware scanning pipeline
- Quarantine UX + notifications + delete/appeal
- Evidence Manifest page skeleton (shows hashes/source IDs/timestamps)

**Demo check**
- Show manifest view; show quarantined item behavior.

---

## Chunk 4 — X-LLM multimodal extraction (bbox + transcript + video moments/clips)
**Deliverables**
- Image/PDF extraction → extracted fields + bounding boxes
- Audio transcription → timestamps + key moments
- Video understanding → key moments + generated short clips
- Verification states (Needs review / High confidence / Verified)
- Viewer UIs:
  - bbox field list → jump/highlight
  - audio transcript synced
  - video markers + clip playback

**Demo check**
- Open a receipt screenshot: field list highlights bboxes.
- Open a video: tap key moment → play clip.

---

## Chunk 5 — LLM enrichment (categorize + timeline + missing items + summary)
**Deliverables**
- Categorization + tagging + relevance scoring
- Cited timeline (events link to record IDs / bbox / timestamps)
- Completeness engine for Landlord–Tenant checklist
- Draft intake summary (AI-assisted, citations)
- Lawyer propose edits; client confirmation workflow

**Demo check**
- Missing-items checklist generates a structured request.
- Lawyer edits a timeline event → client confirms.

---

## Chunk 6 — Consent gating + redaction + sharing
**Deliverables**
- Per-item owner approval to share
- Sensitive items: included by default but requires explicit approval prompt
- Redaction tool (shared-copy only) + preview of redactions
- Revoke sharing (immediate effect) + audit log

**Demo check**
- Contributor client approves their item; primary approves theirs; lawyer sees only approved subset.
- Client redacts a notice date → lawyer sees redacted copy.

---

## Chunk 7 — Evidence Pack export (D + E mic drops)
**Deliverables**
- Lawyer export of approved subset only (ZIP)
- Client export options (vault pack + approved-for-firm pack)
- `hash_manifest.csv` + source IDs + timestamps
- `audit_excerpt.jsonl`
- “Evidence Pack generated: hashes verified” UI moment

**Demo check**
- Export pack and open manifest file; show hashes and source IDs.
- Show video key moments + clips (D) then export manifest (E).

---

## Chunk 8 — Notifications + daily refresh
**Deliverables**
- Daily refresh scheduler + manual refresh
- New items go to client vault only (not auto-shared)
- In-app + email + push notification flows

**Demo check**
- Trigger refresh; show “approval needed” notification.

---

# APPENDIX C — LLM PROMPTPACK (DROP-IN)

> This promptpack is designed to be pasted into an LLM/workers codebase with **zero prior context**.  
> It enforces **no-fabrication**, **mandatory citations**, and **verification states** for every model-generated claim.

---

# DOCKETVAULT LLM PROMPTPACK (MVP)

## 0) Required invariants (apply to every prompt)

### 0.1 No fabrication
- **Never invent facts.** If you can’t find support in the provided inputs, output `"unknown"` and add a `"needs_review"` item.
- Never infer a date/amount/person unless it is explicitly present.

### 0.2 Citations are mandatory
Every claim surfaced to users must include **citations**:
- **Records**: cite `record_id`
- **Artifacts** (image/pdf/audio/video): cite `artifact_id` plus:
  - `region` for image/pdf (`page`, `x`, `y`, `w`, `h`)
  - `time_range` for audio/video (`start_ms`, `end_ms`)

### 0.3 Confidence + verification states
All outputs must carry:
- `confidence` in `[0,1]`
- `verification_state` ∈ `{ "needs_review", "high_confidence", "verified" }`
  - LLM outputs default to `high_confidence` or `needs_review`; never output `verified` unless the input explicitly contains a human-confirmed flag.

### 0.4 Privacy + minimization
- Only use the minimum text needed to produce structured outputs.
- Do not output full sensitive strings if not needed; prefer masked representation (e.g., last 4 digits).

### 0.5 Role safety
- Do not provide legal advice or conclusions (“illegal eviction,” “you should sue”). You may label items as “potentially relevant” to landlord–tenant workflows.

---

## 1) Shared data model conventions

### 1.1 Inputs (what your app passes to LLMs)
**Record (structured):**
```json
{
  "record_id": "rec_123",
  "owner_user_id": "usr_clientA",
  "ts": "2026-03-01T18:22:11Z",
  "source": "gmail|calendar|export|manual",
  "type": "email|calendar_event|message|transaction|note",
  "text": "…",
  "metadata": { "subject": "...", "from": "...", "to": ["..."], "thread_id": "...", "source_id": "..." }
}
```

**Artifact (blob):**
```json
{
  "artifact_id": "art_456",
  "owner_user_id": "usr_clientB",
  "mime_type": "image/png|application/pdf|audio/m4a|video/mp4",
  "source_system": "drive|gmail|upload|export_zip",
  "source_id": "drive_file_id|gmail_attachment_id|zip_path",
  "original_timestamps": { "exif_taken_at": "...", "drive_modified": "..." },
  "import_timestamp": "2026-03-02T00:10:00Z"
}
```

### 1.2 Citation object schema (use everywhere)
```json
{
  "citation_type": "record|artifact_region|artifact_time",
  "record_id": "rec_123",
  "artifact_id": "art_456",
  "page": 1,
  "region": { "x": 0.12, "y": 0.34, "w": 0.20, "h": 0.05 },
  "time_range": { "start_ms": 12000, "end_ms": 18500 }
}
```

Notes:
- `x,y,w,h` are **normalized 0..1** coordinates relative to page/image.
- For PDFs, include `page`.
- For audio/video, include `time_range`.

---

## 2) Strict JSON output rules
For every task:
- Output **JSON only** (no prose).
- No trailing commentary.
- If unknown, use `"unknown"` and include a `needs_review` note with citations.

---

# PROMPTS BY PIPELINE STAGE

## 3) Multimodal Extraction — Images (screenshots, receipts, scans)

### 3.1 System message
You are an evidence extraction engine for a landlord–tenant legal intake vault. Extract only what is visible. Do not infer. Always provide citations as bounding boxes.

### 3.2 User prompt template
Inputs provided:
- `artifact` metadata
- The image content (or extracted OCR text + token/region mapping if available)
- Optional context: `matter_template="landlord_tenant"`

Task:
Return a JSON object matching the schema below. Extract: doc type, parties, dates, amounts, addresses, unit numbers, deadlines, policy/claim/invoice IDs, and key quotes relevant to landlord–tenant matters. Provide bounding boxes for each extracted field. If any field is uncertain, set it to unknown and mark needs_review.

### 3.3 Output schema
```json
{
  "artifact_id": "art_456",
  "doc_type_guess": "receipt|chat_screenshot|lease|notice|invoice|photo_damage|other|unknown",
  "summary": "string",
  "structured_claims": {
    "parties": [
      { "name": "string", "role": "tenant|landlord|property_manager|maintenance|other|unknown", "confidence": 0.0, "citations": [] }
    ],
    "dates": [
      { "date": "YYYY-MM-DD|unknown", "context": "string", "confidence": 0.0, "citations": [] }
    ],
    "amounts": [
      { "amount": "number|unknown", "currency": "USD|unknown", "context": "string", "confidence": 0.0, "citations": [] }
    ],
    "addresses": [
      { "address": "string|unknown", "context": "string", "confidence": 0.0, "citations": [] }
    ],
    "identifiers": [
      { "id_type": "invoice|account|lease|case|other|unknown", "value_masked": "string|unknown", "confidence": 0.0, "citations": [] }
    ],
    "deadlines": [
      { "date": "YYYY-MM-DD|unknown", "context": "string", "confidence": 0.0, "citations": [] }
    ],
    "key_quotes": [
      { "text": "string", "confidence": 0.0, "citations": [] }
    ]
  },
  "sensitivity_flags": {
    "contains_ssn": false,
    "contains_account_number": false,
    "contains_health_info": false,
    "contains_minor_info": false,
    "contains_other_high_risk": false
  },
  "verification_state": "needs_review|high_confidence",
  "confidence": 0.0,
  "needs_review_notes": [
    { "issue": "string", "citations": [] }
  ]
}
```

---

## 4) Multimodal Extraction — PDFs (native + scanned)
Same as images, but citations include `page`.  
Requirement: `artifact_region` citations must include `"page": <int>`.

---

## 5) Multimodal Extraction — Audio (voice notes, voicemails)

### 5.1 System message
You are an evidence extraction engine. Produce a transcript with timestamps and extract landlord–tenant-relevant events. Do not infer.

### 5.2 Output schema
```json
{
  "artifact_id": "art_audio_1",
  "transcript": [
    { "start_ms": 0, "end_ms": 4200, "text": "string", "confidence": 0.0 }
  ],
  "key_moments": [
    {
      "title": "string",
      "start_ms": 12000,
      "end_ms": 18500,
      "summary": "string",
      "confidence": 0.0,
      "citations": [
        { "citation_type": "artifact_time", "artifact_id": "art_audio_1", "time_range": { "start_ms": 12000, "end_ms": 18500 } }
      ]
    }
  ],
  "structured_claims": {
    "dates_mentioned": [
      { "date": "YYYY-MM-DD|unknown", "context": "string", "confidence": 0.0, "citations": [] }
    ],
    "addresses_mentioned": [
      { "address": "string|unknown", "context": "string", "confidence": 0.0, "citations": [] }
    ],
    "repair_issues": [
      { "issue": "mold|leak|pests|heat|lock|other|unknown", "details": "string", "confidence": 0.0, "citations": [] }
    ]
  },
  "sensitivity_flags": { "contains_ssn": false, "contains_account_number": false, "contains_health_info": false, "contains_minor_info": false, "contains_other_high_risk": false },
  "verification_state": "needs_review|high_confidence",
  "confidence": 0.0,
  "needs_review_notes": [ { "issue": "string", "citations": [] } ]
}
```

---

## 6) Multimodal Extraction — Video (key moments + clips)

### 6.1 System message
You are an evidence extraction engine. Identify key moments relevant to landlord–tenant matters (damage, unsafe conditions, notices on doors, etc.). Provide timestamps. Do not infer unseen facts.

### 6.2 Output schema
```json
{
  "artifact_id": "art_video_1",
  "overall_summary": "string",
  "key_moments": [
    {
      "title": "string",
      "start_ms": 10000,
      "end_ms": 16000,
      "summary": "string",
      "confidence": 0.0,
      "citations": [
        { "citation_type": "artifact_time", "artifact_id": "art_video_1", "time_range": { "start_ms": 10000, "end_ms": 16000 } }
      ],
      "clip_suggestion": { "start_ms": 9000, "end_ms": 17000 }
    }
  ],
  "visible_text_claims": [
    { "text": "string", "confidence": 0.0, "citations": [] }
  ],
  "sensitivity_flags": { "contains_ssn": false, "contains_account_number": false, "contains_health_info": false, "contains_minor_info": false, "contains_other_high_risk": false },
  "verification_state": "needs_review|high_confidence",
  "confidence": 0.0,
  "needs_review_notes": [ { "issue": "string", "citations": [] } ]
}
```

Implementation note: the video service generates clips from `clip_suggestion` ranges and stores them as derived artifacts linked to the parent.

---

# ORGANIZATION & “CASE MEMORY” PROMPTS

## 7) Categorization + relevance scoring (Records + Artifacts + Extractions)

### 7.1 System message
You are a classification engine for landlord–tenant case intake. Categorize items and assign relevance. Only use provided content. Provide citations to the item itself.

### 7.2 Output schema
```json
{
  "item_type": "record|artifact",
  "item_id": "rec_123|art_456",
  "category": "lease_notices|communications|payments_receipts|condition_evidence|court_dates|witnesses|other|unknown",
  "subtype": "string",
  "relevance_score": 0.0,
  "suggested_tags": ["string"],
  "sensitivity_flags": { "contains_ssn": false, "contains_account_number": false, "contains_health_info": false, "contains_minor_info": false, "contains_other_high_risk": false },
  "verification_state": "needs_review|high_confidence",
  "confidence": 0.0,
  "citations": [
    { "citation_type": "record", "record_id": "rec_123" }
  ],
  "rationale_short": "string"
}
```

---

## 8) Entity extraction (parties, addresses, units, organizations)
```json
{
  "matter_id": "mat_1",
  "entities": [
    {
      "entity_type": "person|organization|address|unit|phone|email|other",
      "value": "string|unknown",
      "role_hint": "tenant|landlord|property_manager|witness|other|unknown",
      "confidence": 0.0,
      "citations": []
    }
  ]
}
```

---

## 9) Timeline event synthesis (cited, deduped, landlord–tenant oriented)

### 9.1 System message
Create a landlord–tenant timeline from the provided items. Each event must cite at least one record or artifact region/time. Do not invent dates. If date is unknown, create an event without a date and flag needs_review.

### 9.2 Output schema
```json
{
  "matter_id": "mat_1",
  "timeline_events": [
    {
      "event_id": "evt_001",
      "event_type": "lease_signed|notice_received|repair_requested|repair_completed|rent_paid|inspection|communication|damage_documented|court_date|other|unknown",
      "title": "string",
      "event_ts": "YYYY-MM-DDTHH:MM:SSZ|unknown",
      "actors": ["string"],
      "location": "string|unknown",
      "summary": "string",
      "confidence": 0.0,
      "verification_state": "needs_review|high_confidence",
      "citations": [],
      "related_item_ids": ["rec_123", "art_456"],
      "dedupe_key": "string"
    }
  ],
  "needs_review_notes": [
    { "issue": "string", "citations": [] }
  ]
}
```

---

## 10) Missing-items detection + structured request generation
```json
{
  "matter_id": "mat_1",
  "missing_items": [
    {
      "missing_type": "lease_copy|notice_to_vacate|repair_request_proof|repair_invoice|rent_receipt|photos_video|inspection_report|court_notice|other|unknown",
      "why_needed": "string",
      "evidence_we_saw_referencing_it": [
        { "reference": "string", "citations": [] }
      ],
      "priority": "low|medium|high",
      "suggested_request": {
        "title": "string",
        "description": "string",
        "accepted_types": ["pdf","image","video","audio","zip","csv"],
        "due_date_suggestion": "YYYY-MM-DD|unknown"
      },
      "confidence": 0.0,
      "verification_state": "needs_review|high_confidence"
    }
  ]
}
```

---

## 11) Intake Summary drafting (AI-assisted, no legal conclusions)

### 11.1 System message
Draft a neutral intake summary for a landlord–tenant matter. Do not give legal advice. Only include claims with citations. Clearly separate “Verified” vs “Model-suggested / Needs review.”

### 11.2 Output schema
```json
{
  "matter_id": "mat_1",
  "summary_sections": {
    "case_overview": { "text": "string", "citations": [] },
    "key_timeline": [
      { "bullet": "string", "verification_state": "verified|high_confidence|needs_review", "citations": [] }
    ],
    "evidence_index_highlights": [
      { "item": "string", "category": "string", "citations": [] }
    ],
    "open_questions": [
      { "question": "string", "why": "string", "citations": [] }
    ],
    "sensitivity_notes": [
      { "note": "string", "citations": [] }
    ]
  },
  "confidence": 0.0
}
```

---

# EDITS & CONFIRMATION PROMPTS

## 12) Lawyer edit proposal assistant (propose, not finalize)
```json
{
  "proposal": {
    "target_type": "timeline_event|item_category",
    "target_id": "evt_001|rec_123|art_456",
    "proposed_change": { "field": "string", "from": "string", "to": "string" },
    "reason": "string",
    "citations": [],
    "requires_owner_confirmations": ["usr_clientA"]
  }
}
```

## 13) Client confirmation prompt generator
```json
{
  "confirmation_request": {
    "title": "Confirm proposed change",
    "message": "string",
    "options": ["approve","reject","edit"],
    "citations": []
  }
}
```

---

# SENSITIVITY & CONSENT GATING PROMPTS

## 14) Sensitive item approval prompt (included-by-default but must confirm)
```json
{
  "sensitive_prompt": {
    "item_type": "record|artifact",
    "item_id": "rec_123|art_456",
    "detected_risk": ["account_number","ssn","health_info","minor_info","other_high_risk"],
    "message": "string",
    "recommended_default": "include_pending_confirmation",
    "actions": ["approve_include","exclude","redact_before_sharing"],
    "citations": []
  }
}
```

---

# QUALITY CONTROL PROMPTS

## 15) Consistency checker (optional)
```json
{
  "matter_id": "mat_1",
  "issues": [
    {
      "issue_type": "contradiction|duplicate|ambiguous_party|missing_date|other",
      "description": "string",
      "severity": "low|medium|high",
      "citations": [],
      "recommended_action": "string"
    }
  ]
}
```

---

# IMPLEMENTATION NOTES (how to run this safely)

## A) Routing rules (cheap → expensive)
1) Parse deterministically where possible (exports, metadata).
2) Multimodal extraction for artifacts (image/pdf/audio/video).
3) Categorization + entity extraction.
4) Timeline synthesis.
5) Missing-items.
6) Intake summary.

## B) Confidence thresholds (suggested)
- `>= 0.85`: `high_confidence`
- `0.60–0.85`: `needs_review` unless multiple corroborating citations
- `< 0.60`: `needs_review` always

## C) Citation enforcement
Reject any model output that:
- contains a claim with empty `citations`
- provides a date/amount with `confidence < 0.60` without `needs_review`

## D) “Verified” transitions
Only set `verification_state="verified"` when a human confirms via UI.
