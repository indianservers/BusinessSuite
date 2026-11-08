from pathlib import Path
p=Path('backend/app/services/employee_profile_reliability.py');s=p.read_text(encoding='utf-8').replace("Employee.phone_number_country_code.is_(None)","True");p.write_text(s,encoding='utf-8')
p=Path('backend/app/api/v1/employees.py');s=p.read_text(encoding='utf-8').replace('def employee_duplicate_check(data: dict,','''class EmployeeDuplicateCheck(BaseModel):
    personal_email: str | None = Field(default=None, max_length=320)
    work_email: str | None = Field(default=None, max_length=320)
    phone_number: str | None = Field(default=None, max_length=30)
    phone_number_country_code: str | None = Field(default=None, max_length=8)
    employee_id: str | None = Field(default=None, max_length=60)
    exclude_id: int | None = Field(default=None, gt=0)


def employee_duplicate_check(data: EmployeeDuplicateCheck,''')
# Move decorator to the endpoint rather than the schema declaration.
s=s.replace('@router.post("/duplicate-check")\nclass EmployeeDuplicateCheck','class EmployeeDuplicateCheck').replace('\ndef employee_duplicate_check(data: EmployeeDuplicateCheck,','\n@router.post("/duplicate-check")\ndef employee_duplicate_check(data: EmployeeDuplicateCheck,').replace('duplicate_matches(db, data, data.get("exclude_id"))','duplicate_matches(db, data.model_dump(), data.exclude_id)')
# Serialize review decisions and prevent self-review / stale approval overwrites.
s=s.replace('item = db.query(EmployeeChangeRequest).filter(EmployeeChangeRequest.id == request_id).first()', 'item = db.query(EmployeeChangeRequest).filter(EmployeeChangeRequest.id == request_id).with_for_update().first()')
s=s.replace('    if item.status != "Pending":','    if not current_user.is_superuser and item.requested_by == current_user.id:\n        raise HTTPException(403, "You cannot approve your own profile change request")\n    if item.status != "Pending":')
s=s.replace('        org_fields = {','''        if item.effective_date and item.effective_date > date.today():
            raise HTTPException(422, "Future-dated organizational changes must use the scheduled transfer workflow")
        employee = lock_profile(db, employee.id)
        originals = item.old_value_json or {}
        for field, original in originals.items():
            if field in changes and hasattr(employee, field) and str(getattr(employee, field, None)) != str(original):
                raise HTTPException(409, "Employee details changed since this request was submitted. Review the latest profile and submit a new request.")
        org_fields = {''')
# Document rejection reasons and privacy checks are enforced at the write endpoint.
s=s.replace('    if data.verification_status not in {"Pending", "Verified", "Rejected"}:', '''    from app.core.masking import can_view_sensitive_employee
    if not can_view_sensitive_employee(current_user, employee_id):
        raise HTTPException(403, "Document verification requires sensitive employee access")
    if data.verification_status == "Rejected" and not (data.verification_notes or "").strip():
        raise HTTPException(422, "A rejection reason is required")
    if data.verification_status not in {"Pending", "Verified", "Rejected"}:''')
p.write_text(s,encoding='utf-8')
p=Path('frontend/src/services/api.ts');s=p.read_text(encoding='utf-8')
s=s.replace('update: (id: number, data: unknown) => api.put(`/employees/${id}`, data),','update: (id: number, data: unknown, version?: string) => api.put(`/employees/${id}`, data, {headers: version ? {"If-Match": version} : {}}),')
for method,route in [('addEducation','education'),('addExperience','experience'),('addCertification','certifications'),('addSkill','skills')]:
 s=s.replace(f'{method}: (id: number, data: unknown) => api.post(`/employees/${{id}}/{route}`, data)',f'{method}: (id: number, data: unknown, version?: string) => api.post(`/employees/${{id}}/{route}`, data, {{headers: version ? {{"If-Match": version}} : {{}}}})')
s=s.replace('recordId: number, data: unknown) => api.put(`/employees/${id}/${section}/${recordId}`, data)', 'recordId: number, data: unknown, version?: string) => api.put(`/employees/${id}/${section}/${recordId}`, data, {headers: version ? {"If-Match": version} : {}})')
s=s.replace('recordId: number) => api.delete(`/employees/${id}/${section}/${recordId}`)', 'recordId: number, version?: string) => api.delete(`/employees/${id}/${section}/${recordId}`, {headers: version ? {"If-Match": version} : {}})')
p.write_text(s,encoding='utf-8')
p=Path('frontend/src/apps/hrms/pages/employees/EmployeeDetailPage.tsx');s=p.read_text(encoding='utf-8')
s=s.replace('import Employee360Panel', 'import EmployeeReliabilityPanel from "./EmployeeReliabilityPanel";\nimport Employee360Panel')
s=s.replace('  { id: "education", label: "Education", icon: GraduationCap },','  { id: "history", label: "Profile checks & history", icon: Clock },\n  { id: "education", label: "Education", icon: GraduationCap },')
s=s.replace('useEffect, useState','useEffect, useState, useRef')
s=s.replace('const [editingRecord, setEditingRecord] = useState<{section: string; id: number}', 'const [editVersion, setEditVersion] = useState<string | undefined>();\n  const initializedEdit = useRef("");\n  const [editingRecord, setEditingRecord] = useState<{section: string; id: number; version?: string}')
s=s.replace('  const editing = employeeId != null ? popupEditing : params.get("edit") === "true";', '  const requestedEditing = employeeId != null ? popupEditing : params.get("edit") === "true";')
pos=s.index('  const userOptions = useQuery')
s=s[:pos]+'''  const canEditProfile = emp?.can_edit_profile ?? canChangeRole;
  const editing = requestedEditing && canEditProfile;

'''+s[pos:]
s=s.replace('custom_fields:customFieldForm.validate()})','custom_fields:customFieldForm.validate()}, editVersion)')
s=s.replace('toast({ title: "Could not update employee", variant: "destructive" });','toast({ title: "Could not update employee", description: getApiErrorMessage(err), variant: "destructive" });')
# Freeze the baseline when edit mode opens. Background refresh must not overwrite unsaved input.
s=s.replace('    if (!emp || !editing) return;\n    setEditForm({', '''    if (!editing) { initializedEdit.current=""; return; }
    if (!emp || initializedEdit.current === String(id)) return;
    initializedEdit.current=String(id);
    setEditVersion(emp.profile_version);
    setEditForm({''')
s=s.replace('  }, [emp, editing]);','  }, [!!emp, editing, id]);')
s=s.replace('setEditingRecord({section, id: record.id})','setEditingRecord({section, id: record.id, version: emp?.profile_version})')
s=s.replace('    <div className="mt-3 flex gap-2">','    !canEditProfile ? null : <div className="mt-3 flex gap-2">',1)
s=s.replace('activeTab !== "profile" && activeTab !== "verification" && <Button','canEditProfile && activeTab !== "profile" && activeTab !== "verification" && activeTab !== "history" && <Button')
s=s.replace('"certifications","documents","verification"','"certifications","documents","verification","history"')
s=s.replace('        {label:"Work", sections:TABS.filter(t=>[','        {label:"Work", sections:TABS.filter(t=>(t.id !== "history" || canEditProfile) && [')
for section,method in [('education','Education'),('experience','Experience'),('skills','Skill'),('certifications','Certification')]:
 s=s.replace(f'editingRecord.id, payload) : employeeApi.add{method}(Number(id), payload)',f'editingRecord.id, payload, editingRecord.version) : employeeApi.add{method}(Number(id), payload, emp?.profile_version)')
# Certification expression spans lines.
s=s.replace('editingRecord.id, payload)\n      : employeeApi.addCertification(Number(id), payload)', 'editingRecord.id, payload, editingRecord.version)\n      : employeeApi.addCertification(Number(id), payload, emp?.profile_version)')
s=s.replace('employeeApi.deleteProfileRecord(Number(id), section, recordId)', 'employeeApi.deleteProfileRecord(Number(id), section, recordId, emp?.profile_version)')
s=s.replace('      {activeTab === "verification" &&', '      {activeTab === "history" && <EmployeeReliabilityPanel employeeId={Number(id)}/>}\n      {activeTab === "verification" &&')
# Disable duplicate submissions while an existing request is in flight (including Enter-key repeats).
s=s.replace('                  event.preventDefault();\n                  const allowedFields', '                  event.preventDefault();\n                  if(updateMutation.isPending)return;\n                  const allowedFields')
s=s.replace('        event.preventDefault();\n        const payload = { ...form };','        event.preventDefault();\n        if(saving)return;\n        const payload = { ...form };')
p.write_text(s,encoding='utf-8')
