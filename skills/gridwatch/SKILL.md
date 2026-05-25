---
name: gridwatch
version: 1.0.0
description: Defers non-urgent AI tasks to the lowest-carbon window on the UK National Grid.
triggers:
  - pattern: "by (tomorrow|tonight|Monday|Tuesday|Wednesday|Thursday|Friday|\\d+(am|pm)|end of day|this week)"
    confidence: 0.75
  - pattern: "(now|urgent|asap|immediately)"
    confidence: 0.9
endpoint: http://localhost:8000
---

## What this skill does

GridWatch intercepts task requests with a deadline and schedules them to run at the lowest-carbon 30-minute window before that deadline.

## Rules

- Extract the deadline from the user message and convert to ISO 8601.
- If urgency keywords are present, set urgency_override: true.
- Call POST /tasks with description, deadline, urgency_override and header X-API-Key.
- Always report the carbon receipt to the user.
- If the scheduler is unreachable, tell the user and proceed without deferral.

## Carbon receipt format

Deferred:
> Scheduled for [time] (forecast: [X] gCO₂/kWh). I'll notify you when it completes.

Immediate:
> Running now. Current grid intensity: [X] gCO₂/kWh.
