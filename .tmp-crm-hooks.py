from pathlib import Path
p=Path('backend/app/apps/crm/sales_process.py');s=p.read_text(encoding='utf-8');s=s.replace('"meetingId": meeting.id})', '"meetingId": meeting.id, "dealId": lead.converted_deal_id})');s=s.replace('        if stage.name == "Proposal Sent":', '''        if stage.name == "Demo Completed":
            existing = db.query(CRMActivity.id).filter(CRMActivity.organization_id==lead.organization_id, CRMActivity.lead_id==lead.id, CRMActivity.status=="Pending", CRMActivity.metadata_json["salesAutomation"].as_string()=="demo_completed").first()
            if not existing:
                m.task(db, lead, user, "Follow up after completed demo", m.now()+timedelta(days=1), metadata={"salesAutomation":"demo_completed", "dealId":deal.id})
        if stage.name == "Proposal Sent":''');p.write_text(s,encoding='utf-8')
p=Path('backend/app/apps/crm/api/router.py');s=p.read_text(encoding='utf-8');needle='    if resource.model is CRMDeal and changed_audit:\n';s=s.replace(needle,'''    if resource.model is CRMMeeting and record.status in {"Completed", "Attended"} and before.get("status") not in {"Completed", "Attended"} and record.lead_id:
        from app.apps.crm.sales_process import completed_demo
        linked_lead = db.query(CRMLead).filter_by(id=record.lead_id, organization_id=organization_id, deleted_at=None).first()
        if linked_lead:
            completed_demo(db, linked_lead, current_user, record)
'''+needle);p.write_text(s,encoding='utf-8')
