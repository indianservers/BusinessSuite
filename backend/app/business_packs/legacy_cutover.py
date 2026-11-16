"""Exact retained onboarding schema for cutover booleans; never an ORM grant.

These two tables are preserved by the frozen PostgreSQL baseline/coverage file.
They are not new schema and are never registered on Base.metadata.
"""
from sqlalchemy import Table,Column,MetaData,Integer,String,Text,Boolean,DateTime,ForeignKey


class LegacyInventoryIncomplete(ValueError):
    pass


def _descriptors():
    from app.models.onboarding import OnboardingTemplate,EmployeeOnboarding
    from app.models.user import User
    metadata=MetaData()
    tasks=Table('onboarding_tasks',metadata,
        Column('id',Integer,primary_key=True),
        Column('template_id',Integer,ForeignKey(OnboardingTemplate.__table__.c.id,ondelete='CASCADE'),nullable=False),
        Column('title',String(200),nullable=False),Column('description',Text),Column('category',String(50)),
        Column('assigned_to_role',String(50)),Column('due_days',Integer),Column('is_mandatory',Boolean),Column('order_sequence',Integer))
    completions=Table('onboarding_task_completions',metadata,
        Column('id',Integer,primary_key=True),
        Column('onboarding_id',Integer,ForeignKey(EmployeeOnboarding.__table__.c.id,ondelete='CASCADE'),nullable=False),
        Column('task_id',Integer,ForeignKey(tasks.c.id,ondelete='CASCADE'),nullable=False),
        Column('is_completed',Boolean),Column('completed_at',DateTime(timezone=False)),
        Column('completed_by',Integer,ForeignKey(User.__table__.c.id,ondelete='SET NULL')),
        Column('remarks',Text),Column('document_url',String(500)))
    return {table.name:table for table in (tasks,completions)}


def _type(value):
    if isinstance(value,Boolean):return ('boolean',)
    if isinstance(value,Text):return ('text',)
    if isinstance(value,String):return ('varchar',value.length)
    if isinstance(value,DateTime):return ('timestamp',bool(value.timezone))
    if str(value).upper()=='INTEGER':return ('integer',)
    return ('unsupported',)


def legacy_tables(inspector):
    declared=_descriptors()
    present={name for name in declared if inspector.has_table(name)}
    if not present:
        if inspector.bind.dialect.name=='postgresql':
            raise LegacyInventoryIncomplete('Native cutover source inventory is incomplete.')
        return {}  # ORM-only SQLite installs never fabricate preserved PostgreSQL tables.
    if present!=set(declared):raise LegacyInventoryIncomplete('Native cutover source inventory is incomplete.')
    for name,table in declared.items():
        columns={column['name']:column for column in inspector.get_columns(name)}
        if set(columns)!=set(table.c.keys()):raise LegacyInventoryIncomplete('Native cutover source inventory is incomplete.')
        for expected in table.c:
            actual=columns[expected.name]
            if _type(actual['type'])!=_type(expected.type) or actual['nullable']!=expected.nullable:
                raise LegacyInventoryIncomplete('Native cutover source inventory is incomplete.')
        if inspector.get_pk_constraint(name).get('constrained_columns')!=['id']:
            raise LegacyInventoryIncomplete('Native cutover source inventory is incomplete.')
        expected={(tuple([key.parent.name]),key.column.table.name,tuple([key.column.name]),key.ondelete)
            for key in table.foreign_keys}
        actual=set()
        for key in inspector.get_foreign_keys(name):
            if key.get('referred_schema') not in {None,inspector.default_schema_name}:
                raise LegacyInventoryIncomplete('Native cutover source inventory is incomplete.')
            actual.add((tuple(key['constrained_columns']),key['referred_table'],tuple(key['referred_columns']),
                (key.get('options') or {}).get('ondelete')))
        if actual!=expected:raise LegacyInventoryIncomplete('Native cutover source inventory is incomplete.')
    return declared
