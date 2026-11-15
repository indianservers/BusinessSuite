from pathlib import Path
p=Path('frontend/src/apps/crm/leads/SalesProcessPanel.tsx');s=p.read_text(encoding="utf-8");s=s.replace('Existing permission must be confirmed from the lead history before changing it.', 'Permission changes are recorded in the lead history.')
s=s.replace('  const update = async (meeting:Meeting,status:string) => {', '''  useRefreshableEffect(()=>{let active=true;api.get<{allowed:boolean;evidence:string}>(`${root}/leads/${id}/nurture-consent`).then(r=>{if(active){setConsent(r.data.allowed);setEvidence(r.data.evidence);}}).catch(e=>{if(active)setError(errorMessage(e));});return()=>{active=false;};},[id]);
  const update = async (meeting:Meeting,status:string) => {''')
p.write_text(s,encoding="utf-8")
p=Path('backend/app/apps/crm/engagements.py');s=p.read_text().replace('["cancelled", "canceled", "completed", "done"]', '["cancelled", "canceled", "completed", "done", "attended", "no-show", "rescheduled"]');p.write_text(s,encoding="utf-8")
p=Path('backend/app/apps/crm/lead_management.py');s=p.read_text().replace('if target == "Lost" and not details.get("lossReason"):', 'if target == "Lost" and not str(details.get("lossReason") or "").strip():');p.write_text(s,encoding="utf-8")

