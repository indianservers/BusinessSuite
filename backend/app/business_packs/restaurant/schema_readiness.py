"""Read-only deployed Restaurant schema gates; no DDL or activation authority."""
import re
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, inspect, text


def _identity_guard(sql):
    # Parse only this fixed integer provenance predicate. Parentheses preserve
    # precedence; a named but weakened A AND B OR C constraint must fail closed.
    source=str(sql).lower().replace('"','')
    tokens=re.findall(r'[a-z_][a-z_0-9]*|[0-9]+|[()>=]',source)
    if ''.join(tokens)!=re.sub(r'\s+','',source):return False
    index=0
    def take():
        nonlocal index
        value=tokens[index];index+=1;return value
    def atom():
        if tokens[index]=='(':
            take();value=disjunction()
            if take()!=')':raise ValueError()
            return value
        left=take();op=take()
        if op=='is':
            if take()!='null':raise ValueError()
            return ('null',left)
        if op not in {'>','='}:raise ValueError()
        return (op,left,take())
    def conjunction():
        nonlocal index
        value=atom()
        while index<len(tokens) and tokens[index]=='and':
            take();value=('and',value,atom())
        return value
    def disjunction():
        nonlocal index
        value=conjunction()
        while index<len(tokens) and tokens[index]=='or':
            take();value=('or',value,conjunction())
        return value
    expected=('and',('>','original_sales_order_line_id','0'),('or',('null','sales_order_line_id'),('=','sales_order_line_id','original_sales_order_line_id')))
    try:return disjunction()==expected and index==len(tokens)
    except (IndexError,ValueError):return False


def _branch_guards(connection):
    if connection.dialect.name=='sqlite':
        rows=connection.execute(text("SELECT name,tbl_name FROM sqlite_master WHERE type='trigger' AND tbl_name IN ('suite_branch_ownership','suite_branch_record_shares')"))
        expected={('suite_pack_branch_'+action,'suite_branch_ownership') for action in ('insert','update','delete')} | {('suite_pack_share_'+action,'suite_branch_record_shares') for action in ('insert','update')}
        return expected<={tuple(row) for row in rows}
    if connection.dialect.name=='postgresql':
        rows=connection.execute(text("""SELECT t.tgname,c.relname,p.proname,t.tgtype::integer
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid
            WHERE n.nspname=current_schema() AND NOT t.tgisinternal AND t.tgenabled IN ('O','A')
            AND c.relname IN ('suite_branch_ownership','suite_branch_record_shares')"""))
        expected={('suite_pack_branch_identity','suite_branch_ownership','suite_pack_branch_identity_guard',31),('suite_pack_share_identity','suite_branch_record_shares','suite_pack_share_guard',23)}
        return expected<={tuple(row) for row in rows}
    return False


def installation_reasons(connection):
    from .models import MODELS,RestaurantTabLine,RestaurantServiceOrder
    inspector=inspect(connection);reasons=[]
    for model in MODELS:
        table=model.__table__;name=table.name
        if not inspector.has_table(name):
            reasons.append('Restaurant schema is missing '+name+'.');continue
        columns={column['name']:column for column in inspector.get_columns(name)}
        if any(column.name not in columns or columns[column.name]['nullable']!=column.nullable for column in table.columns):
            reasons.append('Restaurant schema columns require migration: '+name+'.')
        actual_fks={(tuple(fk['constrained_columns']),fk['referred_table'],tuple(fk['referred_columns']),str(fk.get('options',{}).get('ondelete','')).upper()) for fk in inspector.get_foreign_keys(name)}
        actual_unique={tuple(row['column_names']) for row in inspector.get_unique_constraints(name)}
        for constraint in table.constraints:
            if isinstance(constraint,ForeignKeyConstraint):
                expected=(tuple(column.name for column in constraint.columns),constraint.elements[0].column.table.name,tuple(element.column.name for element in constraint.elements),str(constraint.ondelete or '').upper())
                if expected not in actual_fks:reasons.append('Restaurant source foreign key is missing: '+name+'.')
            elif isinstance(constraint,UniqueConstraint) and tuple(column.name for column in constraint.columns) not in actual_unique:
                reasons.append('Restaurant source uniqueness is missing: '+name+'.')
        actual_checks={row['name']:row['sqltext'] for row in inspector.get_check_constraints(name)}
        expected_checks={constraint.name for constraint in table.constraints if constraint.__class__.__name__=='CheckConstraint'}
        if not expected_checks<=set(actual_checks):reasons.append('Restaurant source checks are missing: '+name+'.')
        if model is RestaurantTabLine and not _identity_guard(actual_checks.get('ck_restaurant_tab_original_identity','')):
            reasons.append('Restaurant cancellation provenance guard requires migration 117.')
        if model is RestaurantServiceOrder:
            indexes=inspector.get_indexes(name)
            valid=False
            for item in indexes:
                predicate=item.get('dialect_options',{}).get(connection.dialect.name+'_where')
                normalized=re.sub(r"[\s()\"]",'',str(predicate if predicate is not None else '')).lower()
                normalized=normalized.replace('::text','').replace('::charactervarying','')
                if item['name']=='uq_restaurant_active_table' and item.get('unique') and item['column_names']==['table_id'] and normalized=="state='open'":valid=True
            if not valid:reasons.append('Restaurant active-table uniqueness guard is missing.')
    if not _branch_guards(connection):reasons.append('Restaurant immutable branch/share provenance guards require migration 107.')
    return sorted(set(reasons))
