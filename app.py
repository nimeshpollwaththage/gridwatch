import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

import carbon
from database import get_conn, init_db
from scheduler import start_scheduler, stop_scheduler

load_dotenv()

_API_KEY = os.environ.get("GRIDWATCH_API_KEY", "dev-key")
_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

if _API_KEY == "dev-key":
    import logging
    logging.warning("GRIDWATCH_API_KEY is not set — using insecure default")


def _auth(key: str = Security(_key_header)):
    if key != _API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return key


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="GridWatch", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")


class TaskIn(BaseModel):
    description: str
    deadline: str
    urgency_override: bool = False

    @field_validator("description")
    @classmethod
    def _desc(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 500:
            raise ValueError("description must be 1-500 characters")
        return v

    @field_validator("deadline")
    @classmethod
    def _dl(cls, v: str) -> str:
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("deadline must be ISO 8601")
        if dt <= datetime.now(timezone.utc):
            raise ValueError("deadline must be in the future")
        return v


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/carbon")
def current_carbon(_: str = Depends(_auth)):
    try:
        intensity = carbon.get_current_intensity()
        forecast = carbon.get_forecast()[:16]
        return {"current": intensity, "forecast": forecast}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/tasks", status_code=201)
def create_task(req: TaskIn, _: str = Depends(_auth)):
    with get_conn() as conn:
        queued = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='queued'"
        ).fetchone()[0]
    if queued >= 100:
        raise HTTPException(status_code=429, detail="Queue limit reached")

    deadline_dt = datetime.fromisoformat(req.deadline.replace("Z", "+00:00"))
    task_id = str(uuid.uuid4())[:8]
    scheduled_for = None
    forecast_gco2 = None

    if req.urgency_override:
        scheduled_for = datetime.now(timezone.utc).isoformat()
    else:
        try:
            window, gco2 = carbon.best_window_before(deadline_dt)
            if window:
                scheduled_for = window.isoformat()
                forecast_gco2 = gco2
        except Exception:
            pass

        if not scheduled_for:
            scheduled_for = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO tasks
               (id, description, deadline, urgency, scheduled_for, forecast_gco2)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (task_id, req.description, req.deadline,
             int(req.urgency_override), scheduled_for, forecast_gco2),
        )

    deferred = not req.urgency_override and forecast_gco2 is not None
    return {
        "id": task_id,
        "scheduled_for": scheduled_for,
        "forecast_gco2": forecast_gco2,
        "deferred": deferred,
        "message": (
            f"Scheduled for optimal window ({forecast_gco2} gCO2/kWh)"
            if deferred else "Running immediately"
        ),
    }


@app.get("/tasks")
def list_tasks(_: str = Depends(_auth)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/tasks/{task_id}")
def get_task(task_id: str, _: str = Depends(_auth)):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return dict(row)


@app.get("/stats")
def stats(_: str = Depends(_auth)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT forecast_gco2, actual_gco2 FROM tasks WHERE status='done'"
        ).fetchall()

    saved_g = 0.0
    deferred = 0
    kwh_per_task = 0.01
    baseline = 300.0

    for r in rows:
        if r["forecast_gco2"] is not None:
            deferred += 1
        if r["actual_gco2"]:
            gain = (baseline - r["actual_gco2"]) * kwh_per_task
            if gain > 0:
                saved_g += gain

    return {
        "total_tasks": len(rows),
        "tasks_deferred": deferred,
        "total_co2_saved_grams": round(saved_g, 1),
    }
