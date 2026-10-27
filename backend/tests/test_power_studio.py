import copy
import json
import time
import pytest
from tests.test_power_apps import actors
from app.apps.power_apps.node_registry import NODES
from app.apps.power_apps.graph import VisualWorkflowDefinition
from app.apps.power_apps.studio import validate_graph
from app.apps.power_apps.models import PowerExecution, PowerResource, PowerVersion
ROOT = "/api/v1/power-apps/automations"

def node(id, kind, **config):
    return {"id": id, "type": kind, "label": NODES[kind]["name"], "position": {"x": 100, "y": 200}, "config": {**{f["key"]: f["default"] for f in NODES[kind]["fields"] if "default" in f}, **config}}

def edge(source, target, port="out"):
    return {"id": f"{source}_{port}_{target}", "source": source, "target": target, "source_port": port, "target_port": "in", "label": ""}

def graph():
    return {"schema_version": 2, "nodes": [node("trigger", "manual_trigger"), node("condition", "if_else", left="{{trigger.record.status}}", right="Open"), node("yes", "set_variable", value="{{trigger.record.id}}"), node("no", "log_event", message="Closed {{trigger.record.id}}")], "edges": [edge("trigger", "condition"), edge("condition", "yes", "true"), edge("condition", "no", "false")]}

def create(client, headers, definition=None, name="Visual workflow"):
    response = client.post(ROOT, headers=headers, json={"name": name, "definition": definition or graph()})
    assert response.status_code == 201, response.text
    return response.json()

def test_catalog_preserves_schema_driven_editor_nodes(client, actors):
    result = client.get(ROOT + "/node-catalog", headers=actors[0])
    assert result.status_code == 200, result.text
    definitions = result.json()["nodes"]
    assert len(definitions) == len({n["id"] for n in definitions}) >= 48
    assert "approval_wait" in {n["id"] for n in definitions}
    from app.apps.power_apps.runtime_executors import EXECUTORS
    assert all(n["editor_ready"] and n["executable"] == (n["id"] in EXECUTORS) and n["help"] for n in definitions)
    assert all(n["outputs"] or n["id"] == "stop_workflow" for n in definitions)
    for definition in definitions:
        VisualWorkflowDefinition.model_validate({"schema_version": 2, "nodes": [node("sample", definition["id"])]})
    assert client.get(ROOT + "/node-catalog").status_code in {401,403}

def test_visual_layout_and_configuration_persist_and_snapshot(client, db, actors):
    payload = graph(); payload["viewport"] = {"x": 35, "y": -40, "zoom": .7}
    payload["nodes"][1]["position"] = {"x": 440, "y": 300}
    row = create(client, actors[0], payload)
    result = client.get(f"{ROOT}/{row['id']}", headers=actors[0]).json()
    assert result["definition"]["viewport"] == payload["viewport"]
    assert result["definition"]["nodes"][1]["position"] == payload["nodes"][1]["position"]
    update = {"name": "Renamed visual workflow", "definition": result["definition"], "description": "Version two", "expected_version": 1}
    update["definition"]["nodes"][2]["config"]["value"] = "Changed"
    saved = client.put(f"{ROOT}/{row['id']}", headers=actors[0], json=update)
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 2
    assert client.put(f"{ROOT}/{row['id']}", headers=actors[0], json=update).status_code == 409
    versions = client.get(f"{ROOT}/{row['id']}/versions", headers=actors[0]).json()["items"]
    assert versions[1]["snapshot"]["definition"]["nodes"][2]["config"]["value"] == "{{trigger.record.id}}"
    assert db.query(PowerExecution).count() == 0

def test_structural_validation_and_pure_branch_preview(client, db, actors):
    response = client.post(ROOT + "/validate", headers=actors[0], json={"definition": graph()})
    assert response.status_code == 200, response.text
    assert response.json()["valid"] is True and response.json()["executable"] is False
    result = client.post(ROOT + "/preview", headers=actors[0], json={"definition": graph(), "test_input": {"record": {"id": 42, "status": "Open"}}})
    assert result.status_code == 200, result.text
    body = result.json(); assert body["design_time_only"] and not body["integration_execution"]
    entries = {e["node_id"]: e for e in body["timeline"]}
    assert entries["yes"]["output"] == {"value":42}
    assert entries["no"]["status"] == "not_reached"
    assert entries["condition"]["output"] == {"result":True}
    assert db.query(PowerExecution).count() == 0
    assert db.query(PowerResource).count() == 0  # Preview cannot mutate drafts either.

def test_incomplete_drafts_save_but_validation_reports_missing_settings(client, actors):
    value = {"schema_version": 2, "nodes": [node("trigger", "manual_trigger"), node("email", "send_email")], "edges": []}
    create(client, actors[0], value)
    result = client.post(ROOT + "/validate", headers=actors[0], json={"definition": value}).json()
    assert result["valid"] is False
    assert {"required", "credential", "disconnected"} <= {i["code"] for i in result["issues"]}
    preview = client.post(ROOT + "/preview", headers=actors[0], json={"definition": value}).json()
    assert preview["timeline"] == []

@pytest.mark.parametrize("change", ["unknown_node","javascript","secret","cycle","incompatible","bad_reference_edge","oversized_loop","unknown_config","prototype"])
def test_server_rejects_unsafe_graphs(client, actors, change):
    value = graph()
    if change == "unknown_node": value["nodes"][2]["type"] = "run_javascript"
    if change == "javascript": value["nodes"][2]["config"]["value"] = "{{__import__('os').system('echo unsafe')}}"
    if change == "secret": value["nodes"][2]["config"] = {"api_key":"unsafe-secret"}
    if change == "prototype": value["nodes"][2]["config"]["value"] = "{{trigger.record.__proto__}}"
    if change == "bad_reference_edge": value["edges"][0]["target"] = "missing"
    if change == "incompatible": value["edges"][1]["source_port"] = "error"
    if change == "oversized_loop": value = {"schema_version":2,"nodes":[node("loop","loop",max_iterations=1001)]}
    if change == "unknown_config": value["nodes"][0]["config"] = {"unexpected": True}
    if change == "cycle": value = {"schema_version":2,"nodes":[node("a","set_variable",value="a"),node("b","set_variable",value="b")],"edges":[edge("a","b"),edge("b","a")]}
    response = client.post(ROOT, headers=actors[0], json={"name":"Unsafe", "definition":value})
    assert response.status_code == 422, response.text

def test_forward_reference_is_an_authoritative_validation_error(client, actors):
    value = graph(); value["nodes"][1]["config"]["left"] = "{{steps.yes.output.value}}"
    result = client.post(ROOT + "/validate", headers=actors[0], json={"definition":value})
    assert result.status_code == 200, result.text
    assert not result.json()["valid"]
    assert any(i["code"] == "reference" for i in result.json()["issues"])

def test_external_actions_are_never_previewed(client, db, actors, monkeypatch):
    import httpx
    def forbidden(*args, **kwargs): raise AssertionError("A design-time preview attempted a network call")
    monkeypatch.setattr(httpx, "get", forbidden)
    value = {"schema_version":2,"nodes":[node("trigger","manual_trigger"),{**node("request","http_request",url="https://example.com"),"credential_reference":"ref_only"}],"edges":[edge("trigger","request")]}
    response = client.post(ROOT + "/preview", headers=actors[0], json={"definition":value})
    assert response.status_code == 200, response.text
    assert response.json()["timeline"][1]["status"] == "not_executable"
    assert response.json()["timeline"][1]["output"] is None
    assert db.query(PowerExecution).count() == 0

def test_archive_duplicate_restore_and_scope(client, actors):
    row = create(client, actors[0]); id = row["id"]
    duplicate = client.post(f"{ROOT}/{id}/duplicate", headers=actors[0], json={})
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["id"] != id and duplicate.json()["version"] == 1
    restored = client.post(f"{ROOT}/{id}/restore", headers=actors[0], json={"version":1})
    assert restored.status_code == 201 and restored.json()["id"] not in {id, duplicate.json()["id"]}
    archived = client.post(f"{ROOT}/{id}/archive", headers=actors[0], json={"expected_version":1})
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived_at"] and archived.json()["version"] == 2
    assert id not in [r["id"] for r in client.get(ROOT, headers=actors[0]).json()["items"]]
    assert [r["id"] for r in client.get(ROOT + "?view=disabled", headers=actors[0]).json()["items"]] == [id]
    assert client.put(f"{ROOT}/{id}", headers=actors[0], json={"name":"No", "definition":graph(), "expected_version":2}).status_code == 409
    assert client.post(f"{ROOT}/{id}/unarchive", headers=actors[0], json={"expected_version":1}).status_code == 409
    assert client.post(f"{ROOT}/{id}/unarchive", headers=actors[0], json={"expected_version":2}).status_code == 200
    for action, body in [("duplicate", {}), ("restore", {"version":1}), ("archive", {"expected_version":3})]:
        assert client.post(f"{ROOT}/{id}/{action}", headers=actors[1], json=body).status_code == 404
        assert client.post(f"{ROOT}/{id}/{action}", headers=actors[2], json=body).status_code == 403
    assert client.get(ROOT + "?view=published", headers=actors[0]).json()["items"] == []

def test_templates_are_versioned_and_require_explicit_configuration(client, actors):
    templates = client.get(ROOT + "/templates", headers=actors[0])
    assert templates.status_code == 200, templates.text
    assert len(templates.json()["items"]) >= 30
    for template in templates.json()["items"]:
        assert template["version"] == 1 and template["definition"]["schema_version"] == 2
        assert template["requires_configuration"] and not template["executable"]
    response = client.post(ROOT + "/templates/critical-escalation/use", headers=actors[0])
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "draft"
    assert client.post(ROOT + "/templates/critical-escalation/use", headers=actors[2]).status_code == 403
    assert client.post(ROOT + "/templates/does-not-exist/use", headers=actors[0]).status_code == 404

@pytest.mark.parametrize("count", [10,50,100,250])
def test_graph_validation_scales_and_round_trips(client, actors, count):
    value = {"schema_version":2,"nodes":[node("trigger","manual_trigger")] + [node(f"step_{i}","set_variable",value=i) for i in range(1,count)],"edges":[edge("trigger" if i==1 else f"step_{i-1}", f"step_{i}") for i in range(1,count)]}
    # Dynamic fields accept string references or literal text; use strings for literal values.
    for n in value["nodes"][1:]: n["config"]["value"] = str(n["config"]["value"])
    started = time.perf_counter(); parsed = VisualWorkflowDefinition.model_validate(value); result = validate_graph(parsed); elapsed = time.perf_counter() - started
    assert result["valid"] and elapsed < 1.5
    row = create(client, actors[0], value, name=f"{count} node graph")
    reopened = client.get(f"{ROOT}/{row['id']}", headers=actors[0]).json()
    assert len(reopened["definition"]["nodes"]) == count


def test_sensitive_reference_changes_are_audited_without_loading_secrets(client, db, actors):
    value = {"schema_version":2,"nodes":[node("trigger","manual_trigger"),{**node("request","http_request",url="https://example.com"),"credential_reference":"reference_one"}],"edges":[edge("trigger","request")]}
    row = create(client, actors[0], value)
    value["nodes"][1]["credential_reference"] = "reference_two"
    result = client.put(f"{ROOT}/{row['id']}", headers=actors[0], json={"name":row["name"],"definition":value,"expected_version":row["version"]})
    assert result.status_code == 200, result.text
    activity = client.get("/api/v1/power-apps/activity", headers=actors[0]).json()["items"]
    assert any(item["action"] == "credential_reference_changed" for item in activity)
    assert db.query(PowerExecution).count() == 0


@pytest.mark.parametrize("key", ["api-key", "X-API-Key", "client-secret", "token"])
def test_json_configuration_cannot_hide_inline_secrets(client, actors, key):
    value = {"schema_version":2,"nodes":[node("trigger","manual_trigger"),node("json","build_json",value={key:"inline-secret"})],"edges":[edge("trigger","json")]}
    assert client.post(ROOT,headers=actors[0],json={"name":"Unsafe body","definition":value}).status_code == 422


def test_premium_metadata_roundtrip_snapshots_and_safe_preview(client, actors):
    value = graph()
    value.update({"tags": ["Sales", "Review"], "variables": {"greeting": "Welcome", "limit": 42},
        "editor": {"snap_to_grid": False, "connection_style": "orthogonal"},
        "annotations": [{"id": "note_a", "text": "<script>plain text</script>", "position": {"x": 12, "y": 34}}],
        "groups": [{"id": "group_a", "label": "Branches", "node_ids": ["yes", "no"], "position": {"x": 0, "y": 0}, "width": 500, "height": 400, "collapsed": True}]})
    value["nodes"][2]["config"]["value"] = "{{workflow.variables.limit}}"
    value["nodes"][3]["disabled"] = True
    value["edges"][0]["style"] = "orthogonal"
    row = create(client, actors[0], value)
    saved = client.get(f"{ROOT}/{row['id']}", headers=actors[0]).json()["definition"]
    assert saved["groups"][0]["collapsed"] and saved["nodes"][3]["disabled"]
    assert saved["annotations"][0]["text"] == "<script>plain text</script>"
    assert saved["editor"] == value["editor"] and saved["variables"]["limit"] == 42
    response = client.post(ROOT + "/preview", headers=actors[0], json={"definition": saved, "test_input": {"record": {"status": "Open", "id": 1}}})
    assert response.status_code == 200, response.text
    timeline = {entry["node_id"]: entry for entry in response.json()["timeline"]}
    assert timeline["yes"]["output"]["value"] == 42
    assert timeline["no"]["status"] == "disabled"
    saved["nodes"][2]["config"]["value"] = "{{env.name}}"
    response = client.post(ROOT + "/preview", headers=actors[0], json={"definition": saved, "test_input": {"record": {"status": "Open"}}})
    assert response.json()["timeline"][2]["output"]["value"] == "development"

@pytest.mark.parametrize("mutation", ["secret", "expression", "duplicate_note", "unsafe_variable", "long_tag", "oversized_notes"])
def test_premium_metadata_rejects_unsafe_imports(client, actors, mutation):
    value = graph()
    if mutation == "secret": value["variables"] = {"api-key": "hidden"}
    if mutation == "expression": value["variables"] = {"name": "{{trigger.record.id}}"}
    if mutation == "unsafe_variable": value["variables"] = {"constructor": "unsafe"}
    if mutation == "duplicate_note": value["annotations"] = [{"id": "trigger", "position": {"x": 0, "y": 0}}]
    if mutation == "long_tag": value["tags"] = ["x" * 61]
    if mutation == "oversized_notes": value["annotations"] = [{"id": f"n_{i}", "position": {"x": 0, "y": 0}} for i in range(101)]
    assert client.post(ROOT, headers=actors[0], json={"name": "Unsafe", "definition": value}).status_code == 422


def test_subworkflow_reference_validation_respects_tenant_environment_and_archive(client, actors):
    original = create(client, actors[0])
    value = {"schema_version": 2, "nodes": [node("start", "manual_trigger"), node("sub", "sub_workflow", workflow_id=str(original["id"]))], "edges": [edge("start", "sub")]}
    result = client.post(ROOT + "/validate", headers=actors[0], json={"definition": value})
    assert result.status_code == 200 and result.json()["valid"], result.text
    value["nodes"][1]["config"]["workflow_id"] = "9" * 5000
    result = client.post(ROOT + "/validate", headers=actors[0], json={"definition": value}).json()
    assert any(issue["code"] == "workflow_reference" for issue in result["issues"])
    value["nodes"][1]["config"]["workflow_id"] = str(original["id"])
    client.post(f"{ROOT}/{original['id']}/archive", headers=actors[0], json={"expected_version": 1})
    assert not client.post(ROOT + "/validate", headers=actors[0], json={"definition": value}).json()["valid"]
