"""Disposable local browser fixture. Not a production server."""

import os

os.environ.setdefault(
    "COMMERCIAL_QA_DATABASE_NAME", "businesssuite-commercial-forms-browser.db"
)
from scripts.run_commercial_browser_qa import app
from app.forms.router import router

app.include_router(router, prefix="/api/v1")
from app.apps.business_os.api.router import router as business_os_router
from app.api.v1.notifications import router as notifications_router

app.include_router(business_os_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
