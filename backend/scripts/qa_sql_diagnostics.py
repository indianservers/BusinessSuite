"""Optional pytest-only diagnostics for synthetic fixture SQL failures."""
import json
from pathlib import Path
import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

@pytest.fixture(autouse=True)
def fixture_sql_diagnostics():
    def capture(context):
        path=Path(__file__).resolve().parents[2]/'output/business-profile-15-companies/sql-fixture-errors.jsonl'
        with path.open('a',encoding='utf-8') as handle:
            handle.write(json.dumps({'type':type(context.original_exception).__name__,'message':str(context.original_exception)[:1800]})+'\n')
    event.listen(Engine,'handle_error',capture)
    try:yield
    finally:event.remove(Engine,'handle_error',capture)
