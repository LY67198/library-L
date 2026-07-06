"""Celery 应用实例 + Beat 调度配置"""

from __future__ import annotations

import sys
from pathlib import Path

from celery import Celery
from celery.schedules import crontab

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from backend.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "library",
    broker=settings.redis_url,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "release-expired-slots": {
        "task": "tasks.cleanup.release_expired_slots",
        "schedule": crontab(minute="*/5"),
    },
}
