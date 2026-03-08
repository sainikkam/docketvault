# DocketVault

Consent-Aware Legal Intake Vault — Track 1: Memory Infrastructure

## Quick Start (Local Dev)

```bash
brew install postgresql@15 python@3.11
brew services start postgresql@15
createdb docketvault

cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp ../.env.example .env
# Edit .env as needed

make migrate
make dev
# http://localhost:8000/health → {"status": "ok"}
```

## Commands

```bash
make dev            # Start dev server
make migrate        # Run Alembic migrations
make test           # Run pytest
make lint           # Ruff check + format check
make format         # Auto-format with ruff
```
