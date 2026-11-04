from tests.rich_text_test_utils import organization_context
"""The deployment migration chain must contain the task collaboration schema."""
from pathlib import Path
import uuid
import pytest
from sqlalchemy import text, inspect
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]
OLD = "pg_20261031_045_people_workspace"
HEAD = "pg_20261101_049_arrangement"


def test_deployment_chain_reaches_task_schema():
    scripts = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    assert HEAD in {revision.revision for revision in scripts.walk_revisions()}
    revisions = list(scripts.iterate_revisions(HEAD, OLD))
    assert len(revisions) == 4
    assert {r.module.revision for r in revisions} == {
        "pg_20261101_046_task_groups", "pg_20261101_047_general_tasks",
        "pg_20261101_048_task_workspace", HEAD,
    }


def test_deployed_postgres_task_upgrade_preserves_rows(db_engine):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Real PostgreSQL migration integration")
    assert db_engine.url.database.endswith("_test")
    schema = "pms_upgrade_" + uuid.uuid4().hex
    config = Config(str(ROOT / "alembic.ini"))
    with db_engine.connect() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
        db.execute(text(f'SET search_path TO "{schema}"'))
        db.commit()
        config.attributes["connection"] = db
        try:
            # An isolated pre-change schema prevents current ORM create_all from
            # supplying the very columns whose absence caused the live failure.
            # The db_engine fixture separately builds the full PostgreSQL chain.
            for ddl in [
                "CREATE TABLE users (id SERIAL PRIMARY KEY)",
                "CREATE TABLE companies (id SERIAL PRIMARY KEY)",
                "CREATE TABLE ai_action_logs (id SERIAL PRIMARY KEY)",
                "CREATE TABLE ai_prompt_runs (id SERIAL PRIMARY KEY)",
                "CREATE TABLE ai_agent_actions (id SERIAL PRIMARY KEY)",
                "CREATE TABLE ai_user_feedback (id SERIAL PRIMARY KEY)",
                "CREATE TABLE communication_whatsapp_templates (id SERIAL PRIMARY KEY)",
                "CREATE TABLE communication_auto_response_rules (id SERIAL PRIMARY KEY)",
                "CREATE TABLE communication_webforms (id SERIAL PRIMARY KEY)",
                "CREATE TABLE pms_projects (id SERIAL PRIMARY KEY, name TEXT, project_key TEXT, workspace_id INTEGER)",
                "CREATE TABLE pms_tasks (id SERIAL PRIMARY KEY, project_id INTEGER REFERENCES pms_projects(id), title TEXT, task_key TEXT)",
                "CREATE TABLE pms_comments (id SERIAL PRIMARY KEY)",
                "CREATE TABLE crm_file_assets (id SERIAL PRIMARY KEY)",
                "CREATE TABLE crm_quotation_items (id SERIAL PRIMARY KEY)",
                "CREATE TABLE pms_file_assets (id SERIAL PRIMARY KEY)",
            ]:
                db.execute(text(ddl))
            command.stamp(config, OLD)
            db.commit()
            db.execute(text("INSERT INTO pms_projects (name,project_key) VALUES ('Existing project','KEEP')"))
            db.execute(text("INSERT INTO pms_tasks (project_id,title,task_key) SELECT id,'Existing task','KEEP-1' FROM pms_projects WHERE project_key='KEEP'"))
            db.commit()
            command.upgrade(config, "head")
            db.commit()
            assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == ScriptDirectory.from_config(config).get_current_head()
            assert db.execute(text("SELECT title FROM pms_tasks WHERE task_key='KEEP-1'")).scalar_one() == "Existing task"
            assert db.execute(text("SELECT is_task_collection FROM pms_projects WHERE project_key='KEEP'")).scalar_one() is False
            tables = set(inspect(db).get_table_names(schema=schema))
            assert {"pms_task_group_targets","pms_task_workspace_state","pms_task_watchers","pms_task_read_positions","pms_comment_reactions","pms_task_update_entries","pms_file_folders","crm_file_folders"} <= tables
            for table,column in [("pms_projects","is_task_collection"),("pms_comments","is_resolved"),("pms_file_assets","folder_id"),("crm_file_assets","folder_id"),("crm_quotation_items","sort_order")]:
                assert column in {c['name'] for c in inspect(db).get_columns(table,schema=schema)}
            command.upgrade(config, "head")  # second deployment remains a no-op
            db.commit()
            assert db.execute(text("SELECT count(*) FROM pms_tasks WHERE task_key='KEEP-1'")).scalar_one() == 1
        finally:
            db.rollback()
            db.execute(text('SET search_path TO public'))
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            db.commit()
