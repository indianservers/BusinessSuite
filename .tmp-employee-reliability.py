from pathlib import Path
p=Path('backend/app/core/hr_audit.py');s=p.read_text(encoding='utf-8');s=s.replace('    for field in AUDITED_EMPLOYEE_FIELDS:', '''    # Audit the full saved profile; secrets and raw document links are never retained.
    fields = set(incoming) & {column.name for column in Employee.__table__.columns}
    fields -= {"id", "created_at", "updated_at", "deleted_at", "deleted_by"}
    for field in fields:''');s=s.replace('    return _stringify(value)\n\n\ndef record_field_audit', '''    if field_name not in PLAINTEXT_ALLOWED_FIELDS and field_name not in {"first_name", "middle_name", "last_name", "degree", "institution", "board_university", "specialization", "pass_year", "percentage_cgpa", "company_name", "designation", "from_date", "to_date", "is_current", "skill_name", "proficiency", "years_experience", "certification_name", "issuing_body", "certification_type", "issue_date", "expiry_date", "is_renewable", "score_grade"}:
        return "Changed (private)"
    return _stringify(value)


def record_field_audit''');p.write_text(s,encoding='utf-8')
p=Path('backend/app/schemas/employee.py');s=p.read_text(encoding='utf-8').replace('class EmployeeCreate(EmployeeBase):','class EmployeeCreate(EmployeeBase):\n    allow_contact_duplicate: bool = False').replace('class EmployeeUpdate(BaseModel):','class EmployeeUpdate(BaseModel):\n    allow_contact_duplicate: bool = False').replace('class EmployeeSchema(EmployeeBase):','class EmployeeSchema(EmployeeBase):\n    profile_version: Optional[str] = None\n    can_edit_profile: bool = False');p.write_text(s,encoding='utf-8')
p=Path('backend/app/core/masking.py');s=p.read_text(encoding='utf-8').replace('    data = EmployeeSchema.model_validate(employee).model_dump()','''    data = EmployeeSchema.model_validate(employee).model_dump()
    from sqlalchemy.orm import object_session
    from app.services.employee_profile_reliability import profile_version
    if object_session(employee): data['profile_version'] = profile_version(object_session(employee), employee)
    data['can_edit_profile'] = user_has_permission(user, 'employee_update')''');p.write_text(s,encoding='utf-8')
p=Path('backend/app/crud/crud_employee.py');s=p.read_text(encoding='utf-8').replace('"employee_id", "custom_fields"}', '"employee_id", "custom_fields", "allow_contact_duplicate"}');p.write_text(s,encoding='utf-8')
p=Path('backend/app/api/v1/employees.py');s=p.read_text(encoding='utf-8').replace('from fastapi import APIRouter,','from fastapi import Request, APIRouter,');s=s.replace('from app.core.employee_scope import employee_tenant_scope, validate_employee_links','''from app.core.employee_scope import employee_tenant_scope, validate_employee_links
from app.services.employee_profile_reliability import lock_profile, profile_version, audit_record, check_duplicates, duplicate_matches, history, touch''')
s=s.replace('    if data.employee_id and crud_employee.get_by_employee_id(db, data.employee_id):','    check_duplicates(db, data.model_dump(), allow_contact_duplicate=data.allow_contact_duplicate)\n    if data.employee_id and crud_employee.get_by_employee_id(db, data.employee_id):')
# Scoped routes precede /{employee_id}.
pos=s.index('@router.get("/{employee_id}", response_model=EmployeeSchema)')
s=s[:pos]+'''@router.get("/{employee_id}/history")
def employee_profile_history(employee_id: int, db: Session = Depends(get_db), user: User = Depends(RequirePermission("employee_update"))):
    _profile_employee(db, employee_id)
    return {"items": history(db, employee_id)}


@router.post("/duplicate-check")
def employee_duplicate_check(data: dict, db: Session = Depends(get_db), user: User = Depends(RequirePermission("employee_create", "employee_update"))):
    matches = duplicate_matches(db, data, data.get("exclude_id"))
    return {"items": [{"id": e.id, "employee_code": e.employee_id} for e in matches]}


'''+s[pos:]
s=s.replace('    data: EmployeeUpdate,\n    db:', '    data: EmployeeUpdate,\n    request: Request,\n    db:')
start=s.index('def update_employee(');end=s.index('@router.get("/{employee_id}/lifecycle"',start);block=s[start:end]
a=block.index('    emp = db.query(Employee)');b=block.index('    values = ',a)
block=block[:a]+'''    emp = lock_profile(db, employee_id, request.headers.get("If-Match"))
'''+block[b:]
block=block.replace('    from app.services.employee_custom_fields import save as save_custom_fields', '''    allow_duplicate = values.pop("allow_contact_duplicate", False)
    if {"personal_email", "work_email", "phone_number", "phone_number_country_code"}.intersection(values):
        check_duplicates(db, {**{k: getattr(emp,k) for k in ("personal_email","work_email","phone_number","phone_number_country_code")}, **values}, employee_id, allow_duplicate)
    from app.services.employee_custom_fields import save as save_custom_fields''')
block=block.replace('    updated = crud_employee.update','    touch(emp)\n    updated = crud_employee.update')
s=s[:start]+block+s[end:]
start=s.index('@router.post("/{employee_id}/education"');end=s.index('# ── Documents',start);block=s[start:end]
import re
block=block.replace('data: EmployeeEducationCreate, db:', 'data: EmployeeEducationCreate, request: Request, db:').replace('data: EmployeeExperienceCreate, db:', 'data: EmployeeExperienceCreate, request: Request, db:').replace('data: EmployeeSkillCreate, db:', 'data: EmployeeSkillCreate, request: Request, db:').replace('data: EmployeeCertificationCreate, db:', 'data: EmployeeCertificationCreate, request: Request, db:').replace('record_id: int, db:', 'record_id: int, request: Request, db:')
block=block.replace('    _profile_employee(db, employee_id)','    employee = lock_profile(db, employee_id, request.headers.get("If-Match"))')
block=block.replace('    record = _profile_record', '    employee = lock_profile(db, employee_id, request.headers.get("If-Match"))\n    record = _profile_record')
block=block.replace('    db.add(record)\n    db.commit()', '''    db.add(record)
    db.flush()
    audit_record(db, employee, record, data.model_dump(), current_user, "created")
    db.commit()''')
block=block.replace('    for key, value in data.model_dump(exclude_unset=True).items():', '''    audit_record(db, employee, record, data.model_dump(exclude_unset=True), current_user, "updated")
    for key, value in data.model_dump(exclude_unset=True).items():''')
block=block.replace('    db.delete(record)', '    audit_record(db, employee, record, {}, current_user, "deleted")\n    db.delete(record)')
s=s[:start]+block+s[end:]
# Include relational skills in directory filtering, rather than obsolete free-text tags alone.
s=s.replace('query = query.filter(Employee.skills_tags.ilike(f"%{skills.strip()}%"))', 'query = query.filter(or_(Employee.skills_tags.ilike(f"%{skills.strip()}%"), Employee.skills.any(EmployeeSkill.skill_name.ilike(f"%{skills.strip()}%"))))')
p.write_text(s,encoding='utf-8')
