from celery import Celery

from medgraph_api.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "medgraph_api",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    task_track_started=True,
    task_acks_late=True,
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["medgraph_api.tasks"])
