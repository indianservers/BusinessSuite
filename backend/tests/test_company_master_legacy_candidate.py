"""Run unchanged original master-data assertions with the actual Company candidate mounted.

The imported tests retain their complete native parameterization and assertions.
No auth dependency, source body, response, or permission is substituted.
"""
from types import MappingProxyType
import pytest
from tests.test_master_data import *  # noqa: F401,F403 - exact native regression cases


@pytest.fixture(autouse=True)
def actual_company_candidate_registration(monkeypatch):
    from app.business_packs import common_core,company_master_core
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,
        **company_master_core.candidate_operations(common_core.CoreOperation)}))
