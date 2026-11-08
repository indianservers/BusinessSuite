from pathlib import Path
p=Path('backend/tests/test_employee_profile_reliability.py');s=p.read_text(encoding='utf-8').replace(" ident,_=profile_employee;emp=db.get(Employee,ident);emp.personal_email='same@example.com';db.commit()", """ ident,_=profile_employee;emp=db.get(Employee,ident);emp.personal_email='same@example.com'
 from app.models.company import Department,Designation
 department=Department(name='Duplicate review QA',branch_id=emp.branch_id);db.add(department);db.flush();db.add(Designation(name='Duplicate review QA',department_id=department.id));db.commit()""")
s=s.replace("assert r.status_code==409,r.text\n payload['allow_contact_duplicate']", "assert r.status_code==409 and 'duplicate' in r.text.lower(),r.text\n payload['allow_contact_duplicate']")
p.write_text(s,encoding='utf-8')
p=Path('backend/app/common/services/profiles.py');s=p.read_text(encoding='utf-8');needle='            record_employee_field_changes(db, employee, direct, actor.id, reason)';s=s.replace(needle,needle+'''
            from app.core.hr_audit import record_field_audit
            for collection in {"education", "experience", "skills"}.intersection(direct):
                record_field_audit(db,module="employee",entity_type="employee",entity_id=employee.id,employee_id=employee.id,field_name=collection,old_value=current["values"].get(collection),new_value=direct[collection],actor_user_id=actor.id,reason=reason)''');p.write_text(s,encoding='utf-8')
p=Path('backend/app/api/v1/profile_change_requests.py');s=p.read_text(encoding='utf-8').replace(' or _role_key(current_user) in {"admin", "hr"}', '')
s=s.replace('        record_employee_field_changes(db,employee,changes,current_user.id,"Approved profile change request")', '''        record_employee_field_changes(db,employee,changes,current_user.id,"Approved profile change request")
        if "unified_profile" in changes:
            from app.core.hr_audit import record_field_audit
            record_field_audit(db,module="employee",entity_type="employee",entity_id=employee.id,employee_id=employee.id,field_name="unified_profile",old_value=originals.get("unified_profile"),new_value=changes["unified_profile"],actor_user_id=current_user.id,reason="Approved profile change request")''');p.write_text(s,encoding='utf-8')
p=Path('frontend/src/apps/hrms/pages/employees/EmployeeDetailPage.tsx');s=p.read_text(encoding='utf-8');s=s.replace('  const [allowContactDuplicate,setAllowContactDuplicate]', '  const [saveConflict,setSaveConflict]=useState(false);\n  const [allowContactDuplicate,setAllowContactDuplicate]');s=s.replace('    onError: (err:unknown) => {\n      const details=', '    onError: (err:unknown) => {\n      if(getApiErrorMessage(err).includes("profile changed"))setSaveConflict(true);\n      const details=')
s=s.replace('      {editing && (','''      {saveConflict && <div role="alert" className="rounded border border-amber-400 p-4"><p>This profile changed while you were editing. Your draft has been retained and has not overwritten the newer values.</p><Button variant="outline" onClick={async()=>{await qc.refetchQueries({queryKey:["employee",id]});setSaveConflict(false);setParams({});}}>Discard draft and review latest profile</Button></div>}
      {editing && (''');p.write_text(s,encoding='utf-8')
