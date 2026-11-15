from pathlib import Path
p=Path('backend/app/apps/crm/sales_process.py');s=p.read_text();s=s.replace('from pydantic import BaseModel, ConfigDict, Field', 'from pydantic import BaseModel, ConfigDict, Field, field_validator')
s=s.replace('    evidence: str = Field(min_length=1, max_length=1000)\n', '''    evidence: str = Field(min_length=1, max_length=1000)

    @field_validator("evidence")
    @classmethod
    def evidence_required(cls, value):
        if not value.strip(): raise ValueError("Record permission evidence or a withdrawal reason")
        return value.strip()

@router.get("/leads/{ident}/nurture-consent")
def get_nurture_consent(ident: int, db: Session = Depends(get_db), user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "crm_leads_view", "crm_leads_manage"))):
    m = lm()
    lead = m.lead_record(db, user, ident)
    row = m.state(db, lead, False)
    return (row.data_json or {}).get("nurtureConsent", {"allowed": False, "evidence": ""}) if row else {"allowed": False, "evidence": ""}
''')
s=s.replace('        completed_demo(db, lead, user, item)', '        row = m.state(db, lead)\n        row.data_json = {**row.data_json, "lastResponseAt": m.now().isoformat()}\n        row.version += 1\n        completed_demo(db, lead, user, item)')
s=s.replace('    # Stable cycle keys are indexed by state;', '    # Stable cycle keys are stored in state;')
p.write_text(s)
p=Path('frontend/src/apps/crm/leads/SalesProcessPanel.tsx');s=p.read_text();s=s.replace('Existing permission must be confirmed from the lead history before changing it.', 'Permission changes are recorded in the lead history.')
s=s.replace('  const update = async (meeting:Meeting,status:string) => {', '''  useRefreshableEffect(()=>{let active=true;api.get<{allowed:boolean;evidence:string}>(`${root}/leads/${id}/nurture-consent`).then(r=>{if(active){setConsent(r.data.allowed);setEvidence(r.data.evidence);}}).catch(e=>{if(active)setError(errorMessage(e));});return()=>{active=false;};},[id]);
  const update = async (meeting:Meeting,status:string) => {''')
p.write_text(s)
p=Path('backend/app/apps/crm/engagements.py');s=p.read_text().replace('["cancelled", "canceled", "completed", "done"]', '["cancelled", "canceled", "completed", "done", "attended", "no-show", "rescheduled"]');p.write_text(s)
p=Path('backend/app/apps/crm/lead_management.py');s=p.read_text().replace('if target == "Lost" and not details.get("lossReason"):', 'if target == "Lost" and not str(details.get("lossReason") or "").strip():');p.write_text(s)
