"""Audit all published editor contracts against the registered runtime models."""
import pytest
from app.apps.power_apps.integrations.registry import REGISTRY, INPUTS, catalog
from app.apps.power_apps.integrations.editor_options import ACTION_FIELDS, editor_options
from app.apps.power_apps.integrations.vault import SECRET_FIELDS
from app.apps.power_apps.node_registry import NODES

ALL_ACTIONS = [(cid, action) for cid, connector in REGISTRY.items() for action in connector.actions]


@pytest.mark.parametrize("connector,action", ALL_ACTIONS, ids=[cid + "-" + a.id for cid, a in ALL_ACTIONS])
def test_every_action_exposes_only_real_fields(connector, action):
    schema = action.input_schema
    fields = set(schema["properties"])
    assert fields <= set(INPUTS[connector, action.id].model_fields)
    assert set(schema.get("required", [])) <= fields
    if connector in ACTION_FIELDS:
        assert list(schema["properties"]) == ACTION_FIELDS[connector][action.id]
    assert not fields & {"access_token", "password", "api_key", "bot_token"}


@pytest.mark.parametrize("connector", REGISTRY.values(), ids=list(REGISTRY))
def test_every_connection_offers_only_supported_auth_and_settings(connector):
    options = editor_options(connector)
    assert set(options["credentials"]) == set(connector.authentication)
    for auth, fields in options["credentials"].items():
        expected = set() if auth == "oauth2" else SECRET_FIELDS[auth]
        assert set(fields) == expected
    schema = options["config_schema"]
    properties = set(schema["properties"])
    assert set(schema["required"]) <= properties
    assert ("database" in properties) == (connector.id == "postgresql")
    assert ("hosts" in properties) == (connector.id in {"postgresql", "http", "outgoing_webhook"})
    assert ("header_name" in properties) == ("api_key" in connector.authentication)
    assert options["write_actions"] == [a.name for a in connector.actions if a.mutates]


def test_module_options_are_published_and_match_node_action_menus():
    for connector in catalog():
        assert "editor_options" in connector
        if not connector["actions"]:
            continue
        node = NODES["connector_" + connector["id"]]
        assert node["fields"][0]["options"] == [a["id"] for a in connector["actions"]]
    assert REGISTRY["github"].actions[0].input_schema["properties"] == {}
    assert REGISTRY["smtp"].actions[0].input_schema["properties"] == {}


def test_ai_options_follow_task_requirements():
    fields = {a.id: set(a.input_schema["properties"]) for a in REGISTRY["ai_gateway"].actions}
    assert "target_language" in fields["translate"]
    assert "target_language" not in fields["summarize"]
    assert "document_b" in fields["compare"]
    assert "document_b" not in fields["generate_text"]
    assert "categories" in fields["classify"]
    assert "categories" not in fields["extract"]
    assert "output_schema" in fields["extract"]
