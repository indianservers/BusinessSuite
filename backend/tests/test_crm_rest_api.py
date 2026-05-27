from datetime import date, datetime, timezone

from app.apps.crm.models import CRMApprovalRequest, CRMCalendarIntegration, CRMContact, CRMDeal, CRMDealContact, CRMEnrichmentLog, CRMLead, CRMMessage, CRMNoteMention, CRMPipeline, CRMPipelineStage, CRMQuotationItem, CRMTask, CRMTerritoryUser, CRMWebhookDelivery
from app.models.company import Branch, Company
from app.models.employee import Employee
from app.models.notification import Notification
from app.models.user import User


def test_crm_leads_crud_is_scoped_to_current_organization(client, db, superuser_headers):
    db.add(
        CRMLead(
            organization_id=2,
            first_name="Other",
            full_name="Other Org Lead",
            email="other@example.com",
            status="New",
        )
    )
    db.commit()

    created = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={
            "firstName": "Rahul",
            "lastName": "Mehta",
            "fullName": "Rahul Mehta",
            "email": "rahul@example.com",
            "companyName": "Apex Digital",
            "status": "Qualified",
        },
    )
    assert created.status_code == 201
    lead_id = created.json()["id"]
    assert created.json()["organizationId"] == 1
    assert created.json()["createdBy"] is not None

    listed = client.get("/api/v1/crm/leads", headers=superuser_headers, params={"search": "Rahul"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == lead_id
    assert all(item["organizationId"] == 1 for item in listed.json()["items"])

    patched = client.patch(
        f"/api/v1/crm/leads/{lead_id}",
        headers=superuser_headers,
        json={"status": "Converted"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "Converted"
    assert patched.json()["updatedBy"] is not None

    deleted = client.delete(f"/api/v1/crm/leads/{lead_id}", headers=superuser_headers)
    assert deleted.status_code == 200

    after_delete = client.get("/api/v1/crm/leads", headers=superuser_headers, params={"include_deleted": False})
    assert all(item["id"] != lead_id for item in after_delete.json()["items"])


def test_crm_validates_unknown_entity_and_required_fields(client, superuser_headers):
    missing_required = client.post("/api/v1/crm/products", headers=superuser_headers, json={"sku": "NO-NAME"})
    assert missing_required.status_code == 422

    unknown = client.get("/api/v1/crm/unknown-resource", headers=superuser_headers)
    assert unknown.status_code == 404


def test_crm_secondary_list_pages_use_backend_resources(client, superuser_headers):
    resources = [
        ("campaigns", {"name": "Renewal Push", "campaignType": "Email", "status": "Planned"}),
        ("tickets", {"ticketNumber": "TCK-9001", "subject": "Customer escalation", "priority": "High", "status": "Open"}),
        ("files", {"fileName": "proposal.txt", "originalName": "Proposal.txt", "storagePath": "metadata-only", "mimeType": "text/plain"}),
    ]

    for entity, payload in resources:
        created = client.post(f"/api/v1/crm/{entity}", headers=superuser_headers, json=payload)
        assert created.status_code == 201
        assert created.json()["organizationId"] == 1

        listed = client.get(f"/api/v1/crm/{entity}", headers=superuser_headers)
        assert listed.status_code == 200
        assert any(item["id"] == created.json()["id"] for item in listed.json()["items"])

        deleted = client.delete(f"/api/v1/crm/{entity}/{created.json()['id']}", headers=superuser_headers)
        assert deleted.status_code == 200


def test_crm_custom_field_values_are_persisted_and_org_scoped(client, superuser_headers):
    field = client.post(
        "/api/v1/crm/custom-fields",
        headers=superuser_headers,
        json={
            "entityType": "leads",
            "fieldName": "Preferred Plan",
            "fieldKey": "preferred_plan",
            "fieldType": "dropdown",
            "options": ["Enterprise", "Growth"],
            "isVisible": True,
            "isUnique": True,
            "isFilterable": True,
        },
    )
    assert field.status_code == 201
    assert field.json()["entityType"] == "leads"
    assert field.json()["fieldKey"] == "preferred_plan"
    assert field.json()["fieldName"] == "Preferred Plan"
    assert field.json()["isUnique"] is True

    duplicate = client.post(
        "/api/v1/crm/custom-fields",
        headers=superuser_headers,
        json={"entityType": "lead", "fieldName": "Preferred Plan Again", "fieldKey": "preferred_plan", "fieldType": "text"},
    )
    assert duplicate.status_code == 409

    value = client.post(
        "/api/v1/crm/custom-field-values",
        headers=superuser_headers,
        json={
            "customFieldId": field.json()["id"],
            "entity": "leads",
            "recordId": 1001,
            "valueText": "Enterprise",
        },
    )
    assert value.status_code == 201
    assert value.json()["organizationId"] == 1
    assert value.json()["createdBy"] is not None

    listed = client.get(
        "/api/v1/crm/custom-field-values",
        headers=superuser_headers,
        params={"entity": "leads", "record_id": 1001},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["value_text"] == "Enterprise"

    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Inline", "fullName": "Inline Lead", "status": "New", "customFields": {"preferred_plan": "Growth"}},
    )
    assert lead.status_code == 201
    listed_leads = client.get("/api/v1/crm/leads", headers=superuser_headers, params={"cf_preferred_plan": "Growth"})
    assert listed_leads.status_code == 200
    assert any(item["id"] == lead.json()["id"] and item["cf_preferred_plan"] == "Growth" for item in listed_leads.json()["items"])

    upsert = client.post(
        "/api/v1/crm/custom-field-values/upsert",
        headers=superuser_headers,
        json={
            "customFieldId": field.json()["id"],
            "entity": "leads",
            "recordId": lead.json()["id"],
            "value": "Growth",
        },
    )
    assert upsert.status_code == 200
    assert upsert.json()["value"] == "Growth"

    invalid = client.post(
        "/api/v1/crm/custom-field-values/upsert",
        headers=superuser_headers,
        json={
            "customFieldId": field.json()["id"],
            "entity": "leads",
            "recordId": lead.json()["id"],
            "value": "Invalid Plan",
        },
    )
    assert invalid.status_code == 422

    detail = client.get(f"/api/v1/crm/leads/{lead.json()['id']}", headers=superuser_headers)
    assert detail.status_code == 200
    assert any(item["value"] == "Growth" for item in detail.json()["customFields"])

    required = client.post(
        "/api/v1/crm/custom-fields",
        headers=superuser_headers,
        json={"entityType": "tasks", "fieldName": "SLA Code", "fieldKey": "sla_code", "fieldType": "text", "isRequired": True},
    )
    assert required.status_code == 201
    missing_required = client.post("/api/v1/crm/tasks", headers=superuser_headers, json={"title": "Task without SLA"})
    assert missing_required.status_code == 422
    client.delete(f"/api/v1/crm/custom-fields/{required.json()['id']}", headers=superuser_headers)


def test_crm_detail_payload_includes_related_records_and_timeline(client, superuser_headers):
    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Nisha", "fullName": "Nisha Shah", "email": "nisha@example.com", "status": "New"},
    )
    assert lead.status_code == 201
    lead_id = lead.json()["id"]

    note = client.post(
        "/api/v1/crm/notes",
        headers=superuser_headers,
        json={"body": "Discovery call notes", "leadId": lead_id},
    )
    assert note.status_code == 201

    detail = client.get(f"/api/v1/crm/leads/{lead_id}", headers=superuser_headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["id"] == lead_id
    assert payload["organizationId"] == 1
    assert payload["related"]["notes"][0]["body"] == "Discovery call notes"
    assert any(event["type"] == "notes" for event in payload["timeline"])

    related = client.get(f"/api/v1/crm/leads/{lead_id}/related", headers=superuser_headers)
    assert related.status_code == 200
    assert related.json()["related"]["notes"][0]["body"] == "Discovery call notes"


def test_crm_contact_enrichment_preview_apply_and_history(client, db, superuser_headers):
    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Enrich", "fullName": "Enrich Lead", "email": "enrich@example.com", "status": "New"},
    )
    assert lead.status_code == 201
    lead_id = lead.json()["id"]

    preview = client.post(
        "/api/v1/crm/enrichment/preview",
        headers=superuser_headers,
        json={
            "entityType": "lead",
            "entityId": lead_id,
            "provider": "manual",
            "data": {
                "jobTitle": "Founder",
                "company": "Enriched Co",
                "companyWebsite": "https://enriched.example",
                "industry": "Software",
                "phone": "+91 90000 11111",
                "linkedInUrl": "https://linkedin.com/in/enrich",
                "emailVerificationStatus": "verified",
            },
        },
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["provider"] == "manual"
    assert any(field["key"] == "jobTitle" and field["supported"] for field in payload["fields"])
    assert any(field["key"] == "linkedInUrl" and not field["supported"] for field in payload["fields"])

    applied = client.post(
        "/api/v1/crm/enrichment/apply",
        headers=superuser_headers,
        json={
            "entityType": "lead",
            "entityId": lead_id,
            "provider": "manual",
            "values": payload["values"],
            "appliedFields": ["jobTitle", "company", "companyWebsite", "industry", "phone", "linkedInUrl"],
        },
    )
    assert applied.status_code == 200
    record = applied.json()["record"]
    assert record["job_title"] == "Founder"
    assert record["company_name"] == "Enriched Co"
    assert record["website"] == "https://enriched.example"
    assert "linkedInUrl" not in applied.json()["appliedFields"]

    history = client.get("/api/v1/crm/enrichment/history", headers=superuser_headers, params={"entityType": "lead", "entityId": lead_id})
    assert history.status_code == 200
    assert history.json()["total"] >= 2
    assert db.query(CRMEnrichmentLog).filter(CRMEnrichmentLog.organization_id == 1, CRMEnrichmentLog.entity_id == lead_id).count() >= 2

    detail = client.get(f"/api/v1/crm/leads/{lead_id}", headers=superuser_headers)
    assert detail.status_code == 200
    assert any(event["type"] == "activities" and event["record"].get("activityType") == "enrichment" for event in detail.json()["timeline"])


def test_crm_note_mentions_create_scoped_notifications(client, db, superuser_headers):
    teammate = User(email="teammate@example.com", hashed_password="not-used", is_active=True)
    outsider = User(email="outsider@example.com", hashed_password="not-used", is_active=True)
    db.add_all([teammate, outsider])
    db.flush()
    company = Company(id=2, name="Other Org")
    branch = Branch(name="Other Branch", company_id=2)
    db.add_all([company, branch])
    db.flush()
    db.add(
        Employee(
            employee_id="OUT-1",
            user_id=outsider.id,
            first_name="Other",
            last_name="User",
            date_of_joining=date(2026, 1, 1),
            branch_id=branch.id,
            work_email="outsider@example.com",
        )
    )
    db.commit()

    search = client.get("/api/v1/users/search", headers=superuser_headers, params={"q": "teammate"})
    assert search.status_code == 200
    assert any(item["id"] == teammate.id for item in search.json()["items"])
    assert not any(item["id"] == outsider.id for item in search.json()["items"])

    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Mention", "fullName": "Mention Lead", "status": "New"},
    )
    assert lead.status_code == 201

    note = client.post(
        "/api/v1/crm/notes",
        headers=superuser_headers,
        json={"body": f"Please review @[Team Mate](user:{teammate.id})", "leadId": lead.json()["id"]},
    )
    assert note.status_code == 201

    mention = db.query(CRMNoteMention).filter_by(note_id=note.json()["id"], mentioned_user_id=teammate.id).first()
    assert mention is not None
    assert mention.entity_type == "lead"
    assert mention.entity_id == lead.json()["id"]

    notification = db.query(Notification).filter_by(user_id=teammate.id, event_type="crm_mention").first()
    assert notification is not None
    assert notification.action_url == f"/crm/leads/{lead.json()['id']}"

    detail = client.get(f"/api/v1/crm/leads/{lead.json()['id']}", headers=superuser_headers)
    assert any(event["type"] == "notes" and event["record"].get("mentions") for event in detail.json()["timeline"])

    blocked = client.post(
        "/api/v1/crm/notes",
        headers=superuser_headers,
        json={"body": "Cross org mention", "leadId": lead.json()["id"], "mentions": [{"id": outsider.id}]},
    )
    assert blocked.status_code == 422


def test_crm_activity_timeline_endpoint_and_system_events(client, superuser_headers):
    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Arjun", "fullName": "Arjun Rao", "status": "New"},
    )
    assert lead.status_code == 201
    lead_id = lead.json()["id"]

    created_activity = client.post(
        "/api/v1/crm/activities",
        headers=superuser_headers,
        json={
            "entityType": "lead",
            "entityId": lead_id,
            "activityType": "note",
            "title": "Qualification note",
            "body": "Budget confirmed",
            "metadata": {"source": "test"},
        },
    )
    assert created_activity.status_code == 201
    assert created_activity.json()["entityType"] == "lead"
    assert created_activity.json()["activityType"] == "note"
    assert created_activity.json()["metadata"]["source"] == "test"

    status_update = client.patch(
        f"/api/v1/crm/leads/{lead_id}",
        headers=superuser_headers,
        json={"status": "Qualified"},
    )
    assert status_update.status_code == 200

    timeline = client.get(
        "/api/v1/crm/activities",
        headers=superuser_headers,
        params={"entityType": "lead", "entityId": lead_id, "sort_by": "activity_date"},
    )
    assert timeline.status_code == 200
    items = timeline.json()["items"]
    assert any(item["title"] == "Qualification note" for item in items)
    assert any(item["activityType"] == "status_change" for item in items)
    assert all(item["organizationId"] == 1 for item in items)

    task = client.post(
        "/api/v1/crm/tasks",
        headers=superuser_headers,
        json={"title": "Priority follow-up", "leadId": lead_id, "priority": "Medium"},
    )
    assert task.status_code == 201
    priority_update = client.patch(
        f"/api/v1/crm/tasks/{task.json()['id']}",
        headers=superuser_headers,
        json={"priority": "High"},
    )
    assert priority_update.status_code == 200
    updated_timeline = client.get(
        "/api/v1/crm/activities",
        headers=superuser_headers,
        params={"entityType": "lead", "entityId": lead_id},
    )
    assert any(item["activityType"] == "field_change" and item["metadata"]["field"] == "priority" for item in updated_timeline.json()["items"])


def test_crm_email_templates_and_draft_send_log_to_timeline(client, superuser_headers):
    contact = client.post(
        "/api/v1/crm/contacts",
        headers=superuser_headers,
        json={"firstName": "Maya", "fullName": "Maya Sen", "email": "maya@example.com"},
    )
    assert contact.status_code == 201
    contact_id = contact.json()["id"]

    templates = client.get("/api/v1/crm/email-templates", headers=superuser_headers, params={"entityType": "contact"})
    assert templates.status_code == 200
    assert templates.json()["items"]

    draft = client.post(
        "/api/v1/crm/emails/send",
        headers=superuser_headers,
        json={
            "entityType": "contact",
            "entityId": contact_id,
            "to": "maya@example.com",
            "cc": "sales@example.com",
            "bcc": "",
            "subject": "Welcome Maya",
            "body": "<p>Hello Maya</p>",
            "saveAsDraft": True,
        },
    )
    assert draft.status_code == 201
    assert draft.json()["status"] == "draft"
    assert draft.json()["entityType"] == "contact"
    assert draft.json()["to_email"] == "maya@example.com"

    timeline = client.get(
        "/api/v1/crm/activities",
        headers=superuser_headers,
        params={"entityType": "contact", "entityId": contact_id},
    )
    assert timeline.status_code == 200
    assert any(item["activityType"] == "email" and "Welcome Maya" in item["title"] for item in timeline.json()["items"])


def test_crm_whatsapp_sms_templates_send_logs_and_timeline(client, db, superuser_headers):
    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Aarav", "fullName": "Aarav Shah", "phone": "+919876543210", "status": "New"},
    )
    assert lead.status_code == 201
    lead_id = lead.json()["id"]

    template = client.post(
        "/api/v1/crm/message-templates",
        headers=superuser_headers,
        json={"name": "Lead WhatsApp intro", "channel": "whatsapp", "body": "Hi Aarav, thanks for your interest.", "entityType": "lead"},
    )
    assert template.status_code == 201

    templates = client.get("/api/v1/crm/message-templates", headers=superuser_headers, params={"entityType": "lead", "channel": "whatsapp"})
    assert templates.status_code == 200
    assert any(item["name"] == "Lead WhatsApp intro" for item in templates.json()["items"])

    sent = client.post(
        "/api/v1/crm/messages/send",
        headers=superuser_headers,
        json={
            "entityType": "lead",
            "entityId": lead_id,
            "channel": "whatsapp",
            "to": "+91 98765 43210",
            "templateId": template.json()["id"],
            "body": "Hi Aarav, thanks for your interest.",
        },
    )
    assert sent.status_code == 201
    assert sent.json()["status"] == "sent"
    assert sent.json()["provider"] == "mock"
    assert sent.json()["providerMessageId"]
    assert sent.json()["to"] == "+919876543210"

    listed = client.get("/api/v1/crm/messages", headers=superuser_headers, params={"entityType": "lead", "entityId": lead_id})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    assert db.query(CRMMessage).filter(CRMMessage.organization_id == 1, CRMMessage.entity_type == "lead", CRMMessage.entity_id == lead_id).count() == 1

    invalid = client.post(
        "/api/v1/crm/messages/send",
        headers=superuser_headers,
        json={"entityType": "lead", "entityId": lead_id, "channel": "sms", "to": "123", "body": "Bad phone"},
    )
    assert invalid.status_code == 422

    detail = client.get(f"/api/v1/crm/leads/{lead_id}", headers=superuser_headers)
    assert any(event["type"] == "activities" and event["record"].get("activityType") == "message" for event in detail.json()["timeline"])


def test_crm_outbound_webhooks_send_signed_deliveries(client, db, superuser_headers, monkeypatch):
    calls = []

    class FakeResponse:
        status_code = 202
        text = "accepted"

    def fake_post(url, content=None, headers=None, timeout=None):
        calls.append({"url": url, "content": content, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("app.apps.crm.api.router.httpx.post", fake_post)

    webhook = client.post(
        "/api/v1/crm/webhooks",
        headers=superuser_headers,
        json={"name": "Zapier lead hook", "url": "https://hooks.example.test/crm", "secret": "super-secret", "events": ["lead.created", "deal.stage_changed"]},
    )
    assert webhook.status_code == 201
    assert webhook.json()["secret"] != "super-secret"
    assert "lead.created" in webhook.json()["events"]

    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Webhook", "fullName": "Webhook Lead", "status": "New"},
    )
    assert lead.status_code == 201
    assert calls
    assert calls[-1]["url"] == "https://hooks.example.test/crm"
    assert calls[-1]["headers"]["X-CRM-Event"] == "lead.created"
    assert calls[-1]["headers"]["X-CRM-Signature"].startswith("sha256=")
    assert "Webhook Lead" in calls[-1]["content"]

    deliveries = client.get(f"/api/v1/crm/webhooks/{webhook.json()['id']}/deliveries", headers=superuser_headers)
    assert deliveries.status_code == 200
    assert deliveries.json()["total"] >= 1
    assert deliveries.json()["items"][0]["status"] == "delivered"
    assert db.query(CRMWebhookDelivery).filter(CRMWebhookDelivery.organization_id == 1, CRMWebhookDelivery.event_type == "lead.created").count() >= 1

    test_delivery = client.post(f"/api/v1/crm/webhooks/{webhook.json()['id']}/test", headers=superuser_headers)
    assert test_delivery.status_code == 201
    assert test_delivery.json()["status"] == "delivered"


def test_crm_calendar_returns_normalized_org_scoped_events(client, db, superuser_headers):
    db.add(
        CRMTask(
            organization_id=2,
            title="Other org task",
            due_date=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc),
            status="To Do",
        )
    )
    db.commit()

    task = client.post(
        "/api/v1/crm/tasks",
        headers=superuser_headers,
        json={"title": "Call procurement", "dueDate": "2026-05-12T10:00:00+00:00", "status": "To Do"},
    )
    assert task.status_code == 201

    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Calendar", "fullName": "Calendar Lead", "status": "New", "expectedCloseDate": "2026-05-15"},
    )
    assert lead.status_code == 201

    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Calendar Pipeline"})
    assert pipeline.status_code == 201
    stage = client.post(
        "/api/v1/crm/pipeline-stages",
        headers=superuser_headers,
        json={"pipelineId": pipeline.json()["id"], "name": "Prospecting"},
    )
    assert stage.status_code == 201
    deal = client.post(
        "/api/v1/crm/deals",
        headers=superuser_headers,
        json={"name": "Calendar Deal", "pipelineId": pipeline.json()["id"], "stageId": stage.json()["id"], "expectedCloseDate": "2026-05-16"},
    )
    assert deal.status_code == 201

    quote = client.post(
        "/api/v1/crm/quotations",
        headers=superuser_headers,
        json={"quoteNumber": "CAL-001", "issueDate": "2026-05-10", "expiryDate": "2026-05-18", "dealId": deal.json()["id"]},
    )
    assert quote.status_code == 201

    calendar = client.get(
        "/api/v1/crm/calendar",
        headers=superuser_headers,
        params={"startDate": "2026-05-01T00:00:00+00:00", "endDate": "2026-05-31T23:59:59+00:00"},
    )
    assert calendar.status_code == 200
    items = calendar.json()["items"]
    assert any(item["type"] == "task" and item["title"] == "Call procurement" for item in items)
    assert any(item["type"] == "deal" and item["entityType"] == "deal" for item in items)
    assert any(item["type"] == "quotation" and item["entityType"] == "quotation" for item in items)
    assert not any(item["title"] == "Other org task" for item in items)

    tasks_only = client.get(
        "/api/v1/crm/calendar",
        headers=superuser_headers,
        params={"startDate": "2026-05-01T00:00:00+00:00", "endDate": "2026-05-31T23:59:59+00:00", "type": "task"},
    )
    assert tasks_only.status_code == 200
    assert tasks_only.json()["items"]
    assert all(item["type"] == "task" for item in tasks_only.json()["items"])


def test_crm_calendar_integrations_and_meeting_sync(client, db, superuser_headers):
    connected = client.post(
        "/api/v1/crm/calendar-integrations/connect",
        headers=superuser_headers,
        json={"provider": "mock", "mock": True},
    )
    assert connected.status_code == 201
    assert connected.json()["provider"] == "mock"
    assert connected.json()["connected"] is True
    assert "accessTokenEncrypted" not in connected.json()
    assert db.query(CRMCalendarIntegration).filter(CRMCalendarIntegration.organization_id == 1, CRMCalendarIntegration.provider == "mock").count() == 1

    integrations = client.get("/api/v1/crm/calendar-integrations", headers=superuser_headers)
    assert integrations.status_code == 200
    assert integrations.json()["total"] == 1
    assert "refreshTokenEncrypted" not in integrations.json()["items"][0]

    meeting = client.post(
        "/api/v1/crm/meetings",
        headers=superuser_headers,
        json={
            "title": "Calendar sync demo",
            "start_time": "2026-05-14T10:00:00+00:00",
            "end_time": "2026-05-14T11:00:00+00:00",
            "status": "Scheduled",
            "syncToCalendar": True,
        },
    )
    assert meeting.status_code == 201
    assert meeting.json()["syncStatus"] == "synced"
    assert meeting.json()["externalProvider"] == "mock"
    assert meeting.json()["externalEventId"]

    synced = client.post(f"/api/v1/crm/meetings/{meeting.json()['id']}/sync", headers=superuser_headers, json={"provider": "mock"})
    assert synced.status_code == 200
    assert synced.json()["syncStatus"] == "synced"

    calendar = client.get(
        "/api/v1/crm/calendar",
        headers=superuser_headers,
        params={"startDate": "2026-05-14T00:00:00+00:00", "endDate": "2026-05-15T00:00:00+00:00", "type": "meeting"},
    )
    assert calendar.status_code == 200
    assert any(item["syncStatus"] == "synced" and item["externalProvider"] == "mock" for item in calendar.json()["items"])

    disconnected = client.delete(f"/api/v1/crm/calendar-integrations/{connected.json()['id']}", headers=superuser_headers)
    assert disconnected.status_code == 200


def test_crm_quotation_pdf_generation_uses_persisted_quote_data(client, db, superuser_headers):
    contact = client.post(
        "/api/v1/crm/contacts",
        headers=superuser_headers,
        json={"firstName": "Priya", "fullName": "Priya Customer", "email": "priya@example.com", "phone": "9999999999"},
    )
    assert contact.status_code == 201
    quote = client.post(
        "/api/v1/crm/quotations",
        headers=superuser_headers,
        json={
            "quoteNumber": "PDF-001",
            "issueDate": "2026-05-11",
            "expiryDate": "2026-05-25",
            "contactId": contact.json()["id"],
            "currency": "INR",
            "subtotal": 2000,
            "discountAmount": 100,
            "taxAmount": 342,
            "totalAmount": 2242,
            "terms": "Payment due within 15 days.",
        },
    )
    assert quote.status_code == 201
    db.add(
        CRMQuotationItem(
            quotation_id=quote.json()["id"],
            name="Implementation Service",
            description="CRM onboarding package",
            quantity=2,
            unit_price=1000,
            discount_amount=100,
            tax_rate=18,
            total_amount=2242,
        )
    )
    db.commit()

    pdf = client.get(f"/api/v1/crm/quotations/{quote.json()['id']}/pdf", headers=superuser_headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")

    detail = client.get(f"/api/v1/crm/quotations/{quote.json()['id']}", headers=superuser_headers)
    assert detail.status_code == 200
    assert detail.json()["pdfStatus"] == "generated"
    assert detail.json()["pdfUrl"].endswith("PDF-001-" + str(quote.json()["id"]) + ".pdf")

    timeline = client.get(f"/api/v1/crm/quotations/{quote.json()['id']}/related", headers=superuser_headers)
    assert any(item["record"].get("activityType") == "quotation_pdf" and item["title"] == "Quotation PDF generated" for item in timeline.json()["timeline"])

    emailed = client.post(
        f"/api/v1/crm/quotations/{quote.json()['id']}/send-pdf-email",
        headers=superuser_headers,
        json={"to": "buyer@example.com", "saveAsDraft": True},
    )
    assert emailed.status_code == 201
    assert emailed.json()["status"] == "draft"
    assert emailed.json()["pdfUrl"] == detail.json()["pdfUrl"]


def test_crm_multiple_pipelines_stage_management_and_remap(client, superuser_headers):
    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Enterprise Sales"})
    assert pipeline.status_code == 201
    pipeline_id = pipeline.json()["id"]

    discovery = client.post(
        f"/api/v1/crm/pipelines/{pipeline_id}/stages",
        headers=superuser_headers,
        json={"name": "Discovery", "position": 1, "probability": 20, "color": "#2563eb"},
    )
    assert discovery.status_code == 201
    proposal = client.post(
        f"/api/v1/crm/pipelines/{pipeline_id}/stages",
        headers=superuser_headers,
        json={"name": "Proposal", "position": 2, "probability": 60, "color": "#f59e0b"},
    )
    assert proposal.status_code == 201

    deal = client.post(
        "/api/v1/crm/deals",
        headers=superuser_headers,
        json={"name": "Enterprise ERP", "pipelineId": pipeline_id, "stageId": discovery.json()["id"], "amount": 900000},
    )
    assert deal.status_code == 201
    assert deal.json()["pipeline_id"] == pipeline_id
    assert deal.json()["stage_id"] == discovery.json()["id"]

    blocked_delete = client.delete(f"/api/v1/crm/pipeline-stages/{discovery.json()['id']}", headers=superuser_headers)
    assert blocked_delete.status_code == 409

    remapped_delete = client.delete(
        f"/api/v1/crm/pipeline-stages/{discovery.json()['id']}",
        headers=superuser_headers,
        params={"remapStageId": proposal.json()["id"]},
    )
    assert remapped_delete.status_code == 200

    updated_deal = client.get(f"/api/v1/crm/deals/{deal.json()['id']}", headers=superuser_headers)
    assert updated_deal.status_code == 200
    assert updated_deal.json()["stage_id"] == proposal.json()["id"]

    other_pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Renewals"})
    assert other_pipeline.status_code == 201
    other_stage = client.post(
        f"/api/v1/crm/pipelines/{other_pipeline.json()['id']}/stages",
        headers=superuser_headers,
        json={"name": "Renewal Open"},
    )
    assert other_stage.status_code == 201
    invalid_move = client.patch(
        f"/api/v1/crm/deals/{deal.json()['id']}",
        headers=superuser_headers,
        json={"pipelineId": pipeline_id, "stageId": other_stage.json()["id"]},
    )
    assert invalid_move.status_code == 422


def test_crm_deal_supports_multiple_stakeholder_contacts(client, db, superuser_headers):
    contact_1 = client.post(
        "/api/v1/crm/contacts",
        headers=superuser_headers,
        json={"firstName": "Decision", "fullName": "Decision Maker", "email": "decision@example.com"},
    )
    contact_2 = client.post(
        "/api/v1/crm/contacts",
        headers=superuser_headers,
        json={"firstName": "Champion", "fullName": "Internal Champion", "email": "champion@example.com"},
    )
    contact_3 = client.post(
        "/api/v1/crm/contacts",
        headers=superuser_headers,
        json={"firstName": "Influencer", "fullName": "Deal Influencer", "email": "influencer@example.com"},
    )
    assert contact_1.status_code == 201
    assert contact_2.status_code == 201
    assert contact_3.status_code == 201

    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Stakeholder Sales"})
    stage = client.post(
        f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages",
        headers=superuser_headers,
        json={"name": "Evaluation"},
    )
    assert pipeline.status_code == 201
    assert stage.status_code == 201

    deal = client.post(
        "/api/v1/crm/deals",
        headers=superuser_headers,
        json={
            "name": "Multi stakeholder ERP",
            "pipelineId": pipeline.json()["id"],
            "stageId": stage.json()["id"],
            "contacts": [
                {"contactId": contact_1.json()["id"], "role": "Decision Maker", "influenceLevel": "High", "isPrimary": True},
                {"contactId": contact_2.json()["id"], "role": "Champion", "influenceLevel": "High"},
            ],
        },
    )
    assert deal.status_code == 201, deal.text
    assert deal.json()["contact_id"] == contact_1.json()["id"]
    assert db.query(CRMDealContact).filter(CRMDealContact.deal_id == deal.json()["id"]).count() == 2

    detail = client.get(f"/api/v1/crm/deals/{deal.json()['id']}", headers=superuser_headers)
    assert detail.status_code == 200
    related_contacts = detail.json()["related"]["contacts"]
    assert {item["role"] for item in related_contacts} == {"Decision Maker", "Champion"}
    assert related_contacts[0]["isPrimary"] is True

    added = client.post(
        f"/api/v1/crm/deals/{deal.json()['id']}/contacts",
        headers=superuser_headers,
        json={"contactId": contact_3.json()["id"], "role": "Influencer", "influenceLevel": "Medium"},
    )
    assert added.status_code == 201, added.text

    promoted = client.patch(
        f"/api/v1/crm/deals/{deal.json()['id']}/contacts/{added.json()['id']}",
        headers=superuser_headers,
        json={"contactId": contact_3.json()["id"], "role": "Economic Buyer", "isPrimary": True},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["isPrimary"] is True

    refreshed = client.get(f"/api/v1/crm/deals/{deal.json()['id']}", headers=superuser_headers)
    assert refreshed.json()["contact_id"] == contact_3.json()["id"]
    assert len([item for item in refreshed.json()["related"]["contacts"] if item["isPrimary"]]) == 1

    replaced = client.put(
        f"/api/v1/crm/deals/{deal.json()['id']}/contacts",
        headers=superuser_headers,
        json={"contacts": [{"contactId": contact_2.json()["id"], "role": "Champion", "isPrimary": True}]},
    )
    assert replaced.status_code == 200, replaced.text
    assert len(replaced.json()["items"]) == 1

    final_deal = client.get(f"/api/v1/crm/deals/{deal.json()['id']}", headers=superuser_headers)
    assert final_deal.json()["contact_id"] == contact_2.json()["id"]


def test_crm_numeric_lead_scoring_rules_and_manual_override(client, superuser_headers):
    rules = client.get("/api/v1/crm/lead-scoring-rules", headers=superuser_headers)
    assert rules.status_code == 200
    assert any(item["name"] == "Has email" for item in rules.json()["items"])

    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={
            "firstName": "Score",
            "fullName": "Score Lead",
            "email": "score@example.com",
            "phone": "9999999999",
            "companyName": "Score Co",
            "source": "Website",
            "estimatedValue": 800000,
        },
    )
    assert lead.status_code == 201
    assert lead.json()["leadScore"] >= 45
    assert lead.json()["scoreLabel"] in {"Warm", "Hot"}

    manual = client.patch(
        f"/api/v1/crm/leads/{lead.json()['id']}",
        headers=superuser_headers,
        json={"leadScore": 25},
    )
    assert manual.status_code == 200
    assert manual.json()["leadScore"] == 25
    assert manual.json()["scoreLabel"] == "Cold"
    assert manual.json()["leadScoreMode"] == "manual"

    recalc = client.post(f"/api/v1/crm/leads/{lead.json()['id']}/recalculate-score", headers=superuser_headers)
    assert recalc.status_code == 200
    assert recalc.json()["leadScoreMode"] == "automatic"
    assert recalc.json()["leadScore"] >= 45
    assert recalc.json()["scoreReasons"]

    bulk = client.post("/api/v1/crm/leads/recalculate-scores", headers=superuser_headers)
    assert bulk.status_code == 200
    assert bulk.json()["updated"] >= 1


def test_crm_approval_workflow_submit_approve_and_final_gate(client, superuser_headers):
    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Approval Pipeline"})
    assert pipeline.status_code == 201
    stage = client.post(
        f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages",
        headers=superuser_headers,
        json={"name": "Negotiation", "position": 1},
    )
    assert stage.status_code == 201
    deal = client.post(
        "/api/v1/crm/deals",
        headers=superuser_headers,
        json={"name": "Approval Deal", "pipelineId": pipeline.json()["id"], "stageId": stage.json()["id"], "amount": 1500000, "discountAmount": 75000},
    )
    assert deal.status_code == 201

    workflow = client.post(
        "/api/v1/crm/approval-workflows",
        headers=superuser_headers,
        json={
            "name": "High value deal approval",
            "entityType": "deal",
            "triggerType": "manual",
            "conditions": {"minAmount": 1000000},
            "steps": [{"stepOrder": 1, "approverType": "user", "approverId": 1, "actionOnReject": "stop"}],
        },
    )
    assert workflow.status_code == 201
    assert workflow.json()["steps"][0]["approverType"] == "user"

    submitted = client.post(
        "/api/v1/crm/approvals/submit",
        headers=superuser_headers,
        json={"entityType": "deal", "entityId": deal.json()["id"], "workflowId": workflow.json()["id"], "comments": "Needs discount signoff"},
    )
    assert submitted.status_code == 201
    request_id = submitted.json()["id"]
    assert submitted.json()["status"] == "pending"
    assert submitted.json()["steps"][0]["status"] == "pending"

    blocked = client.patch(f"/api/v1/crm/deals/{deal.json()['id']}", headers=superuser_headers, json={"status": "Won"})
    assert blocked.status_code == 409

    pending = client.get("/api/v1/crm/approvals/my-pending", headers=superuser_headers)
    assert pending.status_code == 200
    assert any(item["id"] == request_id for item in pending.json()["items"])

    approved = client.post(
        f"/api/v1/crm/approvals/{request_id}/approve",
        headers=superuser_headers,
        json={"comments": "Approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    won = client.patch(f"/api/v1/crm/deals/{deal.json()['id']}", headers=superuser_headers, json={"status": "Won"})
    assert won.status_code == 200
    assert won.json()["status"] == "Won"

    detail = client.get(f"/api/v1/crm/deals/{deal.json()['id']}", headers=superuser_headers)
    assert detail.status_code == 200
    assert detail.json()["related"]["approval"]["status"] == "approved"
    assert any(event["type"] == "approval" for event in detail.json()["timeline"])


def test_crm_approvals_are_org_scoped(client, db, superuser_headers):
    db.add(CRMApprovalRequest(organization_id=2, workflow_id=None, entity_type="deal", entity_id=999, status="pending", submitted_by=1))
    db.commit()

    approvals = client.get("/api/v1/crm/approvals", headers=superuser_headers, params={"entityType": "deal"})
    assert approvals.status_code == 200
    assert all(item["organizationId"] == 1 for item in approvals.json()["items"])


def test_crm_duplicate_detection_and_merge_relinks_related_records(client, superuser_headers):
    first = client.post(
        "/api/v1/crm/contacts",
        headers=superuser_headers,
        json={"firstName": "Asha", "lastName": "Rao", "fullName": "Asha Rao", "email": "asha@example.com", "phone": "+91 90000 12345"},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/crm/contacts",
        headers=superuser_headers,
        json={"firstName": "Asha", "lastName": "R", "fullName": "Asha R", "email": "asha@example.com", "phone": "9000012345"},
    )
    assert second.status_code == 201
    winner_id = first.json()["id"]
    loser_id = second.json()["id"]

    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Duplicate Pipeline"})
    stage = client.post(f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages", headers=superuser_headers, json={"name": "Open"})
    deal = client.post(
        "/api/v1/crm/deals",
        headers=superuser_headers,
        json={"name": "Duplicate linked deal", "pipelineId": pipeline.json()["id"], "stageId": stage.json()["id"], "contactId": loser_id},
    )
    assert deal.status_code == 201
    quote = client.post(
        "/api/v1/crm/quotations",
        headers=superuser_headers,
        json={"quoteNumber": "DUP-001", "issueDate": "2026-05-10", "expiryDate": "2026-05-30", "contactId": loser_id},
    )
    assert quote.status_code == 201
    task = client.post("/api/v1/crm/tasks", headers=superuser_headers, json={"title": "Duplicate follow-up", "contactId": loser_id})
    assert task.status_code == 201

    detected = client.get("/api/v1/crm/duplicates", headers=superuser_headers, params={"entityType": "contact"})
    assert detected.status_code == 200
    group = next(item for item in detected.json()["items"] if {winner_id, loser_id}.issubset(set(item["recordIds"])))
    assert "Same email" in group["reasons"]

    detail = client.get(f"/api/v1/crm/contacts/{winner_id}", headers=superuser_headers)
    assert detail.status_code == 200
    assert detail.json()["related"]["duplicates"]["count"] >= 1

    merged = client.post(
        "/api/v1/crm/duplicates/merge",
        headers=superuser_headers,
        json={"entityType": "contact", "winnerId": winner_id, "loserIds": [loser_id], "fieldValues": {"phone": "+91 90000 12345"}},
    )
    assert merged.status_code == 200
    assert merged.json()["mergedIds"] == [loser_id]
    assert merged.json()["relatedCounts"]["deals"] == 1
    assert merged.json()["relatedCounts"]["quotations"] == 1
    assert merged.json()["relatedCounts"]["tasks"] == 1

    loser = client.get(f"/api/v1/crm/contacts/{loser_id}", headers=superuser_headers)
    assert loser.status_code == 404
    linked_deal = client.get(f"/api/v1/crm/deals/{deal.json()['id']}", headers=superuser_headers)
    assert linked_deal.json()["contact_id"] == winner_id
    linked_quote = client.get(f"/api/v1/crm/quotations/{quote.json()['id']}", headers=superuser_headers)
    assert linked_quote.json()["contact_id"] == winner_id
    timeline = client.get(f"/api/v1/crm/contacts/{winner_id}", headers=superuser_headers)
    assert any(event["type"] == "activities" and event["record"]["activityType"] == "duplicate_merge" for event in timeline.json()["timeline"])


def test_crm_duplicate_detection_uses_custom_unique_fields_and_merges_values_safely(client, superuser_headers):
    field = client.post(
        "/api/v1/crm/custom-fields",
        headers=superuser_headers,
        json={"entityType": "leads", "fieldName": "External Reference", "fieldKey": "external_ref", "fieldType": "text", "isUnique": True},
    )
    assert field.status_code == 201

    first = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Mira", "fullName": "Mira Iyer", "email": "mira.one@example.com", "customFields": {"external_ref": "EXT-42"}},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Mohan", "fullName": "Mohan Das", "email": "mohan.two@example.com", "customFields": {"external_ref": "EXT-42"}},
    )
    assert second.status_code == 201
    winner_id = first.json()["id"]
    loser_id = second.json()["id"]

    detected = client.get("/api/v1/crm/duplicates", headers=superuser_headers, params={"entityType": "lead"})
    assert detected.status_code == 200
    group = next(item for item in detected.json()["items"] if {winner_id, loser_id}.issubset(set(item["recordIds"])))
    assert "Same custom unique field: external_ref" in group["reasons"]

    merged = client.post(
        "/api/v1/crm/duplicates/merge",
        headers=superuser_headers,
        json={"entityType": "lead", "winnerId": winner_id, "loserIds": [loser_id], "fieldValues": {"status": "Qualified"}},
    )
    assert merged.status_code == 200
    assert merged.json()["relatedCounts"]["customFieldValues"] >= 1

    detail = client.get(f"/api/v1/crm/leads/{winner_id}", headers=superuser_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "Qualified"
    assert any(item["fieldKey"] == "external_ref" and item["value"] == "EXT-42" for item in detail.json()["customFields"])


def test_crm_duplicate_detection_never_compares_across_organizations(client, db, superuser_headers):
    db.add(CRMContact(organization_id=2, first_name="Cross", full_name="Cross Org", email="cross@example.com", phone="9999999999"))
    db.commit()
    contact = client.post(
        "/api/v1/crm/contacts",
        headers=superuser_headers,
        json={"firstName": "Cross", "fullName": "Cross Org", "email": "cross@example.com", "phone": "9999999999"},
    )
    assert contact.status_code == 201

    detected = client.get("/api/v1/crm/duplicates", headers=superuser_headers, params={"entityType": "contact"})
    assert detected.status_code == 200
    assert not any(contact.json()["id"] in group["recordIds"] for group in detected.json()["items"])


def test_crm_win_loss_reports_are_organization_scoped(client, db, superuser_headers):
    owner = db.query(User).filter(User.email == "admin@example.com").first() or db.query(User).first()
    pipeline = CRMPipeline(organization_id=1, name="Report Pipeline")
    other_pipeline = CRMPipeline(organization_id=2, name="Other Org Pipeline")
    db.add_all([pipeline, other_pipeline])
    db.flush()
    proposal = CRMPipelineStage(organization_id=1, pipeline_id=pipeline.id, name="Proposal", position=1, probability=40)
    negotiation = CRMPipelineStage(organization_id=1, pipeline_id=pipeline.id, name="Negotiation", position=2, probability=70)
    other_stage = CRMPipelineStage(organization_id=2, pipeline_id=other_pipeline.id, name="Proposal", position=1, probability=40)
    db.add_all([proposal, negotiation, other_stage])
    db.flush()
    db.add_all(
        [
            CRMDeal(
                organization_id=1,
                owner_user_id=owner.id if owner else None,
                pipeline_id=pipeline.id,
                stage_id=proposal.id,
                name="Won analytics deal",
                amount=100000,
                status="Won",
                source="Website",
                won_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
                closed_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
                created_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
            ),
            CRMDeal(
                organization_id=1,
                owner_user_id=owner.id if owner else None,
                pipeline_id=pipeline.id,
                stage_id=negotiation.id,
                name="Lost analytics deal",
                amount=50000,
                status="Lost",
                source="Referral",
                lost_reason="Price",
                lost_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
                closed_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
                created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
            CRMDeal(
                organization_id=2,
                pipeline_id=other_pipeline.id,
                stage_id=other_stage.id,
                name="Other org won deal",
                amount=999999,
                status="Won",
                source="Website",
                won_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
                closed_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
                created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()

    report = client.get(
        "/api/v1/crm/reports/win-loss",
        headers=superuser_headers,
        params={"startDate": "2026-05-01", "endDate": "2026-05-31", "pipelineId": pipeline.id},
    )
    assert report.status_code == 200
    payload = report.json()
    assert payload["summary"]["wonDeals"] == 1
    assert payload["summary"]["lostDeals"] == 1
    assert payload["summary"]["wonRevenue"] == 100000
    assert payload["summary"]["winRate"] == 50
    assert payload["lostReasonBreakdown"][0]["reason"] == "Price"
    assert all(deal["amount"] != 999999 for deal in payload["deals"])

    funnel = client.get("/api/v1/crm/reports/sales-funnel", headers=superuser_headers, params={"startDate": "2026-05-01", "endDate": "2026-05-31"})
    assert funnel.status_code == 200
    assert {row["stage"] for row in funnel.json()["items"]} >= {"Proposal", "Negotiation"}

    trend = client.get("/api/v1/crm/reports/revenue-trend", headers=superuser_headers, params={"startDate": "2026-05-01", "endDate": "2026-05-31"})
    assert trend.status_code == 200
    assert trend.json()["items"][0]["revenue"] == 100000


def test_crm_territory_rules_assign_records_and_remain_org_scoped(client, db, superuser_headers):
    owner = db.query(User).filter(User.email == "admin@example.com").first() or db.query(User).first()
    territory = client.post(
        "/api/v1/crm/territories",
        headers=superuser_headers,
        json={
            "name": "Karnataka Enterprise",
            "rules": {"country": "India", "state": "Karnataka", "industry": "Software"},
            "priority": 1,
            "isActive": True,
        },
    )
    assert territory.status_code == 201
    territory_id = territory.json()["id"]

    user_link = client.post(f"/api/v1/crm/territories/{territory_id}/users", headers=superuser_headers, json={"userId": owner.id})
    assert user_link.status_code == 201
    assert db.query(CRMTerritoryUser).filter(CRMTerritoryUser.territory_id == territory_id, CRMTerritoryUser.user_id == owner.id).count() == 1

    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Tara", "fullName": "Tara Rao", "companyName": "Cloud Works", "country": "India", "state": "Karnataka", "industry": "Software"},
    )
    assert lead.status_code == 201
    assert lead.json()["territoryId"] == territory_id
    assert lead.json()["ownerId"] == owner.id

    manual = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Manual", "fullName": "Manual Owner", "companyName": "Cloud Works", "country": "India", "state": "Karnataka", "industry": "Software", "territoryId": territory_id},
    )
    assert manual.status_code == 201
    assert manual.json()["territoryId"] == territory_id

    db.add(CRMLead(organization_id=2, first_name="Other", full_name="Other Org", company_name="Other Org", country="India", state="Karnataka", industry="Software"))
    db.commit()
    assigned = client.post("/api/v1/crm/territories/auto-assign", headers=superuser_headers, json={})
    assert assigned.status_code == 200
    assert all(item["entityId"] != 999999 for item in assigned.json()["items"])
    listed = client.get("/api/v1/crm/leads", headers=superuser_headers, params={"territoryId": territory_id})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2
    report = client.get("/api/v1/crm/reports/territories", headers=superuser_headers)
    assert report.status_code == 200
    row = next(item for item in report.json()["items"] if item["territoryId"] == territory_id)
    assert row["leads"] >= 2
    assert row["users"] == 1


def test_crm_contact_enrichment_preview_apply_and_history(client, db, superuser_headers):
    lead = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={"firstName": "Enrich", "fullName": "Enrich Lead", "email": "enrich@example.com", "companyName": "OldCo"},
    )
    assert lead.status_code == 201
    lead_id = lead.json()["id"]

    preview = client.post(
        "/api/v1/crm/enrichment/preview",
        headers=superuser_headers,
        json={
            "entityType": "lead",
            "entityId": lead_id,
            "provider": "manual",
            "enrichmentData": {
                "jobTitle": "VP Sales",
                "company": "NewCo",
                "companyWebsite": "https://newco.example",
                "industry": "Software",
                "companySize": 250,
                "linkedInUrl": "https://linkedin.example/in/enrich",
                "phone": "+91 90000 44444",
                "emailVerificationStatus": "verified",
                "socialProfiles": {"linkedin": "https://linkedin.example/in/enrich"},
            },
        },
    )
    assert preview.status_code == 200
    fields = {field["key"]: field for field in preview.json()["fields"]}
    assert fields["jobTitle"]["supported"] is True
    assert fields["company"]["oldValue"] == "OldCo"

    applied = client.post(
        "/api/v1/crm/enrichment/apply",
        headers=superuser_headers,
        json={
            "entityType": "lead",
            "entityId": lead_id,
            "provider": "manual",
            "values": preview.json()["values"],
            "appliedFields": ["jobTitle", "company", "companyWebsite", "emailVerificationStatus"],
        },
    )
    assert applied.status_code == 200
    record = applied.json()["record"]
    assert record["job_title"] == "VP Sales"
    assert record["company_name"] == "NewCo"
    assert record["company_website"] == "https://newco.example"
    assert record["email_verification_status"] == "verified"

    history = client.get("/api/v1/crm/enrichment/history", headers=superuser_headers, params={"entityType": "lead", "entityId": lead_id})
    assert history.status_code == 200
    assert history.json()["total"] >= 2
    assert db.query(CRMEnrichmentLog).filter(CRMEnrichmentLog.entity_type == "lead", CRMEnrichmentLog.entity_id == lead_id, CRMEnrichmentLog.status == "applied").count() == 1

    detail = client.get(f"/api/v1/crm/leads/{lead_id}", headers=superuser_headers)
    assert any(event["type"] == "activities" and event["record"]["activityType"] == "enrichment" for event in detail.json()["timeline"])

    db.add(CRMLead(organization_id=2, first_name="Other", full_name="Other Enrich", email="other-enrich@example.com"))
    db.commit()
    other = db.query(CRMLead).filter(CRMLead.organization_id == 2, CRMLead.email == "other-enrich@example.com").first()
    blocked = client.post(
        "/api/v1/crm/enrichment/preview",
        headers=superuser_headers,
        json={"entityType": "lead", "entityId": other.id, "provider": "manual", "data": {"jobTitle": "Blocked"}},
    )
    assert blocked.status_code == 404
