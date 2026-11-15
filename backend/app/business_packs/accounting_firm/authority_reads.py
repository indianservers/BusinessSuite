"""Frozen exact native entitlement reads, with no database connection exposed."""
from types import SimpleNamespace
from hashlib import sha256
from sqlalchemy import inspect, select
from sqlalchemy.inspection import _inspects
from fastapi import HTTPException


def _key(statement, parameters=None):
    return str(statement.compile(compile_kwargs={'literal_binds': True})), repr(parameters or {})


class _Schema:
    def __init__(self, columns):
        self._columns = columns

    def has_table(self, name, schema=None, **kwargs):
        if schema is not None or name not in self._columns:
            raise HTTPException(403, 'Unreviewed Accounts authority schema read: ' + str(name))
        return self._columns[name] is not None

    def get_columns(self, name, schema=None, **kwargs):
        if not self.has_table(name, schema):
            from sqlalchemy.exc import NoSuchTableError
            raise NoSuchTableError(name)
        return [{'name': column} for column in self._columns[name]]


class AuthorityReads:
    def __init__(self, dialect_name, rows, columns):
        self.dialect = SimpleNamespace(name=dialect_name)
        self._rows = rows
        self._schema = _Schema(columns)
        self.fingerprint = sha256(repr([(key, value.data) for key, value in rows.items()]).encode()).hexdigest()

    def execute(self, statement, parameters=None, **kwargs):
        frozen = self._rows.get(_key(statement, parameters))
        if frozen is None or kwargs:
            raise HTTPException(403, 'Unreviewed Accounts authority query')
        # IteratorResult carries frozen values, not CursorResult.context or a connection.
        return frozen()


@_inspects(AuthorityReads)
def _inspect_authority(value):
    return value._schema


def capture(db, company):
    from app.apps.business_os.models import BOSEnabledModule
    from app.models.company import Company
    from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
    from app.db.schema_columns import table_columns
    from app.shared.master_data_models import ContactChannel
    from app.shared.models import ServiceEvent
    connection = db.connection()
    inspector = inspect(connection)
    columns = {name: [column['name'] for column in inspector.get_columns(name)] if inspector.has_table(name) else None
        for name in ('bos_enabled_modules', 'tenant_subscriptions', ContactChannel.__tablename__, ServiceEvent.__tablename__)}
    rows = {}
    def freeze(statement, parameters=None):
        result = connection.execute(statement, parameters or {})
        frozen = result.freeze()
        rows[_key(statement, parameters)] = frozen
        return frozen().mappings().first()
    enabled, organization, subscription, plan = (model.__table__ for model in
        (BOSEnabledModule, Company, TenantSubscription, TenantSubscriptionPlan))
    if columns['bos_enabled_modules'] is not None:
        freeze(enabled.select().where(enabled.c.company_id == company))
    freeze(organization.select().where(organization.c.id == company))
    # Capture the real schema helper's fixed native probe for PostgreSQL as well.
    class Recorder:
        dialect = connection.dialect
        def execute(self, statement, parameters=None):
            frozen = connection.execute(statement, parameters or {}).freeze()
            rows[_key(statement, parameters)] = frozen
            return frozen()
    if connection.dialect.name == 'postgresql':
        table_columns(Recorder(), ('tenant_subscriptions',))
    if columns['tenant_subscriptions'] is not None and 'company_id' in columns['tenant_subscriptions']:
        current = freeze(select(subscription).where(subscription.c.company_id == company))
        if current:
            assigned = freeze(select(plan).where(plan.c.id == current['plan_id']))
            config = dict(assigned['config_json'] or {}) if assigned else {}
            config.update(current['config_json'] or {})
            pending = config.get('scheduled_change')
            if isinstance(pending, dict) and type(pending.get('plan_id')) is int:
                freeze(select(plan).where(plan.c.id == pending['plan_id']))
    return AuthorityReads(connection.dialect.name, rows, columns)
