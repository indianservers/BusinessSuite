import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.migration import MigrationContext
from alembic.operations import Operations

@pytest.mark.parametrize("folder,prefix",[("alembic",""),("alembic_postgresql","pg_")])
def test_custom_columns_migration_preserves_legacy_values(folder,prefix):
 path=Path(__file__).resolve().parents[1]/folder/"versions"/(prefix+"20261027_034_custom_columns.py")
 spec=importlib.util.spec_from_file_location("columns_migration",path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
 engine=create_engine("sqlite://")
 with engine.begin() as c:
  c.exec_driver_sql("CREATE TABLE pms_projects (id INTEGER PRIMARY KEY, organization_id INTEGER)")
  c.exec_driver_sql("INSERT INTO pms_projects VALUES (1,7)")
  c.exec_driver_sql("CREATE TABLE pms_custom_fields (id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES pms_projects(id), name VARCHAR(120) NOT NULL, field_type VARCHAR(20), options_json TEXT, CONSTRAINT uq_pms_custom_field_name UNIQUE(project_id,name))")
  c.exec_driver_sql("INSERT INTO pms_custom_fields VALUES (1,1,'Legacy','text','[]')")
  c.exec_driver_sql("CREATE TABLE pms_custom_field_values (field_id INTEGER REFERENCES pms_custom_fields(id), task_id INTEGER, value_json TEXT)")
  c.exec_driver_sql("INSERT INTO pms_custom_field_values VALUES (1,99,'123')")
  migration.op=Operations(MigrationContext.configure(c));migration.upgrade()
  assert c.execute(text("SELECT organization_id,scope_key,entity_type,archived FROM pms_custom_fields WHERE id=1")).one()==(7,"project:1","task",False)
  assert c.execute(text("SELECT value_json FROM pms_custom_field_values")).scalar_one()=="123"
  c.exec_driver_sql("INSERT INTO pms_custom_fields (id,project_id,name,field_type,options_json,organization_id,scope_key,entity_type) VALUES (2,NULL,'Financial Year','text','[]',7,'company:7','both')")
  c.exec_driver_sql("INSERT INTO pms_project_custom_field_values VALUES (2,1,'2026')")
  assert "pms_project_custom_field_values" in inspect(c).get_table_names()
 engine.dispose()
