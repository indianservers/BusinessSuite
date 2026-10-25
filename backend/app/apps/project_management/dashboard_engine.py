"""Batched, permission-scoped dashboard analytics over approved ORM sources."""

import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import func
from .access import accessible_project_query
from .models import (
    PMSProject,
    PMSTask,
    PMSTimeLog,
    PMSActivity,
    PMSSprint,
    PMSMilestone,
    PMSRisk,
    PMSWorkspaceMember,
    PMSTaskTag,
    PMSWorkspaceTeam,
    PMSCustomField,
    PMSCustomFieldValue,
)
from app.models.user import User
from .dashboard_config import WIDGETS, Configuration, Filters

DONE = {"done", "completed", "closed", "resolved"}


def complete(status):
    return str(status or "").lower() in DONE


def day(value, zone="UTC"):
    if value is None:
        return None
    if isinstance(value, datetime):
        return (
            (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value)
            .astimezone(ZoneInfo(zone))
            .date()
        )
    return value


def numeric(value):
    try:
        result = float(value or 0)
        return result if math.isfinite(result) else 0
    except (ValueError, TypeError):
        return 0


class Engine:
    def __init__(self, db, user, workspace_id):
        self.db = db
        self.user = user
        self.workspace_id = workspace_id
        self.projects = (
            accessible_project_query(db, user)
            .filter(
                PMSProject.workspace_id == workspace_id, PMSProject.is_archived == False
            )
            .all()
        )
        self.project_names = {p.id: p.name for p in self.projects}
        self.ids = list(self.project_names)
        self.cache = {}
        self.filtered = {}
        member = (
            db.query(PMSWorkspaceMember)
            .filter_by(workspace_id=workspace_id, user_id=user.id)
            .first()
        )
        self.manages = bool(member and member.role in {"Owner", "Admin"})
        self.people = (
            dict(
                db.query(User.id, User.email)
                .join(PMSWorkspaceMember, PMSWorkspaceMember.user_id == User.id)
                .filter(PMSWorkspaceMember.workspace_id == workspace_id)
                .all()
            )
            if self.ids
            else {}
        )

    def load(self, source, project_ids=None):
        ids = (
            sorted(set(self.ids).intersection(project_ids))
            if project_ids is not None
            else self.ids
        )
        cache_key = (source, tuple(ids))
        if cache_key in self.cache:
            return self.cache[cache_key]
        if source == "projects":
            rows = [p for p in self.projects if p.id in ids]
        else:
            model = {
                "tasks": PMSTask,
                "time": PMSTimeLog,
                "activity": PMSActivity,
                "sprints": PMSSprint,
                "milestones": PMSMilestone,
                "risks": PMSRisk,
            }[source]
            query = self.db.query(model).filter(model.project_id.in_(ids))
            if hasattr(model, "deleted_at"):
                query = query.filter(model.deleted_at == None)
            if source == "time" and not self.manages:
                query = query.filter(model.user_id == self.user.id)
            if source == "activity":
                query = query.order_by(model.created_at.desc())
            rows = query.limit(10001).all() if ids else []
        if len(rows) > 10000:
            raise ValueError(
                "More than 10,000 visible source records. Select a smaller project scope before loading this widget."
            )
        self.cache[cache_key] = rows
        return rows

    def rows(self, source, filters):
        key = (source, filters.model_dump_json())
        if key in self.filtered:
            return self.filtered[key]
        project_ids = set(filters.project_ids) if filters.project_ids else set(self.ids)
        if filters.project_statuses:
            project_ids &= {
                p.id for p in self.projects if p.status in filters.project_statuses
            }
        rows = self.load(source, project_ids)
        if filters.assignee_ids:
            selected = set(filters.assignee_ids)
            rows = (
                [r for r in rows if selected.intersection(r.assignee_user_ids)]
                if source == "tasks"
                else [
                    r
                    for r in rows
                    if getattr(r, "user_id", getattr(r, "owner_user_id", None))
                    in selected
                ]
            )
        if filters.team_ids and source == "tasks":
            teams = (
                self.db.query(PMSWorkspaceTeam)
                .filter(
                    PMSWorkspaceTeam.workspace_id == self.workspace_id,
                    PMSWorkspaceTeam.id.in_(filters.team_ids),
                )
                .all()
            )
            ids = {
                ident
                for team in teams
                for ident in json.loads(team.member_ids_json or "[]")
            }
            rows = [r for r in rows if ids.intersection(r.assignee_user_ids)]
        if filters.statuses and source == "tasks":
            rows = [r for r in rows if getattr(r, "status", "") in filters.statuses]
        if filters.priorities and source == "tasks":
            rows = [r for r in rows if getattr(r, "priority", "") in filters.priorities]
        if filters.sprint_ids and source in {"tasks", "sprints"}:
            rows = [
                r
                for r in rows
                if (r.id if source == "sprints" else getattr(r, "sprint_id", None))
                in filters.sprint_ids
            ]
        if filters.tag_ids and source == "tasks":
            tagged = {
                r[0]
                for r in self.db.query(PMSTaskTag.task_id)
                .filter(PMSTaskTag.tag_id.in_(filters.tag_ids))
                .all()
            }
            rows = [r for r in rows if r.id in tagged]
        if filters.custom_field_id and source == "tasks":
            field = self.db.get(PMSCustomField, filters.custom_field_id)
            if not field or field.project_id not in self.ids:
                rows = []
            else:
                values = (
                    self.db.query(PMSCustomFieldValue)
                    .filter_by(field_id=field.id)
                    .all()
                )
                matching = {
                    v.task_id
                    for v in values
                    if str(json.loads(v.value_json)) == filters.custom_field_value
                }
                rows = [r for r in rows if r.id in matching]
        if filters.date_from or filters.date_to:
            date_field = "log_date" if source == "time" else filters.date_field
            rows = [
                r
                for r in rows
                if (d := day(getattr(r, date_field, None), filters.timezone))
                and (not filters.date_from or d >= filters.date_from)
                and (not filters.date_to or d <= filters.date_to)
            ]
        self.filtered[key] = rows
        return rows

    def metric(self, kind, filters, formula="completion_rate"):
        if kind == "formula":
            kind = formula
        today = datetime.now(ZoneInfo(filters.timezone)).date()
        if kind in {
            "total_projects",
            "active_projects",
            "completed_projects",
            "budget_utilization",
        }:
            projects = self.rows("projects", filters)
            if kind == "budget_utilization":
                if not self.manages:
                    return (
                        None,
                        "Budget metrics require workspace administration access.",
                    )
                budget = sum(numeric(p.budget_amount) for p in projects)
                cost = sum(numeric(p.actual_cost) for p in projects)
                return (
                    (round(cost / budget * 100, 2) if budget else None),
                    "Actual project cost / configured budget; no currency conversion is applied.",
                )
            return (
                len(
                    [
                        p
                        for p in projects
                        if kind == "total_projects"
                        or (
                            complete(p.status)
                            if kind == "completed_projects"
                            else not complete(p.status)
                        )
                    ]
                ),
                "Visible, non-archived projects.",
            )
        if kind == "actual_hours":
            return (
                round(
                    sum(r.duration_minutes for r in self.rows("time", filters)) / 60, 2
                ),
                "Recorded time logs; non-admins see their own time only.",
            )
        tasks = self.rows("tasks", filters)
        closed = [t for t in tasks if complete(t.status)]
        open_tasks = [t for t in tasks if not complete(t.status)]
        eligible = [t for t in closed if t.completed_at and t.created_at]
        if kind == "average_completion":
            return (
                (
                    round(
                        statistics.mean(
                            (
                                t.completed_at.replace(tzinfo=None)
                                - t.created_at.replace(tzinfo=None)
                            ).total_seconds()
                            / 86400
                            for t in eligible
                        ),
                        2,
                    )
                    if eligible
                    else None
                ),
                "Days from creation to recorded completion; tasks without completion timestamps are excluded.",
            )
        if kind == "completion_rate":
            return (
                round(len(closed) / len(tasks) * 100, 2) if tasks else None
            ), "Completed / visible tasks."
        if kind == "on_time_rate":
            eligible = [t for t in closed if t.completed_at and t.due_date]
            return (
                round(
                    sum(
                        day(t.completed_at, filters.timezone) <= t.due_date
                        for t in eligible
                    )
                    / len(eligible)
                    * 100,
                    2,
                )
                if eligible
                else None
            ), "Completed tasks with recorded completion and due dates only."
        if kind in {"estimated_hours", "remaining_hours"}:
            estimated = sum(numeric(t.estimated_hours) for t in tasks)
            return (
                round(
                    (
                        estimated
                        if kind == "estimated_hours"
                        else sum(
                            max(0, numeric(t.estimated_hours) - numeric(t.actual_hours))
                            for t in open_tasks
                        )
                    ),
                    2,
                ),
                "Task estimates; missing estimates contribute zero.",
            )
        selected = {
            "total_tasks": tasks,
            "open_tasks": open_tasks,
            "completed_tasks": closed,
            "overdue_tasks": [
                t for t in open_tasks if t.due_date and t.due_date < today
            ],
            "due_today": [t for t in open_tasks if t.due_date == today],
            "due_this_week": [
                t
                for t in open_tasks
                if t.due_date
                and today - timedelta(days=today.weekday())
                <= t.due_date
                <= today + timedelta(days=6 - today.weekday())
            ],
            "in_progress": [t for t in tasks if t.status == "In Progress"],
            "blocked_tasks": [
                t for t in tasks if t.status == "Blocked" or t.is_blocking
            ],
        }.get(kind, tasks)
        return len(selected), "Filtered records visible to this viewer."

    def task_rows(self, kind, filters):
        rows = self.rows("tasks", filters)
        today = datetime.now(ZoneInfo(filters.timezone)).date()
        if kind in {"task_list", "deadlines", "calendar"}:
            rows = [r for r in rows if not complete(r.status)]
        if kind == "my_tasks":
            rows = [r for r in rows if self.user.id in r.assignee_user_ids]
        if kind == "unassigned":
            rows = [r for r in rows if not r.assignee_user_ids]
        if kind == "recent_completed":
            rows = sorted(
                [r for r in rows if complete(r.status)],
                key=lambda r: str(r.completed_at or ""),
                reverse=True,
            )
        if kind == "overdue_list":
            rows = [
                r
                for r in rows
                if not complete(r.status) and r.due_date and r.due_date < today
            ]
        if kind in {"deadlines", "calendar"}:
            rows = sorted([r for r in rows if r.due_date], key=lambda r: r.due_date)
        return rows

    def payload(self, row, source):
        title = getattr(row, "title", getattr(row, "name", getattr(row, "summary", "")))
        result = {
            "id": row.id,
            "title": title,
            "status": getattr(row, "status", ""),
            "priority": getattr(row, "priority", ""),
            "due_date": str(getattr(row, "due_date", "") or ""),
            "project": self.project_names.get(getattr(row, "project_id", row.id), ""),
            "url": (
                f"/pms/projects/{row.id}"
                if source == "projects"
                else (
                    f"/pms/tasks/{row.id}"
                    if source == "tasks"
                    else f"/pms/projects/{row.project_id}"
                )
            ),
        }
        if source == "tasks":
            result.update(
                assignees=[
                    self.people.get(uid, "Workspace member")
                    for uid in row.assignee_user_ids
                ],
                estimated_hours=numeric(row.estimated_hours),
                created_at=str(row.created_at),
                completed_at=str(row.completed_at or ""),
            )
        if source == "projects":
            result.update(
                progress=numeric(row.progress_percent),
                health=row.health,
                start_date=str(row.start_date or ""),
                budget=numeric(row.budget_amount) if self.manages else None,
                actual_cost=numeric(row.actual_cost) if self.manages else None,
            )
        if source == "activity":
            result.update(
                actor=self.people.get(row.actor_user_id, "System"),
                created_at=str(row.created_at),
                task_id=row.task_id,
            )
        if source == "sprints":
            result.update(
                start_date=str(row.start_date),
                end_date=str(row.end_date),
                committed=row.committed_story_points,
                completed=row.completed_story_points,
            )
        if source == "time":
            result.update(
                title=row.description or "Recorded time",
                assignees=[self.people.get(row.user_id, "Workspace member")],
                hours=numeric(row.duration_minutes) / 60,
                log_date=str(row.log_date),
            )
        if source == "risks":
            result.update(score=row.risk_score)
        return result

    def aggregate(self, rows, widget, filters):
        groups = defaultdict(list)
        for row in rows:
            if widget.group_by == "project":
                labels = [
                    self.project_names.get(
                        row.id if widget.source == "projects" else row.project_id,
                        "Project",
                    )
                ]
            elif widget.group_by == "assignee":
                labels = [
                    self.people.get(uid, "Workspace member")
                    for uid in getattr(row, "assignee_user_ids", [])
                    or [getattr(row, "user_id", 0)]
                ]
                labels = [
                    "Unassigned" if label == "Workspace member" else label
                    for label in labels
                ]
            elif widget.group_by in {"day", "week", "month", "quarter", "year"}:
                value = day(
                    getattr(
                        row,
                        "log_date" if widget.source == "time" else filters.date_field,
                        None,
                    ),
                    filters.timezone,
                )
                if not value:
                    continue
                labels = [
                    (
                        str(value - timedelta(days=value.weekday()))
                        if widget.group_by == "week"
                        else (
                            value.strftime("%Y-%m")
                            if widget.group_by == "month"
                            else (
                                f"{value.year}-Q{(value.month-1)//3+1}"
                                if widget.group_by == "quarter"
                                else (
                                    str(value.year)
                                    if widget.group_by == "year"
                                    else str(value)
                                )
                            )
                        )
                    )
                ]
            else:
                labels = [
                    str(getattr(row, widget.group_by, "Unspecified") or "Unspecified")
                ]
            for label in labels:
                groups[label].append(row)
        output = []
        for label, items in groups.items():
            numbers = [
                (
                    numeric(getattr(r, widget.metric, None))
                    if widget.metric != "duration_hours"
                    else numeric(getattr(r, "duration_minutes", 0)) / 60
                )
                for r in items
            ]
            value = (
                len(items)
                if widget.aggregation == "count"
                else (
                    sum(numbers)
                    if widget.aggregation == "sum"
                    else (
                        statistics.mean(numbers)
                        if widget.aggregation == "average"
                        else (
                            min(numbers)
                            if widget.aggregation == "minimum"
                            else (
                                max(numbers)
                                if widget.aggregation == "maximum"
                                else (
                                    statistics.median(numbers)
                                    if widget.aggregation == "median"
                                    else (
                                        len(set(numbers))
                                        if widget.aggregation == "distinct_count"
                                        else len(items) / len(rows) * 100 if rows else 0
                                    )
                                )
                            )
                        )
                    )
                )
            )
            output.append(
                {
                    "name": label,
                    "value": round(value, 4),
                    "count": len(items),
                    "open": sum(not complete(getattr(r, "status", "")) for r in items),
                    "completed": sum(complete(getattr(r, "status", "")) for r in items),
                }
            )
        output.sort(
            key=(
                (lambda r: r["name"])
                if widget.sort == "name"
                else (lambda r: r["value"])
            ),
            reverse=widget.sort == "value_desc",
        )
        return output[: widget.limit]

    def widget(self, widget, global_filters):
        spec = WIDGETS[widget.type]
        filters = widget.filters or global_filters
        kind = widget.type
        if spec["requirement"]:
            return {"state": "unavailable", "message": spec["requirement"]}
        if kind in {"notes", "image", "bookmark"}:
            return {
                "state": "ready",
                "rows": [],
                "message": "User-provided content; dashboard filters do not apply.",
            }
        if (
            widget.metric in {"budget_amount", "actual_cost"}
            or kind == "project_budget"
        ) and not self.manages:
            return {
                "state": "unavailable",
                "message": "Budget data requires workspace administration access.",
            }
        result = {"state": "ready", "message": ""}
        if widget.drilldown:
            source = widget.source
            target = widget.formula if kind == "formula" else kind
            if spec["view"] == "metric":
                source = (
                    "projects"
                    if target
                    in {
                        "total_projects",
                        "active_projects",
                        "completed_projects",
                        "budget_utilization",
                    }
                    else "time" if target == "actual_hours" else "tasks"
                )
            rows = (
                self.task_rows(kind, filters)
                if source == "tasks"
                else self.rows(source, filters)
            )
            today = datetime.now(ZoneInfo(filters.timezone)).date()
            if target in {
                "completed_tasks",
                "completed_projects",
                "average_completion",
                "on_time_rate",
            }:
                rows = [r for r in rows if complete(r.status)]
            if target in {
                "open_tasks",
                "active_projects",
                "remaining_hours",
                "overdue_tasks",
                "due_today",
                "due_this_week",
            }:
                rows = [r for r in rows if not complete(r.status)]
            if target == "overdue_tasks":
                rows = [r for r in rows if r.due_date and r.due_date < today]
            if target == "due_today":
                rows = [r for r in rows if r.due_date == today]
            if target == "due_this_week":
                rows = [
                    r
                    for r in rows
                    if r.due_date
                    and today - timedelta(days=today.weekday())
                    <= r.due_date
                    <= today + timedelta(days=6 - today.weekday())
                ]
            if target == "in_progress":
                rows = [r for r in rows if r.status == "In Progress"]
            if target == "blocked_tasks":
                rows = [r for r in rows if r.status == "Blocked" or r.is_blocking]
            if target in {"average_completion", "on_time_rate"}:
                rows = [
                    r
                    for r in rows
                    if r.completed_at
                    and (r.created_at if target == "average_completion" else r.due_date)
                ]
            return {
                "state": "ready",
                "rows": [self.payload(r, source) for r in rows[: widget.limit]],
                "total": len(rows),
                "message": "Authorized records behind this widget.",
            }
        if spec["view"] == "metric":
            value, note = self.metric(kind, filters, widget.formula)
            result.update(value=value, message=note)
            if widget.comparison and filters.date_from and filters.date_to:
                duration = filters.date_to - filters.date_from + timedelta(days=1)
                previous = filters.model_copy(
                    update={
                        "date_from": filters.date_from - duration,
                        "date_to": filters.date_from - timedelta(days=1),
                    }
                )
                before, _ = self.metric(kind, previous, widget.formula)
                result.update(
                    previous=before,
                    change=(
                        round((value - before) / abs(before) * 100, 2)
                        if value is not None and before
                        else None
                    ),
                )
            return result
        if spec["view"] in {"radial", "gauge"}:
            value, note = self.metric(widget.formula, filters)
            return {"state": "ready", "value": value, "message": note}
        if spec["view"] == "trend":
            rows = self.rows(
                "tasks", filters.model_copy(update={"date_from": None, "date_to": None})
            )
            daily = defaultdict(lambda: {"created": 0, "completed": 0})
            for task in rows:
                for field, column in [
                    ("created_at", "created"),
                    ("completed_at", "completed"),
                ]:
                    stamp = day(getattr(task, field, None), filters.timezone)
                    if (
                        stamp
                        and (not filters.date_from or stamp >= filters.date_from)
                        and (not filters.date_to or stamp <= filters.date_to)
                    ):
                        daily[str(stamp)][column] += 1
            result["series"] = [
                {"name": key, **values} for key, values in sorted(daily.items())
            ][-90:]
            result["message"] = (
                "Recorded creation and completion timestamps. No past in-progress counts are inferred."
            )
            return result
        if spec["view"] in {"sprints", "velocity", "commitment"}:
            sprints = self.rows("sprints", filters)
            result["rows"] = [
                self.payload(r, "sprints") for r in sprints[: widget.limit]
            ]
            result["series"] = [
                {
                    "name": r.name,
                    "value": r.completed_story_points or 0,
                    "committed": r.committed_story_points or 0,
                    "completed": r.completed_story_points or 0,
                }
                for r in sprints[: widget.limit]
                if r.completed_at or kind != "velocity"
            ]
            result["message"] = (
                "Persisted sprint commitment and completion points; velocity includes completed sprints only."
            )
            return result
        if spec["view"] == "health":
            rows = self.rows("projects", filters)
            result["series"] = [
                {"name": name, "value": count}
                for name, count in Counter(
                    r.health or "Unspecified" for r in rows
                ).items()
            ]
            return result
        rows = (
            self.task_rows(kind, filters)
            if widget.source == "tasks"
            else self.rows(widget.source, filters)
        )
        if kind == "delayed_projects":
            rows = [
                r
                for r in rows
                if r.due_date and r.due_date < date.today() and not complete(r.status)
            ]
        if kind == "pivot":
            result["series"] = self.aggregate(rows, widget, filters)
            return result
        if kind in {"team_workload", "assignee_workload", "workload_heatmap"}:
            rows = [r for r in rows if not complete(r.status)]
        if spec["view"] == "histogram" and kind != "aging":
            if widget.metric == "count":
                return {
                    "state": "unavailable",
                    "message": "Select a numeric metric in widget settings to build a histogram.",
                }
            values = [
                (
                    numeric(getattr(r, widget.metric, None))
                    if widget.metric != "duration_hours"
                    else numeric(r.duration_minutes) / 60
                )
                for r in rows
            ]
            if not values:
                return {
                    "state": "ready",
                    "series": [],
                    "message": "No matching numeric records.",
                }
            low, high = min(values), max(values)
            span = (high - low) / 5 if high != low else 1
            counts = Counter(min(4, int((value - low) / span)) for value in values)
            result["series"] = [
                {
                    "name": f"{low+i*span:.1f}–{low+(i+1)*span:.1f}",
                    "value": counts.get(i, 0),
                }
                for i in range(5 if high != low else 1)
            ]
            result["message"] = "Five equal-width bins of the selected numeric metric."
            return result
        if spec["view"] in {
            "table",
            "progress",
            "deadlines",
            "activity",
            "calendar",
            "timeline",
        }:
            result["rows"] = [
                self.payload(r, widget.source) for r in rows[: widget.limit]
            ]
            result["total"] = len(rows)
            return result
        if spec["view"] in {"scatter", "bubble"}:
            result["series"] = [
                {
                    "name": r.title,
                    "x": numeric(r.estimated_hours),
                    "y": numeric(r.actual_hours),
                    "z": numeric(r.story_points),
                    "id": r.id,
                }
                for r in self.rows("tasks", filters)[:100]
            ]
            return result
        if kind == "aging" or spec["view"] == "histogram":
            counts = Counter()
            for row in self.task_rows("task_list", filters):
                if not row.created_at:
                    continue
                age = (
                    datetime.now(ZoneInfo(filters.timezone)).date()
                    - day(row.created_at, filters.timezone)
                ).days
                counts[
                    (
                        "0–7 days"
                        if age <= 7
                        else (
                            "8–14 days"
                            if age <= 14
                            else "15–30 days" if age <= 30 else "31+ days"
                        )
                    )
                ] += 1
            result["series"] = [
                {"name": key, "value": value} for key, value in counts.items()
            ]
            return result
        result["series"] = self.aggregate(rows, widget, filters)
        if widget.group_by == "assignee":
            result["message"] = (
                "Tasks with multiple assignees count once for each assignee. No capacity or utilization is inferred."
            )
        return result

    def batch(self, configuration):
        output = {}
        for widget in configuration.widgets:
            if widget.hidden:
                continue
            try:
                output[widget.id] = self.widget(widget, configuration.filters)
            except (ValueError, TypeError, AttributeError, KeyError) as error:
                output[widget.id] = {"state": "error", "message": str(error)[:200]}
        return {
            "widgets": output,
            "scope": {
                "visible_projects": len(self.ids),
                "time_scope": "workspace" if self.manages else "personal",
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
