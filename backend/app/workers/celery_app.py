import os

from celery import Celery

from app.core.config import settings

if settings.hf_endpoint.strip():
    os.environ["HF_ENDPOINT"] = settings.hf_endpoint
else:
    os.environ.pop("HF_ENDPOINT", None)
if settings.hf_home.strip():
    os.environ["HF_HOME"] = settings.hf_home
os.environ["MINERU_MODEL_SOURCE"] = settings.mineru_model_source

_LOCAL = "localhost,127.0.0.1,::1"
for _k in ("NO_PROXY", "no_proxy"):
    _existing = os.environ.get(_k, "")
    if _LOCAL not in _existing:
        os.environ[_k] = f"{_LOCAL},{_existing}".strip(",")

celery_app = Celery(
    "georag",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    timezone="Asia/Shanghai",
    enable_utc=False,
)
