"""Project Management schema compatibility helpers."""

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


def _columns(db: Session, table_name: str) -> set[str]:
    try:
        inspector = inspect(db.bind)
        if not inspector.has_table(table_name):
            return set()
        return {column["name"] for column in inspector.get_columns(table_name)}
    except Exception:
        return set()


def ensure_pms_schema(db: Session) -> None:
    """Keep existing dev databases compatible with the PMS models when create_all is used."""
    project_columns = _columns(db, "pms_projects")
    if project_columns:
        project_additions = {
            "owner_user_id": "INTEGER",
            "department_id": "INTEGER",
            "branch_id": "INTEGER",
            "category": "VARCHAR(80)",
            "planned_start_date": "DATE",
            "planned_end_date": "DATE",
            "actual_start_date": "DATE",
            "actual_end_date": "DATE",
            "estimated_hours": "NUMERIC(10, 2)",
            "estimated_cost": "NUMERIC(12, 2)",
            "billing_status": "VARCHAR(40) DEFAULT 'Unbilled'",
            "is_template": "BOOLEAN DEFAULT 0",
        }
        for column_name, column_type in project_additions.items():
            if column_name not in project_columns:
                db.execute(text(f"ALTER TABLE pms_projects ADD COLUMN {column_name} {column_type}"))

    member_columns = _columns(db, "pms_project_members")
    if member_columns and "allocation_percent" not in member_columns:
        db.execute(text("ALTER TABLE pms_project_members ADD COLUMN allocation_percent NUMERIC(5, 2) DEFAULT 100"))

    task_columns = _columns(db, "pms_tasks")
    if task_columns:
        task_additions = {
            "recurrence_rule": "VARCHAR(40)",
            "recurrence_interval": "INTEGER DEFAULT 1",
            "recurrence_until": "DATE",
        }
        for column_name, column_type in task_additions.items():
            if column_name not in task_columns:
                db.execute(text(f"ALTER TABLE pms_tasks ADD COLUMN {column_name} {column_type}"))

    sprint_columns = _columns(db, "pms_sprints")
    if not sprint_columns:
        db.commit()
        return
    additions = {
        "completed_by_user_id": "INTEGER",
        "review_notes": "TEXT",
        "retrospective_notes": "TEXT",
        "what_went_well": "TEXT",
        "what_did_not_go_well": "TEXT",
        "outcome": "TEXT",
    }
    for column_name, column_type in additions.items():
        if column_name not in sprint_columns:
            db.execute(text(f"ALTER TABLE pms_sprints ADD COLUMN {column_name} {column_type}"))
    time_log_columns = _columns(db, "pms_time_logs")
    if time_log_columns and "timesheet_id" not in time_log_columns:
        db.execute(text("ALTER TABLE pms_time_logs ADD COLUMN timesheet_id INTEGER"))
    db.commit()
