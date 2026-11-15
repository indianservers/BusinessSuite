"""Isolated unpublished-reader descriptor only; no runtime Pack activation."""
from types import MappingProxyType
import pytest

@pytest.fixture(autouse=True)
def review_candidate(monkeypatch):
    from app.business_packs import common_core,payroll_review
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,
        **payroll_review.candidate_operations(common_core.CoreOperation)}))
