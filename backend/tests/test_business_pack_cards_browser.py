"""Actual Settings cards over JWT-authenticated disposable FastAPI HTTP."""
import os

import pytest

from app.business_packs import service, schemas
from app.core.security import create_access_token
from tests.test_business_pack_configuration import owner, pack_client


@pytest.mark.skipif(os.getenv('RUN_BUSINESS_PACK_CARDS_BROWSER') != '1', reason='Opt-in disposable native Settings browser')
def test_native_business_pack_cards_selection_terms_and_preserved_access(pack_client, db, owner):
    from tests.workflow_browser_utils import run_browser
    actor, branch, _, ordinary = owner
    for key in ('construction', 'salon'):
        ready = service.readiness(db, actor, key)
        assert ready['ready'] is True, ready
    # Existing canonical draft configuration must survive company selection.
    activation = service.draft_activation(db, actor, schemas.DraftActivation(
        pack_key='hospital', expected_revision=0, reason='Existing browser setup'))
    context = service.draft_context(db, actor, schemas.DraftContext(
        activation_id=activation['id'], activation_revision=activation['revision'],
        branch_id=branch.id, expected_revision=0, reason='Existing branch setup'))
    service.grant_role(db, actor, context['id'], ordinary.id, schemas.GrantRole(
        context_revision=context['revision'], role='doctor', active=True,
        expected_revision=0, reason='Existing canonical staff assignment'))
    db.commit()
    run_browser(pack_client, db, 'test-business-pack-cards-native.cjs', {
        'WORKFLOW_TEST_TOKEN': create_access_token(actor.id),
        'WORKFLOW_TEST_ORDINARY_TOKEN': create_access_token(ordinary.id),
        'WORKFLOW_TEST_BRANCH': str(branch.id),
        'WORKFLOW_TEST_COMPANY': '1',
    })
