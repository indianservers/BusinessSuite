"""10,000 synthetic customers; pagination must not issue queries per record."""
import time
from sqlalchemy import event, insert
from tests.test_contact_directory import directory_identity
from app.apps.crm.models import CRMCompany
from app.models.user import User
from app.shared.master_data import list_companies


def test_tc077_ten_thousand_customers_have_bounded_page_and_queries(db, superuser_headers, request):
    db.execute(insert(CRMCompany), [{'organization_id':1, 'name':f'QA Customer {i:05}', 'account_type':'Customer'} for i in range(10000)])
    db.commit()
    actor = db.query(User).filter_by(email='testadmin@test.com').one()
    # Request dependencies normally attach this selected-company context.
    actor.organization_id = 1
    queries = []
    def count(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith('SELECT'):
            queries.append(statement)
    engine = db.get_bind()
    event.listen(engine, 'before_cursor_execute', count)
    started = time.perf_counter()
    try:
        data = list_companies(source='srm', search='QA Customer', role='Customer', page=50, per_page=100,
                              db=db, actor=actor, entity_kind='all')
    finally:
        event.remove(engine, 'before_cursor_execute', count)
    request.node.user_properties.extend([('query_count', len(queries)), ('seconds', round(time.perf_counter()-started, 4)), ('seeded_customers',10000)])
    assert data['total'] == 10000
    assert len(data['items']) == 100
    assert data['items'][0]['name'] == 'QA Customer 04900'
    assert len({row['id'] for row in data['items']}) == 100
    assert len(queries) <= 20, f'100-row page used {len(queries)} SELECTs (N+1)'
