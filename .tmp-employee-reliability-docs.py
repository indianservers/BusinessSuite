from pathlib import Path
p=Path('backend/app/services/employee_profile_reliability.py');s=p.read_text(encoding='utf-8').replace('EmployeeSkill, EmployeeCertification','EmployeeSkill, EmployeeCertification, EmployeeDocument').replace('EmployeeSkill, EmployeeCertification)','EmployeeSkill, EmployeeCertification, EmployeeDocument)');p.write_text(s,encoding='utf-8')
p=Path('backend/app/api/v1/employees.py');s=p.read_text(encoding='utf-8');s=s.replace('async def upload_document(\n    employee_id: int,','async def upload_document(\n    employee_id: int,\n    request: Request,');a=s.index('async def upload_document(');b=s.index('@router.put("/{employee_id}/documents/',a);block=s[a:b]
needle='    # Validate file type'
parse='''    employee = lock_profile(db, employee_id, request.headers.get("If-Match"))
    try:
        parsed_expiry_date = _parse_date(expiry_date, 0, "expiry_date") if expiry_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="expiry_date must be YYYY-MM-DD")
'''
block=block.replace(needle,parse+needle)
a2=block.index('    try:\n        parsed_expiry_date', block.index('    persist_file'))
b2=block.index('    return crud_employee.add_document',a2);block=block[:a2]+block[b2:]
block=block.replace('    return crud_employee.add_document(db, employee_id, {','    values = {').replace('        "expiry_date": parsed_expiry_date,\n    })','''        "expiry_date": parsed_expiry_date,
    }
    record = EmployeeDocument(employee_id=employee_id, **values)
    db.add(record); db.flush()
    audit_record(db, employee, record, values, current_user, "created")
    db.commit(); db.refresh(record)
    return record''')
s=s[:a]+block+s[b:]
a=s.index('def verify_employee_document(');block=s[a:];block=block.replace('    document = db.query(EmployeeDocument)', '    employee = lock_profile(db, employee_id)\n    document = db.query(EmployeeDocument)',1).replace('    document.verification_status = data.verification_status', '    audit_record(db, employee, document, data.model_dump(), current_user, "updated")\n    document.verification_status = data.verification_status',1);s=s[:a]+block;p.write_text(s,encoding='utf-8')
