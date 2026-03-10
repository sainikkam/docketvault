# DocketVault

**Consent-Aware Legal Intake Vault** — Turn scattered personal data into lawyer-ready evidence packs, with full client control over what gets shared.

DocketVault is a permissioned data pipeline and secure vault built for legal intake. Clients upload evidence (documents, images, audio), AI extracts and organizes it into a structured timeline, and attorneys receive a complete evidence pack — only after the client explicitly approves sharing.

---

## Key Features

- **Client-private vault** — uploads are private by default; attorneys see nothing until the client approves
- **AI-powered extraction** — Claude analyzes images/PDFs, Whisper transcribes audio, structured data is extracted automatically
- **Timeline & categorization** — events are placed on a timeline with categories, summaries, and gap detection
- **Consent-gated sharing** — clients preview, approve/exclude, and can revoke access at any time
- **Evidence Pack export** — attorneys export a ZIP with summaries, indexes, files, hashes, and audit trails
- **Append-only audit log** — every view, share, export, and revoke is recorded

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend API** | FastAPI, SQLModel, PostgreSQL, Alembic |
| **Async Workers** | Celery + Redis |
| **AI / LLM** | Anthropic Claude (extraction & enrichment), OpenAI Whisper (audio) |
| **Frontend** | Streamlit |
| **Auth** | JWT + bcrypt, Google OAuth (Drive/Gmail/Calendar) |
| **Storage** | Local filesystem (dev) or S3-compatible (prod) |

---

## Prerequisites

- **Python 3.10+**
- **PostgreSQL 15+** — `brew install postgresql@15`
- **Redis** — `brew install redis && brew services start redis`
- **API Keys** (optional for basic demo):
  - `ANTHROPIC_API_KEY` — Claude-powered extraction & enrichment
  - `OPENAI_API_KEY` — Whisper audio transcription

---

## Quick Start

### 1. Clone & set up the database

```bash
git clone https://github.com/sainikkam/docketvault.git
cd docketvault

brew services start postgresql@15
createdb docketvault
```

### 2. Install backend dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp ../.env.example .env
```

Edit `backend/.env` with your values:

```env
DATABASE_URL=postgresql+asyncpg://<your-user>@localhost:5432/docketvault
STORAGE_BACKEND=local
JWT_SECRET=change-me-in-production
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
REDIS_URL=redis://localhost:6379/0
```

### 4. Run database migrations

```bash
make migrate
```

### 5. Launch (3 terminals)

**Terminal 1 — FastAPI backend:**

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Celery worker (AI extraction):**

```bash
cd backend
source .venv/bin/activate
celery -A app.worker worker --loglevel=info
```

**Terminal 3 — Streamlit frontend:**

```bash
cd streamlit
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

Open **http://localhost:8501** in your browser.

---

## Docker (Optional)

For PostgreSQL and Redis only (the app itself runs locally):

```bash
docker compose up -d
```

---

## Project Structure

```
docketvault/
├── backend/
│   ├── app/
│   │   ├── auth/           # JWT auth, user registration, roles
│   │   ├── matters/        # Legal matters (cases) CRUD
│   │   ├── firms/          # Law firm management
│   │   ├── evidence/       # Evidence artifact storage
│   │   ├── extraction/     # AI extraction (Claude + Whisper)
│   │   ├── enrichment/     # Timeline, categorization, gap analysis
│   │   ├── sharing/        # Consent-gated sharing & revocation
│   │   ├── exports/        # Evidence Pack ZIP generation
│   │   ├── notifications/  # In-app notifications
│   │   ├── oauth/          # Google OAuth connectors
│   │   ├── gmail/          # Gmail import
│   │   ├── main.py         # FastAPI app entry point
│   │   ├── worker.py       # Celery worker config
│   │   └── config.py       # App settings
│   ├── requirements.txt
│   └── Makefile
├── streamlit/
│   ├── streamlit_app.py    # Main app & navigation
│   ├── pages/              # One file per page (login, upload, review, etc.)
│   └── lib/                # Shared helpers (API client, session, theme)
├── persona_p01/            # Sample persona data for testing
├── demo/                   # Demo RFP / scenario files
├── docker-compose.yml      # PostgreSQL + Redis containers
└── .env.example            # Template for backend/.env
```

---

## Demo Walkthrough

1. **Register** an attorney account and a client account
2. **Attorney** creates a firm, template, and matter, then sets up evidence requests with AI-generated checklists
3. **Attorney** generates an invitation token and shares it with the client
4. **Client** joins the matter using the token
5. **Client** uploads evidence (images, PDFs, audio) — AI extraction runs automatically in the background
6. **Client** reviews the AI-generated timeline, extracted data, and missing items
7. **Client** approves sharing (with per-item control and sensitivity flags)
8. **Attorney** views the dashboard, browses approved evidence, and exports the Evidence Pack

See [LAUNCH_GUIDE.md](LAUNCH_GUIDE.md) for the full step-by-step walkthrough.

---

## Makefile Commands

```bash
make dev        # Start FastAPI dev server
make migrate    # Run Alembic migrations
make test       # Run pytest
make lint       # Ruff check + format check
make format     # Auto-format with ruff
```

---

## API Documentation

FastAPI auto-generates interactive docs at **http://localhost:8000/docs** when the backend is running.

---

## License

All rights reserved.
