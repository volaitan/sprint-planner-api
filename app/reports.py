"""Burndown and velocity calculations, kept free of HTTP concerns so they're easy to test."""
from __future__ import annotations

from datetime import date, timedelta

from .models import Sprint, SprintStatus, StoryStatus


def sprint_points(sprint: Sprint) -> tuple[int, int]:
    committed = sum(s.points for s in sprint.stories)
    completed = sum(s.points for s in sprint.stories if s.status == StoryStatus.done)
    return committed, completed


def burndown(sprint: Sprint, today: date) -> list[dict]:
    """Remaining points at the end of each sprint day, plus a straight 'ideal' line.

    A story counts as burned down on the day it was completed. Days after today have no
    actual value yet.
    """
    committed, _ = sprint_points(sprint)
    total_days = (sprint.end_date - sprint.start_date).days
    days = []
    for offset in range(total_days + 1):
        day = sprint.start_date + timedelta(days=offset)
        ideal = committed * (1 - offset / total_days) if total_days else 0.0
        if day > today and sprint.status != SprintStatus.completed:
            remaining = None
        else:
            done = sum(s.points for s in sprint.stories if s.completed_on is not None and s.completed_on <= day)
            remaining = committed - done
        days.append({"date": day, "ideal": round(ideal, 2), "remaining": remaining})
    return days


def velocity(sprints: list[Sprint], window: int = 3) -> dict:
    """Completed points per finished sprint; the forecast is the average of the last `window`."""
    finished = sorted((s for s in sprints if s.status == SprintStatus.completed), key=lambda s: s.end_date)
    rows = []
    for s in finished:
        committed, completed = sprint_points(s)
        rows.append({"sprint_id": s.id, "name": s.name, "committed": committed, "completed": completed})
    recent = [r["completed"] for r in rows[-window:]]
    avg = round(sum(r["completed"] for r in rows) / len(rows), 1) if rows else 0.0
    forecast = round(sum(recent) / len(recent), 1) if recent else 0.0
    return {"sprints": rows, "average": avg, "forecast_next": forecast}
