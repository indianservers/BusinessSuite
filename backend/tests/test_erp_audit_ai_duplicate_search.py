"""CRM duplicate matching must preserve literal company names."""
from types import SimpleNamespace
from datetime import datetime, timezone
import pytest
from app.ai_agents.adapters.crm_ai_adapter import CrmAiAdapter
from app.apps.crm.models import CRMLead

@pytest.mark.parametrize("needle",["%","_",chr(92),chr(92)+"%",chr(92)+"_","/"])
@pytest.mark.parametrize("source",["company_name","lead_id"])
def test_duplicate_company_search_literal(db,needle,source):
    ordinary=CRMLead(organization_id=1,first_name="Ordinary",full_name="Ordinary",company_name="QA ordinary")
    match=CRMLead(organization_id=1,first_name="Match",full_name="Match",company_name="QA"+needle+"Co")
    seed=CRMLead(organization_id=1,first_name="Source",full_name="Source",company_name="QA"+needle+"Co")
    foreign=CRMLead(organization_id=2,first_name="Foreign",full_name="Foreign",company_name="QA"+needle+"Co")
    deleted=CRMLead(organization_id=1,first_name="Deleted",full_name="Deleted",company_name="QA"+needle+"Co",deleted_at=datetime.now(timezone.utc))
    db.add_all([ordinary,match,seed,foreign,deleted]);db.commit()
    adapter=CrmAiAdapter(db)
    user=SimpleNamespace(is_superuser=False,employee=SimpleNamespace(organization_id=1))
    result=adapter.search_duplicate_leads(user,{source:seed.id if source=="lead_id" else needle})
    expected=[match.id] if source=="lead_id" else [match.id,seed.id]
    assert sorted(r["id"] for r in result["duplicates"])==sorted(expected)
    assert result["count"]==len(expected)
    assert [r["id"] for r in adapter.search_duplicate_leads(user,{"company_name":"ORDINARY"})["duplicates"]]==[ordinary.id]
