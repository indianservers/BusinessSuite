"""Idempotent catalog reads must not write protected global agent records."""
from app.ai_agents.services.registry import AiAgentRegistryService
from ai_test_utils import auth_headers


def test_initialized_catalog_is_read_only_for_an_ordinary_member(client, db):
    headers, user = auth_headers(client, db, permissions=['ai_assistant'])
    assert not user.is_superuser
    from sqlalchemy import event
    statements=[]
    def capture(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith(('INSERT INTO AI_AGENTS','UPDATE AI_AGENTS','DELETE FROM AI_AGENTS')):
            statements.append(statement)
    engine=db.get_bind()
    event.listen(engine,'before_cursor_execute',capture)
    try:
        result=client.get('/api/v1/ai-agents',headers=headers)
        assert result.status_code==200,result.text
        assert statements==[]
    finally:
        event.remove(engine,'before_cursor_execute',capture)
