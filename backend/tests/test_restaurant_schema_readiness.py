"""Owned SQLite schema only; code-owned support injection is not activation proof."""
from pathlib import Path
import importlib.util
from types import MappingProxyType
import pytest
from sqlalchemy import text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.business_packs import runtime
from app.business_packs.restaurant.schema_readiness import installation_reasons,_identity_guard
from app.business_packs.restaurant.models import MODELS
from app.business_packs.registry import get_pack
from tests.test_branch_access import setup

@pytest.fixture
def installed(db,monkeypatch):
    _,branch,*_=setup(db)
    path=Path(__file__).resolve().parents[1]/'alembic_postgresql/versions/pg_20261115_107_pack_branch_guard.py'
    spec=importlib.util.spec_from_file_location('native107_readiness',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(db.connection())):module.upgrade()
    pack=get_pack('restaurant')
    monkeypatch.setattr(runtime,'RUNTIME_SUPPORT',MappingProxyType({'restaurant':runtime.PackRuntimeSupport(pack.version,1,frozenset(w.key for w in pack.workflows))}))
    return branch

def ready(db,branch):return runtime.activation_readiness(db,1,'restaurant',branch.id)

def test_complete_domain_and_real_native_guards_are_required_without_creating_activation(db,installed):
    from app.business_packs.models import PackActivation,PackContext,PackUserGrant
    before=tuple(db.query(model).count() for model in (PackActivation,PackContext,PackUserGrant))
    assert installation_reasons(db.connection())==[]
    assert ready(db,installed)['ready'] is True
    assert tuple(db.query(model).count() for model in (PackActivation,PackContext,PackUserGrant))==before

@pytest.mark.parametrize('table',['business_restaurant_tables','business_restaurant_kitchen_issues','business_restaurant_tab_lines'])
def test_missing110_or113_domain_never_ready(db,installed,table):
    db.connection().execute(text('DROP TABLE '+table))
    result=ready(db,installed)
    assert not result['ready'] and not result['schema_ready']
    assert any(table in reason for reason in result['reasons'])

def test_missing117_column_never_ready(db,installed):
    with Operations.context(MigrationContext.configure(db.connection())) as op:
        with op.batch_alter_table('business_restaurant_tab_lines') as batch:
            batch.drop_constraint('ck_restaurant_tab_original_identity',type_='check')
            batch.drop_column('original_sales_order_line_id')
    result=ready(db,installed)
    assert not result['ready'] and not result['schema_ready']
    assert any('117' in reason for reason in result['reasons'])

@pytest.mark.parametrize('fault',['missing','weak'])
def test_named117_guard_must_preserve_exact_boolean_provenance(db,installed,fault):
    with Operations.context(MigrationContext.configure(db.connection())) as op:
        with op.batch_alter_table('business_restaurant_tab_lines') as batch:
            batch.drop_constraint('ck_restaurant_tab_original_identity',type_='check')
            if fault=='weak':batch.create_check_constraint('ck_restaurant_tab_original_identity','original_sales_order_line_id > 0 AND sales_order_line_id IS NULL OR sales_order_line_id = original_sales_order_line_id')
    result=ready(db,installed)
    assert not result['ready'] and any('117' in reason for reason in result['reasons'])

def test_missing_native107_branch_guard_never_ready(db,installed):
    db.connection().execute(text('DROP TRIGGER suite_pack_branch_update'))
    assert not ready(db,installed)['ready']
    assert any('107' in reason for reason in ready(db,installed)['reasons'])

def test_missing_active_table_partial_uniqueness_never_ready(db,installed):
    db.connection().execute(text('DROP INDEX uq_restaurant_active_table'))
    assert not ready(db,installed)['ready']
    assert any('active-table' in reason for reason in ready(db,installed)['reasons'])

@pytest.mark.parametrize('expression,expected',[
 ('original_sales_order_line_id > 0 AND (sales_order_line_id IS NULL OR sales_order_line_id = original_sales_order_line_id)',True),
 ('((original_sales_order_line_id > 0) AND ((sales_order_line_id IS NULL) OR (sales_order_line_id = original_sales_order_line_id)))',True),
 ('original_sales_order_line_id > 0 AND sales_order_line_id IS NULL OR sales_order_line_id = original_sales_order_line_id',False),
 ('original_sales_order_line_id >= 0 AND (sales_order_line_id IS NULL OR sales_order_line_id = original_sales_order_line_id)',False),
 ('1=1',False),('',False)])
def test_guard_parser_is_closed_and_preserves_precedence(expression,expected):assert _identity_guard(expression) is expected


def test_scope_fk_is_not_replaceable_by_matching_scalar_columns(db,installed):
    with Operations.context(MigrationContext.configure(db.connection())) as op:
        with op.batch_alter_table('business_restaurant_kitchen_lines') as batch:
            batch.drop_constraint('fk_restaurant_line_context',type_='foreignkey')
    result=ready(db,installed)
    assert not result['ready'] and any('foreign key' in reason for reason in result['reasons'])


def test_live_native_line_delete_rule_must_preserve117_history(db,installed):
    naming={'fk':'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s'}
    with Operations.context(MigrationContext.configure(db.connection())) as op:
        with op.batch_alter_table('business_restaurant_tab_lines',naming_convention=naming) as batch:
            batch.drop_constraint('fk_business_restaurant_tab_lines_sales_order_line_id_srm_sales_order_lines',type_='foreignkey')
            batch.create_foreign_key('fk_wrong_live_source','srm_sales_order_lines',['sales_order_line_id'],['id'],ondelete='CASCADE')
    result=ready(db,installed)
    assert not result['ready'] and any('foreign key' in reason for reason in result['reasons'])


def test_readiness_performs_no_ddl_dml_or_runtime_support_publication(db,installed):
    from sqlalchemy import event
    seen=[];connection=db.connection()
    def capture(conn,cursor,statement,params,context,many):seen.append(statement.strip().split(None,1)[0].upper())
    event.listen(connection,'before_cursor_execute',capture)
    try:assert ready(db,installed)['ready'] is True
    finally:event.remove(connection,'before_cursor_execute',capture)
    assert seen and not {'INSERT','UPDATE','DELETE','CREATE','ALTER','DROP','GRANT','REVOKE'} & set(seen)
