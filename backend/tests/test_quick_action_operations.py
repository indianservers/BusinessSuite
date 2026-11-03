"""Real request/database regressions for the quick-action operation boundaries."""
from datetime import date, timedelta
import pytest
from app.models.company import Company, Branch
from tests.fam_test_utils import balanced_voucher_payload


@pytest.fixture
def scope(db, superuser_headers):
    if not db.get(Company, 1):
        db.add(Company(id=1, name="Quick action regression tenant", is_active=True))
        db.flush()
    db.get(Company, 1).email = "office@quick-action.example.com"
    branch = Branch(company_id=1, name="Quick action test", code="QUICK")
    db.add(branch)
    db.commit()
    return {**superuser_headers, "X-Suite-Organization": "1", "X-Suite-Branch": str(branch.id)}


def test_voucher_draft_edit_post_and_reverse_preserve_lines(client, db, scope):
    payload = balanced_voucher_payload(client, scope, amount=250)
    payload["voucher_date"] = str(date.today())
    created = client.post("/api/v1/fam/vouchers", headers=scope, json=payload)
    assert created.status_code == 201, created.text
    path = f"/api/v1/fam/vouchers/{created.json()['id']}"
    edited = client.put(path, headers=scope, json={**payload, "reference_number": "QUICK-EDITED"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["reference_number"] == "QUICK-EDITED"
    assert len(edited.json()["lines"]) == 2
    posted = client.post(path + "/post", headers=scope)
    assert posted.status_code == 200, posted.text
    assert posted.json()["status"] == "posted"
    assert client.put(path, headers=scope, json=payload).status_code == 409
    reversal = client.post(path + "/reverse", headers=scope)
    assert reversal.status_code == 201, reversal.text
    assert client.get(path, headers=scope).json()["status"] == "reversed"


def test_failed_quote_conversion_does_not_accept_quote(client, db, scope):
    quote = client.post("/api/v1/crm/quotes", headers=scope, json={"quoteNumber": "QA-UNLINKED", "issueDate": str(date.today()), "expiryDate": str(date.today()+timedelta(days=30))})
    assert quote.status_code == 201, quote.text
    path = f"/api/v1/crm/quotes/{quote.json()['id']}"
    assert client.post(path + "/submit", headers=scope, json={}).status_code == 200
    assert client.post(path + "/approve", headers=scope, json={}).status_code == 200
    assert client.post(path + "/send", headers=scope, json={}).status_code == 200
    failed = client.post(path + "/accept", headers=scope, json={})
    assert failed.status_code == 400, failed.text
    current = client.get(path, headers=scope).json()
    assert current["status"] == "Sent"
    assert not current.get("accepted_at")
