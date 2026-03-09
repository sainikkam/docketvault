# DocketVault — Launch, Demo & Usage Guide

## Prerequisites

- **PostgreSQL** running locally with a `docketvault` database
- **Redis** running locally (`brew services start redis`)
- **Python 3.10+**
- **API Keys** configured in `backend/.env`:
  - `ANTHROPIC_API_KEY` — required for Claude-powered extraction & enrichment
  - `OPENAI_API_KEY` — required for audio transcription (Whisper)
  - Both can be left empty to demo the app without AI features

---

## Launching the App

You need **3 terminal windows** (or tabs):

### Terminal 1: FastAPI Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Terminal 2: Celery Worker (AI extraction & enrichment)

```bash
cd backend
source .venv/bin/activate
celery -A app.worker worker --loglevel=info
```

### Terminal 3: Streamlit Frontend

```bash
cd streamlit
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

Then open **http://localhost:8501** in your browser.

---

## Demo Walkthrough

### 1. Register & Login (Page: Login)

- Register a **client** account (e.g., `client@test.com` / `password123`)
- Register an **attorney** account (e.g., `attorney@test.com` / `password123`, role = `attorney`)
- Log in as the **client** first

### 2. Upload Evidence (Page: Client Upload)

- Select your matter from the sidebar
- Upload files: images (JPG/PNG), PDFs, or audio files (MP3/WAV)
- Each upload triggers background AI extraction via Celery:
  - **Images/PDFs** — Claude analyzes content, extracts structured data
  - **Audio** — Whisper transcribes, Claude extracts key moments

### 3. Review AI Analysis (Page: Client Review)

- View the AI-generated **timeline** of events
- See **extracted evidence** with summaries and categories
- Check **missing items** the AI identified as gaps in your case
- Verify/confirm timeline events

### 4. Share with Attorney (Page: Client Share)

- Review the share preview — each artifact listed with sensitivity flags
- **Approve All** to share everything, or selectively approve/exclude
- Sensitive items require explicit acknowledgment before sharing
- **Revoke** button pulls back all sharing at any time

### 5. Switch to Attorney View

- Log out, log in as the **attorney**

### 6. Attorney Dashboard (Page: Lawyer Dashboard)

- See aggregated case overview: timeline, category breakdown, missing items
- Create **evidence requests** to ask the client for specific documents

### 7. Evidence Viewer (Page: Lawyer Evidence)

- Browse all client-approved artifacts
- View AI extractions: summaries, document types, audio transcripts, claims

### 8. Export Evidence Pack (Page: Lawyer Export)

- Generate a ZIP containing:
  - `intake_summary.json` — AI case summary
  - `evidence_index.csv` — full evidence index
  - `approved_records.jsonl` — structured data
  - `approved_artifacts/` — actual files
  - `hash_manifest.csv` — SHA-256 integrity hashes
  - `audit_excerpt.jsonl` — audit trail

### 9. Audit Log (Page: Audit Log)

- View the complete append-only audit trail
- Filter by action type

---

## API Documentation

FastAPI auto-generates interactive API docs at **http://localhost:8000/docs** — useful for testing endpoints directly.

---

## Database Setup

If you haven't created the database yet:

```bash
createdb docketvault
cd backend
source .venv/bin/activate
alembic upgrade head
```

## Environment Variables

Copy the example below into `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://<your-user>@localhost:5432/docketvault
STORAGE_BACKEND=local
JWT_SECRET=your-secret-key
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key
REDIS_URL=redis://localhost:6379/0
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```
