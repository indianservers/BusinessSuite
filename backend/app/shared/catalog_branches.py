"""Branch offering availability; stock and historical transactions stay untouched.

The existing product JSON holds a default plus explicit branch overrides. Legacy
catalogues default to available everywhere; new copies default to their target.
"""
from fastapi import HTTPException
from sqlalchemy import func


def selected_branch(user):
    value = getattr(user, "_suite_branch_id", None)
    return int(value) if value is not None and str(value).isdigit() else None


def availability_clause(model, branch_id):
    if branch_id is None:
        return True
    policy = model.metadata_json["catalog_branches"]
    return func.coalesce(policy["overrides"][str(branch_id)].as_boolean(), policy["default"].as_boolean(), True)


def is_available(row, branch_id):
    policy = (row.metadata_json or {}).get("catalog_branches") or {}
    return branch_id is None or policy.get("overrides", {}).get(str(branch_id), policy.get("default", True))


def set_availability(row, branch_id, enabled):
    attributes = dict(row.metadata_json or {})
    policy = attributes.get("catalog_branches") or {"default": True}
    attributes["catalog_branches"] = {"default": policy.get("default", True), "overrides": {**policy.get("overrides", {}), str(branch_id): enabled}}
    row.metadata_json = attributes


def assert_available(row, user):
    if not is_available(row, selected_branch(user)):
        raise HTTPException(422, "This offering is unavailable in the selected branch. Reuse it from its source branch first.")
