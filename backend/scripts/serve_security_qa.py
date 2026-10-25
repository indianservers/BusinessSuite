"""Run the real middleware/router stack against disposable synthetic QA data."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve_interns_hub_qa as fixture

from app.core.config import settings
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
settings.BACKEND_PUBLIC_URL = 'http://127.0.0.1:1549'
from app.main import app
from app.core.deps import get_db
from app.db.base import Base
from importlib import import_module
from app.module_registry import APP_MODULES

for module in APP_MODULES.values():
    for model_module in module.model_modules:
        import_module(model_module)
import_module('app.models.audit')

# The real app imports additional module models after the fixture seeds its DB.
# Create only their missing tables in this disposable QA database.
Base.metadata.create_all(fixture.engine)

app.dependency_overrides[get_db] = fixture.qa_db
app.state.audit_session_factory = fixture.Session
app.state.business_os_session_factory = fixture.Session
app.state.business_os_close_session = True
for directory in ('employee_docs', 'certificates', '_private'):
    target = Path(settings.UPLOAD_DIR)/directory/'synthetic-canary.txt'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('SYNTHETIC RESTRICTED CANARY — no real personal data', encoding='utf-8')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=1549)
