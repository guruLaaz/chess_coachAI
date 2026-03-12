"""Celery application for Chess CoachAI background analysis."""

import logging
from celery import Celery
from celery.signals import worker_ready
from config import REDIS_URL

logger = logging.getLogger(__name__)

app = Celery("chesscoach", broker=REDIS_URL, backend=REDIS_URL)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # one task at a time (CPU-bound)
)

app.autodiscover_tasks(["worker"])


@worker_ready.connect
def cleanup_orphaned_jobs(**kwargs):
    """Mark any in-progress jobs as failed on worker startup.

    If the worker crashed or restarted mid-task, those jobs will never complete.
    """
    try:
        import db.queries as dbq
        from db.connection import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE analysis_jobs SET status='failed', "
                    "error_message='Worker restarted — please retry' "
                    "WHERE status IN ('pending', 'fetching', 'analyzing')"
                )
                count = cur.rowcount
            conn.commit()
        if count:
            logger.info("Cleaned up %d orphaned job(s) on startup", count)
    except Exception as e:
        logger.warning("Failed to clean up orphaned jobs: %s", e)
