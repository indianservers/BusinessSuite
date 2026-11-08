from pathlib import Path
p=Path('backend/app/services/employee_profile_reliability.py');s=p.read_text(encoding='utf-8').replace('from sqlalchemy import func, or_, text','from sqlalchemy import func, or_, text, select');needle='    matches = duplicate_matches(db, values, exclude_id)';s=s.replace(needle,'''    if values.get('employee_id'):
        table=Employee.__table__
        statement=select(table.c.id).where(func.lower(table.c.employee_id)==values['employee_id'].strip().lower())
        if exclude_id: statement=statement.where(table.c.id!=exclude_id)
        if db.connection().execute(statement.limit(1)).first():
            raise HTTPException(409, 'Employee code already exists')
'''+needle);p.write_text(s,encoding='utf-8')
p=Path('backend/app/api/v1/employees.py');s=p.read_text(encoding='utf-8');s=s.replace('    return crud_employee.create_with_user(db, obj_in=data, created_by=current_user.id)','''    from sqlalchemy.exc import IntegrityError
    try:
        return crud_employee.create_with_user(db, obj_in=data, created_by=current_user.id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Employee code or login account already exists. Review existing records before trying again.") from None''');p.write_text(s,encoding='utf-8')
