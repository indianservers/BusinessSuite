"""Preserve verified company ownership for reusable salary component masters."""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261114_101_salary_ownership'
down_revision = 'pg_20261114_100_industry'
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    required = {'salary_components', 'security_resource_ownership', 'suite_branch_ownership', 'branches'}
    if not required <= set(sa.inspect(bind).get_table_names()):
        return
    metadata = sa.MetaData()
    component, owner, branch_owner, branch = [
        sa.Table(name, metadata, autoload_with=bind)
        for name in ('salary_components', 'security_resource_ownership', 'suite_branch_ownership', 'branches')
    ]
    # The historical branch stamp must agree with the branch's actual company.
    # An optional category may provide evidence, but contradictory companies are
    # left unresolved rather than guessed or made visible to either company.
    branch_evidence = sa.select(component.c.id.label('component_id'), branch_owner.c.company_id.label('company_id')).select_from(
        component.join(branch_owner, sa.and_(branch_owner.c.resource_table == 'salary_components', branch_owner.c.resource_key == sa.cast(component.c.id, sa.String)))
        .join(branch, sa.and_(branch.c.id == branch_owner.c.branch_id, branch.c.company_id == branch_owner.c.company_id))
    )
    category_evidence = sa.select(component.c.id.label('component_id'), owner.c.company_id.label('company_id')).select_from(
        component.join(owner, sa.and_(owner.c.resource_table == 'salary_component_categories', owner.c.resource_id == component.c.category_id))
    )
    evidence = sa.union_all(branch_evidence, category_evidence).subquery()
    claims = sa.select(evidence.c.component_id, sa.func.min(evidence.c.company_id).label('company_id')).group_by(evidence.c.component_id).having(
        sa.func.count(sa.distinct(evidence.c.company_id)) == 1
    ).subquery()
    missing = sa.select(sa.literal('salary_components'), claims.c.component_id, claims.c.company_id).where(
        ~sa.exists(sa.select(1).where(owner.c.resource_table == 'salary_components', owner.c.resource_id == claims.c.component_id))
    )
    if bind.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif bind.dialect.name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError('Salary ownership repair requires PostgreSQL or SQLite verification')
    bind.execute(insert(owner).from_select(['resource_table', 'resource_id', 'company_id'], missing).on_conflict_do_nothing(
        index_elements=['resource_table', 'resource_id']
    ))


def downgrade():
    # Ownership evidence must survive a code rollback; never remove grants that
    # cannot be distinguished from later administrator-reviewed ownership.
    pass
