from pathlib import Path
p=Path('backend/app/api/v1/employees.py');s=p.read_text(encoding='utf-8');s=s.replace('skills=[skill.strip() for skill in (employee.skills_tags or "").replace(";", ",").split(",") if skill.strip()],','skills=sorted({skill.strip() for skill in (employee.skills_tags or "").replace(";", ",").split(",") if skill.strip()} | {row.skill_name for row in employee.skills}),')
a=s.index('    skills: dict[str, int] = {}');b=s.index('    return {',a)
s=s[:a]+'''    skills: dict[str, int] = {}
    employees_with_skills = base.with_entities(Employee.id, Employee.skills_tags).limit(1000).all()
    names_by_employee = {row[0]: {value.strip() for value in (row[1] or "").replace(";", ",").split(",") if value.strip()} for row in employees_with_skills}
    if names_by_employee:
        for row in db.query(EmployeeSkill.employee_id, EmployeeSkill.skill_name).filter(EmployeeSkill.employee_id.in_(names_by_employee)).all():
            names_by_employee[row[0]].add(row[1])
    for names in names_by_employee.values():
        for name in names: skills[name] = skills.get(name, 0) + 1
'''+s[b:];p.write_text(s,encoding='utf-8')
p=Path('backend/app/api/v1/profile_change_requests.py');s=p.read_text(encoding='utf-8').replace('from datetime import datetime, timezone','from datetime import date, datetime, timezone').replace('effectiveDate: str | None = None','effectiveDate: date | None = None').replace('        request_type=data.requestType,','        request_type=data.requestType,\n        effective_date=data.effectiveDate,');s=s.replace('        employee=lock_profile(db, employee.id)','        if item.effective_date and item.effective_date > date.today():\n            raise HTTPException(422, "This request is not effective yet; review it on or after its effective date")\n        employee=lock_profile(db, employee.id)');p.write_text(s,encoding='utf-8')
p=Path('backend/app/common/services/profiles.py');s=p.read_text(encoding='utf-8').replace('        "pendingRequests": pending,','''        "pendingRequests": pending,
        "certificationAlerts": [
            {"name": row.certification_name, "expires": str(row.expiry_date), "expired": row.expiry_date < date.today()}
            for row in employee.certifications
            if row.expiry_date and (row.expiry_date-date.today()).days <= 90
        ] if employee else [],''');p.write_text(s,encoding='utf-8')
p=Path('frontend/src/features/profiles/UnifiedProfile.tsx');s=p.read_text(encoding='utf-8').replace('  pendingRequests: Values[];','  pendingRequests: Values[];\n  certificationAlerts?: Array<{name:string;expires:string;expired:boolean}>;');pos=s.index('      {error && (',s.index('profile.displayName || "My profile"'));s=s[:pos]+'''      {!!profile.certificationAlerts?.length && <aside role="status" className="profile-card"><h2>Certification expiry alerts</h2>{profile.certificationAlerts.map((certificate,index)=><p key={index}>{certificate.name}: {certificate.expired?"Expired":"Expires within 90 days"} · {certificate.expires}</p>)}</aside>}
'''+s[pos:];p.write_text(s,encoding='utf-8')
