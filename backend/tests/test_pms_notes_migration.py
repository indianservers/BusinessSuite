"""Upgrade/downgrade preserves legacy rows in an isolated database."""
import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from app.db.base import Base


def test_notes_workspace_upgrade_downgrade_preserves_legacy_data():
    engine=create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for name in ["pms_note_events","pms_note_shares","pms_private_notes","pms_note_folders"]:
            connection.exec_driver_sql("DROP TABLE "+name)
        connection.exec_driver_sql("""CREATE TABLE pms_private_notes (
          id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id), title VARCHAR(180) NOT NULL,
          content TEXT NOT NULL, project_id INTEGER REFERENCES pms_projects(id), task_id INTEGER REFERENCES pms_tasks(id),
          tags JSON NOT NULL, pinned BOOLEAN NOT NULL, archived BOOLEAN NOT NULL, version INTEGER NOT NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, deleted_at DATETIME)""")
        connection.execute(text("INSERT INTO pms_private_notes (id,owner_id,title,content,tags,pinned,archived,version) VALUES (1,1,'Legacy','## Original markdown',:tags,0,0,7)"),{"tags":"[]"})
        path=Path(__file__).resolve().parents[1]/"alembic/versions/20261026_028_notes_workspace.py"
        spec=importlib.util.spec_from_file_location("notes_migration",path)
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        migration.op=Operations(MigrationContext.configure(connection))
        migration.upgrade()
        row=connection.execute(text("SELECT content,version,favorite,folder_id FROM pms_private_notes WHERE id=1")).one()
        assert tuple(row)==("## Original markdown",7,0,None)
        migration.downgrade()
        assert connection.execute(text("SELECT content,version FROM pms_private_notes WHERE id=1")).one()==("## Original markdown",7)
        migration.upgrade()
        assert connection.execute(text("SELECT content FROM pms_private_notes WHERE id=1")).scalar()=="## Original markdown"
    engine.dispose()
