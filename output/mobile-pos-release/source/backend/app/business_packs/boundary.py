"""Conservative pack primitives over an explicitly audited native-table policy.

There is deliberately no generic FK/label-to-pack inference: a shared customer,
employee, department or catalog item cannot establish an invoice/task's pack.
Every operational row needs its own immutable anchor; every master needs exact
context availability. Unknown mapped tables fail closed in a bound session.

Native authorization, company/branch guards and domain validators still apply.
JSON/polymorphic references require audited domain validation or explicit links.
Like the existing native boundaries, Session Core/bulk bypasses are blocked;
db.connection() is trusted server infrastructure and is NOT intercepted here.
Runtime support must stay disabled until each route/graph/connection use is audited.
"""
from dataclasses import dataclass
import re

from fastapi import HTTPException
from sqlalchemy import String, UniqueConstraint, and_, cast, event, exists, false, inspect, literal, or_, select
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.orm.util import LoaderCriteriaOption
from sqlalchemy.sql.selectable import Alias, CompoundSelect, FromClause, Join, Select, Subquery
from sqlalchemy.sql.functions import count as CountFunction
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause, TextClause

from app.db.base_class import Base
from app.branches.catalog import key_expression, resource_key
from app.core.tenant_boundary import ACTOR_FIELDS, GLOBAL_CATALOGUES, tenant_company_column
from .access import PackScope
from .models import PackActivation, PackContext, PackMasterAvailability, PackRecordOwnership, PackUserGrant
from .registry import PackRegistryError, get_pack, get_role


_IDENTITIES = frozenset({'companies', 'branches', 'users', 'common_people', 'common_profiles'})
_CONFIGURATION = frozenset(model.__tablename__ for model in (PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability))
_NAME = re.compile(r'[a-z][a-z0-9_]{0,119}\Z', re.ASCII)
_SHARED_READS = frozenset({'suite_access_memberships', 'suite_access_policies', 'suite_access_roles',
                          'bos_enabled_modules', 'suite_service_policies', 'suite_company_master_details', 'business_seller_grants'})


@dataclass(frozen=True)
class PackNativeLink:
    source_table: str
    source_column: str
    target_table: str
    target_column: str = 'id'

    def __post_init__(self):
        if any(not isinstance(value, str) or not _NAME.fullmatch(value) for value in (self.source_table, self.source_column, self.target_table, self.target_column)):
            raise ValueError('Native reference adapters require fixed identifier names')


@dataclass(frozen=True)
class PackSourceLink:
    source_table: str
    kind_column: str
    id_column: str
    targets: tuple[tuple[str, str], ...]

    def __post_init__(self):
        if any(not isinstance(value, str) or not _NAME.fullmatch(value)
               for value in (self.source_table, self.kind_column, self.id_column)):
            raise ValueError('Polymorphic source adapters require fixed identifiers')
        if (not isinstance(self.targets, tuple) or not self.targets
                or any(not isinstance(pair, tuple) or len(pair) != 2
                       or any(not isinstance(value, str) or not _NAME.fullmatch(value) for value in pair)
                       for pair in self.targets)
                or len({pair[0] for pair in self.targets}) != len(self.targets)):
            raise ValueError('Polymorphic sources require an immutable unambiguous target allow-list')


@dataclass(frozen=True)
class PackDerivedLink:
    """Creation-only provenance for a private native delivery/event row."""
    record_table: str
    source_tables: frozenset[str]
    immutable_fields: frozenset[str]

    def __post_init__(self):
        if (not isinstance(self.record_table, str) or not _NAME.fullmatch(self.record_table)
                or not isinstance(self.source_tables, frozenset) or not self.source_tables
                or not isinstance(self.immutable_fields, frozenset) or not self.immutable_fields
                or any(not isinstance(value, str) or not _NAME.fullmatch(value)
                       for value in self.source_tables | self.immutable_fields)
                or self.record_table in self.source_tables):
            raise ValueError('Derived native adapters require fixed private sources and immutable fields')


@dataclass(frozen=True)
class PackBoundaryPolicy:
    record_tables: frozenset[str]
    master_tables: frozenset[str]
    read_only_tables: frozenset[str] = frozenset({'roles', 'permissions'})
    native_links: tuple[PackNativeLink, ...] = ()
    shared_read_tables: frozenset[str] = frozenset()
    source_links: tuple[PackSourceLink, ...] = ()
    derived_links: tuple[PackDerivedLink, ...] = ()

    def __post_init__(self):
        groups = (self.record_tables, self.master_tables, self.read_only_tables)
        if any(not isinstance(group, frozenset) for group in groups):
            raise ValueError('Pack boundary tables must be immutable code-owned sets')
        if any(not isinstance(name, str) or not _NAME.fullmatch(name) for group in groups for name in group):
            raise ValueError('Invalid audited native table name')
        if any(groups[a] & groups[b] for a, b in ((0, 1), (0, 2), (1, 2))):
            raise ValueError('Native record, master and read-only categories must be distinct')
        if (self.record_tables | self.master_tables) & (_IDENTITIES | _CONFIGURATION | GLOBAL_CATALOGUES):
            raise ValueError('Identity/configuration/global definitions cannot be operational pack records')
        if not self.read_only_tables <= GLOBAL_CATALOGUES:
            raise ValueError('Read-only global tables must be declared native global definitions')
        if not isinstance(self.native_links, tuple) or any(not isinstance(link, PackNativeLink) for link in self.native_links):
            raise ValueError('Native reference adapters must be immutable code-owned links')
        if not isinstance(self.shared_read_tables, frozenset) or not self.shared_read_tables <= _SHARED_READS:
            raise ValueError('Shared native reads require a fixed reviewed authority adapter')
        if self.shared_read_tables & (self.master_tables | self.read_only_tables):
            raise ValueError('Shared authority reads cannot be global or enrolled master declarations')
        if (self.record_tables | self.master_tables) & (_SHARED_READS - {'suite_service_policies'}):
            raise ValueError('Native authority and shared-master extensions are not private pack records')
        if not isinstance(self.source_links, tuple) or any(not isinstance(link, PackSourceLink) for link in self.source_links):
            raise ValueError('Native source adapters must be immutable code-owned links')
        if (not isinstance(self.derived_links, tuple)
                or any(not isinstance(link, PackDerivedLink) for link in self.derived_links)
                or len({link.record_table for link in self.derived_links}) != len(self.derived_links)
                or any(link.record_table not in self.record_tables or not link.source_tables <= self.record_tables
                       for link in self.derived_links)):
            raise ValueError('Derived adapters require unambiguous declared private native records')


def deny(message='Native record is outside the assigned Business Pack context'):
    raise HTTPException(403, message)


def _current(scope, connection):
    """A cached scope cannot outlive its grant/context/activation revision."""
    try:
        manifest = get_pack(scope.pack_key)
        role = get_role(scope.pack_key, scope.role)
    except PackRegistryError:
        deny('Unsupported Business Pack authorization')
    if scope.pack_version != manifest.version or scope.capabilities != role.capabilities:
        deny('Business Pack authorization does not match its registered role/version')
    from app.models.company import Branch, Company
    from app.models.user import User
    from app.branches.models import BranchLifecycle
    a, c, g = PackActivation.__table__, PackContext.__table__, PackUserGrant.__table__
    statement = select(g.c.id).select_from(g.join(c, and_(
        c.c.id == g.c.context_id, c.c.company_id == g.c.company_id, c.c.branch_id == g.c.branch_id,
    )).join(a, and_(
        a.c.id == c.c.activation_id, a.c.company_id == c.c.company_id,
        a.c.pack_key == c.c.pack_key, a.c.pack_version == c.c.pack_version,
    )).join(Branch.__table__, and_(Branch.id == c.c.branch_id, Branch.company_id == c.c.company_id))
      .join(Company.__table__, Company.id == c.c.company_id).join(User.__table__, User.id == g.c.user_id)).where(
        g.c.id == scope.grant_id, g.c.user_id == scope.user_id, g.c.active.is_(True), g.c.role == scope.role,
        g.c.revision == scope.grant_revision, c.c.id == scope.context_id, c.c.activation_id == scope.activation_id,
        c.c.company_id == scope.company_id, c.c.branch_id == scope.branch_id,
        c.c.pack_key == scope.pack_key, c.c.pack_version == scope.pack_version,
        c.c.state == 'active', a.c.state == 'active', c.c.revision == scope.context_revision,
        a.c.revision == scope.activation_revision, Branch.is_active.is_(True), Company.is_active.is_(True), User.is_active.is_(True),
        ~exists(select(1).where(BranchLifecycle.branch_id == scope.branch_id, BranchLifecycle.deleted_at.is_not(None))),
    )
    if connection.execute(statement).first() is None:
        deny('Business Pack authorization changed; refresh the assigned context')


def install(db, scope: PackScope | None, *, policy: PackBoundaryPolicy | None = None):
    """Install additive request-local guards; None leaves genuinely legacy work alone.

    The policy is a server-owned reviewed graph, never request configuration.
    Unknown tables remain denied. No claim of complete pack support is implied.
    """
    absent = object()
    previous = db.info.get('business_pack_scope', absent)
    previous_policy = db.info.get('business_pack_policy', absent)
    if previous is not absent and previous != scope:
        deny('Business Pack context/policy cannot change inside a bound session')
    if previous_policy is not absent:
        if previous != scope or previous_policy != policy:
            deny('Business Pack context/policy cannot change inside a bound session')
        return lambda: None
    if scope is None:
        return lambda: None
    if not isinstance(scope, PackScope) or not isinstance(policy, PackBoundaryPolicy):
        raise ValueError('A resolved PackScope and audited PackBoundaryPolicy are required')
    if db.new or db.deleted or any(db.is_modified(item, include_collections=True) for item in db.dirty):
        deny('Finish or roll back pending changes before selecting a Business Pack context')
    _current(scope, db.connection())
    models = {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}
    tables = Base.metadata.tables
    declared = policy.record_tables | policy.master_tables | policy.read_only_tables | policy.shared_read_tables
    if not declared <= set(models):
        raise ValueError('An audited pack policy references an unregistered native model')
    for link in policy.native_links:
        if (link.source_table not in policy.record_tables | policy.master_tables
                or link.target_table not in tables or link.source_column not in tables[link.source_table].c
                or link.target_column not in tables[link.target_table].c):
            raise ValueError('Invalid code-owned native reference adapter')
        parent = tables[link.target_table]
        unique = (len(parent.primary_key) == 1 and parent.c[link.target_column].primary_key
                  or parent.c[link.target_column].unique
                  or any(isinstance(constraint, UniqueConstraint) and tuple(constraint.columns.keys()) == (link.target_column,) for constraint in parent.constraints))
        if not unique:
            raise ValueError('A scalar native reference adapter must identify one unique parent row')
    for link in policy.source_links:
        if (link.source_table not in policy.record_tables
                or any(column not in tables[link.source_table].c for column in (link.kind_column, link.id_column))
                or any(target not in policy.record_tables or target not in tables
                       or tuple(tables[target].primary_key.columns.keys()) != ('id',)
                       for _, target in link.targets)):
            raise ValueError('Polymorphic references must identify declared private native records')
    for link in policy.derived_links:
        if (not link.immutable_fields <= set(tables[link.record_table].c.keys())
                or any(len(tables[source].primary_key) != 1 for source in link.source_tables)):
            raise ValueError('Derived native references require real immutable columns and unique scalar sources')
    ownership, availability = PackRecordOwnership.__table__, PackMasterAvailability.__table__

    def shared_read(table):
        name = table.name
        if name not in policy.shared_read_tables:
            return false()
        if name=='business_seller_grants':
            return table.c.organization_id==scope.company_id
        if name in {'suite_access_memberships', 'suite_access_policies'}:
            return and_(table.c.company_id == scope.company_id, table.c.user_id == scope.user_id)
        if name in {'suite_access_roles', 'bos_enabled_modules'}:
            # Disabled/revoked authority stays visible to native validators.
            # Hiding it could turn a denial into a permissive default.
            return table.c.company_id == scope.company_id
        if name == 'suite_company_master_details':
            return and_(table.c.organization_id == scope.company_id, exists(select(1).where(
                availability.c.company_id == scope.company_id, availability.c.branch_id == scope.branch_id,
                availability.c.context_id == scope.context_id, availability.c.active.is_(True),
                availability.c.resource_table == 'crm_companies',
                availability.c.resource_key == cast(table.c.account_id, String),
            )).correlate(table))
        if name == 'suite_service_policies':
            company = scope.company_id
            from app.shared.form_defaults import MODULES, scope_key as defaults_key
            default_keys = [defaults_key(company, module, branch)
                            for branch in (None, scope.branch_id) for module in (None, *sorted(MODULES))]
            profile_keys = [f'business-profile:company:{company}',
                            f'business-profile:company:{company}:branch:{scope.branch_id}']
            return or_(
                and_(table.c.organization_id == company, table.c.kind == 'form_defaults', table.c.scope_key.in_(default_keys)),
                and_(table.c.organization_id == company, table.c.kind == 'employee_categories', table.c.scope_key == f'employee-categories:company:{company}'),
                and_(table.c.organization_id == company, table.c.kind == 'business_profile', table.c.scope_key.in_(profile_keys)),
                and_(table.c.organization_id == company, table.c.kind == 'settings',
                     table.c.scope_key.in_([f'company:{company}', f'company:{company}:module:srm'])),
                and_(table.c.organization_id.is_(None), table.c.kind == 'settings', table.c.scope_key == 'platform'),
            )
        return false()

    def criterion(table, *, for_write=False):
        name = table.name
        if name in policy.read_only_tables:
            return literal(True)
        if name == 'companies':
            return table.c.id == scope.company_id
        if name == 'branches':
            return and_(table.c.id == scope.branch_id, table.c.company_id == scope.company_id)
        if name == 'users':
            return table.c.id == scope.user_id
        if name == 'common_people':
            return table.c.user_id == scope.user_id
        if name == 'common_profiles':
            person = tables.get('common_people')
            return table.c.person_id.in_(select(person.c.id).where(person.c.user_id == scope.user_id)) if person is not None else false()
        if name in _CONFIGURATION:
            exact_company = table.c.company_id == scope.company_id
            if name == PackActivation.__tablename__:
                return and_(exact_company, table.c.id == scope.activation_id)
            if name == PackContext.__tablename__:
                return and_(exact_company, table.c.id == scope.context_id, table.c.branch_id == scope.branch_id)
            if name == PackUserGrant.__tablename__:
                return and_(exact_company, table.c.id == scope.grant_id, table.c.user_id == scope.user_id,
                            table.c.context_id == scope.context_id, table.c.branch_id == scope.branch_id)
            return and_(exact_company, table.c.context_id == scope.context_id, table.c.branch_id == scope.branch_id)
        if name in policy.record_tables:
            owned = exists(select(1).where(
                ownership.c.resource_table == name, ownership.c.resource_key == key_expression(table),
                ownership.c.company_id == scope.company_id, ownership.c.branch_id == scope.branch_id, ownership.c.context_id == scope.context_id,
            )).correlate(table)
            return owned if for_write else or_(owned, shared_read(table))
        if name in policy.master_tables:
            return exists(select(1).where(
                availability.c.resource_table == name, availability.c.resource_key == key_expression(table),
                availability.c.company_id == scope.company_id, availability.c.branch_id == scope.branch_id,
                availability.c.context_id == scope.context_id, availability.c.active.is_(True),
            )).correlate(table)
        return false() if for_write else shared_read(table)

    criteria = {model: criterion(model.__table__) for model in models.values()}
    allowed_models=frozenset(model for name,model in models.items() if name in declared|_IDENTITIES|_CONFIGURATION)
    options = {model: with_loader_criteria(model, guard, include_aliases=True, propagate_to_loaders=False) for model, guard in criteria.items()}
    pending = []
    trusted_identity_load = False
    original_get, original_refresh = db.get, db.refresh
    bulk_names = ('bulk_insert_mappings', 'bulk_update_mappings', 'bulk_save_objects')
    original_bulk = {name: getattr(db, name) for name in bulk_names}

    def visible(model, identity, *, for_write=False):
        _current(scope, db.connection())
        mapper = inspect(model, raiseerr=False)
        model = getattr(mapper, 'class_', model)
        from .anonymous_birth import read_criteria as birth_criteria
        born = birth_criteria(db)
        if model not in criteria and model not in born:
            return False
        keys = inspect(model).primary_key
        values = [identity.get(key.key) for key in keys] if isinstance(identity, dict) else list(identity) if isinstance(identity, (tuple, list)) else [identity]
        if len(keys) != len(values):
            return False
        with db.no_autoflush:
            guard = born[model] if model in born else criterion(model.__table__, for_write=True) if for_write else criteria[model]
            return db.connection().execute(select(*keys).where(guard, *(key == value for key, value in zip(keys, values)))).first() is not None

    def restrict(execution):
        _current(scope, db.connection())
        from .retail.accounting import _restrict as retail_accounting_read
        if retail_accounting_read(execution, scope):
            return
        if not execution.is_orm_statement:
            deny('Session Core SQL requires an audited native service; unscoped pack SQL is blocked')
        if execution.is_insert or execution.is_update or execution.is_delete:
            deny('Use validated per-record native writes in a Business Pack context')
        if isinstance(execution.statement, CompoundSelect):
            deny('Compound native queries require an audited Business Pack adapter')
        from sqlalchemy.sql.selectable import Exists
        from .catalog_predicate import _verified_workspace_predicate
        from .common_queries import assert_mapped_sources
        # Validation copy only: the original SQL and its row filters are never
        # rewritten. Certifying one negative metadata predicate cannot certify
        # a reused column, a second mapper or an eager relationship elsewhere.
        checked=visitors.replacement_traverse(execution.statement,{},lambda node:
            node if isinstance(node,LoaderCriteriaOption) else
            literal(True) if isinstance(node,Exists) and _verified_workspace_predicate(db,scope,node) else None)
        associations=()
        if {'roles','permissions'}<=policy.read_only_tables:
            from app.models.user import role_permissions
            associations=(role_permissions,)
        from .anonymous_birth import leased_models, read_criteria as birth_criteria
        born = birth_criteria(db)
        assert_mapped_sources(checked,allowed_models|frozenset(leased_models(db)),trusted_identity=trusted_identity_load,allowed_associations=associations)
        if not trusted_identity_load and not execution.is_column_load and not execution.is_relationship_load:
            count_stars = set()
            statement = execution.statement
            columns, sources = getattr(statement, '_raw_columns', ()), getattr(statement, '_from_obj', ())
            # Query(Model).count() wraps a scoped ORM select in count(*).
            # Only that structural form admits the star literal; a raw FROM,
            # arbitrary literal, or a mixed unscoped alias remains forbidden.
            if len(columns) == len(sources) == 1 and isinstance(columns[0], CountFunction) and not statement._where_criteria:
                arguments = list(columns[0].clauses)
                inner = sources[0]
                while isinstance(inner, (Alias, Subquery)):
                    inner = inner.element
                if (len(arguments) == 1 and isinstance(arguments[0], ColumnClause)
                        and arguments[0].is_literal and arguments[0].name == '*' and isinstance(inner, Select)):
                    nodes = tuple(visitors.iterate(inner))
                    mapped_froms = [node._deannotate() for node in nodes if isinstance(node, FromClause)
                                    and (node._annotations.get('parententity') or node._annotations.get('parentmapper'))]
                    def scoped_from(node):
                        if isinstance(node, Join):
                            return scoped_from(node.left) and scoped_from(node.right)
                        return any(node._deannotate() is known for known in mapped_froms)
                    if mapped_froms and all(scoped_from(source) for node in nodes if isinstance(node, Select)
                                           for source in node.get_final_froms()):
                        count_stars.add(id(arguments[0]))
            def validation_nodes(root):
                # Prune only this certified occurrence. A raw column reused in
                # another projection/filter remains visible to validation.
                from sqlalchemy.sql.selectable import Exists
                from .catalog_predicate import _verified_workspace_predicate
                stack=[root]
                while stack:
                    node=stack.pop()
                    if isinstance(node,Exists) and _verified_workspace_predicate(db,scope,node):
                        from app.apps.srm.models import SRMProduct
                        if execution.bind_mapper is None or execution.bind_mapper.class_ is not SRMProduct:
                            deny('Catalog metadata projection requires its native product parent')
                        continue
                    yield node
                    stack.extend(reversed(tuple(node.get_children())))
            for node in validation_nodes(execution.statement):
                if isinstance(node, TextClause):
                    deny('Textual SQL requires an audited Business Pack adapter')
                if isinstance(node, ColumnClause) and getattr(node, 'is_literal', False) and id(node) not in count_stars:
                    deny('Literal SQL columns require an audited Business Pack adapter')
                if isinstance(node, ColumnClause) and getattr(node, 'table', None) is not None:
                    annotations = node._annotations
                    if not (annotations.get('parententity') or annotations.get('parentmapper')):
                        deny('Raw native columns require an audited Business Pack adapter')
        if execution.bind_mapper is not None and execution.bind_mapper.class_ not in criteria and execution.bind_mapper.class_ not in born:
            deny('Unregistered native model requires a Business Pack adapter')
        if execution.is_column_load:
            state = getattr(execution.load_options, '_refresh_state', None)
            if state is not None and state.identity is not None and not visible(state.class_, state.identity):
                deny()
        if execution.is_select:
            execution.update_execution_options(compiled_cache=None)
            inherited = {id(option) for option in getattr(execution.statement, '_with_options', ())}
            current_options = [option for model, option in options.items() if model not in born]
            current_options += [with_loader_criteria(model, guard, include_aliases=True, propagate_to_loaders=False) for model, guard in born.items()]
            execution.statement = execution.statement.options(*(option for option in current_options if id(option) not in inherited))

    def native_references(item, *, new=False):
        table = inspect(item).mapper.local_table
        references = [(constraint.referred_table, tuple((element.parent.name, element.column) for element in constraint.elements))
                      for constraint in table.foreign_key_constraints]
        references += [(tables[link.target_table], ((link.source_column, tables[link.target_table].c[link.target_column]),))
                       for link in policy.native_links if link.source_table == table.name]
        with db.no_autoflush:
            for parent, pairs in references:
                values = [(name, key, getattr(item, name)) for name, key in pairs]
                if any(value is None for name, key, value in values):
                    continue
                if not new and all(name in ACTOR_FIELDS and not inspect(item).attrs[name].history.has_changes() for name, key, value in values):
                    continue  # Historical authorship is not operational ownership.
                if scope.pack_key == 'construction':
                    from .construction import project_reference
                    from .construction_billing import project_reference as billing_project_reference
                    if (project_reference(db, scope, item, parent, pairs)
                            or billing_project_reference(db, scope, item, parent, pairs)):
                        continue
                if scope.pack_key == 'retail':
                    from .retail.accounting import _reference as retail_accounting_reference
                    if retail_accounting_reference(db, scope, item, parent, pairs):
                        continue
                if scope.pack_key == 'pharma':
                    from .pharma.references import reference as pharma_batch_reference
                    from .pharma.recall_references import reference as pharma_recall_reference
                    if (pharma_batch_reference(db, scope, item, parent, pairs)
                            or pharma_recall_reference(db, scope, item, parent, pairs)):
                        continue
                if scope.pack_key == 'restaurant':
                    from .restaurant.references import reference as restaurant_header_reference
                    if restaurant_header_reference(db, scope, item, parent, pairs):
                        continue
                if scope.pack_key == 'accounting_firm':
                    from .accounting_firm.references import historical_preparer
                    from .accounting_firm.project_links import reference as accounts_project_reference
                    if (historical_preparer(db, scope, item, parent, pairs)
                            or accounts_project_reference(db, scope, item, parent, pairs)):
                        continue
                # A composite FK is one exact tuple, never independent sets of
                # parent keys that could form a cross-context product.
                if not db.connection().execute(select(literal(1)).select_from(parent).where(
                    criterion(parent), *(key == value for name, key, value in values),
                )).first():
                    deny('A native relationship is outside the assigned Business Pack context')
            for link in policy.source_links:
                if link.source_table != table.name:
                    continue
                target = dict(link.targets).get(getattr(item, link.kind_column))
                source_id = getattr(item, link.id_column)
                if target is None or type(source_id) is not int or source_id <= 0:
                    deny('Native event source is unsupported or malformed')
                parent = tables[target]
                marker = getattr(item, '_suite_source_record', None)
                if marker is not None:
                    state = inspect(marker, raiseerr=False)
                    if (state is None or getattr(state, 'session', None) is not db
                            or state.mapper.local_table is not parent or getattr(marker, 'id', None) != source_id):
                        deny('Native event source marker does not match its persisted source')
                if not db.connection().execute(select(literal(1)).select_from(parent).where(
                    criterion(parent, for_write=True), parent.c.id == source_id,
                )).first():
                    deny('Native event source crosses the assigned Business Pack boundary')

    def native_identity(item, *, new):
        table = inspect(item).mapper.local_table
        fields = {'organization_id'} & set(table.c.keys())
        if tenant_company_column(type(item)):
            fields.add('company_id')
        for field in fields:
            value = getattr(item, field)
            if value is None and new:
                setattr(item, field, scope.company_id)
            elif value is not None and value != scope.company_id:
                deny('Native record belongs to another company')
        if 'branch_id' in table.c:
            column = table.c.branch_id
            value = getattr(item, 'branch_id')
            accounting = any(fk.column.table.name == 'fam_branches' for fk in column.foreign_keys)
            if accounting:
                from app.branches.models import AccountingBranchMap
                if value is not None and not db.connection().execute(select(AccountingBranchMap.branch_id).where(
                    AccountingBranchMap.accounting_branch_id == value, AccountingBranchMap.company_id == scope.company_id,
                    AccountingBranchMap.branch_id == scope.branch_id,
                )).first():
                    deny('Accounting branch does not match the assigned Business Pack branch')
            elif value is None and new:
                item.branch_id = scope.branch_id
            elif value is not None and value != scope.branch_id:
                deny('Native record belongs to another branch')

    def derived_source(item, *, queue=()):
        """A Python marker identifies an object to prove; it grants no authority."""
        table = inspect(item).mapper.local_table
        link = next((link for link in policy.derived_links if link.record_table == table.name), None)
        if link is None:
            return
        if scope.pack_key in {'retail','pharma'}:
            from .retail.accounting import _derived_delivery
            if _derived_delivery(db, scope, item):
                return
        source = getattr(item, '_suite_source_record', None)
        state = inspect(source, raiseerr=False)
        if (source is item or state is None or getattr(state, 'session', None) is not db
                or not getattr(state, 'persistent', False) or source in db.new or source in db.deleted
                or any(source is candidate for candidate in (*pending, *queue))):
            deny('Derived native record requires an already persisted private source')
        parent = state.mapper.local_table
        keys = tuple(parent.primary_key)
        identity = state.identity
        if (parent.name not in link.source_tables or state.mapper.class_ is not models.get(parent.name)
                or len(keys) != 1 or not identity or len(identity) != 1
                or type(identity[0]) is not int or identity[0] <= 0
                or state.attrs[state.mapper.get_property_by_column(keys[0]).key].history.has_changes()
                or any(state.attrs[name].history.has_changes()
                       for name in ('organization_id', 'company_id', 'branch_id') if name in state.attrs)):
            deny('Derived native source identity is unsupported or changed')
        source_id = identity[0]
        native_scope = []
        if 'organization_id' in parent.c:
            native_scope.append(parent.c.organization_id == scope.company_id)
        if tenant_company_column(state.mapper.class_):
            native_scope.append(parent.c.company_id == scope.company_id)
        if not native_scope:
            # A declared private child may inherit native company only through
            # an explicitly audited real scalar FK to another PRIVATE record.
            # Shared products/customers/availability never establish provenance.
            from app.branches.models import BranchOwnership
            branch_owner = BranchOwnership.__table__
            def native_owned(table, key):
                return exists(select(1).where(
                    branch_owner.c.resource_table == table.name,
                    branch_owner.c.resource_key == cast(key, String),
                    branch_owner.c.company_id == scope.company_id,
                    branch_owner.c.branch_id == scope.branch_id,
                )).correlate(table)
            paths = []
            for declared in policy.native_links:
                if declared.source_table != parent.name or declared.target_table not in policy.record_tables:
                    continue
                root = tables[declared.target_table]
                root_keys = tuple(root.primary_key)
                source_column, root_column = parent.c[declared.source_column], root.c[declared.target_column]
                if (len(root_keys) != 1 or root_column is not root_keys[0]
                        or not any(fk.column is root_column and len(fk.constraint.elements) == 1 for fk in source_column.foreign_keys)):
                    continue
                attribute = state.mapper.get_property_by_column(source_column).key
                if state.attrs[attribute].history.has_changes():
                    deny('Derived private native parent reference changed')
                referenced = getattr(source, attribute)
                if type(referenced) is not int or referenced <= 0:
                    deny('Derived private native parent identity is invalid')
                cached = db.identity_map.get((models[root.name], (referenced,), None))
                if cached is not None:
                    root_state = inspect(cached)
                    root_attribute = root_state.mapper.get_property_by_column(root_column).key
                    if (root_state.session is not db or not root_state.persistent or cached in db.deleted
                            or root_state.identity != (referenced,)
                            or root_state.attrs[root_attribute].history.has_changes()
                            or getattr(cached, root_attribute) != referenced):
                        deny('Derived private native root identity is not persistent')
                company_checks = []
                if 'organization_id' in root.c: company_checks.append(root.c.organization_id == scope.company_id)
                if tenant_company_column(models[root.name]): company_checks.append(root.c.company_id == scope.company_id)
                if not company_checks:
                    continue
                if 'branch_id' in root.c: company_checks.append(root.c.branch_id == scope.branch_id)
                paths.append(and_(source_column == referenced, native_owned(parent, keys[0]),
                    exists(select(1).select_from(root).where(
                        root_column == source_column, *company_checks,
                        criterion(root, for_write=True), native_owned(root, root_column),
                    )).correlate(parent)))
            if not paths:
                deny('Derived native source requires an explicit persisted native company')
            native_scope.append(or_(*paths))
        if 'branch_id' in parent.c:
            column = parent.c.branch_id
            if any(fk.column.table.name == 'fam_branches' for fk in column.foreign_keys):
                from app.branches.models import AccountingBranchMap
                native_scope.append(exists(select(1).where(
                    AccountingBranchMap.accounting_branch_id == column,
                    AccountingBranchMap.company_id == scope.company_id,
                    AccountingBranchMap.branch_id == scope.branch_id,
                )).correlate(parent))
            else:
                native_scope.append(column == scope.branch_id)
        # Both proofs use the actual persisted identity. A mutable source.id,
        # a shared-master availability row or a same-flush future anchor cannot
        # substitute for this pre-existing private parent anchor.
        anchored = exists(select(1).where(
            ownership.c.resource_table == parent.name,
            ownership.c.resource_key == cast(keys[0], String),
            ownership.c.company_id == scope.company_id, ownership.c.branch_id == scope.branch_id,
            ownership.c.context_id == scope.context_id,
        )).correlate(parent)
        if not db.connection().execute(select(keys[0]).where(
                keys[0] == source_id, *native_scope, criterion(parent, for_write=True), anchored)).first():
            deny('Derived native source crosses the assigned private Business Pack boundary')

    def validate(session, *args):
        _current(scope, session.connection())
        from .anonymous_birth import prepare_flush, allow_write as birth_write
        prepare_flush(session)
        for item in session.new | session.dirty | session.deleted:
            if birth_write(session, item):
                continue
            from .retail.accounting import _write as retail_accounting_write
            if retail_accounting_write(session, scope, item):
                continue
            if type(item) not in allowed_models:
                deny('This native mapper has no audited Business Pack adapter')
            mapper = inspect(item).mapper
            table = mapper.local_table
            if table.name not in policy.record_tables | policy.master_tables:
                deny('This native table has no writable audited Business Pack adapter')
            if table.name == 'suite_service_policies' and item.kind in {'settings', 'form_defaults', 'business_profile'}:
                deny('Shared company configuration cannot be changed through an operational pack write')
            if not scope.writable:
                deny('The assigned Business Pack branch is read-only')
            state = inspect(item)
            new = item in session.new
            for link in policy.source_links:
                if link.source_table == table.name and (
                    getattr(item, link.kind_column) not in dict(link.targets)
                    or type(getattr(item, link.id_column)) is not int or getattr(item, link.id_column) <= 0
                ):
                    deny('Native event source is unsupported or malformed')
            native_identity(item, new=new)
            if scope.pack_key == 'retail':
                from .retail.stock_receipts import validate_item as validate_retail_receipt
                validate_retail_receipt(session, scope, item)
            if scope.pack_key == 'construction':
                from .construction import validate_industry_source
                validate_industry_source(session, scope, item)
            if new:
                derived_source(item)
            if not new:
                if table.name in policy.master_tables:
                    deny('Shared native masters require an independently authorized core or configuration purpose')
                if not visible(type(item), state.identity, for_write=True):
                    deny()
                immutable = {column.name for column in table.primary_key} | ({'organization_id', 'branch_id'} & set(table.c.keys()))
                if tenant_company_column(type(item)):
                    immutable.add('company_id')
                if any(state.attrs[name].history.has_changes() for name in immutable):
                    deny('Native source identity cannot be changed through a pack update')
                if any(state.attrs[column].history.has_changes() for link in policy.source_links
                       if link.source_table == table.name for column in (link.kind_column, link.id_column)):
                    deny('Native event source identity is immutable')
                if any(state.attrs[column].history.has_changes() for link in policy.derived_links
                       if link.record_table == table.name for column in link.immutable_fields):
                    deny('Derived native delivery identity and payload are immutable')
                if item not in session.deleted:
                    native_references(item)
            if new:
                pending.append(item)

    def stamp(session, *args):
        queue = list(dict.fromkeys(pending)); pending.clear()
        if not queue:
            return
        _current(scope, session.connection())
        # Validate provenance for the whole batch BEFORE any child gets an
        # anchor, so same-flush peers cannot authorize each other or a cycle.
        for item in queue:
            derived_source(item, queue=queue)
        # Stamp every generated child independently. All writes remain in the
        # native transaction, so a bad relationship rolls back the whole set.
        for item in queue:
            table = inspect(item).mapper.local_table
            values = {column.name: getattr(item, column.name) for column in table.c}
            key = resource_key(table, values)
            target = ownership if table.name in policy.record_tables else availability
            existing = session.connection().execute(select(target.c.id).where(target.c.resource_table == table.name, target.c.resource_key == key)).first()
            if existing:
                deny('Native source identity already has Business Pack history; it cannot be reused')
            data = dict(company_id=scope.company_id, branch_id=scope.branch_id, context_id=scope.context_id, resource_table=table.name, resource_key=key, revision=1)
            data.update(source='pack-native-create') if target is ownership else data.update(active=True)
            session.connection().execute(target.insert().values(**data))
        for item in queue:
            native_references(item, new=True)
        from .delivery_sources import finalize_pack_births
        finalize_pack_births(session,scope,queue)

    def scoped_get(model, identity, **kwargs):
        nonlocal trusted_identity_load
        if not visible(model, identity):
            return None
        previous_load = trusted_identity_load
        trusted_identity_load = True
        try:
            return original_get(model, identity, **kwargs)
        finally:
            trusted_identity_load = previous_load

    def scoped_refresh(item, *args, **kwargs):
        if not visible(type(item), inspect(item).identity):
            deny()
        return original_refresh(item, *args, **kwargs)

    def reject_bulk(*args, **kwargs):
        deny('Bulk mappings cannot bypass Business Pack native validation')

    def discard_pending(*args):
        pending.clear()

    # An object/relationship loaded before binding cannot expose cached foreign
    # fields afterward. Never discard pending changes: those were rejected above.
    for state in list(db.identity_map.all_states()):
        model = state.class_
        if model not in criteria:
            item=state.obj()
            if item is not None:db.expire(item)
        elif model.__table__.name not in policy.read_only_tables:
            item = state.obj()
            if item is not None and (model.__table__.name not in _IDENTITIES or not visible(model, state.identity)):
                db.expire(item)
    db.get, db.refresh = scoped_get, scoped_refresh
    for name in bulk_names:
        setattr(db, name, reject_bulk)
    db.info['business_pack_scope'], db.info['business_pack_policy'] = scope, policy
    listeners = (('do_orm_execute', restrict), ('before_flush', validate), ('after_flush_postexec', stamp), ('after_soft_rollback', discard_pending))
    for name, callback in listeners:
        event.listen(db, name, callback)
    closed = False

    def cleanup():
        nonlocal closed
        if closed:
            return
        closed = True
        db.get, db.refresh = original_get, original_refresh
        for name, method in original_bulk.items():
            setattr(db, name, method)
        for name, callback in listeners:
            event.remove(db, name, callback)
        for key, value in (('business_pack_scope', previous), ('business_pack_policy', previous_policy)):
            if value is absent:
                db.info.pop(key, None)
            else:
                db.info[key] = value
        pending.clear()
    return cleanup
