from email import policy
from email.parser import BytesParser
from unittest.mock import Mock, MagicMock

import pytest

from app.apps.interns_hub.confirmation_email import send_confirmation
from app.apps.interns_hub.management_models import ApplicationEvent
from app.apps.interns_hub.models import InternApplication
from app.core.config import settings


@pytest.fixture
def saved_application(db):
    item = InternApplication(organization_id=1, reference="APP-EMAIL-TEST",
                            full_name="Test Applicant", email="synthetic@example.com",
                            password_hash="test", details={}, identity_number_encrypted="test",
                            identity_last4="1234", status="Pending")
    db.add(item)
    db.commit()
    return item


def test_confirmation_uses_requested_sender_and_is_not_sent_twice(db, saved_application, monkeypatch):
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", True)
    client = Mock()
    client.send_raw_email.return_value = {"MessageId": "ses-test-id"}
    monkeypatch.setattr("boto3.client", Mock(return_value=client))
    assert send_confirmation(db, saved_application)
    payload = client.send_raw_email.call_args.kwargs
    assert payload["Source"] == "Interns Hub <noreply@indianservers.com>"
    assert payload["Destinations"] == [saved_application.email]
    body = BytesParser(policy=policy.default).parsebytes(payload["RawMessage"]["Data"]).get_content()
    assert saved_application.reference in body
    assert "not an internship offer or approval" in body
    assert "password_hash" not in body and "1234" not in body
    assert not send_confirmation(db, saved_application)
    assert client.send_raw_email.call_count == 1
    assert db.query(ApplicationEvent).one().state == "Confirmation Accepted"


def test_uncertain_delivery_does_not_resend_or_lose_application(db, saved_application, monkeypatch):
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", True)
    client = Mock()
    client.send_raw_email.side_effect = TimeoutError("provider timeout")
    monkeypatch.setattr("boto3.client", Mock(return_value=client))
    assert not send_confirmation(db, saved_application)
    assert not send_confirmation(db, saved_application)
    assert client.send_raw_email.call_count == 1
    assert db.get(InternApplication, saved_application.id).status == "Pending"
    assert db.query(ApplicationEvent).one().state == "Confirmation Uncertain"


def test_disabled_delivery_does_not_contact_aws(db, saved_application, monkeypatch):
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", False)
    factory = Mock()
    monkeypatch.setattr("boto3.client", factory)
    assert not send_confirmation(db, saved_application)
    factory.assert_not_called()


def test_smtp_receipt_requires_tls_and_uses_supplied_credentials(db, saved_application, monkeypatch):
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", True)
    monkeypatch.setattr(settings, "INTERN_HUB_SES_SMTP_SERVER", "smtp.example.com")
    monkeypatch.setattr(settings, "INTERN_HUB_SES_SMTP_USERNAME", "smtp-user")
    monkeypatch.setattr(settings, "INTERN_HUB_SES_SMTP_PASSWORD", "smtp-secret")
    factory = MagicMock()
    smtp = factory.return_value.__enter__.return_value
    smtp.send_message.return_value = {}
    monkeypatch.setattr("smtplib.SMTP", factory)
    assert send_confirmation(db, saved_application)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("smtp-user", "smtp-secret")
    names = [entry[0] for entry in smtp.method_calls]
    assert names.index("starttls") < names.index("login") < names.index("send_message")
    message = smtp.send_message.call_args.args[0]
    assert str(message["From"]) == "Interns Hub <noreply@indianservers.com>"
    assert saved_application.reference in message.get_content()


def test_dsb_confirmation_uses_dsb_sender_and_brand(db, saved_application, monkeypatch):
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", True)
    monkeypatch.setattr(settings, "INTERN_HUB_SES_FROM", "noreply@dsbchartered.com")
    monkeypatch.setattr(settings, "INTERN_HUB_SES_BRAND", "DSB Chartered")
    deliver = Mock(return_value={"MessageId": "dsb-test-id"})
    monkeypatch.setattr("app.apps.interns_hub.confirmation_email.deliver_ses", deliver)
    assert send_confirmation(db, saved_application)
    payload = deliver.call_args.kwargs
    assert payload["Source"] == "Interns Hub <noreply@dsbchartered.com>"
    body = payload["Message"]["Body"]["Text"]["Data"]
    assert "DSB Chartered — Interns Hub" in body
    assert "Indian Servers" not in body
