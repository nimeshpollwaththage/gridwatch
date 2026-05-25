# GridWatch

Carbon-aware AI workload scheduler for OpenClaw — runs your agent tasks when the UK grid is cleanest.

**Live demo:** http://136.113.34.44:8000/static/index.html?key=gridwatch2026

**API docs:** http://136.113.34.44:8000/docs

---

## The problem

UK grid carbon intensity varies by up to **10x in a single day** — from ~30 gCO2/kWh during high wind periods to over 300 gCO2/kWh in winter peaks. AI agents generate real electricity load, but they fire the moment you trigger them with no awareness of what the grid is doing.

Most tasks don't need to run right now. A research summary by Tuesday, a report draft before end of day, a batch of PDFs overnight — all have slack. GridWatch intercepts those requests, checks the National Grid ESO 48-hour carbon forecast, and defers execution to the lowest-carbon window before the deadline.

---

## How it works

    User → OpenClaw skill → POST /tasks
                                 |
                   Carbon Intensity API (48h forecast)
                                 |
                       greedy window picker
                                 |
                        SQLite task queue
                                 |
                  scheduler poll (60s interval)
                                 |
                   task executes at optimal window
                                 |
                 carbon receipt returned to user

---

## Quickstart

    git clone https://github.com/nimeshpollwaththage/gridwatch
    cd gridwatch
    cp .env.example .env
    pip install -r requirements.txt
    uvicorn app:app --reload

Dashboard: http://localhost:8000/static/index.html?key=your-key

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Liveness check |
| GET | /carbon | Current intensity + 8h forecast |
| POST | /tasks | Schedule a task |
| GET | /tasks | List tasks |
| GET | /tasks/{id} | Task detail |
| GET | /stats | Cumulative CO2 saved |

All endpoints except /health require X-API-Key header.

Schedule a task:

    curl -X POST http://136.113.34.44:8000/tasks \
      -H "X-API-Key: gridwatch2026" \
      -H "Content-Type: application/json" \
      -d '{"description": "summarise these PDFs", "deadline": "2026-05-26T09:00:00Z"}'

---

## Design decisions

**Greedy window picker, not a constraint solver.** The 48-hour forecast has ~96 slots. A greedy minimum scan is O(n) and correct here. A solver would only help if the objective had multiple dimensions (cost, model choice, latency) — a natural extension, but premature.

**Graceful degradation when the carbon API is down.** The task runs immediately with a logged warning. Carbon-awareness is an optimisation, not a hard dependency. User work is never blocked.

**Hard deadline enforcement.** Every scheduler poll sweeps for tasks past their deadline and force-executes them. A task will never silently expire.

**Idempotent execution.** max_instances=1 on the poll job prevents a slow cycle stacking with the next. The state machine (queued to done) prevents double-execution after a crash and restart.

---

## Running tests

    pytest tests/ -v

---

## What is next

- Model-aware routing — prefer smaller, lower-energy models in high-carbon windows
- Multi-region — extend to European grid APIs for distributed workloads
- Carbon budget — monthly CO2 cap; pause non-essential agents when nearly exceeded
- DataVita National Cloud integration — carbon receipt endpoint for enterprise workload reporting

---

## Why this matters for DataVita

DataVita runs on 100% renewable energy. As AI inference workloads grow, the question of when those workloads run — not just where — becomes part of the sustainability story. GridWatch demonstrates that carbon-aware scheduling is practical at the personal-agent level today, and is a natural feature for DataVita to offer enterprise customers on their National Cloud.
