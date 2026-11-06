from io import BytesIO
from decimal import Decimal
import httpx
import pytest
from pypdf import PdfReader
from app.models.payroll import PayrollRun, PayrollRecord, PayrollDeliveryProfile, PayrollPayoutAttempt, PayrollPaymentBatch
from tests.test_payslip_workflow import slips
from tests.payroll_test_utils import commit_payroll_fixture


def test_ytd_crosses_calendar_year_and_honors_company_policy(client, db, slips):
    run, record, admin, employee = slips
    for year, month, status in [(2026, 3, "locked"), (2026, 12, "paid"), (2027, 1, "locked"), (2026, 11, "calculated")]:
        other = PayrollRun(year=year, month=month, status=status, company_id=run.company_id)
        db.add(other); db.flush()
        db.add(PayrollRecord(payroll_run_id=other.id, employee_id=record.employee_id, gross_salary=50000, net_salary=45000, total_deductions=5000))
    commit_payroll_fixture(db)
    result = client.get("/api/v1/payroll/payslip?month=1&year=2027", headers=employee)
    assert result.status_code == 200, result.text
    assert result.json()["financial_year"] == "2026-27"
    assert result.json()["ytd"]["net_salary"] == 135000
    history = client.get("/api/v1/payroll/my-payslips", headers=employee).json()
    assert {row["financial_year"] for row in history} == {"2025-26", "2026-27"}
    changed = client.put("/api/v1/payroll/delivery/settings", json={"ytd_basis": "calendar"}, headers=admin)
    assert changed.status_code == 200, changed.text
    assert client.get("/api/v1/payroll/payslip?month=1&year=2027", headers=employee).json()["ytd"]["net_salary"] == 45000


def test_templates_preview_and_employee_permission(client, db, slips):
    run, record, admin, employee = slips
    response = client.put("/api/v1/payroll/delivery/settings", json={"regular_template": {
        "layout": "professional", "show_employee_code": False, "show_ytd": False, "footer": "Company payroll footer"}}, headers=admin)
    assert response.status_code == 200, response.text
    assert client.put("/api/v1/payroll/delivery/settings", json={}, headers=employee).status_code == 403
    assert client.get("/api/v1/payroll/delivery/settings", headers=employee).status_code == 403
    assert client.get("/api/v1/payroll/delivery/template-preview", headers=employee).status_code == 403
    preview = client.get("/api/v1/payroll/delivery/template-preview", headers=admin)
    assert preview.status_code == 200, preview.text
    text = " ".join(page.extract_text() for page in PdfReader(BytesIO(preview.content)).pages)
    assert "Company payroll footer" in text
    assert "SAMPLE-001" not in text
    assert "Year to date" not in text
    settlement = client.get("/api/v1/payroll/delivery/template-preview?kind=settlement", headers=admin)
    assert "Full & Final Settlement Statement" in PdfReader(BytesIO(settlement.content)).pages[0].extract_text()


def _payout_fixture(client, db, slips, mode="test"):
    run, record, admin, employee = slips
    record.employee.account_number = "123456789012"
    record.employee.ifsc_code = "HDFC0001234"
    db.commit()
    response = client.put("/api/v1/payroll/delivery/payout-connection", json={"key_id": f"rzp_{mode}_ABC12345", "key_secret": "a-test-only-secret", "debit_account": "2323232323", "mode": mode}, headers=admin)
    assert response.status_code == 200, response.text
    assert "a-test-only-secret" not in response.text
    profile = db.query(PayrollDeliveryProfile).one()
    assert "a-test-only-secret" not in profile.payout_secret_encrypted
    batch = client.post("/api/v1/payroll/payments/batches", json={"payroll_run_id": run.id}, headers=admin)
    assert batch.status_code == 201, batch.text
    return batch.json()["id"], admin, employee


@pytest.mark.parametrize("mode", ["test", "live"])
def test_payout_approval_reconciliation_and_duplicate_prevention(client, db, slips, monkeypatch, mode):
    from app.services import salary_payouts
    batch_id, admin, employee = _payout_fixture(client, db, slips, mode)
    endpoint = f"/api/v1/payroll/delivery/payouts/{batch_id}"
    payload = {"confirm_total": "45000", "confirm_mode": mode}
    assert client.post(endpoint + "/submit", json=payload, headers=admin).status_code == 409
    assert client.post(endpoint + "/approve", headers=employee).status_code == 403
    assert client.post(endpoint + "/approve", headers=admin).status_code == 200
    requests = []
    def provider(method, auth, path, **kwargs):
        requests.append((method, kwargs))
        request = kwargs.get("json") or db.query(PayrollPayoutAttempt).one().request_json
        return httpx.Response(200, request=httpx.Request(method, "https://api.razorpay.com/v1/" + path), json={
            "id": "pout_TEST123", "amount": request["amount"], "currency": "INR", "reference_id": request["reference_id"],
            "status": "processed" if method == "GET" else "processing", "utr": "UTR-TEST-123" if method == "GET" else None})
    monkeypatch.setattr(salary_payouts, "_request", provider)
    for _ in range(2):
        result = client.post(endpoint + "/submit", json=payload, headers=admin)
        assert result.status_code == 200, result.text
    assert len([call for call in requests if call[0] == "POST"]) == 1
    assert db.query(PayrollPayoutAttempt).count() == 1
    reconciled = client.post(endpoint + "/reconcile", headers=admin)
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["items"][0]["status"] == ("test_processed" if mode == "test" else "processed")
    batch = db.get(PayrollPaymentBatch, batch_id)
    assert batch.lines[0].payment_status == ("Pending" if mode == "test" else "Paid")


def test_uncertain_payout_retry_reuses_the_saved_idempotency_key(client, db, slips, monkeypatch):
    from app.services import salary_payouts
    batch_id, admin, employee = _payout_fixture(client, db, slips)
    endpoint = f"/api/v1/payroll/delivery/payouts/{batch_id}"
    assert client.post(endpoint + "/approve", headers=admin).status_code == 200
    keys = []
    def timeout(method, auth, path, **kwargs):
        keys.append(kwargs["headers"]["X-Payout-Idempotency"])
        raise httpx.ReadTimeout("Test timeout")
    monkeypatch.setattr(salary_payouts, "_request", timeout)
    for _ in range(2):
        result = client.post(endpoint + "/submit", json={"confirm_total": 45000, "confirm_mode": "test"}, headers=admin)
        assert result.status_code == 200, result.text
        assert result.json()["items"][0]["status"] == "unknown"
    assert len(keys) == 2 and keys[0] == keys[1]


def test_payout_totals_and_connection_modes_cannot_be_substituted(client, db, slips):
    batch_id, admin, employee = _payout_fixture(client, db, slips)
    endpoint = f"/api/v1/payroll/delivery/payouts/{batch_id}"
    assert client.post(endpoint + "/approve", headers=admin).status_code == 200
    assert client.post(endpoint + "/submit", json={"confirm_total": 1, "confirm_mode": "test"}, headers=admin).status_code == 409
    assert client.post(endpoint + "/submit", json={"confirm_total": 45000, "confirm_mode": "live"}, headers=admin).status_code == 409
    assert db.query(PayrollPayoutAttempt).count() == 0


def test_hr_can_manage_payslip_settings_without_superuser_access(client, slips):
    run, record, admin, employee = slips
    login = client.post("/api/v1/auth/login", json={"email": "hr@aihrms.com", "password": "HR@123456"})
    assert login.status_code == 200, login.text
    assert not login.json()["is_superuser"]
    hr = {"Authorization": f"Bearer {login.json()['access_token']}"}
    settings = client.get("/api/v1/payroll/delivery/settings", headers=hr)
    assert settings.status_code == 200, settings.text
    assert settings.json()["can_manage"]
    changed = client.put("/api/v1/payroll/delivery/settings", json={"ytd_basis": "financial", "regular_template": {"layout": "compact"}}, headers=hr)
    assert changed.status_code == 200, changed.text


def test_managed_hr_can_prepare_approve_and_submit_a_company_scoped_payout(client, db, slips, monkeypatch):
    from app.access.models import AccessPolicy
    from app.models.user import User
    from app.services import salary_payouts
    run, record, admin, employee = slips
    _payout_fixture(client, db, slips)
    hr_user = db.query(User).filter_by(email="hr@aihrms.com").one()
    policy = db.query(AccessPolicy).filter_by(user_id=hr_user.id, company_id=run.company_id).first()
    if not policy:
        policy = AccessPolicy(user_id=hr_user.id, company_id=run.company_id)
        db.add(policy)
    policy.status = "active"
    policy.grants = {"hrms": {"enabled": True, "role": "hr", "scope": "organization",
        "permissions": ["payroll_view", "payroll_run", "payroll_approve", "employee_view"],
        "actions": ["view", "create", "edit", "approve", "configure", "export"]}}
    db.commit()
    login = client.post("/api/v1/auth/login", json={"email": "hr@aihrms.com", "password": "HR@123456"})
    assert login.status_code == 200, login.text
    hr = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post("/api/v1/payroll/delivery/payment-batches", json={"payroll_run_id": run.id}, headers=hr)
    assert response.status_code == 201, response.text
    batch_id = response.json()["id"]
    endpoint = f"/api/v1/payroll/delivery/payouts/{batch_id}"
    assert client.post(endpoint + "/approve", headers=hr).status_code == 200
    def provider(method, auth, path, **kwargs):
        request = kwargs["json"]
        return httpx.Response(200, request=httpx.Request(method, "https://api.razorpay.com/v1/payouts"), json={
            "id": "pout_MANAGEDHR", "amount": request["amount"], "currency": "INR", "reference_id": request["reference_id"], "status": "processing"})
    monkeypatch.setattr(salary_payouts, "_request", provider)
    sent = client.post(endpoint + "/submit", json={"confirm_total": 45000, "confirm_mode": "test"}, headers=hr)
    assert sent.status_code == 200, sent.text
    assert len(sent.json()["items"]) == 1
    assert sent.json()["items"][0]["status"] == "test_processing"


def test_branding_upload_is_validated_and_used_in_pdf(client, slips):
    from PIL import Image
    run, record, admin, employee = slips
    stream = BytesIO()
    Image.new("RGB", (120, 40), "navy").save(stream, format="PNG")
    uploaded = client.post("/api/v1/payroll/delivery/branding/logo", files={"file": ("brand.png", stream.getvalue(), "image/png")}, headers=admin)
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["logo_available"]
    preview = client.get("/api/v1/payroll/delivery/template-preview", headers=admin)
    assert preview.status_code == 200
    assert "/XObject" in PdfReader(BytesIO(preview.content)).pages[0]["/Resources"]
    invalid = client.post("/api/v1/payroll/delivery/branding/signature", files={"file": ("not-image.png", b"<script>not an image</script>", "image/png")}, headers=admin)
    assert invalid.status_code == 422


def test_form16_rejects_invalid_year_unreviewed_publication_and_wrong_pan(client, db, slips):
    run, record, admin, employee = slips
    record.employee.pan_number = "ABCDE1234F"
    db.commit()
    assert client.post("/api/v1/hrms/form16/generate", json={"financialYear": "2026-99"}, headers=admin).status_code == 422
    generated = client.post("/api/v1/hrms/form16/generate", json={"financialYear": "2026-27", "employeeIds": [record.employee_id]}, headers=admin)
    assert generated.status_code == 200, generated.text
    record_id = generated.json()[0]["id"]
    assert client.post(f"/api/v1/hrms/form16/{record_id}/publish", headers=admin).status_code == 409
    assert client.get(f"/api/v1/hrms/form16/{record_id}/download", headers=employee).status_code == 403
    from reportlab.pdfgen import canvas
    data = BytesIO(); pdf = canvas.Canvas(data); pdf.drawString(40, 720, "WRONG1234F"); pdf.save()
    assert client.post(f"/api/v1/hrms/form16/{record_id}/upload-part-a", files={"file": ("part-a.pdf", data.getvalue(), "application/pdf")}, headers=admin).status_code == 422


def test_signature_verification_rejects_unsigned_or_replaced_documents(tmp_path):
    from tests.payroll_signing_utils import signing_material, sign_pdf
    from app.services.form16_signing import verify_signed_pdf
    from reportlab.pdfgen import canvas
    from fastapi import HTTPException
    data = BytesIO(); pdf = canvas.Canvas(data); pdf.drawString(40, 720, "Original employee certificate"); pdf.save()
    original = data.getvalue()
    pfx, pem = signing_material(tmp_path)
    with pytest.raises(HTTPException):
        verify_signed_pdf(original, original, pem.decode())
    signed = sign_pdf(original, pfx)
    evidence = verify_signed_pdf(signed, original, pem.decode())
    assert evidence["signatures"][0]["valid"]
    tampered = signed.replace(b"/ByteRange", b"/BiteRange", 1)
    assert tampered != signed
    with pytest.raises(HTTPException):
        verify_signed_pdf(tampered, original, pem.decode())


def test_failed_payout_retry_requires_provider_failure_and_preserves_audit(client, db, slips, monkeypatch):
    from app.services import salary_payouts
    from app.access.models import AccessAudit
    batch_id, admin, employee = _payout_fixture(client, db, slips)
    endpoint = f"/api/v1/payroll/delivery/payouts/{batch_id}"
    confirmation = {"confirm_total": 45000, "confirm_mode": "test"}
    assert client.post(endpoint + "/approve", headers=admin).status_code == 200
    sent_keys = []
    provider_status = "processing"
    def provider(method, auth, path, **kwargs):
        if method == "POST":
            sent_keys.append(kwargs["headers"]["X-Payout-Idempotency"])
        attempt = db.query(PayrollPayoutAttempt).one()
        request = kwargs.get("json") or attempt.request_json
        return httpx.Response(200, request=httpx.Request(method, "https://api.razorpay.com/v1/" + path), json={
            "id": "pout_FAILEDRETRY", "amount": request["amount"], "currency": "INR", "reference_id": request["reference_id"], "status": provider_status})
    monkeypatch.setattr(salary_payouts, "_request", provider)
    result = client.post(endpoint + "/submit", json=confirmation, headers=admin)
    assert result.status_code == 200, result.text
    attempt_id = result.json()["items"][0]["id"]
    retry_url = endpoint + f"/attempts/{attempt_id}/prepare-retry"
    assert client.post(retry_url, json=confirmation, headers=admin).status_code == 409
    original_key = db.query(PayrollPayoutAttempt).one().idempotency_key
    provider_status = "failed"
    retried = client.post(retry_url, json=confirmation, headers=admin)
    assert retried.status_code == 200, retried.text
    attempt = db.query(PayrollPayoutAttempt).one()
    assert attempt.idempotency_key != original_key
    assert attempt.provider_id is None
    audit = db.query(AccessAudit).filter_by(operation="salary_payout_retry_prepared").one()
    assert audit.before_json["provider_id"] == "pout_FAILEDRETRY"
    assert audit.before_json["idempotency_key"] == original_key
    assert audit.after_json["idempotency_key"] == attempt.idempotency_key


def test_payout_connection_change_cannot_replay_an_uncertain_transfer(client, db, slips, monkeypatch):
    from app.services import salary_payouts
    batch_id, admin, employee = _payout_fixture(client, db, slips)
    endpoint = f"/api/v1/payroll/delivery/payouts/{batch_id}"
    confirmation = {"confirm_total": 45000, "confirm_mode": "test"}
    assert client.post(endpoint + "/approve", headers=admin).status_code == 200
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("Test timeout")
    monkeypatch.setattr(salary_payouts, "_request", timeout)
    assert client.post(endpoint + "/submit", json=confirmation, headers=admin).status_code == 200
    changed = client.put("/api/v1/payroll/delivery/payout-connection", json={"key_id": "rzp_test_OTHER123", "key_secret": "different-test-secret", "debit_account": "2323232323", "mode": "test"}, headers=admin)
    assert changed.status_code == 200
    assert client.post(endpoint + "/submit", json=confirmation, headers=admin).status_code == 409
    assert db.query(PayrollPayoutAttempt).count() == 1
