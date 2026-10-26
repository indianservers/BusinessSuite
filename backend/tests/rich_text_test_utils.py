"""Minimum tenant bootstrap for workflow tests using the production middleware."""
import pytest
from app.models.company import Company

@pytest.fixture(autouse=True)
def organization_context(db):
    if not db.get(Company,1):
        db.add(Company(id=1,name="Workflow test organization",is_active=True))
        db.commit()
