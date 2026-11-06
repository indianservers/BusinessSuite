"""RazorpayX composite payouts with durable idempotency and reconciliation."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import uuid
import re
import httpx
from fastapi import HTTPException
from sqlalchemy import update
from app.models.employee import Employee
from app.models.payroll import PayrollRecord, PayrollPaymentLine, PayrollPayoutAttempt
from app.services.payroll_delivery import profile_for


def validate_batch(db, batch):
    from app.crud.crud_payroll import normalize_payroll_run_status
    run = batch.payroll_run
    if run.deleted_at or normalize_payroll_run_status(run.status) not in {"locked", "paid"}:
        raise HTTPException(409, "Lock payroll before approving salary payouts")
    if not batch.lines:
        raise HTTPException(422, "A direct payout batch must contain employees")
    total = Decimal("0")
    for line in batch.lines:
        record = db.query(PayrollRecord).filter_by(id=line.payroll_record_id, payroll_run_id=run.id, employee_id=line.employee_id).first()
        employee = db.query(Employee).filter_by(id=line.employee_id).first()
        if not record or not employee or not employee.branch or employee.branch.company_id != run.company_id:
            raise HTTPException(422, "Payment employee and payroll company must match")
        if (record.converted_currency or "INR") != "INR":
            raise HTTPException(422, "RazorpayX salary payouts require INR payroll")
        if line.net_amount <= 0 or line.net_amount != record.net_salary:
            raise HTTPException(422, "Payment amounts must match positive finalized net salaries")
        if not line.bank_account or not line.ifsc or line.bank_account != employee.account_number or line.ifsc != employee.ifsc_code:
            raise HTTPException(422, "Payment bank details must match the employee profile; regenerate the batch after a correction")
        if not re.fullmatch(r"\d{9,18}", line.bank_account) or not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", line.ifsc):
            raise HTTPException(422, "Validate employee bank account numbers and IFSC codes before payout approval")
        if db.query(PayrollPaymentLine.id).filter(PayrollPaymentLine.payroll_record_id == record.id,
                PayrollPaymentLine.batch_id != batch.id,
                PayrollPaymentLine.payment_status == "Paid").first():
            raise HTTPException(409, "A salary in this batch is already confirmed paid")
        total += line.net_amount
    if total != batch.total_amount:
        raise HTTPException(409, "Payment batch total no longer matches its employee lines")


def _connection(db, batch):
    from app.api.v1.payroll_delivery import cipher
    profile = profile_for(db, batch.payroll_run.company_id)
    if not profile or not profile.payout_key_id or not profile.payout_secret_encrypted or not profile.payout_account:
        raise HTTPException(409, "Configure a RazorpayX payout connection for this payroll company")
    if not profile.payout_key_id.startswith(f"rzp_{profile.payout_mode}_"):
        raise HTTPException(409, "Payout key and connection mode do not match")
    try:
        secret = cipher().decrypt(profile.payout_secret_encrypted.encode()).decode()
    except Exception:
        raise HTTPException(409, "Reconnect the payout provider; its credentials cannot be decrypted") from None
    return profile, (profile.payout_key_id, secret)


def _request(method, auth, path, **kwargs):
    # Provider host is fixed. Neither HR input nor webhook data can redirect credentials.
    with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
        return client.request(method, "https://api.razorpay.com/v1/" + path, auth=auth, **kwargs)


def _fingerprint(request, key_id):
    return hashlib.sha256((key_id + ":" + json.dumps(request, sort_keys=True)).encode()).hexdigest()


def _apply_response(db, attempt, data):
    expected = attempt.request_json
    if data.get("amount") != expected["amount"] or data.get("currency") != "INR" or data.get("reference_id") != expected["reference_id"]:
        raise ValueError("Provider response does not match the salary request")
    payout_id = data.get("id", "")
    if not payout_id.startswith("pout_") or (attempt.provider_id and attempt.provider_id != payout_id):
        raise ValueError("Provider payout identity mismatch")
    attempt.provider_id = payout_id
    status = data.get("status", "unknown")
    if status not in {"queued", "pending", "processing", "processed", "failed", "reversed", "rejected", "cancelled"}:
        raise ValueError("Unrecognized provider payout status")
    attempt.status = f"test_{status}" if attempt.mode == "test" else status
    attempt.utr = data.get("utr")
    attempt.error = "Provider rejected or reversed this payout. Review the provider dashboard." if status in {"failed", "reversed", "rejected", "cancelled"} else None
    if attempt.mode == "live":
        line = db.query(PayrollPaymentLine).filter_by(batch_id=attempt.batch_id, payroll_record_id=attempt.payroll_record_id).one()
        if status == "processed" and attempt.utr:
            line.payment_status, line.utr_number, line.paid_at = "Paid", attempt.utr, datetime.now(timezone.utc)
        elif status in {"failed", "rejected", "cancelled", "reversed"}:
            line.payment_status, line.failure_reason = ("Reversed" if status == "reversed" else "Failed"), attempt.error
        elif line.payment_status != "Paid":
            line.payment_status = "Processing"


def _update_batch(db, batch):
    attempts = db.query(PayrollPayoutAttempt).filter_by(batch_id=batch.id).all()
    mode = "live" if any(a.mode == "live" for a in attempts) else "test"
    attempts = [a for a in attempts if a.mode == mode]
    if len(attempts) != len(batch.lines):
        batch.status = "Processing"
    elif all(a.status == "test_processed" for a in attempts):
        batch.status = "Test completed"
    elif all(line.payment_status == "Paid" for line in batch.lines):
        batch.status, batch.released_at = "Paid", datetime.now(timezone.utc)
    elif any(a.status.removeprefix("test_") in {"failed", "reversed", "rejected", "cancelled"} for a in attempts):
        batch.status = "Partially Failed"
    else:
        batch.status = "Processing"


def submit_batch(db, batch, confirmed_total, confirmed_mode, user):
    if not batch.approved_by or batch.status not in {"Approved", "Processing", "Partially Failed", "Test completed"}:
        raise HTTPException(409, "Approve this payment batch before sending it")
    validate_batch(db, batch)
    profile, auth = _connection(db, batch)
    if confirmed_total != batch.total_amount or confirmed_mode != profile.payout_mode:
        raise HTTPException(409, "Confirm the current batch total and provider mode")
    from app.services.payroll_delivery import audit_delivery
    sent = 0
    for line in batch.lines:
        attempt = db.query(PayrollPayoutAttempt).filter_by(payroll_record_id=line.payroll_record_id, mode=profile.payout_mode).first()
        if attempt and attempt.batch_id != batch.id:
            raise HTTPException(409, "A payout attempt already exists for this salary; reconcile its original batch")
        if not attempt:
            employee = db.get(Employee, line.employee_id)
            request = {"account_number": profile.payout_account, "amount": int(line.net_amount * 100), "currency": "INR", "mode": "NEFT", "purpose": "salary",
                "queue_if_low_balance": True, "reference_id": f"salary-{line.payroll_record_id}", "narration": "Salary payment",
                "fund_account": {"account_type": "bank_account", "bank_account": {"name": f"{employee.first_name} {employee.last_name or ''}".strip(),
                    "ifsc": line.ifsc, "account_number": line.bank_account}, "contact": {"name": f"{employee.first_name} {employee.last_name or ''}".strip(),
                    "type": "employee", "reference_id": str(employee.id)}}}
            attempt = PayrollPayoutAttempt(company_id=batch.payroll_run.company_id, employee_id=line.employee_id, batch_id=batch.id, payroll_record_id=line.payroll_record_id, mode=profile.payout_mode,
                idempotency_key=str(uuid.uuid4()), request_hash=_fingerprint(request, profile.payout_key_id),
                request_json=request, status="prepared", created_by=user.id)
            db.add(attempt)
            db.commit()  # Persist the key and immutable request before contacting the provider.
        if attempt.mode != profile.payout_mode or attempt.request_json["account_number"] != profile.payout_account:
            raise HTTPException(409, "Existing payout attempts must use their original provider account and mode")
        if attempt.request_hash != _fingerprint(attempt.request_json, profile.payout_key_id):
            raise HTTPException(409, "Restore the original API key before retrying this payout")
        if attempt.provider_id:
            continue  # A response exists; refresh from provider instead of issuing another transfer.
        if sent >= 5:
            break
        now = datetime.now(timezone.utc)
        claimed = db.execute(update(PayrollPayoutAttempt).where(PayrollPayoutAttempt.id == attempt.id,
            (PayrollPayoutAttempt.lease_until.is_(None)) | (PayrollPayoutAttempt.lease_until < now)).values(
                status="submitting", lease_until=now + timedelta(minutes=2))).rowcount
        db.commit()
        if not claimed:
            continue
        sent += 1
        try:
            response = _request("POST", auth, "payouts", json=attempt.request_json, headers={"X-Payout-Idempotency": attempt.idempotency_key})
            response.raise_for_status()
            _apply_response(db, attempt, response.json())
        except (httpx.HTTPError, ValueError, KeyError):
            attempt.status, attempt.error = "unknown", "Provider outcome is uncertain. Retry with the same saved request; do not create another payment."
        finally:
            attempt.lease_until = None
        audit_delivery(db, user, batch.payroll_run.company_id, "salary_payout_submitted", f"attempt={attempt.id}:mode={attempt.mode}:status={attempt.status}")
        db.commit()
    _update_batch(db, batch)
    db.commit()


def reconcile_batch(db, batch, user):
    profile, auth = _connection(db, batch)
    attempts = db.query(PayrollPayoutAttempt).filter_by(batch_id=batch.id, mode=profile.payout_mode).all()
    for attempt in attempts:
        if not attempt.provider_id:
            continue
        if profile.payout_mode != attempt.mode:
            raise HTTPException(409, "Restore the original provider mode before reconciling this batch")
        if attempt.request_hash != _fingerprint(attempt.request_json, profile.payout_key_id):
            raise HTTPException(409, "Restore the original API key before reconciling this payout")
        try:
            response = _request("GET", auth, "payouts/" + attempt.provider_id)
            response.raise_for_status()
            _apply_response(db, attempt, response.json())
        except (httpx.HTTPError, ValueError, KeyError):
            attempt.error = "Could not verify the current provider status. Retry reconciliation."
    _update_batch(db, batch)
    from app.services.payroll_delivery import audit_delivery
    audit_delivery(db, user, batch.payroll_run.company_id, "salary_payout_reconciled", f"batch={batch.id}:status={batch.status}")
    db.commit()


def prepare_failed_retry(db, batch, attempt_id, confirmed_total, confirmed_mode, user):
    profile, auth = _connection(db, batch)
    if confirmed_total != batch.total_amount or confirmed_mode != profile.payout_mode:
        raise HTTPException(409, "Confirm the current batch total and provider mode before reviewing a retry")
    attempt = db.query(PayrollPayoutAttempt).filter_by(id=attempt_id, batch_id=batch.id, mode=profile.payout_mode).with_for_update().first()
    if not attempt or not attempt.provider_id:
        raise HTTPException(409, "Only a provider-confirmed failed payout can receive a new payment key")
    if attempt.request_hash != _fingerprint(attempt.request_json, profile.payout_key_id):
        raise HTTPException(409, "Restore this payout's original provider connection")
    try:
        response = _request("GET", auth, "payouts/" + attempt.provider_id)
        response.raise_for_status()
        data = response.json()
        _apply_response(db, attempt, data)
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(502, "Could not verify the previous payout outcome; no retry was prepared") from None
    if data["status"] not in {"failed", "reversed", "rejected", "cancelled"}:
        raise HTTPException(409, "The provider has not confirmed failure or reversal. Refresh its status; do not issue another transfer")
    previous = {"provider_id": attempt.provider_id, "idempotency_key": attempt.idempotency_key, "status": attempt.status, "request_hash": attempt.request_hash, "utr": attempt.utr}
    line = db.query(PayrollPaymentLine).filter_by(batch_id=batch.id, payroll_record_id=attempt.payroll_record_id).one()
    employee = db.get(Employee, line.employee_id)
    line.bank_account, line.ifsc = employee.account_number, employee.ifsc_code
    line.payment_status, line.failure_reason, line.utr_number, line.paid_at = "Pending", None, None, None
    validate_batch(db, batch)
    request = json.loads(json.dumps(attempt.request_json))
    request["fund_account"]["bank_account"] = {"name": f"{employee.first_name} {employee.last_name or ''}".strip(), "ifsc": line.ifsc, "account_number": line.bank_account}
    attempt.request_json, attempt.idempotency_key = request, str(uuid.uuid4())
    attempt.request_hash = _fingerprint(request, profile.payout_key_id)
    attempt.provider_id = attempt.utr = attempt.error = attempt.lease_until = None
    attempt.status = "prepared"
    batch.status, batch.approved_by = "Approved", user.id
    from app.services.payroll_delivery import audit_delivery
    audit_delivery(db, user, batch.payroll_run.company_id, "salary_payout_retry_prepared", f"Reviewed retry for salary record {attempt.payroll_record_id}",
        before=previous, after={"idempotency_key": attempt.idempotency_key, "request_hash": attempt.request_hash})
    db.commit()
