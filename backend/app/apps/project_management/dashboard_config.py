"""Versioned dashboard configuration; deliberately no SQL or executable formulas."""

from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Filters(Strict):
    project_ids: list[int] = Field(default_factory=list, max_length=200)
    statuses: list[str] = Field(default_factory=list, max_length=40)
    priorities: list[str] = Field(default_factory=list, max_length=20)
    assignee_ids: list[int] = Field(default_factory=list, max_length=200)
    sprint_ids: list[int] = Field(default_factory=list, max_length=200)
    tag_ids: list[int] = Field(default_factory=list, max_length=100)
    team_ids: list[int] = Field(default_factory=list, max_length=100)
    project_statuses: list[str] = Field(default_factory=list, max_length=30)
    date_from: date | None = None
    date_to: date | None = None
    date_field: Literal["created_at", "due_date", "completed_at", "start_date"] = (
        "created_at"
    )
    timezone: str = Field(default="UTC", max_length=80)
    custom_field_id: int | None = Field(default=None, gt=0)
    custom_field_value: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def dates(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Start date must precede end date")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid IANA timezone")
        return self


class Widget(Strict):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    type: str = Field(min_length=1, max_length=80)
    title: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=500)
    icon: Literal[
        "auto",
        "chart",
        "tasks",
        "projects",
        "team",
        "calendar",
        "time",
        "target",
        "activity",
        "notes",
    ] = "auto"
    x: int = Field(default=0, ge=0, le=11)
    y: int = Field(default=0, ge=0, le=10000)
    w: int = Field(default=4, ge=2, le=12)
    h: int = Field(default=7, ge=3, le=24)
    drilldown: bool = False
    hidden: bool = False
    locked: bool = False
    source: Literal[
        "tasks", "projects", "time", "activity", "sprints", "milestones", "risks"
    ] = "tasks"
    metric: Literal[
        "count",
        "estimated_hours",
        "actual_hours",
        "story_points",
        "progress_percent",
        "budget_amount",
        "actual_cost",
        "duration_hours",
        "risk_score",
        "completion_rate",
    ] = "count"
    aggregation: Literal[
        "count",
        "sum",
        "average",
        "minimum",
        "maximum",
        "median",
        "distinct_count",
        "percentage",
    ] = "count"
    group_by: Literal[
        "status",
        "priority",
        "project",
        "assignee",
        "day",
        "week",
        "month",
        "quarter",
        "year",
    ] = "status"
    filters: Filters | None = None
    color: str = Field(default="#6d3df5", pattern=r"^#[0-9a-fA-F]{6}$")
    legend: bool = True
    gridlines: bool = True
    labels: bool = False
    tooltips: bool = True
    comparison: bool = False
    decimals: int = Field(default=0, ge=0, le=4)
    number_format: Literal["number", "percent", "hours", "currency"] = "number"
    sort: Literal["value_desc", "value_asc", "name"] = "value_desc"
    limit: int = Field(default=10, ge=1, le=100)
    notes: str = Field(default="", max_length=5000)
    url: str = Field(default="", max_length=2000)
    formula: Literal[
        "completion_rate", "on_time_rate", "remaining_hours", "budget_utilization"
    ] = "completion_rate"

    @model_validator(mode="after")
    def valid(self):
        if self.x + self.w > 12:
            raise ValueError("Widget exceeds the 12-column grid")
        if self.type not in WIDGETS:
            raise ValueError("Unknown widget type")
        if self.url and not self.url.startswith("https://"):
            raise ValueError("Widget links must use HTTPS")
        fields = {
            "tasks": {"count", "estimated_hours", "actual_hours", "story_points"},
            "projects": {"count", "progress_percent", "budget_amount", "actual_cost"},
            "time": {"count", "duration_hours"},
            "activity": {"count"},
            "sprints": {"count"},
            "milestones": {"count"},
            "risks": {"count", "risk_score"},
        }
        if self.metric not in fields[self.source]:
            raise ValueError("Metric is not supported by the selected data source")
        if self.metric == "count" and self.aggregation not in {"count", "percentage"}:
            raise ValueError("Choose count or percentage for record counts")
        return self


class Configuration(Strict):
    version: Literal[2] = 2
    widgets: list[Widget] = Field(default_factory=list, max_length=50)
    filters: Filters = Field(default_factory=Filters)
    template: str = Field(default="project_overview", max_length=60)
    refresh_seconds: int = Field(default=120, ge=30, le=3600)
    density: Literal["comfortable", "compact"] = "comfortable"
    filter_presets: dict[str, Filters] = Field(default_factory=dict, max_length=12)

    @model_validator(mode="after")
    def unique(self):
        if len({w.id for w in self.widgets}) != len(self.widgets):
            raise ValueError("Widget IDs must be unique")
        return self


# Catalog entries identify actual calculations. Unsupported historical/availability
# sources are explicit requirements, never proxy values or invented forecasts.
WIDGETS = {}


def register(key, title, category, view="metric", source="tasks", requirement=""):
    WIDGETS[key] = dict(
        id=key,
        title=title,
        category=category,
        view=view,
        source=source,
        requirement=requirement,
    )


for key, title, source in [
    ("total_projects", "Total Projects", "projects"),
    ("active_projects", "Active Projects", "projects"),
    ("completed_projects", "Completed Projects", "projects"),
    ("total_tasks", "Total Tasks", "tasks"),
    ("open_tasks", "Open Tasks", "tasks"),
    ("completed_tasks", "Completed Tasks", "tasks"),
    ("overdue_tasks", "Overdue Tasks", "tasks"),
    ("due_today", "Tasks Due Today", "tasks"),
    ("due_this_week", "Tasks Due This Week", "tasks"),
    ("in_progress", "Tasks In Progress", "tasks"),
    ("blocked_tasks", "Blocked Tasks", "tasks"),
    ("average_completion", "Average Completion Time", "tasks"),
    ("completion_rate", "Task Completion Rate", "tasks"),
    ("on_time_rate", "On-Time Delivery Rate", "tasks"),
    ("estimated_hours", "Estimated Hours", "tasks"),
    ("actual_hours", "Actual Hours", "time"),
    ("remaining_hours", "Remaining Hours", "tasks"),
    ("budget_utilization", "Budget Utilization", "projects"),
]:
    register(key, title, "Metrics", source=source)
register(
    "team_utilization",
    "Team Utilization",
    "Metrics",
    requirement="Configure per-person capacity and working schedules before utilization can be measured.",
)
register(
    "project_health_score",
    "Project Health Score",
    "Metrics",
    requirement="Define an approved numeric health scoring model. Project Health shows the existing categorical values.",
)
for key, title in [
    ("line", "Line Chart"),
    ("area", "Area Chart"),
    ("smooth_area", "Smooth Area Chart"),
    ("bar", "Bar Chart"),
    ("horizontal_bar", "Horizontal Bar Chart"),
    ("stacked_bar", "Stacked Bar Chart"),
    ("grouped_bar", "Grouped Bar Chart"),
    ("percent_bar", "100% Stacked Bar Chart"),
    ("pie", "Pie Chart"),
    ("donut", "Donut Chart"),
    ("radial", "Radial Progress Chart"),
    ("gauge", "Gauge Chart"),
    ("scatter", "Scatter Plot"),
    ("bubble", "Bubble Chart"),
    ("heatmap", "Heatmap"),
    ("treemap", "Treemap"),
    ("funnel", "Funnel Chart"),
    ("waterfall", "Waterfall Chart"),
    ("radar", "Radar Chart"),
    ("combo", "Combo Chart"),
    ("histogram", "Histogram"),
    ("pareto", "Pareto Chart"),
]:
    register(key, title, "Charts", view=key)
for key, title, view, source in [
    ("project_progress", "Project Progress", "progress", "projects"),
    ("portfolio", "Portfolio Overview", "table", "projects"),
    ("project_health", "Project Health", "health", "projects"),
    ("project_timeline", "Project Timeline", "timeline", "projects"),
    ("milestones", "Milestone Tracker", "table", "milestones"),
    ("deadlines", "Upcoming Deadlines", "deadlines", "tasks"),
    ("delayed_projects", "Delayed Projects", "table", "projects"),
    ("risks", "Risk Register", "table", "risks"),
    ("project_status", "Project Status Breakdown", "donut", "projects"),
    ("project_budget", "Project Budget Overview", "bar", "projects"),
]:
    register(key, title, "Projects", view, source)
for key, title in [
    ("planned_actual", "Planned vs Actual Progress"),
    ("completion_forecast", "Project Completion Forecast"),
]:
    register(
        key,
        title,
        "Projects",
        requirement="Requires dated baseline snapshots and an approved forecast model; no historical progress is inferred from current state.",
    )
for key, title, view in [
    ("task_status", "Task Status Distribution", "donut"),
    ("task_priority", "Task Priority Distribution", "donut"),
    ("task_trend", "Task Activity Trend", "trend"),
    ("task_list", "Open Task List", "table"),
    ("my_tasks", "My Tasks", "table"),
    ("unassigned", "Unassigned Tasks", "table"),
    ("recent_completed", "Recently Completed Tasks", "table"),
    ("overdue_list", "Overdue Task List", "table"),
    ("aging", "Task Aging Analysis", "histogram"),
    ("completion_trend", "Task Completion Trend", "trend"),
    ("creation_completion", "Task Creation vs Completion", "trend"),
    ("bottlenecks", "Bottleneck Analysis", "bar"),
    ("assignee_workload", "Task Workload by Assignee", "bar"),
]:
    register(key, title, "Tasks", view)
for key, title in [
    ("burndown", "Sprint Burndown"),
    ("burnup", "Sprint Burnup"),
    ("cumulative_flow", "Cumulative Flow Diagram"),
    ("lead_time", "Lead Time Analysis"),
    ("cycle_time", "Cycle Time Analysis"),
    ("wip_limits", "Work in Progress Limits"),
]:
    register(
        key,
        title,
        "Agile",
        requirement="Requires persisted daily scope/status transition snapshots or configured WIP limits. Current task counts are not historical measurements.",
    )
for key, title, view in [
    ("velocity", "Velocity Chart", "velocity"),
    ("sprint_health", "Sprint Health", "sprints"),
    ("throughput", "Throughput Trend", "trend"),
    ("commitment", "Sprint Commitment vs Completion", "commitment"),
]:
    register(key, title, "Agile", view, "sprints" if key != "throughput" else "tasks")
for key, title, view, source in [
    ("team_workload", "Team Workload", "bar", "tasks"),
    ("assignee_performance", "Assignee Performance", "bar", "tasks"),
    ("workload_heatmap", "Workload Heatmap", "heatmap", "tasks"),
    ("hours_by_employee", "Hours by Employee", "bar", "time"),
    ("productivity_trend", "Team Productivity Trend", "trend", "tasks"),
]:
    register(key, title, "Team", view, source)
for key, title in [
    ("resource_utilization", "Resource Utilization"),
    ("team_capacity", "Team Capacity"),
    ("team_availability", "Team Availability"),
    ("overloaded", "Overloaded Members"),
]:
    register(
        key,
        title,
        "Team",
        requirement="Requires authorized per-member availability and capacity schedules. Assignment counts do not establish capacity.",
    )
for key, title, view, source in [
    ("activity", "Recent Activity Timeline", "activity", "activity"),
    ("calendar", "Calendar Widget", "calendar", "tasks"),
    ("gantt", "Gantt Preview", "timeline", "projects"),
    ("custom_table", "Custom Data Table", "table", "tasks"),
    ("notes", "Rich Text / Notes", "notes", "tasks"),
    ("image", "Image Widget", "image", "tasks"),
    ("bookmark", "Link / Bookmark Widget", "bookmark", "tasks"),
    ("formula", "Custom Formula KPI", "metric", "tasks"),
    ("pivot", "Pivot Summary", "table", "tasks"),
    ("dataset", "Custom Query / Dataset Widget", "bar", "tasks"),
]:
    register(key, title, "More", view, source)
for key, title, requirement in [
    (
        "checklist",
        "Progress Checklist",
        "Use task checklists; dashboard checklist editing is not yet connected.",
    ),
    (
        "okr",
        "Goal / OKR Tracker",
        "Select an authorized goals dataset before enabling this widget.",
    ),
    (
        "custom_fields",
        "Custom Field Visualization",
        "Custom fields are supported as task filters; grouping heterogeneous field types needs a selected field schema.",
    ),
    (
        "ai_insights",
        "AI Insights Widget",
        "Use the suite assistant for authorized analysis; generated insights are not calculated metrics.",
    ),
]:
    register(key, title, "More", requirement=requirement)

TEMPLATES = [
    (
        "project_overview",
        "Project Overview",
        [
            "active_projects",
            "total_tasks",
            "completed_tasks",
            "overdue_tasks",
            "estimated_hours",
            "on_time_rate",
            "task_trend",
            "task_status",
            "project_progress",
            "sprint_health",
            "task_list",
            "activity",
            "deadlines",
        ],
    ),
    (
        "executive",
        "Executive Dashboard",
        [
            "active_projects",
            "completion_rate",
            "overdue_tasks",
            "budget_utilization",
            "project_progress",
            "project_health",
            "project_budget",
            "risks",
            "deadlines",
        ],
    ),
    (
        "team",
        "Team Productivity",
        [
            "open_tasks",
            "completed_tasks",
            "estimated_hours",
            "actual_hours",
            "team_workload",
            "productivity_trend",
            "task_list",
            "deadlines",
        ],
    ),
    (
        "sprint",
        "Sprint Analytics",
        [
            "open_tasks",
            "completed_tasks",
            "blocked_tasks",
            "velocity",
            "sprint_health",
            "commitment",
            "task_list",
        ],
    ),
    (
        "agile",
        "Agile Performance",
        [
            "in_progress",
            "blocked_tasks",
            "average_completion",
            "velocity",
            "throughput",
            "task_status",
            "task_list",
        ],
    ),
    (
        "workload",
        "Workload Management",
        [
            "open_tasks",
            "unassigned",
            "estimated_hours",
            "team_workload",
            "workload_heatmap",
            "hours_by_employee",
        ],
    ),
    (
        "tasks",
        "Task Management",
        [
            "total_tasks",
            "open_tasks",
            "completed_tasks",
            "overdue_tasks",
            "task_status",
            "task_priority",
            "task_list",
        ],
    ),
    (
        "portfolio",
        "Project Portfolio",
        [
            "total_projects",
            "active_projects",
            "completed_projects",
            "project_progress",
            "project_health",
            "portfolio",
        ],
    ),
    (
        "resources",
        "Resource Planning",
        [
            "estimated_hours",
            "actual_hours",
            "remaining_hours",
            "team_workload",
            "hours_by_employee",
        ],
    ),
    (
        "deadlines",
        "Deadline Monitoring",
        [
            "due_today",
            "due_this_week",
            "overdue_tasks",
            "on_time_rate",
            "deadlines",
            "calendar",
            "overdue_list",
        ],
    ),
    (
        "time",
        "Time Tracking",
        [
            "estimated_hours",
            "actual_hours",
            "remaining_hours",
            "hours_by_employee",
            "assignee_workload",
        ],
    ),
    (
        "budget",
        "Budget and Cost",
        ["budget_utilization", "project_budget", "portfolio"],
    ),
    (
        "risk",
        "Risk and Issues",
        ["blocked_tasks", "overdue_tasks", "risks", "task_priority", "overdue_list"],
    ),
    (
        "client",
        "Client Reporting",
        [
            "total_projects",
            "completion_rate",
            "on_time_rate",
            "project_progress",
            "milestones",
            "deadlines",
        ],
    ),
    ("blank", "Custom Blank Dashboard", []),
]


def template_config(key):
    selected = next((types for ident, _, types in TEMPLATES if ident == key), [])
    widgets = []
    x = 0
    y = 0
    row_height = 0
    for i, kind in enumerate(selected):
        metric = WIDGETS[kind]["view"] == "metric"
        w = 2 if metric else 4
        h = 4 if metric else 8
        if x + w > 12:
            x = 0
            y += row_height
            row_height = 0
        widgets.append(
            Widget(
                id=f"widget_{i+1}",
                type=kind,
                title=WIDGETS[kind]["title"],
                source=WIDGETS[kind]["source"],
                x=x,
                y=y,
                w=w,
                h=h,
                group_by=(
                    "project"
                    if kind in {"project_budget", "project_progress"}
                    else (
                        "assignee"
                        if kind
                        in {
                            "team_workload",
                            "assignee_workload",
                            "hours_by_employee",
                            "workload_heatmap",
                            "assignee_performance",
                        }
                        else "priority" if kind == "task_priority" else "status"
                    )
                ),
            )
        )
        x += w
        row_height = max(row_height, h)
    for widget in widgets:
        if widget.type == "project_budget":
            widget.metric = "budget_amount"
            widget.aggregation = "sum"
    if key == "project_overview":
        positions = {
            "task_trend": (0, 4, 5, 8),
            "task_status": (5, 4, 3, 8),
            "project_progress": (8, 4, 4, 4),
            "sprint_health": (8, 8, 4, 4),
            "task_list": (0, 12, 5, 8),
            "activity": (5, 12, 3, 8),
            "deadlines": (8, 12, 4, 8),
        }
        for widget in widgets:
            if widget.type in positions:
                widget.x, widget.y, widget.w, widget.h = positions[widget.type]
    return Configuration(template=key, widgets=widgets)


def validate_layout(configuration):
    if configuration is None:
        return configuration
    widgets = [w for w in configuration.widgets if not w.hidden]
    for index, first in enumerate(widgets):
        for second in widgets[index + 1 :]:
            if (
                first.x < second.x + second.w
                and first.x + first.w > second.x
                and first.y < second.y + second.h
                and first.y + first.h > second.y
            ):
                raise ValueError(
                    "Widgets overlap. Reset positions or move the overlapping widgets before saving."
                )
    return configuration
