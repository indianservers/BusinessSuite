"""Closed ORM-source inventory, independent of loader-criterion snapshots.

An ORM statement can contain several mappers while bind_mapper identifies only
one. Class identity is authority here: another mapper over the same SQL table
does not inherit a registered model's permission.
"""
from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnElement,ColumnClause
from sqlalchemy.sql.selectable import FromClause,Join,Alias,Subquery,Select


def _model(entity):
    inspected=inspect(entity,raiseerr=False)
    mapper=getattr(inspected,'mapper',inspected)
    return getattr(mapper,'class_',None)


def _same_source(left,right):
    left,right=left._deannotate(),right._deannotate()
    if left is right:return True
    if getattr(left,'name',None)!=getattr(right,'name',None) or getattr(left,'schema',None)!=getattr(right,'schema',None):return False
    return bool(getattr(left,'_cloned_set',{left})&getattr(right,'_cloned_set',{right}))


def assert_mapped_sources(statement,allowed_models,*,trusted_identity=False,allowed_associations=()):
    """Reject unknown/mixed/late/eager mappers and uncertified raw FROMs.

    trusted_identity is private caller state around an already proven native
    get/refresh. It never exempts an unknown mapped class. Association tables
    must be explicit immutable metadata links, not guessed from table names.
    """
    allowed=frozenset(allowed_models);associations=frozenset(allowed_associations)
    def deny():raise HTTPException(403,'An ORM source is outside the registered native purpose')
    nodes=tuple(visitors.iterate(statement));models=set()
    checked_aliases=set()
    def register(entity):
        described=inspect(entity,raiseerr=False)
        model=_model(entity)
        if model is not None:
            if model not in allowed:deny()
            models.add(model)
            if getattr(described,'is_aliased_class',False) and id(described) not in checked_aliases:
                checked_aliases.add(id(described))
                source=described.selectable
                while isinstance(source,(Alias,Subquery)):
                    source=source.element
                if not isinstance(source,Select) and not _same_source(source,described.mapper.persist_selectable):deny()
                # Name adaptation cannot re-label another record's payload as
                # a registered entity and thereby borrow its masking/policies.
                if any(described.selectable.corresponding_column(column,require_embedded=True) is None for column in described.mapper.columns):deny()
        return model
    for node in nodes:
        annotations=getattr(node,'_annotations',{})
        for name in ('parentmapper','parententity'):
            if annotations.get(name) is not None and register(annotations[name]) is None:deny()
    for item in getattr(statement,'column_descriptions',()):
        entity=item.get('entity')
        if entity is not None and register(entity) is None:deny()
    # Load/contains_eager paths are visible before SQLAlchemy adds their joins.
    # Protective with_loader_criteria options have no eager path and confer no
    # new source permission, so they are deliberately not treated as queries.
    for option in getattr(statement,'_with_options',()):
        if not getattr(option,'_is_strategy_option',False):continue
        for loader in (option,*getattr(option,'context',())):
            path=getattr(loader,'path',())
            segments=tuple(path) if path is not None else ()
            mapped=False
            for entity in segments:
                target=getattr(entity,'mapper',entity)
                if register(target) is not None:mapped=True
                secondary=getattr(entity,'secondary',None)
                if isinstance(secondary,FromClause) and secondary._deannotate() not in associations:deny()
            strategy=getattr(loader,'strategy',()) or ()
            if any(isinstance(segment,str) for segment in segments) and any(
                    name=='lazy' and value not in {'raise','raise_on_sql','noload'} for name,value in strategy):deny()
            if segments and not mapped and not strategy:deny()
    # A mapped class may itself acquire a default eager relationship after this
    # request's loader criteria were built. Inspect those targets live too.
    pending=list(models);seen=set()
    while pending:
        model=pending.pop()
        if model in seen:continue
        seen.add(model)
        for relationship in inspect(model).relationships:
            if relationship.lazy in {'joined','subquery','selectin','immediate'}:
                target=relationship.mapper.class_
                register(target);pending.append(target)
                if relationship.secondary is not None and relationship.secondary._deannotate() not in associations:deny()
    if trusted_identity:return
    def sources(node):
        # ORM compilation adds anonymous eager joins. Their mapper paths were
        # validated above; inspect caller-supplied FROM/join structure instead
        # of confusing generated eager aliases with unscoped raw SQL aliases.
        explicit=list(getattr(node,'_from_obj',()))
        explicit.extend(join[0] for join in getattr(node,'_setup_joins',()))
        explicit.extend(source for source in getattr(node,'_raw_columns',()) if isinstance(source,FromClause) and not isinstance(source,ColumnElement))
        # Query.join(...).with_entities(...) preserves its actual ORM join
        # targets in this SQLAlchemy structural container, not _setup_joins.
        for memo in getattr(node,'_memoized_select_entities',()):
            explicit.extend(join[0] for join in getattr(memo,'_setup_joins',()))
            explicit.extend(source for source in getattr(memo,'_raw_columns',()) if isinstance(source,FromClause) and not isinstance(source,ColumnElement))
        if not explicit and node._propagate_attrs.get('compile_state_plugin')!='orm':explicit.extend(node.get_final_froms())
        return explicit
    verified_selects=set()
    def local_known(node):
        known=[]
        for item in getattr(node,'column_descriptions',()):
            entity=item.get('entity')
            if entity is not None:
                register(entity);selected=getattr(inspect(entity,raiseerr=False),'selectable',None)
                if isinstance(selected,FromClause):known.append(selected._deannotate())
        # ORM class joins/select_from targets carry their own mapper identity.
        for source in sources(node):
            if not isinstance(source,FromClause):
                inspected=inspect(source,raiseerr=False)
                if register(source) is not None:
                    selected=getattr(inspected,'selectable',None)
                    if isinstance(selected,FromClause):known.append(selected._deannotate())
            annotations=getattr(source,'_annotations',{})
            for key in ('parententity','parentmapper'):
                entity=annotations.get(key)
                if entity is None:continue
                register(entity);selected=getattr(inspect(entity,raiseerr=False),'selectable',None)
                if isinstance(selected,FromClause) and _same_source(source,selected):known.append(source._deannotate())
        # Relationship.any()/has() selects a literal and identifies its mapped
        # source through the actual predicate columns. Keep that proof local
        # to this SELECT; an outer mapper cannot certify a raw nested source.
        pending=[node];seen=set()
        while pending:
            child=pending.pop()
            if id(child) in seen:continue
            seen.add(id(child))
            if child is not node and isinstance(child,Select):continue
            if isinstance(child,ColumnClause) and isinstance(getattr(child,'table',None),FromClause):
                for key in ('parententity','parentmapper'):
                    entity=getattr(child,'_annotations',{}).get(key)
                    if entity is None:continue
                    register(entity);selected=getattr(inspect(entity,raiseerr=False),'selectable',None)
                    if isinstance(selected,FromClause) and _same_source(child.table,selected):known.append(selected._deannotate())
            pending.extend(child.get_children())
        return known
    def scoped(source,seen_sources,known):
        if not isinstance(source,FromClause):
            inspected=inspect(source,raiseerr=False)
            model=register(source)
            selected=getattr(inspected,'selectable',None)
            return model is not None and isinstance(selected,FromClause)
        raw=source._deannotate()
        element=source
        while isinstance(element,(Alias,Subquery)):element=element.element
        if isinstance(element,Select):
            verify_select(element,seen_sources)
            return True
        if any(_same_source(raw,candidate) for candidate in known):return True
        if isinstance(source,Join):return scoped(source.left,seen_sources,known) and scoped(source.right,seen_sources,known)
        if raw in associations:return True
        if isinstance(source,(Alias,Subquery)):
            if element in associations:return True
        return False
    def verify_select(node,ancestors=frozenset()):
        if id(node) in verified_selects:return
        if id(node) in ancestors:deny()
        known=local_known(node)
        for source in sources(node):
            if not scoped(source,set(ancestors)|{id(node)},known):deny()
        pending=[node];seen=set()
        while pending:
            child=pending.pop()
            if id(child) in seen:continue
            seen.add(id(child))
            if child is not node and isinstance(child,Select):continue
            if isinstance(child,ColumnClause) and isinstance(getattr(child,'table',None),FromClause):
                if not scoped(child.table,set(ancestors)|{id(node)},known):deny()
            pending.extend(child.get_children())
        verified_selects.add(id(node))
    for node in nodes:
        if isinstance(node,Select):verify_select(node)
