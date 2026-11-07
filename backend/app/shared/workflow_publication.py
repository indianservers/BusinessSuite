"""Commit-free publication shared by governance APIs and industry onboarding."""
from fastapi import HTTPException
from app.access import service
from app.access.api import authority
from app.models.user import User
from app.shared.contracts import service_identity
from app.shared.gateway import digest
from app.shared.models import WorkflowVersion
from app.shared.runtime import validate_graph
from app.shared.settings import effective


def publish_definition(db, actor, company, row):
    validate_graph(row.graph_json)
    if len(row.graph_json['nodes']) > effective(db, company, row.module_name)['values']['workflow_max_nodes']:
        raise HTTPException(422, 'Graph exceeds the effective module node limit')
    identity = service_identity(db, db.get(User, row.run_as_user_id), company, row.module_name)
    authority(actor, service.resolved_grants(db, service.policy_for(db, identity, company)))
    if db.query(WorkflowVersion).filter_by(workflow_id=row.id, version=row.draft_version).first():
        raise HTTPException(409, 'This version is already published; save a new draft')
    version = WorkflowVersion(organization_id=company, workflow_id=row.id, version=row.draft_version,
        graph_json=row.graph_json, digest=digest(row.graph_json), published_by=actor.id, run_as_user_id=identity.id)
    db.add(version)
    row.published_version, row.is_active = row.draft_version, True
    return version
