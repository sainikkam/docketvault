from celery import Celery

from app.config import Settings

settings = Settings()
celery_app = Celery("docketvault", broker=settings.REDIS_URL)
celery_app.autodiscover_tasks(["app.extraction"])
