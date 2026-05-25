import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

import carbon
from database import get_conn

log = logging.getLogger(__name__)
_scheduler = BackgroundScheduler()


def _execute(task: dict):
    log.info("running task %s", task["id"])
    try:
        raw = carbon.get_current_intensity()
        actual = raw.get("actual") or raw.get("forecast")
    except Exception:
        actual = None

    ran_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status='done', ran_at=?, actual_gco2=? WHERE id=?",
            (ran_at, actual, task["id"]),
        )
    log.info("task %s done — actual carbon: %s gCO2/kWh", task["id"], actual)


def poll():
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        due = conn.execute(
            "SELECT * FROM tasks WHERE status='queued' AND scheduled_for <= ?", (now,)
        ).fetchall()
        overdue = conn.execute(
            "SELECT * FROM tasks WHERE status='queued' AND deadline < ?", (now,)
        ).fetchall()

    seen = set()
    for row in list(due) + list(overdue):
        t = dict(row)
        if t["id"] not in seen:
            seen.add(t["id"])
            _execute(t)


def start_scheduler():
    _scheduler.add_job(poll, "interval", seconds=60, id="poll", max_instances=1)
    _scheduler.start()


def stop_scheduler():
    _scheduler.shutdown(wait=False)
