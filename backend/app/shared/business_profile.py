"""Presentation-only business profiles. Never mutate pipelines or domain records."""
import json
import unicodedata
from copy import deepcopy
from pathlib import Path
from fastapi import HTTPException
from app.shared.models import ServicePolicy

CATALOG = json.loads((Path(__file__).resolve().parents[1] / 'core' / 'business_profiles.json').read_text(encoding='utf-8'))
PROFILES = {profile['id']: profile for profile in CATALOG['profiles']}
KIND = 'business_profile'


def scope_key(company_id, branch_id=None):
    return f'business-profile:company:{company_id}' + (f':branch:{branch_id}' if branch_id else '')


def validate(values):
    if not isinstance(values, dict) or set(values) - {'business_type', 'terms'}:
        raise HTTPException(422, 'Unknown business profile setting')
    if 'business_type' in values and (not isinstance(values['business_type'], str) or values['business_type'] not in PROFILES):
        raise HTTPException(422, 'Choose a supported business type')
    terms = values.get('terms', {})
    if not isinstance(terms, dict) or set(terms) - set(CATALOG['terms']):
        raise HTTPException(422, 'Unknown terminology key')
    clean = {}
    for key, pair in terms.items():
        if not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(label, str) or not 1 <= len(label.strip()) <= 60 or any(unicodedata.category(c).startswith('C') or c in '<>' for c in label) for label in pair):
            raise HTTPException(422, 'Provide singular and plural labels of 1–60 characters without markup or control characters')
        clean[key] = [label.strip() for label in pair]
    return {**({'business_type': values['business_type']} if 'business_type' in values else {}), 'terms': clean}


def resolve(layers):
    business_type, overrides = 'general', {}
    for layer in layers:
        if 'business_type' in layer:
            business_type = layer['business_type']
        overrides.update(layer.get('terms', {}))
    terms = deepcopy(CATALOG['terms'])
    terms.update(deepcopy(PROFILES.get(business_type, PROFILES['general'])['terms']))
    terms.update(deepcopy(overrides))
    return {'business_type': business_type, 'terms': terms, 'custom_terms': deepcopy(overrides)}


def effective(db, company_id, branch_id=None, *, skip_scope=None):
    layers, versions = [], {}
    for key in dict.fromkeys([scope_key(company_id), scope_key(company_id, branch_id)]):
        if key == skip_scope:
            continue
        row = db.query(ServicePolicy).filter_by(organization_id=company_id, kind=KIND, scope_key=key).first()
        if row:
            layers.append(row.values_json)
            versions[key] = row.version
    return {**resolve(layers), 'versions': versions}


def term(db, company_id, key, *, plural=False, branch_id=None):
    return effective(db, company_id, branch_id)['terms'][key][int(plural)]
