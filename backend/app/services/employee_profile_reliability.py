"""Employee profile consistency, duplicate checks and private field history."""
import hashlib
import json
import re
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func, or_, text, select
from app.models.employee import Employee, EmployeeEducation, EmployeeExperience, EmployeeSkill, EmployeeCertification, EmployeeDocument
from app.models.audit import FieldAuditEvent
from app.core.hr_audit import record_field_audit

RECORDS = (EmployeeEducation, EmployeeExperience, EmployeeSkill, EmployeeCertification, EmployeeDocument)


def profile_version(db, employee):
    snapshot = {c.name: getattr(employee, c.name) for c in Employee.__table__.columns}
    for model in RECORDS:
        rows = db.query(model).filter(model.employee_id == employee.id).populate_existing().order_by(model.id).all()
        snapshot[model.__tablename__] = [{c.name: getattr(row, c.name) for c in model.__table__.columns} for row in rows]
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()


def lock_profile(db, employee_id, expected=None):
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).populate_existing().with_for_update().first()
    if not employee:
        raise HTTPException(404, 'Employee not found')
    if expected and expected.strip('"') != profile_version(db, employee):
        raise HTTPException(409, 'This employee profile changed after you opened it. Your draft is retained. Reload the latest profile before saving again.')
    return employee


def touch(employee):
    employee.updated_at = datetime.now(timezone.utc)


def audit_record(db, employee, record, values, actor, action):
    fields = {c.name for c in record.__table__.columns} - {'id', 'employee_id', 'created_at'}
    for field in sorted(fields):
        before = None if action == 'created' else getattr(record, field, None)
        after = None if action == 'deleted' else values.get(field, before)
        record_field_audit(db, module='employee', entity_type=record.__tablename__, entity_id=record.id or employee.id,
            employee_id=employee.id, field_name=field, old_value=before, new_value=after, actor_user_id=actor.id, action=action)
    touch(employee)


def duplicate_matches(db, values, exclude_id=None):
    conditions = []
    for field in ('personal_email', 'work_email'):
        value = values.get(field)
        if value and value.strip():
            normalized = value.strip().lower()
            conditions += [func.lower(func.trim(Employee.personal_email)) == normalized, func.lower(func.trim(Employee.work_email)) == normalized]
    phone = re.sub(r'\D', '', values.get('phone_number') or '')
    if phone:
        # Persisted national numbers are validated digits. Normalize historical punctuation too.
        column = Employee.phone_number
        for char in (' ', '-', '(', ')', '+', '.'):
            column = func.replace(column, char, '')
        code = values.get('phone_number_country_code')
        conditions.append((column == phone) & (Employee.phone_number_country_code == code if code else True))
    code = values.get('employee_id')
    if code:
        conditions.append(func.lower(Employee.employee_id) == code.strip().lower())
    if not conditions:
        return []
    query = db.query(Employee).filter(Employee.deleted_at.is_(None), or_(*conditions))
    if exclude_id:
        query = query.filter(Employee.id != exclude_id)
    return query.order_by(Employee.id).limit(10).all()


def check_duplicates(db, values, exclude_id=None, allow_contact_duplicate=False):
    # Serialize contact checks across simultaneous creates without locking unrelated employees.
    keys = [str(values.get(k) or '').strip().lower() for k in ('personal_email', 'work_email', 'phone_number', 'employee_id')]
    if db.bind.dialect.name == 'postgresql':
        for key in sorted(set(filter(None, keys))):
            lock = int.from_bytes(hashlib.sha256(('employee-contact:' + key).encode()).digest()[:8], 'big', signed=True)
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})
    if values.get('employee_id'):
        table=Employee.__table__
        statement=select(table.c.id).where(func.lower(table.c.employee_id)==values['employee_id'].strip().lower())
        if exclude_id: statement=statement.where(table.c.id!=exclude_id)
        if db.connection().execute(statement.limit(1)).first():
            raise HTTPException(409, 'Employee code already exists')
    matches = duplicate_matches(db, values, exclude_id)
    if matches and not allow_contact_duplicate:
        raise HTTPException(409, 'Possible duplicate employee contact details or employee code. Review matching profiles before saving. Confirm a shared contact only when intentional.')
    if allow_contact_duplicate and values.get('employee_id') and any(e.employee_id.lower() == values['employee_id'].strip().lower() for e in matches):
        raise HTTPException(409, 'Employee code already exists')
    return matches


def history(db, employee_id):
    rows = db.query(FieldAuditEvent).filter(FieldAuditEvent.employee_id == employee_id).order_by(FieldAuditEvent.id.desc()).limit(200).all()
    # The profile history never returns raw private values, hashes, or document URLs.
    private = {'personal_email', 'work_email', 'phone_number', 'alternate_phone', 'emergency_contact_number', 'present_address', 'permanent_address', 'family_information', 'health_information', 'document_url', 'verification_url', 'relieving_letter_url', 'responsibilities', 'bio'}
    return [{'id': r.id, 'entity': r.entity_type, 'field': r.field_name, 'action': r.action,
             'before': ('Changed (private)' if r.old_value_hash else None) if r.is_sensitive or r.field_name in private else r.old_value_masked,
             'after': ('Changed (private)' if r.new_value_hash else None) if r.is_sensitive or r.field_name in private else r.new_value_masked,
             'actor_id': r.actor_user_id, 'at': r.created_at} for r in rows]

def profile_checks(db, employee, user, days=90):
    from datetime import date, timedelta
    from app.models.employee import EmployeeDocument, EmployeeChangeRequest, EmployeeLifecycleEvent
    from app.models.onboarding import EmployeeOnboarding, EmployeeOnboardingTask, OnboardingTemplateTask
    from app.core.masking import can_view_sensitive_employee
    today = date.today()
    certifications = db.query(EmployeeCertification).filter(EmployeeCertification.employee_id == employee.id, EmployeeCertification.expiry_date.isnot(None), EmployeeCertification.expiry_date <= today + timedelta(days=days)).order_by(EmployeeCertification.expiry_date).all()
    result = {'as_of': today, 'certifications': [{'id': r.id, 'name': r.certification_name, 'expires': r.expiry_date, 'days_left': (r.expiry_date-today).days, 'status': 'Expired' if r.expiry_date < today else 'Expires today' if r.expiry_date == today else 'Due within 30 days' if r.expiry_date <= today+timedelta(days=30) else 'Due within 60 days' if r.expiry_date <= today+timedelta(days=60) else 'Due within 90 days'} for r in certifications], 'documents': [], 'mandatory_tasks': []}
    if can_view_sensitive_employee(user, employee.id):
        documents = db.query(EmployeeDocument).filter_by(employee_id=employee.id).all()
        result['documents'] = [{'id': r.id, 'name': r.document_name or r.document_type, 'status': r.verification_status or ('Verified' if r.is_verified else 'Pending'), 'expired': bool(r.expiry_date and r.expiry_date < today)} for r in documents]
    tasks = db.query(EmployeeOnboardingTask).join(EmployeeOnboarding).join(OnboardingTemplateTask, EmployeeOnboardingTask.template_task_id == OnboardingTemplateTask.id).filter(EmployeeOnboarding.employee_id==employee.id, EmployeeOnboarding.status.notin_(['cancelled','completed']), EmployeeOnboardingTask.status!='completed', OnboardingTemplateTask.is_mandatory.is_(True)).all()
    result['mandatory_tasks'] = [{'id': t.id, 'name': t.task_name, 'due': t.due_date} for t in tasks]
    result['pending_requests'] = db.query(EmployeeChangeRequest).filter_by(employee_id=employee.id, status='Pending').count()
    events = db.query(EmployeeLifecycleEvent).filter(EmployeeLifecycleEvent.employee_id==employee.id, EmployeeLifecycleEvent.event_type=='Scheduled transfer').order_by(EmployeeLifecycleEvent.effective_from).all()
    result['scheduled_transfers'] = [{'id': e.id, 'effective': e.effective_from, 'status': 'Ready to apply' if e.effective_from and e.effective_from<=today else 'Scheduled'} for e in events]
    return result
