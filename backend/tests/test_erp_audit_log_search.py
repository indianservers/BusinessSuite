"""Log endpoint filters must treat user text literally across lists and aggregates."""
import pytest
from app.models.audit import AuditLog
from tests.test_import_workspace import import_headers
from app.models.user import User
from test_identity_utils import own_workflow_records

@pytest.mark.parametrize("needle", ["%", "_", chr(92), chr(92)+"%", chr(92)+"_", "/"])
def test_log_endpoint_search_is_literal(client, db, import_headers, needle):
    actor=db.query(User).filter_by(email="testadmin@test.com").one()
    prefix="/qa-log-search-"
    match=AuditLog(user_id=actor.id, organization_id=actor.person.organization_id,
        method="POST", endpoint=prefix+needle+"Literal", status_code=500, duration_ms=100, action="ERROR")
    ordinary=AuditLog(user_id=actor.id, organization_id=actor.person.organization_id,
        method="GET", endpoint=prefix+"ordinary", status_code=200, duration_ms=20, action="GET")
    db.add_all([match,ordinary]);own_workflow_records(db,match,ordinary);db.commit()
    for path in ["audit", "errors"]:
        response=client.get("/api/v1/logs/"+path, headers=import_headers, params={"endpoint":prefix+needle})
        assert response.status_code==200,response.text
        assert [r["id"] for r in response.json()]==[match.id]
    response=client.get("/api/v1/logs/analysis", headers=import_headers, params={"endpoint":prefix+needle})
    assert response.status_code==200,response.text
    result=response.json()
    assert result["total_requests"]==1
    assert result["error_count"]==1
    assert result["server_error_count"]==1
    assert result["avg_duration_ms"]==100
    response=client.get("/api/v1/logs/audit", headers=import_headers, params={"endpoint":prefix.upper()+"ORDINARY"})
    assert response.status_code==200,response.text
    assert [r["id"] for r in response.json()]==[ordinary.id]
