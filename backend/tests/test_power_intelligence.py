import copy
import json
import pytest
from fastapi import HTTPException
from app.apps.power_apps.authoring import map_value, condition
from app.apps.power_apps.graph import VisualWorkflowDefinition
from app.apps.power_apps.intelligence import portable
from app.apps.power_apps.studio import preview_graph, validate_graph
from app.apps.power_apps.models import PowerExecution, PowerResource, PowerVersion
from app.apps.power_apps.node_registry import NODES
from tests.test_power_apps import actors
from tests.test_power_studio import graph, node, edge, ROOT, create


def mapping(value,operations=None,target_type="any",nullable=False):
    return {"constant":value,"source":None,"operations":operations or [],"target_type":target_type,"nullable":nullable}

@pytest.mark.parametrize("value,ops,expected",[
    (None,[{"op":"default","argument":"Missing"}],"Missing"),
    ("42",[{"op":"convert","argument":"number"}],42),
    ("true",[{"op":"convert","argument":"boolean"}],True),
    ("Hello",[{"op":"concat","argument":[" ","world"]}],"Hello world"),
    ("2026-10-27T12:00:00",[{"op":"format_date","argument":"year-month"}],"2026-10"),
    (42.567,[{"op":"format_number","argument":2}],"42.57"),
    ([1,2,3],[{"op":"filter","argument":{"operator":"greater_than","right":1}}],[2,3]),
    ([{"amount":1},{"amount":3}],[{"op":"map","argument":[{"op":"path","argument":"amount"}]}],[1,3]),
    ({"old":1},[{"op":"rename","argument":{"old":"new"}}],{"new":1}),
    (None,[{"op":"conditional","argument":{"condition":{"operator":"is_empty"},"then":"Missing","else":"Present"}}],"Missing"),
    ("High",[{"op":"lookup","argument":{"High":100}}],100),
    ({"items":[{"name":"One"}]},[{"op":"path","argument":"items.0.name"}],"One"),
    ('{"a":1}',[{"op":"convert","argument":"object"}],{"a":1}),
    ('[1,2]',[{"op":"convert","argument":"array"}],[1,2]),
])
def test_restricted_mapping_operators(value,ops,expected):
    assert map_value(mapping(value,ops),{})==expected

@pytest.mark.parametrize("spec",[
    mapping("42",target_type="number"),mapping("not a number",[{"op":"convert","argument":"number"}]),
    mapping(None),mapping(1,[{"op":"format_number","argument":99999}]),
    mapping({},[{"op":"path","argument":"__proto__.secret"}]),
    mapping({"a":1,"b":2},[{"op":"rename","argument":{"a":"x","b":"x"}}]),
    mapping([1],[{"op":"map","argument":[{"op":"eval","argument":"alert(1)"}]}]),
    mapping({"password":"never export"}),
])
def test_mapping_rejects_coercion_secrets_and_code(spec):
    with pytest.raises((ValueError,TypeError,KeyError)):map_value(spec,{})

@pytest.mark.parametrize("operator,left,right",[("greater_or_equal",4,4),("less_or_equal",4,4),("ends_with","hello","lo"),("is_not_empty","a",None),("in_list",2,[1,2]),("not_in_list",3,[1,2]),("date_before","2026-01-01","2026-02-01"),("date_after","2026-03-01","2026-02-01"),("boolean_equals",True,True)])
def test_typed_conditions(operator,left,right):
    assert condition({"join":"and","rules":[{"left":left,"operator":operator,"right":right},{"join":"or","rules":[{"left":1,"operator":"equals","right":1}]}]})


def test_named_router_ports_and_join_validation():
    value={"schema_version":2,"nodes":[node("start","manual_trigger"),node("router","switch",value="High",routes=[{"id":"route_high","label":"Manager review","value":"High"},{"id":"route_low","label":"Standard","value":"Low"}]),node("high","set_variable",value="High"),node("low","set_variable",value="Low"),node("other","set_variable",value="Other")],"edges":[edge("start","router"),edge("router","high","route_high"),edge("router","low","route_low"),edge("router","other","default")]}
    model=VisualWorkflowDefinition.model_validate(value)
    assert validate_graph(model)["valid"]
    timeline={entry["node_id"]:entry for entry in preview_graph(model,{})["timeline"]}
    assert timeline["high"]["status"]=="previewed" and timeline["low"]["status"]=="not_reached"
    value["edges"][1]["source_port"]="route_unknown"
    with pytest.raises(ValueError):VisualWorkflowDefinition.model_validate(value)


def test_mapping_persistence_simulation_fixture_labels_and_error_injection(client,db,actors):
    value={"schema_version":2,"nodes":[node("start","manual_trigger"),node("email","send_email",recipient="fixture@example.invalid",template="review",subject="Review"),node("result","set_variable",value="{{steps.email.output.value}}")],"edges":[edge("start","email"),edge("email","result")]}
    value["nodes"][1]["credential_reference"]="design_connection"
    response=client.post(ROOT+"/preview",headers=actors[0],json={"definition":value,"test_input":{},"synthetic_outputs":{"email":{"value":"synthetic_42"}}})
    assert response.status_code==200,response.text
    timeline=response.json()["timeline"]
    assert timeline[1]["status"]=="synthetic" and timeline[2]["output"]["value"]=="synthetic_42"
    assert db.query(PowerExecution).count()==0
    result=client.post(ROOT+"/preview",headers=actors[0],json={"definition":value,"test_input":{}}).json()
    assert result["timeline"][1]["status"]=="not_executable"
    value=graph();value["nodes"][2]["mappings"]={"value":mapping("42",[{"op":"convert","argument":"number"}],"number")}
    row=create(client,actors[0],value)
    assert client.get(f"{ROOT}/{row['id']}",headers=actors[0]).json()["definition"]["nodes"][2]["mappings"]["value"]["target_type"]=="number"
    result=client.post(ROOT+"/preview",headers=actors[0],json={"definition":value,"test_input":{"record":{"status":"Open","id":1}},"injected_errors":["yes"]}).json()
    assert next(t for t in result["timeline"] if t["node_id"]=="yes")["status"]=="error"


def test_portable_definition_remaps_strips_and_rejects_injection(client,actors):
    value=graph();value["nodes"][2]["credential_reference"]="private_connection"
    response=client.post(ROOT+"/portable/prepare",headers=actors[0],json={"definition":value})
    assert response.status_code==200,response.text
    result=response.json()["definition"]
    assert not any(n["credential_reference"] for n in result["nodes"])
    assert not {n["id"] for n in result["nodes"]}&{n["id"] for n in value["nodes"]}
    assert all(e["source"] in {n["id"] for n in result["nodes"]} for e in result["edges"])
    value["nodes"][2]["config"]["value"]="{{constructor.constructor('return process')()}}"
    assert client.post(ROOT+"/portable/prepare",headers=actors[0],json={"definition":value}).status_code==422


def test_quality_documentation_and_mapping_api_authorization(client,actors):
    row=create(client,actors[0])
    result=client.post(ROOT+"/intelligence/analyze",headers=actors[0],json={"definition":graph(),"name":"Review","workflow_id":row["id"],"version":1})
    assert result.status_code==200,result.text
    data=result.json();assert data["quality"]["score"]<100 and "not a security certification" in data["quality"]["label"]
    assert "Version 1" in data["documentation"] and "design-time" in data["documentation"].lower()
    assert client.post(ROOT+"/mapping/preview",headers=actors[0],json={"mapping":mapping(42),"context":{}}).json()["value"]==42
    assert client.post(ROOT+"/mapping/preview",json={"mapping":mapping(42),"context":{}}).status_code in (401,403)
    assert client.post(ROOT+"/mapping/preview",headers=actors[0],json={"mapping":{**mapping(None),"source":"{{env.password}}"},"context":{}}).status_code==422


def test_block_versions_dependency_cycles_tenant_and_usage_guards(client,db,actors):
    part={"schema_version":2,"nodes":[node("step","set_variable",value="First")],"block_contract":{"inputs":[{"name":"value","node_id":"step","field":"value","data_type":"string","default":"First"}],"outputs":[{"name":"result","node_id":"step","field":"value","data_type":"any","default":None}]}}
    response=client.post(ROOT+"/blocks",headers=actors[0],json={"name":"Review block","definition":part});assert response.status_code==201,response.text
    block=response.json();id=block["id"]
    part["nodes"][0]["config"]["value"]="Second"
    response=client.put(f"{ROOT}/blocks/{id}",headers=actors[0],json={"name":"Review block","definition":part,"expected_version":1});assert response.status_code==200,response.text
    versions=client.get(f"{ROOT}/blocks/{id}/versions",headers=actors[0]).json()["items"]
    assert versions[-1]["snapshot"]["definition"]["nodes"][0]["config"]["value"]=="First"
    assert client.put(f"{ROOT}/blocks/{id}",headers=actors[0],json={"name":"Stale","definition":part,"expected_version":1}).status_code==409
    assert client.get(f"{ROOT}/blocks/{id}/versions",headers=actors[1]).status_code==404
    workflow=graph();workflow["block_references"]=[{"resource_id":id,"version":1,"node_ids":["yes"]}]
    create(client,actors[0],workflow)
    assert client.get(f"{ROOT}/blocks/{id}/usage",headers=actors[0]).json()["items"]
    assert client.post(f"{ROOT}/blocks/{id}/archive",headers=actors[0],json={"expected_version":2}).status_code==409
    part["block_references"]=[{"resource_id":id,"version":1,"node_ids":["step"]}]
    assert client.put(f"{ROOT}/blocks/{id}",headers=actors[0],json={"name":"Cycle","definition":part,"expected_version":2}).status_code==422
    workflow["block_references"][0]["resource_id"]=999999
    assert client.post(ROOT,headers=actors[0],json={"name":"Foreign dependency","definition":workflow}).status_code==404
    assert client.post(ROOT+"/blocks",headers=actors[2],json={"name":"Denied","definition":part}).status_code==403


def test_ai_gateway_unavailable_and_invalid_output_never_apply(client,db,actors,monkeypatch):
    from app.models.user import User
    from app.ai_operator.models import OperatorProvider
    from app.ai_agents.services.advanced_security import AiSecuritySettingsService,AiUsageService
    from app.ai_operator.providers import encrypt_key
    # Gateway contract isolation substitutes AI governance and provider transport, while retaining Power Apps and tenant checks.
    assert client.post(ROOT+"/ai/propose",headers=actors[2],json={"definition":graph(),"prompt":"Denied"}).status_code==403
    assert client.post(ROOT+"/ai/propose",headers=actors[0],json={"definition":graph(),"prompt":"AI access denied"}).status_code==403
    monkeypatch.setattr("app.access.service.check_background_access",lambda *args,**kwargs:None)
    monkeypatch.setattr("app.apps.business_os.services.module_service.assert_module_enabled",lambda *args,**kwargs:None)
    monkeypatch.setattr("app.ai_agents.api._require_ai_access",lambda user:None)
    monkeypatch.setattr(AiSecuritySettingsService,"ensure_enabled",lambda *args,**kwargs:None)
    monkeypatch.setattr(AiUsageService,"check_limits",lambda *args,**kwargs:None)
    request={"definition":graph(),"prompt":"Design a review workflow","provider":"gemini"}
    assert client.post(ROOT+"/ai/propose",headers=actors[0],json=request).status_code==503
    user=db.query(User).filter_by(email="power-0@example.com").one()
    db.add(OperatorProvider(scope_key="company:1",provider="gemini",model="configured-model",encrypted_key=encrypt_key("isolated-test-key"),enabled=True,data_sharing_allowed=True,updated_by=user.id));db.commit()
    assert db.query(OperatorProvider).filter_by(scope_key="company:1",enabled=True,data_sharing_allowed=True).count()==1
    from app.apps.power_apps.service import organization as actual_org
    scopes=[]
    def trace_org(user):
        value=actual_org(user);scopes.append(value);return value
    monkeypatch.setattr("app.apps.power_apps.intelligence_api.organization",trace_org)
    def valid(*args,**kwargs):
        assert kwargs["module"]=="POWER_APPS" and not kwargs.get("tools")
        return {"summary":"Reviewable proposal","findings":[],"definition":graph()}
    monkeypatch.setattr("app.ai_operator.providers.generate_json",valid)
    response=client.post(ROOT+"/ai/propose",headers=actors[0],json=request)
    assert response.status_code==200,(response.text,scopes)
    assert response.json()["requires_approval"] and not db.query(PowerResource).count()
    monkeypatch.setattr("app.ai_operator.providers.generate_json",lambda *args,**kwargs:{"summary":"Unsafe","definition":{"schema_version":2,"nodes":[node("bad","set_variable",value="{{process.exit()}}")],"edges":[]}})
    assert client.post(ROOT+"/ai/propose",headers=actors[0],json=request).status_code==502
    assert db.query(PowerExecution).count()==0


from pathlib import Path
SCENARIOS=json.loads((Path(__file__).parent/"fixtures/power_studio_scenarios.json").read_text())
@pytest.mark.parametrize("scenario",SCENARIOS,ids=[row["id"] for row in SCENARIOS])
def test_five_realistic_design_scenarios(scenario,client,db,actors):
    value=scenario["definition"]
    row=create(client,actors[0],value,name=scenario["name"])
    definition=client.get(f"{ROOT}/{row['id']}",headers=actors[0]).json()["definition"]
    response=client.post(ROOT+"/preview",headers=actors[0],json={"definition":definition,"test_input":scenario["input"],"synthetic_outputs":scenario["synthetic"]})
    assert response.status_code==200,response.text
    result=response.json();assert result["validation"]["valid"],result
    timeline={entry["node_id"]:entry for entry in result["timeline"]}
    assert timeline[scenario["expected_node"]]["output"]==scenario["expected_output"],timeline
    assert all(entry["status"] in {"previewed","synthetic","not_reached","not_executable","waiting_for_inputs"} for entry in result["timeline"])
    prepared=client.post(ROOT+"/portable/prepare",headers=actors[0],json={"definition":definition})
    assert prepared.status_code==200,prepared.text
    assert len(prepared.json()["definition"]["nodes"])==len(value["nodes"])
    assert db.query(PowerExecution).count()==0


def test_gateway_scope_key_rows_enforce_company_and_actor(db,actors):
    from app.ai_operator.models import OperatorProvider
    from app.models.user import User
    from app.core.tenant_boundary import install
    user=db.query(User).filter_by(email="power-0@example.com").one()
    from app.apps.project_management.models import PMSWorkspace
    own=PMSWorkspace(name="Own gateway scope",organization_id=1);foreign=PMSWorkspace(name="Foreign gateway scope",organization_id=2)
    db.add_all([own,foreign]);db.flush()
    own_scope=f"workspace:{own.id}";foreign_scope=f"workspace:{foreign.id}"
    for scope in ["company:1","company:2",f"user:{user.id}","user:999999",own_scope,foreign_scope]:
        db.add(OperatorProvider(scope_key=scope,provider="gemini",model="isolated-model",encrypted_key="encrypted-fixture",enabled=True,data_sharing_allowed=True,updated_by=user.id))
    db.commit()
    release=install(db,user,1)
    try:
        rows=db.query(OperatorProvider).all()
        assert {row.scope_key for row in rows}=={"company:1",f"user:{user.id}",own_scope}
        owned=next(row for row in rows if row.scope_key=="company:1")
        owned.scope_key="company:2"
        with pytest.raises(HTTPException) as exc:db.flush()
        assert exc.value.status_code==403
        db.rollback()
    finally:release()


def test_synthetic_outputs_cannot_impersonate_local_logic(client,actors):
    value=graph()
    response=client.post(ROOT+"/preview",headers=actors[0],json={"definition":value,"test_input":{"record":{"id":1,"status":"Open"}},"synthetic_outputs":{"condition":{"result":True}}})
    assert response.status_code==422,response.text


def test_exports_redact_secret_looking_literal_text(client,actors):
    value=graph();value["nodes"][2]["config"]["value"]="password=never_export_this_value"
    result=client.post(ROOT+"/portable/prepare",headers=actors[0],json={"definition":value})
    assert result.status_code==200,result.text
    assert "never_export_this_value" not in result.text


@pytest.mark.parametrize("identifier",["__proto__","constructor","prototype"])
def test_portable_graph_rejects_prototype_identifiers(client,actors,identifier):
    value={"schema_version":2,"nodes":[node(identifier,"manual_trigger")]}
    assert client.post(ROOT+"/portable/prepare",headers=actors[0],json={"definition":value}).status_code==422


def test_mapping_arguments_resolve_only_safe_upstream_references():
    spec=mapping("Hello",[{"op":"concat","argument":[" ","{{trigger.record.name}}"]}])
    assert map_value(spec,{"trigger":{"record":{"name":"Synthetic"}}})=="Hello Synthetic"


def test_typed_number_equality_and_concurrent_join_status():
    assert condition({"rules":[{"left":42.0,"operator":"equals","right":42}]})
    value={"schema_version":2,"nodes":[node("start","manual_trigger"),node("split","parallel_branch"),node("a","set_variable",value="A"),node("b","set_variable",value="B"),node("join","merge",strategy="keyed",keys=["left","right"])],"edges":[edge("start","split"),edge("split","a","route_1"),edge("split","b","route_2"),edge("a","join"),edge("b","join")]}
    model=VisualWorkflowDefinition.model_validate(value);assert validate_graph(model)["valid"]
    result=preview_graph(model,{})
    assert result["timeline"][-1]["output"]["value"]=={"left":{"value":"A"},"right":{"value":"B"}}
    value["nodes"][-1]["config"]["strategy"]="first_completed"
    result=preview_graph(VisualWorkflowDefinition.model_validate(value),{})
    assert result["timeline"][-1]["status"]=="not_executable"


def test_error_edges_only_activate_on_injected_failure():
    value={"schema_version":2,"nodes":[node("start","manual_trigger"),node("step","set_variable",value="Success"),node("handler","error_handler",message="Review failure")],"edges":[edge("start","step"),{**edge("step","handler","error"),"target_port":"in"}]}
    value["nodes"][1]["advanced"]={"error_strategy":"branch"}
    model=VisualWorkflowDefinition.model_validate(value)
    success=preview_graph(model,{})
    assert success["timeline"][1]["active_ports"]==["out"]
    assert success["timeline"][2]["status"]=="not_reached"
    failure=preview_graph(model,{},injected_errors=["step"])
    assert failure["timeline"][1]["active_ports"]==["error"]
    assert failure["timeline"][2]["status"]=="not_executable"


def test_mapping_defaults_handle_missing_optional_data():
    spec={**mapping(None,[{"op":"default","argument":"Fallback"}]),"source":"{{trigger.record.optional}}"}
    assert map_value(spec,{"trigger":{"record":{}}})=="Fallback"


def test_explicit_trigger_fixture_updates_trigger_variable_context():
    value={"schema_version":2,"nodes":[node("start","webhook_trigger",event_name="synthetic.form"),node("result","set_variable",value="{{trigger.record.id}}")],"edges":[edge("start","result")]}
    result=preview_graph(VisualWorkflowDefinition.model_validate(value),{},synthetic_outputs={"start":{"body":{"id":42}}})
    assert result["timeline"][0]["status"]=="synthetic"
    assert result["timeline"][1]["output"]=={"value":42}


def test_destination_mapping_constraints_are_authoritative(client,actors):
    payload={"mapping":mapping("3"),"context":{},"node_type":"format_number","field":"digits"}
    result=client.post(ROOT+"/mapping/preview",headers=actors[0],json=payload)
    assert result.status_code==422,result.text
    value={"schema_version":2,"nodes":[node("limit","loop",max_iterations=5)]}
    value["nodes"][0]["mappings"]={"max_iterations":mapping(1000000,target_type="number")}
    assert client.post(ROOT,headers=actors[0],json={"name":"Unsafe bound","definition":value}).status_code==422
