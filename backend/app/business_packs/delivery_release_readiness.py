"""Opt-in, read-only actor17/121 release qualification; never an activation switch.

The legacy compatibility checker remains separate. No producer/event/model
bootstrap is imported, and no inspected SQL text is ever executed.
"""
import re
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from .delivery_release_contract import CONTRACT

_VERSION = 'private-delivery-actor17-121-v1'


def _tokens(source):
    # Preserve literals/comments/punctuation: normalization cannot erase a guard.
    return tuple(token if token.startswith("'") else token.lower() for token in
        re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|::|>=|<=|<>|!=|[a-zA-Z_][a-zA-Z_0-9]*|[0-9]+|[^\s]", str(source)))


def _check_tree(source):
    """Closed grammar for the frozen checks, retaining AND/OR precedence."""
    tokens = list(_tokens(source)); position = 0
    def peek(): return tokens[position] if position < len(tokens) else None
    def take(expected=None):
        nonlocal position
        if position >= len(tokens): raise ValueError('Incomplete check')
        item = tokens[position]; position += 1
        if expected is not None and item != expected: raise ValueError('Unexpected check token')
        return item
    def casts():
        # pg_get_constraintdef inserts only these text casts for VARCHAR checks.
        # Do not accept integer/boolean casts that could change positivity.
        while peek() == '::':
            take(); kind = take()
            if kind == 'character': take('varying')
            elif kind != 'text': raise ValueError('Unreviewed check cast')
            if peek() == '[': take('['); take(']')
    def primary():
        item = take()
        if item == '(':
            value = disjunction(); take(')')
        elif item == 'array':
            take('['); values = []
            while peek() != ']':
                values.append(primary())
                if peek() != ']': take(',')
            take(']'); value = ('list', tuple(values))
        elif item.startswith("'"):
            value = ('literal', item[1:-1].replace("''", "'"))
        elif item.isdigit(): value = ('number', int(item))
        elif re.fullmatch(r'[a-z_][a-z_0-9]*|"[a-z_][a-z_0-9]*"', item):
            item = item.strip('"')
            if peek() == '(':
                if item not in {'length', 'trim', 'btrim', 'any'}: raise ValueError('Unreviewed check function')
                take('(')
                if item == 'trim' and peek() == 'both':
                    take('both')
                    # PostgreSQL deparses SQL-standard TRIM this way. Only the
                    # default space is equivalent to the frozen trim(column).
                    if peek() == "' '": take("' '")
                    take('from'); argument = disjunction()
                else:
                    argument = disjunction()
                take(')')
                value = ('function', 'trim' if item == 'btrim' else item, argument)
            else: value = ('column', item)
        else: raise ValueError('Unreviewed check atom')
        casts(); return value
    def predicate():
        left = primary(); operator = peek()
        if operator == 'is':
            take(); negated = peek() == 'not'
            if negated: take()
            take('null'); return ('not-null' if negated else 'null', left)
        if operator == 'in':
            take(); take('('); values = []
            while peek() != ')':
                values.append(primary())
                if peek() != ')': take(',')
            take(')'); return ('in', left, tuple(values))
        if operator == 'between':
            take(); lower = primary(); take('and'); upper = primary()
            return ('and', ('>=', left, lower), ('<=', left, upper))
        if operator in {'=', '>', '<', '>=', '<=', '!=', '<>'}:
            take(); right = primary()
            if operator == '=' and right[:2] == ('function', 'any') and right[2][0] == 'list':
                return ('in', left, right[2][1])
            return (operator, left, right)
        return left
    def conjunction():
        value = predicate()
        while peek() == 'and': take(); value = ('and', value, predicate())
        return value
    def disjunction():
        value = conjunction()
        while peek() == 'or': take(); value = ('or', value, conjunction())
        return value
    def normalized(node):
        if not isinstance(node, tuple): return node
        if node and node[0] in {'and', 'or'}:
            operation = node[0]; children = []
            for item in node[1:]:
                value = normalized(item)
                children.extend(value[1:] if value[0] == operation else (value,))
            return (operation, *sorted(children, key=repr))
        return tuple(normalized(item) for item in node)
    try:
        value = disjunction()
        if position != len(tokens): return None
        return normalized(value)
    except (ValueError, IndexError, TypeError): return None


def _foreign_key(foreign):
    options = foreign.get('options', {})
    return (tuple(foreign['constrained_columns']), foreign['referred_table'],
            tuple(foreign['referred_columns']), str(options.get('ondelete', '')).upper(),
            bool(options.get('deferrable')), bool(options.get('initially')))


def _postgres_constraints(connection, tables):
    statement = text("""SELECT t.relname, c.conname, c.convalidated, c.condeferrable,
        c.condeferred, c.confmatchtype, rn.nspname AS referred_schema
        FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace
        LEFT JOIN pg_class rt ON rt.oid=c.confrelid
        LEFT JOIN pg_namespace rn ON rn.oid=rt.relnamespace
        WHERE n.nspname=current_schema() AND t.relname IN :tables
        AND c.contype IN ('f','p','u','c')""").bindparams(bindparam('tables', expanding=True))
    schema = connection.scalar(text('SELECT current_schema()'))
    reasons = []
    for row in connection.execute(statement, {'tables': tuple(tables)}).mappings():
        if (not row['convalidated'] or row['condeferrable'] or row['condeferred']
                or row['referred_schema'] not in (None, schema)
                or row['referred_schema'] is not None and row['confmatchtype'] != 's'):
            reasons.append('Private delivery release constraint is not enforced: '+row['relname']+'.')
    return reasons


def _guards(connection):
    dialect = connection.dialect.name; reasons = []
    if dialect == 'sqlite':
        if connection.scalar(text('PRAGMA foreign_keys')) != 1:
            reasons.append('Private delivery release foreign keys are disabled.')
        rows = {row['name']: row for row in connection.execute(text(
            "SELECT name,tbl_name,sql FROM sqlite_master WHERE type='trigger'")).mappings()}
        for name, expected in CONTRACT['sqlite_triggers'].items():
            actual = rows.get(name)
            if actual is None or _tokens(actual['sql']) != _tokens(expected):
                reasons.append('Private delivery release guard is missing or changed: '+name+'.')
        allowed_tables = {spec[0] for spec in CONTRACT['guard_specs']}
        if {name for name, row in rows.items() if row['tbl_name'] in allowed_tables} != set(CONTRACT['sqlite_triggers']):
            reasons.append('Private delivery release has an unreviewed native trigger.')
        return reasons
    if connection.scalar(text("SELECT current_setting('session_replication_role')")) != 'origin':
        reasons.append('Private delivery release origin trigger enforcement is unavailable.')
    statement = text("""SELECT t.tgname, c.relname, p.proname, pn.nspname AS function_schema,
        n.nspname AS table_schema, t.tgtype::integer AS kind, t.tgenabled, t.tgqual IS NULL AS no_when,
        t.tgattr::text AS columns, t.tgnargs, t.tgconstraint, p.prosrc, p.prosecdef,
        p.pronargs, p.prokind, p.proconfig, p.proisstrict, p.provolatile, l.lanname, p.prorettype::regtype::text AS returns
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid
        JOIN pg_namespace pn ON pn.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang
        WHERE n.nspname=current_schema() AND NOT t.tgisinternal AND c.relname IN :tables"""
        ).bindparams(bindparam('tables', expanding=True))
    rows = {row['tgname']: row for row in connection.execute(statement,
        {'tables': tuple(spec[0] for spec in CONTRACT['guard_specs'])}).mappings()}
    expected_names = {prefix+'_'+suffix for _, prefix, _, _, _ in CONTRACT['guard_specs'] for suffix in ('identity', 'truncate')}
    if set(rows) != expected_names:
        reasons.append('Private delivery release native trigger set requires reconciliation.')
    for table, prefix, _, _, _ in CONTRACT['guard_specs']:
        function = prefix+'_guard'; expected = CONTRACT['postgresql_functions'][function]
        for suffix, kind in (('identity', 27), ('truncate', 34)):
            name = prefix+'_'+suffix; row = rows.get(name)
            valid = row is not None and (row['relname'], row['proname'], row['kind']) == (table, function, kind)
            valid = valid and row['function_schema'] == row['table_schema'] and row['tgenabled'] in ('O', 'A')
            valid = valid and row['no_when'] and not row['columns'] and not row['tgnargs'] and not row['tgconstraint']
            valid = valid and not row['prosecdef'] and not row['pronargs'] and row['prokind'] == 'f'
            valid = valid and not row['proconfig'] and not row['proisstrict'] and row['provolatile'] == 'v'
            valid = valid and row['lanname'] == 'plpgsql' and row['returns'] == 'trigger'
            valid = valid and _tokens(row['prosrc']) == _tokens(expected)
            if not valid: reasons.append('Private delivery release guard is missing or changed: '+name+'.')
    return reasons


def installation_reasons(connection):
    """Inspect only the fixed release foundation; never execute DDL or payload SQL."""
    dialect = connection.dialect.name
    if dialect not in ('sqlite', 'postgresql'):
        return ['Private delivery release database dialect is unsupported.']
    inspector = inspect(connection); tables = CONTRACT['tables'][dialect]; reasons = []
    try:
        for parent in ('users', 'companies', 'branches'):
            if not inspector.has_table(parent) or tuple(inspector.get_pk_constraint(parent).get('constrained_columns', ())) != ('id',):
                reasons.append('Private delivery release native identity is missing: '+parent+'.')
        for name, expected in tables.items():
            if not inspector.has_table(name):
                reasons.append('Private delivery release table is missing: '+name+'.'); continue
            columns = {column['name']: column for column in inspector.get_columns(name)}
            if set(columns) != set(expected['columns']) or any(
                key not in columns or columns[key]['nullable'] != nullable
                or str(columns[key]['type'].compile(dialect=connection.dialect)).upper() != sql_type.upper()
                for key, (sql_type, nullable) in expected['columns'].items()):
                reasons.append('Private delivery release columns require migration: '+name+'.')
            if tuple(inspector.get_pk_constraint(name).get('constrained_columns', ())) != expected['pk']:
                reasons.append('Private delivery release primary key is missing: '+name+'.')
            actual_foreign = inspector.get_foreign_keys(name)
            if ({_foreign_key(item) for item in actual_foreign}
                    != {tuple(item) for item in expected['foreign_keys']}
                    or any(item.get('referred_schema') not in (None, inspector.default_schema_name) for item in actual_foreign)):
                reasons.append('Private delivery release foreign keys require migration: '+name+'.')
            unique = {tuple(item['column_names']) for item in inspector.get_unique_constraints(name)}
            if unique != set(expected['unique']):
                reasons.append('Private delivery release uniqueness requires migration: '+name+'.')
            checks = {item['name']: item['sqltext'] for item in inspector.get_check_constraints(name)}
            if set(checks) != set(expected['checks']) or any(
                _check_tree(expression) is None or _check_tree(checks.get(key, '')) != _check_tree(expression)
                for key, expression in expected['checks'].items()):
                reasons.append('Private delivery release checks require migration: '+name+'.')
        if dialect == 'postgresql': reasons.extend(_postgres_constraints(connection, tables))
        reasons.extend(_guards(connection))
    except (SQLAlchemyError, NotImplementedError, KeyError, TypeError):
        reasons.append('Private delivery release schema could not be verified.')
    return sorted(set(reasons))


def release_status(connection):
    reasons = installation_reasons(connection)
    return {'ready': not reasons, 'contract': _VERSION, 'reasons': reasons}
