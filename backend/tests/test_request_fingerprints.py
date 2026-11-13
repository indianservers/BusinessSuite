"""Full request provenance is contextual, deterministic and private."""
import copy
import json
from types import SimpleNamespace
import pytest
from app.ai_operator import request_fingerprints as fingerprints


def request():
    return {'provider': 'gemini', 'model': 'synthetic-model', 'purpose': 'suite_plan',
            'scope_key': 'company:1', 'user_id': 7, 'endpoint': 'https://example.invalid/model',
            'body': {'instructions': 'Synthetic policy', 'contents': ['Private synthetic customer context'],
                     'settings': {'max_tokens': 100, 'json': True}}}


def test_canonical_payload_ignores_object_order_but_keeps_list_order(monkeypatch):
    monkeypatch.setattr(fingerprints, 'signing_key', lambda: b'synthetic-server-key')
    original = request()
    one = fingerprints.fingerprint(**original)
    two = {**original, 'body': dict(reversed(list(original['body'].items())))}
    assert fingerprints.fingerprint(**two) == one
    changed = copy.deepcopy(original)
    changed['body']['contents'] = ['Private synthetic customer context', 'Another source']
    three = fingerprints.fingerprint(**changed)
    changed['body']['contents'].reverse()
    assert fingerprints.fingerprint(**changed) != three
    assert set(one) == {'format', 'algorithm', 'key_epoch', 'canonicalization', 'value'}
    assert len(one['value']) == 64 and len(one['key_epoch']) == 16
    assert 'Private synthetic' not in json.dumps(one) and 'synthetic-server-key' not in json.dumps(one)


@pytest.mark.parametrize('field,value', [('provider', 'openai'), ('model', 'another-model'),
    ('purpose', 'suite_summary'), ('scope_key', 'company:2'), ('user_id', 8),
    ('endpoint', 'https://example.invalid/another-model')])
def test_provider_actor_and_scope_are_part_of_identity(field, value):
    original = request()
    assert fingerprints.fingerprint(**original) != fingerprints.fingerprint(**{**original, field: value})


def test_context_settings_tenant_and_key_rotation_change_fingerprint(monkeypatch):
    original = request()
    first = fingerprints.fingerprint(**original)
    for section in ('instructions', 'contents', 'settings'):
        modified = copy.deepcopy(original)
        modified['body'][section] = 'Changed authorized input'
        assert fingerprints.fingerprint(**modified)['value'] != first['value']
    previous = fingerprints.current_tenant.set(SimpleNamespace(tenant_uuid='synthetic-tenant'))
    try:
        assert fingerprints.fingerprint(**original)['value'] != first['value']
    finally:
        fingerprints.current_tenant.reset(previous)
    monkeypatch.setattr(fingerprints, 'signing_key', lambda: b'rotated-synthetic-key')
    rotated = fingerprints.fingerprint(**original)
    assert rotated['key_epoch'] != first['key_epoch'] and rotated['value'] != first['value']


def test_non_json_numbers_are_not_silently_signed():
    original = request()
    original['body']['settings']['max_tokens'] = float('nan')
    with pytest.raises(ValueError):
        fingerprints.fingerprint(**original)
