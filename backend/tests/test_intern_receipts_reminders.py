from datetime import date, timedelta
from io import BytesIO
from unittest.mock import Mock

import jwt
import pytest
from pypdf import PdfReader
from app.core.config import settings
from app.apps.interns_hub.applications import today
from app.apps.interns_hub.application_receipts import receipt_token
from app.apps.interns_hub.correction_reminders import run_correction_reminders
from app.apps.interns_hub.management_models import ApplicationEvent
from app.apps.interns_hub.models import InternApplication


@pytest.fixture
def correction(db):
    item = InternApplication(organization_id=1, reference="APP-RECEIPT-TEST", email="synthetic@example.com",
        full_name="Ananya Rao", password_hash="private-password-hash", details={"role": "Software Intern", "passout_year": 2029},
        identity_number_encrypted="private-identity", identity_last4="1234", status="Correction Requested",
        review_note="Please update your college name")
    db.add(item); db.flush()
    db.add(ApplicationEvent(application_id=item.id, state="Correction Deadline", note="2026-11-10"))
    db.commit()
    return item


def test_private_pdf_receipt_excludes_sensitive_details(client, correction):
    base = "/api/v1/interns-hub/applications/receipt"
    assert client.get(base).status_code == 401
    response = client.get(base, headers={"Authorization": "Bearer " + receipt_token(correction)})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "no-store" in response.headers["cache-control"]
    assert "attachment" in response.headers["content-disposition"]
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert correction.reference in text and correction.full_name in text
    assert "9618222220" in text and "completely free" in text
    assert "10 Nov 2026" in text
    assert "private-password-hash" not in text and "private-identity" not in text


@pytest.mark.parametrize("change", [{"exp": 1}, {"organization": 99}, {"aud": "intern-application"}])
def test_receipt_rejects_expired_or_wrong_scope_tokens(client, correction, change):
    claims = jwt.decode(receipt_token(correction), settings.SECRET_KEY, algorithms=[settings.ALGORITHM], audience="intern-receipt")
    claims.update(change)
    token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert client.get("/api/v1/interns-hub/applications/receipt", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_correction_deadline_saved_and_returned(client, db, superuser_headers, correction):
    base = "/api/v1/interns-hub"
    item = correction
    item.status = "Pending"
    db.commit()
    request = {"status": "Correction Requested", "review_note": "Update your college", "correction_deadline": str(today()+timedelta(days=4))}
    response = client.post(f"{base}/admin/applications/{item.id}/decision", json=request, headers=superuser_headers)
    assert response.status_code == 200, response.text
    assert response.json()["correction_deadline"] == request["correction_deadline"]
    request["correction_deadline"] = str(today()-timedelta(days=1))
    assert client.post(f"{base}/admin/applications/{item.id}/decision", json=request, headers=superuser_headers).status_code == 422


def test_reminders_deduplicate_and_stop_after_corrections(db, correction, monkeypatch):
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", True)
    deliver = Mock(return_value={"MessageId": "test-id"})
    monkeypatch.setattr("app.apps.interns_hub.confirmation_email.deliver_ses", deliver)
    assert run_correction_reminders(db, run_date=date(2026,11,6))["attempted"] == 0
    assert run_correction_reminders(db, run_date=date(2026,11,7))["accepted"] == 1
    assert run_correction_reminders(db, run_date=date(2026,11,7))["attempted"] == 0
    message = deliver.call_args.kwargs["Message"]["Body"]["Text"]["Data"]
    assert "10 Nov 2026" in message and "9618222220" in message
    assert run_correction_reminders(db, run_date=date(2026,11,8))["accepted"] == 1
    correction.status = "Pending"; db.commit()
    assert run_correction_reminders(db, run_date=date(2026,11,9))["attempted"] == 0
    assert deliver.call_count == 2


def test_reminders_exclude_other_tenants_and_past_deadlines(db, correction, monkeypatch):
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", True)
    deliver = Mock()
    monkeypatch.setattr("app.apps.interns_hub.confirmation_email.deliver_ses", deliver)
    assert run_correction_reminders(db, run_date=date(2026,11,11))["attempted"] == 0
    correction.organization_id = 99; db.commit()
    assert run_correction_reminders(db, run_date=date(2026,11,9))["attempted"] == 0
    deliver.assert_not_called()


def test_reminder_failure_is_not_automatically_resent(db, correction, monkeypatch):
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", True)
    deliver = Mock(side_effect=TimeoutError())
    monkeypatch.setattr("app.apps.interns_hub.confirmation_email.deliver_ses", deliver)
    assert run_correction_reminders(db, run_date=date(2026,11,9))["accepted"] == 0
    assert run_correction_reminders(db, run_date=date(2026,11,9))["attempted"] == 0
    assert deliver.call_count == 1


def test_reminder_scheduler_requires_secret(client):
    assert client.get("/api/v1/internal/intern-correction-reminders").status_code == 401


def test_correction_deadline_defaults_to_seven_days(client, superuser_headers, correction):
    response = client.post(f"/api/v1/interns-hub/admin/applications/{correction.id}/decision",
        json={"status": "Correction Requested", "review_note": "Update your college"}, headers=superuser_headers)
    assert response.status_code == 200
    assert response.json()["correction_deadline"] == str(today()+timedelta(days=7))


def test_scheduler_accepts_only_its_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "CRON_SECRET", "synthetic-cron-secret")
    monkeypatch.setattr(settings, "INTERN_HUB_SES_ENABLED", False)
    response = client.get("/api/v1/internal/intern-correction-reminders", headers={"Authorization": "Bearer synthetic-cron-secret"})
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
