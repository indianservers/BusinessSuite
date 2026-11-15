"""Legacy chat copies inherit native scope without granting ordinary writes."""
from dataclasses import replace
import pytest
from fastapi import HTTPException
from app.branches.boundary import install
from app.branches.derived import chat_read_derivatives
from app.branches.models import BranchOwnership
from app.branches.service import context
from app.apps.project_management.models import PMSWorkspace
from app.apps.project_management.chat_models import ChatConversation, ChatMember, ChatMessage
from tests.test_branch_access import setup


@pytest.mark.parametrize('table', ['conversation', 'member', 'message'])
@pytest.mark.parametrize('case', ['allowed', 'missing_marker', 'read_only_parent', 'write_request'])
def test_chat_read_copies_need_marker_and_writable_native_parent(db, table, case):
    user, a, b, *_ = setup(db)
    user.is_superuser = True
    workspace = PMSWorkspace(name='Verified legacy source', organization_id=1)
    db.add(workspace); db.flush()
    room = ChatConversation(workspace_id=workspace.id, key='verified-source', kind='general', owner_id=user.id)
    db.add(room); db.flush()
    for name, ident in [('pms_workspaces', workspace.id), ('pms_chat_conversations', room.id)]:
        db.add(BranchOwnership(company_id=1, branch_id=a.id, resource_table=name, resource_key=str(ident), source='test-native-source'))
    db.commit()
    ctx = context(db, user, 1, 'all')
    if case == 'read_only_parent':
        ctx = replace(ctx, writable=frozenset({b.id}))
    cleanup = install(db, user, ctx)
    db.info['security_write_request'] = case == 'write_request'
    row = (ChatConversation(workspace_id=workspace.id, key='copied-room', kind='general', owner_id=user.id)
        if table == 'conversation' else ChatMember(conversation_id=room.id, user_id=user.id)
        if table == 'member' else ChatMessage(conversation_id=room.id, author_id=user.id, client_id='legacy-copy', body='Preserved'))
    try:
        def flush():
            db.add(row); db.flush()
        if case == 'missing_marker':
            with pytest.raises(HTTPException): flush()
        else:
            with chat_read_derivatives(db, workspace.id) as allow_room:
                allow_room(room.id)
                if case == 'allowed': flush()
                else:
                    with pytest.raises(HTTPException): flush()
        assert 'derived_read_parents' not in db.info
    finally:
        cleanup(); db.rollback()
        db.info.pop('security_write_request', None)
        db.info.pop('derived_read_parents', None)


def test_chat_marker_rejects_other_workspace_and_restores_outer_context(db):
    user, *_ = setup(db)
    workspaces = [PMSWorkspace(name=name, organization_id=1) for name in ['Selected', 'Other']]
    db.add_all(workspaces); db.flush()
    room = ChatConversation(workspace_id=workspaces[1].id, key='other-workspace', kind='general', owner_id=user.id)
    db.add(room); db.commit()
    outer = {'payroll_variance_items': frozenset({99})}
    db.info['derived_read_parents'] = outer
    try:
        with pytest.raises(HTTPException):
            with chat_read_derivatives(db, workspaces[0].id) as allow_room:
                allow_room(room.id)
        assert db.info['derived_read_parents'] is outer
        assert 'pms_chat_members' not in outer and 'pms_chat_conversations' not in outer
    finally:
        db.info.pop('derived_read_parents', None)
