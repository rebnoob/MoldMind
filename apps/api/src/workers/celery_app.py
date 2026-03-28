from celery import Celery

from ..core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "moldmind",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minute hard limit
    task_soft_time_limit=300,  # 5 minute soft limit
    worker_prefetch_multiplier=1,  # One task at a time per worker (heavy compute)
)
