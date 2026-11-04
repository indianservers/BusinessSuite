import pytest
from fastapi import HTTPException
from types import SimpleNamespace
from app.apps.crm.custom_field_config import validate_config, option_values
from app.apps.crm.api.router import _custom_field_storage
from app.apps.project_management.custom_fields import FieldInput, validate_definition, validate_value, ValueInput
from tests.test_crm_associations_merge import superuser_headers, post


@pytest.mark.parametrize("kind", ["radio", "combobox", "dropdown"])
def test_choice_fields_validate_and_preserve_values(client, superuser_headers, kind):
    h = superuser_headers
    field = post(client, h, "crm/custom-fields", {
        "entityType": "leads", "fieldName": "Service", "fieldKey": "service", "fieldType": kind,
        "options": {"values": ["Audit", "Tax"], "ui": {"places": ["create", "edit", "detail"], "section": "Preferences"}},
    })
    lead = post(client, h, "crm/leads", {"first_name": "Client", "full_name": "Client", "customFields": {"service": "Tax"}})
    path = f"/api/v1/crm/leads/{lead['id']}"
    assert client.patch(path, headers=h, json={"notes": "Keep custom values"}).status_code == 200
    detail = client.get(path, headers=h).json()
    assert next(f["value"] for f in detail["customFields"] if f["id"] == field["id"]) == "Tax"
    assert client.patch(path, headers=h, json={"customFields": {"service": "Unknown"}}).status_code == 422
    assert client.patch(f"/api/v1/crm/custom-fields/{field['id']}", headers=h, json={"options": {"values": ["Audit"]}}).status_code == 409
    assert client.patch(f"/api/v1/crm/custom-fields/{field['id']}", headers=h, json={"fieldType": "number"}).status_code == 409
    assert client.patch(path, headers=h, json={"customFields": {"service": None}}).status_code == 200
    assert next(f["value"] for f in client.get(path, headers=h).json()["customFields"] if f["id"] == field["id"]) is None


def test_required_fields_cannot_be_hidden_from_creation():
    with pytest.raises(HTTPException):
        validate_config({"is_required": True, "options_json": {"ui": {"places": ["detail"]}}})
    assert option_values(["Existing"]) == ["Existing"]
    field = SimpleNamespace(field_type="checkbox", is_required=True, options_json=[])
    assert _custom_field_storage(field, False)["value_boolean"] is False
    field.field_type = "number"
    assert _custom_field_storage(field, 0)["value_number"] == 0


@pytest.mark.parametrize("kind", ["radio", "combobox"])
def test_project_choices_accept_new_controls_and_legacy_values(kind):
    assert validate_definition(FieldInput(name="Service", field_type=kind, options=["Audit", "Tax"])) == ("Service", ["Audit", "Tax"])
    for raw in ('["Audit", "Tax"]', '{"values":["Audit","Tax"],"ui":{"places":["detail"]}}'):
        field = SimpleNamespace(field_type=kind, options_json=raw)
        assert validate_value(field, ValueInput(value="Tax")) == "Tax"
        with pytest.raises(HTTPException):
            validate_value(field, ValueInput(value="Other"))


@pytest.mark.parametrize("path", ["/api/v1/employees/", "/api/v1/employees/workbench/quick-add"])
def test_employee_native_forms_store_platform_fields(client, db, superuser_headers, path):
    h = superuser_headers
    from app.models.company import Department, Designation
    from app.models.user import User
    from test_identity_utils import attach_workflow_branch, own_workflow_records
    branch=attach_workflow_branch(db,db.query(User).filter_by(email="testadmin@test.com").one())
    h={**h,"X-Suite-Branch":str(branch.id)}
    department = Department(name="Field test department",branch_id=int(h["X-Suite-Branch"]))
    db.add(department);db.flush()
    designation=Designation(name="Field test designation",department_id=department.id)
    db.add(designation);db.flush()
    own_workflow_records(db,department,designation)
    db.commit()
    field = post(client, h, "custom-fields/definitions", {"module": "employees", "field_key": "service", "label": "Service", "field_type": "radio", "is_required": True, "options_json": {"values": ["Audit", "Tax"], "ui": {"places": ["create", "quick_create", "edit", "detail"]}}})
    payload = {"first_name": "Custom", "last_name": "Employee", "date_of_joining": "2026-11-04", "branch_id": int(h["X-Suite-Branch"])}
    missing = client.post(path, headers=h, json=payload)
    assert missing.status_code == 422, missing.text
    response = client.post(path, headers=h, json={**payload, "custom_fields": {"service": "Audit"}})
    assert response.status_code == 201, response.text
    ident = response.json()["id"]
    fields = client.get("/api/v1/employees/custom-fields/definitions", headers=h, params={"employee_id": ident})
    assert fields.status_code == 200, fields.text
    assert next(f["value"] for f in fields.json()["items"] if f["id"] == field["id"]) == "Audit"
    updated = client.put(f"/api/v1/employees/{ident}", headers=h, json={"custom_fields": {"service": "Tax"}})
    assert updated.status_code == 200, updated.text
    assert client.put(f"/api/v1/employees/{ident}", headers=h, json={"custom_fields": {"service": "Unknown"}}).status_code == 422


@pytest.mark.parametrize("entity,path,payload", [
    ("leads", "crm/lead-management/leads", {"values": {"full_name": "Capture custom client"}}),
    ("contacts", "crm/contact-directory", {"name": "Directory custom client"}),
    ("companies", "master-data/companies", {"name": "Custom company"}),
])
def test_native_crm_entry_points_save_fields_in_existing_tables(client, superuser_headers, entity, path, payload):
    h = superuser_headers
    field = post(client, h, "crm/custom-fields", {"entityType": entity, "fieldName": "Service", "fieldKey": "service", "fieldType": "combobox", "isRequired": True, "options": {"values": ["Audit", "Tax"], "ui": {"places": ["create", "quick_create", "edit", "detail"]}}})
    missing = client.post("/api/v1/" + path, headers=h, json=payload)
    assert missing.status_code == 422, missing.text
    record = post(client, h, path, {**payload, "customFields": {"service": "Audit"}})
    detail = client.get(f"/api/v1/crm/{entity}/{record['id']}", headers=h)
    assert detail.status_code == 200, detail.text
    assert next(f["value"] for f in detail.json()["customFields"] if f["id"] == field["id"]) == "Audit"


def test_custom_module_choices_and_hidden_values_survive_edit(client, superuser_headers):
    h = superuser_headers
    post(client, h, "customization/modules", {"module_api_name": "field_records", "module_label": "Field record", "plural_label": "Field records"})
    field_payload = {"module_name": "field_records", "field_api_name": "service", "field_label": "Service", "field_type": "combobox", "options": [{"value": "Audit", "label": "Audit"}, {"value": "Tax", "label": "Tax"}]}
    field = post(client, h, "customization/fields", field_payload)
    record = post(client, h, "custom/field_records", {"values": {"service": "Audit"}})
    invalid = client.put(f"/api/v1/custom/field_records/{record['id']}", headers=h, json={"values": {"service": "Unknown"}})
    assert invalid.status_code == 400, invalid.text
    hidden = client.put(f"/api/v1/customization/fields/{field['id']}", headers=h, json={**field_payload, "visible": False})
    assert hidden.status_code == 200, hidden.text
    updated = client.put(f"/api/v1/custom/field_records/{record['id']}", headers=h, json={"values": {}})
    assert updated.status_code == 200, updated.text
    assert updated.json()["values_json"]["service"] == "Audit"


def test_public_form_combobox_validates_options():
    from app.forms.schema import Definition, clean_answers
    form = Definition(name="Service request", fields=[{"id": "service", "type": "combobox", "label": "Service", "required": True, "options": ["Audit", "Tax"]}])
    assert clean_answers(form, {"service": "Audit"})["service"] == "Audit"
    with pytest.raises(HTTPException):
        clean_answers(form, {"service": "Unknown"})


def test_inline_company_contact_uses_contact_field_settings(client, superuser_headers):
    h = superuser_headers
    post(client, h, "crm/custom-fields", {"entityType": "contacts", "fieldName": "Contact service", "fieldKey": "service", "fieldType": "radio", "isRequired": True, "options": ["Audit", "Tax"]})
    payload = {"name": "Inline field company", "newPrimaryContact": {"name": "Primary contact", "customFields": {"service": "Audit"}}}
    company = post(client, h, "master-data/companies", payload)
    detail = client.get(f"/api/v1/crm/contacts/{company['primaryContactId']}", headers=h)
    assert detail.status_code == 200, detail.text
    assert next(f["value"] for f in detail.json()["customFields"] if f["fieldKey"] == "service") == "Audit"


@pytest.mark.parametrize("kind,value", [("Number", 0), ("Checkbox", False)])
def test_legacy_platform_value_api_keeps_zero_and_false(client, superuser_headers, kind, value):
    h=superuser_headers
    field=post(client,h,"custom-fields/definitions",{"module":"legacy","field_key":"value","label":"Value","field_type":kind,"is_required":True})
    response=client.put("/api/v1/custom-fields/values",headers=h,json={"definition_id":field["id"],"entity_type":"legacy","entity_id":1,"value_json":value})
    assert response.status_code==200,response.text
    assert response.json()["value_json"] is value or response.json()["value_json"]==value
