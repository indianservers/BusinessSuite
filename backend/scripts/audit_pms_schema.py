"""Read-only deployment schema diagnostic. Never prints connection strings."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect, text
from app.db.session import engine
with engine.connect() as conn:
    inspector = inspect(conn)
    print("Database migration revisions:", conn.execute(text("select version_num from alembic_version")).scalars().all())
    for table in ["pms_tasks", "pms_custom_fields", "pms_custom_field_values", "pms_task_types", "pms_teams", "pms_direct_messages", "pms_running_timers", "pms_documents"]:
        print(table, "present" if inspector.has_table(table) else "MISSING")
