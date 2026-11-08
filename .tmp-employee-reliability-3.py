from pathlib import Path
p=Path('backend/app/api/v1/employees.py');s=p.read_text(encoding='utf-8');pos=s.index('@router.get("/{employee_id}/history")');s=s[:pos]+'''@router.get("/{employee_id}/profile-checks")
def employee_profile_checks(employee_id: int, days: int = Query(90, ge=1, le=90), db: Session = Depends(get_db), user: User = Depends(RequirePermission("employee_update"))):
    from app.services.employee_profile_reliability import profile_checks
    return profile_checks(db, _profile_employee(db, employee_id), user, days)


'''+s[pos:];s=s.replace('        _apply_profile_change(db, employee, changes)','        record_employee_field_changes(db, employee, changes, current_user.id, "Approved profile change request")\n        touch(employee)\n        _apply_profile_change(db, employee, changes)')
p.write_text(s,encoding='utf-8')
p=Path('backend/app/common/services/profiles.py');s=p.read_text(encoding='utf-8').replace('    if direct:\n        apply_values(db, user, direct, employee)', '''    if direct:
        if employee:
            from app.core.hr_audit import record_employee_field_changes
            from app.services.employee_profile_reliability import check_duplicates, touch
            contacts = {k:v for k,v in direct.items() if k in {"personal_email","work_email","phone_number","phone_number_country_code"}}
            if contacts: check_duplicates(db, contacts, employee.id)
            record_employee_field_changes(db, employee, direct, actor.id, reason)
            touch(employee)
        apply_values(db, user, direct, employee)''');p.write_text(s,encoding='utf-8')
# Add actionable certification reminders to the existing overview; these are in-app alerts, not email sends.
p=Path('backend/app/services/employee360.py');s=p.read_text(encoding='utf-8');at=s.index('    verification_allowed =');s=s[:at]+'''    from app.models.employee import EmployeeCertification
    from datetime import timedelta
    due_certificates = db.query(EmployeeCertification).filter(EmployeeCertification.employee_id==employee.id,
        EmployeeCertification.expiry_date.isnot(None), EmployeeCertification.expiry_date<=date.today()+timedelta(days=90)).all()
    for certificate in due_certificates:
        days_left=(certificate.expiry_date-date.today()).days
        action(f"certification-{certificate.id}", f"{certificate.certification_name}: " + ("expired" if days_left<0 else f"expires in {days_left} days"), "certifications", "Employee / HR")

'''+s[at:];p.write_text(s,encoding='utf-8')
