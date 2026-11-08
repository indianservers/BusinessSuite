from sqlalchemy import inspect


def test_partner_commission_claims_schema(db_engine):
    """PostgreSQL fixtures use the migration chain, not ORM create_all."""
    schema = inspect(db_engine)
    columns = {column['name']: column for column in schema.get_columns('partner_commission_claims')}
    assert set(columns) == {
        'id', 'organization_id', 'portal_user_id', 'reference', 'amount',
        'currency', 'notes', 'version', 'created_at',
    }
    assert all(not column['nullable'] for column in columns.values())
    assert schema.get_pk_constraint('partner_commission_claims')['constrained_columns'] == ['id']
    foreign_keys = {(tuple(fk['constrained_columns']), fk['referred_table']) for fk in schema.get_foreign_keys('partner_commission_claims')}
    assert foreign_keys == {(('organization_id',), 'companies'), (('portal_user_id',), 'portal_users')}
    indexes = {tuple(index['column_names']) for index in schema.get_indexes('partner_commission_claims')}
    assert ('organization_id',) in indexes
    assert ('portal_user_id',) in indexes
