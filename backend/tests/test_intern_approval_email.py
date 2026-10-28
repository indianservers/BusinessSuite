from unittest.mock import Mock

import pytest

from app.apps.interns_hub.approval_email import send_approval
from app.apps.interns_hub.management_models import ApplicationEvent
from app.apps.interns_hub.models import InternApplication
from app.core.config import settings


@pytest.fixture
def approved_application(db):
    item = InternApplication(organization_id=1, reference="APP-APPROVAL-EMAIL",
        full_name="Test Intern", email="intern@example.com", password_hash="private-hash",
        details={}, identity_number_encrypted="private-id", identity_last4="1234", status="Approved")
    db.add(item)
    db.commit()
    return item


@pytest.mark.parametrize("fails", [False, True])
def test_approval_delivery_and_duplicate_protection(db, approved_application, monkeypatch, fails):
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", True)
    monkeypatch.setattr(settings, "FRONTEND_PUBLIC_URL", "https://suite.example.com/")
    delivery = Mock(return_value={"MessageId": "approval-test"})
    if fails:
        delivery.side_effect = TimeoutError("timeout")
    monkeypatch.setattr("app.apps.interns_hub.approval_email.deliver_ses", delivery)
    assert send_approval(db, approved_application) is not fails
    assert not send_approval(db, approved_application)
    assert delivery.call_count == 1
    payload = delivery.call_args.kwargs
    assert payload["Destination"]["ToAddresses"] == [approved_application.email]
    body = payload["Message"]["Body"]["Text"]["Data"]
    assert "approved" in body and "https://suite.example.com/login" in body
    assert "password you created" in body and "Forgot password" in body
    assert approved_application.password_hash not in body
    assert db.get(InternApplication, approved_application.id).status == "Approved"
    assert db.query(ApplicationEvent).one().state == ("Approval Email Uncertain" if fails else "Approval Email Accepted")


@pytest.mark.parametrize("status,enabled", [("Pending", True), ("Rejected", True), ("Approved", False)])
def test_only_enabled_approved_applications_send(db, approved_application, monkeypatch, status, enabled):
    approved_application.status = status
    db.commit()
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", enabled)
    delivery = Mock()
    monkeypatch.setattr("app.apps.interns_hub.approval_email.deliver_ses", delivery)
    assert not send_approval(db, approved_application)
    delivery.assert_not_called()
