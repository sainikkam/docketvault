.PHONY: dev migrate new-migration test lint format worker

dev:
	uvicorn app.main:app --reload --port 8000

migrate:
	PYTHONPATH=. alembic upgrade head

new-migration:
	PYTHONPATH=. alembic revision --autogenerate -m "$(msg)"

test:
	pytest tests/ -v

lint:
	ruff check . && ruff format --check .

format:
	ruff format .

worker:
	PYTHONPATH=. celery -A app.worker worker --loglevel=info
