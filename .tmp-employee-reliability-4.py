from pathlib import Path
p=Path('frontend/src/apps/hrms/pages/employees/AddEmployeePage.tsx');s=p.read_text(encoding='utf-8');s='import EmployeeDuplicateWarning from "./EmployeeDuplicateWarning";\n'+s;s=s.replace('  const submitting=useRef(false);','  const submitting=useRef(false);\n  const [allowContactDuplicate,setAllowContactDuplicate]=useState(false);');s=s.replace('custom_fields:customFieldForm.validate()})','custom_fields:customFieldForm.validate(),allow_contact_duplicate:allowContactDuplicate})');s=s.replace('      {/* Step indicator */}', '''      <EmployeeDuplicateWarning values={{personal_email:watch("personal_email"),work_email:watch("work_email"),phone_number:watch("phone_number"),phone_number_country_code:watch("phone_number_country_code")}} acknowledged={allowContactDuplicate} onAcknowledge={setAllowContactDuplicate}/>
      {/* Step indicator */}''');p.write_text(s,encoding='utf-8')
p=Path('frontend/src/apps/hrms/pages/employees/EmployeeDetailPage.tsx');s=p.read_text(encoding='utf-8');s='import EmployeeDuplicateWarning from "./EmployeeDuplicateWarning";\nimport EmployeeDocumentsPanel from "./EmployeeDocumentsPanel";\n'+s;s=s.replace('  const [editVersion, setEditVersion]', '  const [allowContactDuplicate,setAllowContactDuplicate]=useState(false);\n  const [editVersion, setEditVersion]');s=s.replace('custom_fields:customFieldForm.validate()}, editVersion)', 'custom_fields:customFieldForm.validate(),allow_contact_duplicate:allowContactDuplicate}, editVersion)');s=s.replace('                <div className="sm:col-span-2"><CrmRecordFields state={customFieldForm}/></div>', '''                <div className="sm:col-span-2"><CrmRecordFields state={customFieldForm}/>{activeTab==="personal"&&<EmployeeDuplicateWarning excludeId={Number(id)} values={{personal_email:editForm.personal_email,work_email:editForm.work_email,phone_number:editForm.phone_number,phone_number_country_code:editForm.phone_number_country_code}} acknowledged={allowContactDuplicate} onAcknowledge={setAllowContactDuplicate}/>}</div>''')
start=s.index('      {activeTab === "documents" && (', s.index('No certifications added'));end=s.index('      {activeTab === "account"',start)
s=s[:start]+'''      {activeTab === "documents" && <EmployeeDocumentsPanel employeeId={Number(id)} documents={emp.documents||[]} canVerify={canEditProfile&&!emp.restricted_fields?.includes("documents")} canUpload={(canEditProfile||ownEmployeeId===Number(id))&&!emp.restricted_fields?.includes("documents")}/>}

'''+s[end:]
p.write_text(s,encoding='utf-8')
p=Path('frontend/src/apps/hrms/pages/employees/EmployeeReliabilityPanel.tsx');s=p.read_text(encoding='utf-8').replace('/hrms/profile-change-requests','/hrms?view=approvals').replace('Employee actions → Assign work','HRMS daily work → Transfer / promote');p.write_text(s,encoding='utf-8')
p=Path('backend/app/api/v1/profile_change_requests.py');s=p.read_text(encoding='utf-8').replace('.filter(EmployeeChangeRequest.id == request_id).first()', '.filter(EmployeeChangeRequest.id == request_id).with_for_update().first()');s=s.replace('    if item.status != "Pending":', '''    if not current_user.is_superuser and item.requested_by==current_user.id:
        raise HTTPException(403, "You cannot approve your own profile change request")
    if item.status != "Pending":''');s=s.replace('    if action == "approve" and data.applyChanges:\n        _apply_profile_change', '''    if action == "approve" and data.applyChanges:
        from app.services.employee_profile_reliability import lock_profile, touch
        from app.core.hr_audit import record_employee_field_changes
        employee=lock_profile(db, employee.id)
        originals=item.old_value_json or {}
        for field, original in originals.items():
            if field in changes and hasattr(employee,field) and str(getattr(employee,field,None))!=str(original):
                raise HTTPException(409,"Employee details changed since submission. Review the latest profile and submit a new request.")
        if "unified_profile" in changes and employee.user:
            from app.common.services.profiles import serialize_profile
            current=serialize_profile(db,employee.user,current_user)["values"]
            for field,original in originals.get("unified_profile",{}).items():
                if current.get(field)!=original:
                    raise HTTPException(409,"Employee details changed since submission. Review the latest profile and submit a new request.")
        record_employee_field_changes(db,employee,changes,current_user.id,"Approved profile change request")
        touch(employee)
        _apply_profile_change''');p.write_text(s,encoding='utf-8')
