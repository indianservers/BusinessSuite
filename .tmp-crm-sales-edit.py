from pathlib import Path
p=Path('backend/app/apps/crm/lead_management.py')
s=p.read_text()
s=s.replace('settings.pop("sources", None)', 'settings.pop("sources", None)\n    settings.pop("salesProcess", None)')
s=s.replace('"dealStageGuidance", "sources"}', '"dealStageGuidance", "sources", "salesProcess"}')
s=s.replace('CRMMeeting.status != "Cancelled",', 'CRMMeeting.status.in_(["Scheduled", "Confirmed"]),')
s=s.replace('data["lastActivityAt"] = now().isoformat()', 'data["lastActivityAt"] = now().isoformat()\n    if payload.responded:\n        data["lastResponseAt"] = now().isoformat()\n        data.pop("proposalReminder", None)')
s=s.replace('data["booking"]["used"] = True', 'data["booking"]["used"] = True\n    data["lastResponseAt"] = now().isoformat()')
s=s.replace('        settings = config(db, org)\n        due =', '        from app.apps.crm.sales_process import sales_reminders\n        follow_up_reminders += sales_reminders(db, org, per_tenant)\n        settings = config(db, org)\n        due =')
# Keep normal task reminders for converted leads: their deal remains active.
s=s.replace('            CRMLead.is_converted.is_not(True),\n            CRMLead.status.notin_(["Lost", "Converted"]),\n            CRMActivity.status == "Pending",', '            CRMLead.status != "Lost",\n            CRMActivity.status == "Pending",')
# Proposal automation has its own conditional reminder, rather than sending a stale generic reminder.
s=s.replace('    for item, lead in rows:\n        data =', '    for item, lead in rows:\n        if (item.metadata_json or {}).get("salesAutomation") == "proposal":\n            continue\n        data =')
s += '\n\nfrom app.apps.crm.sales_process import router as sales_process_router\nrouter.include_router(sales_process_router)\n'
p.write_text(s)
p=Path('backend/app/apps/crm/api/router.py');s=p.read_text()
needle='        from app.shared.pipeline_workspace import stage_entry\n        stage_entry(db, current_user, "crm", "deal", record.id, before.get("stage_id"), record.stage_id, record.owner_user_id, f"pipeline:{record.pipeline_id}")'
s=s.replace(needle,needle+'\n        from app.apps.crm.sales_process import deal_changed\n        deal_changed(db, record, current_user, before)')
# Choose the dedicated process only for configured tenants; preserve other pipelines/defaults.
s=s.replace('        pipeline_id = payload.pipelineId\n        stage_id = payload.stageId', '        from app.apps.crm.lead_management import config as lead_config\n        school_process = lead_config(db, organization_id).get("salesProcess", {})\n        pipeline_id = payload.pipelineId or (school_process.get("pipelineId") if school_process.get("enabled") else None)\n        stage_id = payload.stageId')
s=s.replace('        company.account_type = "Customer"\n        if created_customer', '        from app.apps.crm.lead_management import config as lead_config\n        school_process = lead_config(db, organization_id).get("salesProcess", {})\n        if company.account_type != "Customer":\n            company.account_type = "Prospect" if school_process.get("enabled") else "Customer"\n        if created_customer')
s=s.replace('        add_tags(contact, "Lead", "Customer")', '        from app.apps.crm.lead_management import config as lead_config\n        add_tags(contact, "Lead", "Opportunity" if lead_config(db, organization_id).get("salesProcess", {}).get("enabled") else "Customer")')
p.write_text(s)
