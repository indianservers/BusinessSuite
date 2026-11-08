"""Deterministic, bounded project-only resource leveling (not a global optimizer)."""
import bisect
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from fastapi import HTTPException

TERMINAL = {"Done", "Completed", "Cancelled", "Canceled", "Closed"}


def resource_inputs(db, project, tasks, calendar, moved, actor):
    from .management import effective_capacity
    if len(tasks) > 200:
        raise HTTPException(422, "Resource leveling supports up to 200 tasks")
    starts = [moved.start_date if moved.task_id == t.id else t.start_date for t in tasks]
    if not starts or not all(starts):
        raise HTTPException(422, "Date every task before resource leveling")
    anchor = min(starts)
    end = anchor + timedelta(days=365)
    people = sorted({uid for t in tasks for uid in t.assignee_user_ids})
    if len(people) > 50:
        raise HTTPException(422, "Resource leveling supports up to 50 assignees")
    capacities = {}
    for uid in people:
        from .people_management import scoped_person
        person = scoped_person(db, actor, uid)
        if not person or not person.is_active:
            raise HTTPException(422, "Resolve unavailable task assignees before leveling")
        result = effective_capacity(db, person, anchor, end, project.organization_id)
        capacities[uid] = {d["date"].isoformat(): max(0, float(d["hours"])) for d in result["days"]}
    inputs = {"capacity": capacities, "tasks": [[t.id, t.assignee_user_ids, str(t.remaining_estimate_hours), str(t.estimated_hours), str(t.actual_hours)] for t in tasks]}
    return capacities, hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def level(tasks, deps, calendar, moved, capacities, dependency_plan):
    if not dependency_plan["complete"]:
        raise HTTPException(422, "Date every task and resolve incomplete dependencies before leveling")
    anchor = min(date.fromisoformat(t["start_date"]) for t in dependency_plan["tasks"])
    if any(date.fromisoformat(r["due_date"]) > anchor + timedelta(days=365) for r in dependency_plan["tasks"]):
        raise HTTPException(422, "All task dates must fit within the 366-day leveling horizon")
    holidays = set(calendar.holidays)
    days = [anchor + timedelta(days=i) for i in range(366) if (anchor + timedelta(days=i)).year <= 2200 and (anchor + timedelta(days=i)).weekday() in calendar.weekdays and anchor + timedelta(days=i) not in holidays]
    lookup = {t.id: t for t in tasks}
    incoming = defaultdict(list)
    for d in deps:
        incoming[d.task_id].append(d)
    pending = {t.id for t in tasks}
    done = {}; used = defaultdict(float); allocations = []
    minimum = {t["id"]: t for t in dependency_plan["tasks"]}
    while pending:
        ready = [tid for tid in pending if all(d.depends_on_task_id in done for d in incoming[tid])]
        if not ready:
            raise HTTPException(409, "Dependency cycle detected")
        tid = min(ready, key=lambda i: (minimum[i]["start_date"], i))
        task = lookup[tid]; row = minimum[tid]; crew = task.assignee_user_ids
        earliest = bisect.bisect_left(days, date.fromisoformat(row["start_date"]))
        finish_floor = bisect.bisect_left(days, date.fromisoformat(row["due_date"]))
        for dep in incoming[tid]:
            first, last = done[dep.depends_on_task_id]; lag = dep.lag_days or 0
            if dep.dependency_type == "Finish To Start": earliest = max(earliest, last + 1 + lag)
            elif dep.dependency_type == "Start To Start": earliest = max(earliest, first + lag)
            elif dep.dependency_type == "Finish To Finish": finish_floor = max(finish_floor, last + lag)
            else: finish_floor = max(finish_floor, first + lag)
        if task.status in TERMINAL:
            first = bisect.bisect_left(days, task.start_date); last = bisect.bisect_left(days, task.due_date)
            if earliest > first or finish_floor > last:
                raise HTTPException(409, "Resource plan would move a completed/cancelled task")
            done[tid] = (first, last); pending.remove(tid); continue
        effort = float(task.remaining_estimate_hours) if task.remaining_estimate_hours is not None else max(0, float(task.estimated_hours or 0) - float(task.actual_hours or 0))
        if not crew or effort <= 0:
            raise HTTPException(422, "Every open task needs assignees and a positive remaining or unspent estimate for leveling")
        # Equal effort per assignee; each person's allocation remains within daily capacity.
        remaining = {uid: effort / len(crew) for uid in crew}; first = None; last = None
        for index in range(max(0, earliest), len(days)):
            day = days[index].isoformat()
            for uid in crew:
                hours = min(remaining[uid], max(0, capacities[uid].get(day, 0) - used[uid, day]))
                if hours > 0.000001:
                    used[uid, day] += hours; remaining[uid] -= hours
                    allocations.append({"task_id": tid, "user_id": uid, "date": day, "hours": round(hours, 4)})
                    first = index if first is None else first; last = index
            if all(v <= 0.000001 for v in remaining.values()): break
        if first is None or any(v > 0.000001 for v in remaining.values()) or finish_floor >= len(days):
            raise HTTPException(422, "Insufficient capacity within the 366-day leveling horizon")
        done[tid] = (first, max(last, finish_floor)); pending.remove(tid)
    rows = []; changes = []
    for task in tasks:
        first, last = done[task.id]
        row = {**minimum[task.id], "start_date": days[first].isoformat(), "due_date": days[last].isoformat(), "duration_workdays": last-first+1, "slack_workdays": None}
        rows.append(row)
        if (row["start_date"], row["due_date"]) != (str(task.start_date), str(task.due_date)):
            changes.append({**row, "old_start_date": str(task.start_date), "old_due_date": str(task.due_date)})
    return {**dependency_plan, "tasks": rows, "changes": changes, "critical_task_ids": [], "finish_date": max(r["due_date"] for r in rows), "resource_allocations": allocations,
            "basis": "Project-only leveling; equal effort per assignee; working hours, dated capacity, applicable holidays and approved leave. Other projects are not reserved. Slack is unavailable for resource-constrained plans."}
