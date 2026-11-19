"""Conservative metadata-only projection of guards for a single ORM table.

Unknown/complex query shapes keep the complete original option graph. No actor,
permission, ownership row, SQL result or allow/deny decision is cached here.
"""
from sqlalchemy import Column, Table
from sqlalchemy.sql.elements import ColumnClause, BindParameter
from sqlalchemy.sql import visitors
from sqlalchemy.sql.selectable import Select, Subquery, FromClause
from sqlalchemy.orm.util import LoaderCriteriaOption


def simple_mapper(statement):
    if isinstance(statement,Select) and len(statement._from_obj)==1:
        source=statement._from_obj[0]
        columns=statement._raw_columns
        count=columns[0] if len(columns)==1 else None
        args=tuple(count.clauses) if getattr(count,'name',None)=='count' else ()
        plain_count=len(args)==1 and isinstance(args[0],ColumnClause) and args[0].name=='*'
        canonical=(plain_count and isinstance(source,Subquery) and isinstance(source.element,Select)
                   and not any((statement._setup_joins,statement._independent_ctes,statement._prefixes,
                                statement._suffixes,statement._hints,statement._statement_hints,
                                statement._where_criteria,statement._order_by_clauses,statement._group_by_clauses,
                                statement._having_criteria,statement._distinct_on)))
        if canonical and all(value is None or isinstance(value,BindParameter) for value in (
                statement._limit_clause,statement._offset_clause,getattr(statement,'_fetch_clause',None))):
            mapper=simple_mapper(source.element)
            if mapper is None:return None
            for option in statement._with_options:
                if not isinstance(option,LoaderCriteriaOption) or option.entity is None:return None
                if option.entity is mapper and not _local_guard(option.where_criteria,mapper):return None
            return mapper
    if not isinstance(statement, Select) or statement._from_obj or statement._setup_joins or statement._independent_ctes:
        return None
    if statement._prefixes or statement._suffixes or statement._hints or statement._statement_hints:
        return None
    columns = statement._raw_columns
    entity = len(columns)==1 and isinstance(columns[0],Table)
    if entity:
        mapper=columns[0]._annotations.get('parentmapper')
    else:
        if any(isinstance(column,FromClause) for column in columns):return None
        mappers={node._annotations.get('parentmapper') for column in columns for node in visitors.iterate(column)}-{None}
        if len(mappers)!=1:return None
        mapper=next(iter(mappers))
    if mapper is None or mapper.inherits is not None or mapper.polymorphic_on is not None or len(tuple(mapper.self_and_descendants)) != 1:
        return None
    if entity and any(relationship.lazy in {False, 'joined', 'subquery', 'selectin', 'immediate'} for relationship in mapper.relationships):
        return None
    if entity and any(not isinstance(column, Column) for attribute in mapper.column_attrs for column in attribute.columns):
        return None
    table = mapper.local_table
    def local(expression, *, guard=False):
        for node in visitors.iterate(expression):
            if (isinstance(node, Select) and not guard) or 'Lambda' in type(node).__name__ or type(node).__name__ == 'TextClause':
                return False
            if not type(node).__module__.startswith('sqlalchemy.'):
                return False
            parent = node._annotations.get('parentmapper')
            if parent is not None and parent is not mapper:
                return False
            if not guard and getattr(node, 'table', table) is not table:
                return False
        return True
    for expression in (*(() if entity else columns), *statement._where_criteria, *statement._order_by_clauses,
                       *statement._group_by_clauses, *statement._having_criteria,
                       *statement._distinct_on, statement._limit_clause, statement._offset_clause,
                       getattr(statement, "_fetch_clause", None)):
        if expression is not None and not local(expression):return None
    # Existing company guards must not introduce another ORM entity at compile
    # time. Core subqueries in such a guard already carry their explicit rules.
    for option in statement._with_options:
        if not isinstance(option, LoaderCriteriaOption) or option.entity is None:
            return None
        if option.entity is mapper and not local(option.where_criteria, guard=True):
            return None
    return mapper


def projected_loader_options(statement, options, mapper=None):
    mapper = mapper or simple_mapper(statement)
    if mapper is None:return None
    selected = tuple(option for option in options if option.entity is mapper)
    if any(not _local_guard(option.where_criteria, mapper) for option in selected):
        return None
    return selected


def _local_guard(expression, mapper):
    for node in visitors.iterate(expression):
        if 'Lambda' in type(node).__name__ or type(node).__name__ == 'TextClause':return False
        if not type(node).__module__.startswith('sqlalchemy.'):return False
        parent=node._annotations.get('parentmapper')
        if parent is not None and parent is not mapper:return False
    return True


def simple_loader_options(statement, options):
    selected=projected_loader_options(statement,options)
    return options if selected is None else selected


from collections.abc import Mapping
from threading import RLock


class GuardPlan(Mapping):
    """Request-owned facade over immutable SQL templates, never over data rows.

    A single-table read constructs its own equivalent guard. Unknown/complex
    statements and private purposes materialize the original complete plan.
    """
    def __init__(self, models, full, single):
        self.models=frozenset(models)
        self._factory,self._single=full,single
        self._complete=None
        self._parts={}
        self._lock=RLock()

    def full(self):
        with self._lock:
            if self._complete is None:self._complete=self._factory()
            return self._complete

    def _part(self, model):
        with self._lock:
            if model not in self._parts:self._parts[model]=self._single(model)
            return self._parts[model]

    def __getitem__(self,model):
        if model not in self.models:raise KeyError(model)
        source=self._complete if self._complete is not None else self._part(model)
        return (self.full() if source is None else source)[0][model]

    def __contains__(self,model):
        try:self[model];return True
        except KeyError:return False

    def __iter__(self):return iter(self.full()[0])
    def __len__(self):return len(self.full()[0])

    def read_options(self,statement,project=True):
        if project:
            mapper=simple_mapper(statement)
            if mapper is not None and mapper.class_ in self.models:
                part=self._part(mapper.class_)
                if part is not None:
                    selected=projected_loader_options(statement,part[1],mapper)
                    if selected is not None:return selected
        return self.full()[1]
