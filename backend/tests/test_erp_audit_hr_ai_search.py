"""Literal text selection in HR AI adapter queries; authorization tested separately."""
from types import SimpleNamespace
import pytest
from app.ai_agents.adapters.hrms_ai_adapter import HrmsAiAdapter
from app.models.document import CompanyPolicy, DocumentTemplate
from app.models.leave import LeaveType

NEEDLES=["%","_",chr(92),chr(92)+"%",chr(92)+"_","/"]

@pytest.mark.parametrize("needle",NEEDLES)
@pytest.mark.parametrize("field",["title","category","content"])
def test_policy_search_literal(db,needle,field):
    ordinary=CompanyPolicy(title="Ordinary policy",category="HR",content="Plain text",is_published=True)
    match=CompanyPolicy(title="Matching policy",category="HR",content="Plain text",is_published=True)
    setattr(match,field,"QA"+needle+"Literal")
    hidden=CompanyPolicy(title="QA"+needle+"Literal",is_published=False)
    db.add_all([ordinary,match,hidden]);db.commit()
    adapter=HrmsAiAdapter(db)
    result=adapter.search_policy(SimpleNamespace(),{"query":needle})
    assert [r["id"] for r in result["policies"]]==[match.id]
    assert [r["id"] for r in adapter.search_policy(SimpleNamespace(),{"query":"ordinary"})["policies"]]==[ordinary.id]

@pytest.mark.parametrize("needle",NEEDLES)
def test_leave_type_text_is_literal(db,needle):
    ordinary=LeaveType(name="Ordinary leave",code="ORD",days_allowed=10,is_active=True)
    match=LeaveType(name="QA"+needle+"Leave",code="MATCH",days_allowed=10,is_active=True)
    hidden=LeaveType(name="QA"+needle+"Leave",code="HIDDEN",days_allowed=10,is_active=False)
    db.add_all([ordinary,match,hidden]);db.commit()
    adapter=HrmsAiAdapter(db)
    assert adapter._find_leave_type(needle).id==match.id
    assert adapter._find_leave_type("ord").id==ordinary.id
    assert adapter._find_leave_type(str(match.id)).id==match.id

@pytest.mark.parametrize("needle",NEEDLES)
def test_letter_draft_template_type_is_literal(db,monkeypatch,needle):
    ordinary=DocumentTemplate(name="Ordinary template",template_type="ordinary",is_active=True)
    hidden=DocumentTemplate(name="Inactive template",template_type="QA"+needle+"Letter",is_active=False)
    match=DocumentTemplate(name="Literal template",template_type="QA"+needle+"Letter",is_active=True)
    db.add_all([ordinary,hidden,match]);db.commit()
    adapter=HrmsAiAdapter(db)
    monkeypatch.setattr(adapter,"_get_employee",lambda user,identity:SimpleNamespace(id=1))
    result=adapter.generate_letter_draft(SimpleNamespace(),{"employee_id":1,"letter_type":needle})
    assert result["draft"]["template_id"]==match.id
