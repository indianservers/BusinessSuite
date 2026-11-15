"""Exclude immutable pack-owned sources from genuine legacy operational reads.

Native tenant/branch/field permissions remain mandatory. This is no CommonCore
realm and grants no access. Trusted Connection SQL is outside this layer and
needs explicit source-aware auditing (exports, jobs and projections included).
"""
import re
from fastapi import HTTPException
from sqlalchemy import event,exists,inspect,select
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import TextClause,ColumnClause,BindParameter,Null
from sqlalchemy.sql.selectable import FromClause,Select
from app.db.base_class import Base
from app.branches.catalog import key_expression,resource_key
from .models import PackRecordOwnership
from .runtime import SCHEMA_COLUMNS


def deny(message='Pack-owned operational records are unavailable in a legacy context'):
    raise HTTPException(403,message)


def installation(db,company_id):
    if type(company_id) is not int or company_id<=0:deny('A verified native company is required')
    from app.db.schema_columns import table_columns
    connection=db.connection()
    columns=table_columns(connection, SCHEMA_COLUMNS)
    present=set(columns)
    if not present:return False
    if present!=set(SCHEMA_COLUMNS) or any(not required<=columns[name] for name,required in SCHEMA_COLUMNS.items()):
        raise HTTPException(503,'Business Pack ownership installation is incomplete')
    table=PackRecordOwnership.__table__
    return bool(connection.scalar(select(exists().where(table.c.company_id==company_id))))


def install(db,actor,company_id):
    """Call only after fresh production resolution yielded a genuine None scope."""
    if db.info.get('business_pack_scope') is not None:deny('Legacy exclusion cannot replace an operational Business Pack scope')
    if not getattr(actor,'is_active',False) or getattr(actor,'organization_id',None)!=company_id:deny('Legacy actor/company does not match native authorization')
    if not installation(db,company_id):return lambda:None
    from app.models.user import User
    from app.models.company import Company
    from app.core.tenant_boundary import company_ids
    current=db.connection().execute(select(User.is_active,User.is_superuser).where(User.id==actor.id)).first()
    company=db.connection().scalar(select(Company.id).where(Company.id==company_id,Company.is_active.is_(True)))
    if not current or not current.is_active or company is None or (not current.is_superuser and company_id not in company_ids(db,actor)):
        deny('Fresh native actor/company authority is required')
    ownership=PackRecordOwnership.__table__
    models={mapper.class_:mapper.local_table for mapper in Base.registry.mappers if len(mapper.primary_key)>0}
    original_get,original_refresh=db.get,db.refresh
    bulk_names=('bulk_insert_mappings','bulk_update_mappings','bulk_save_objects')
    originals={name:getattr(db,name) for name in bulk_names}
    trusted_identity_load=False
    previous=db.info.get('business_pack_legacy_company',None)
    if previous is not None and previous!=company_id:deny('Legacy company cannot change inside a bound request')

    def anchored_tables():
        return set(db.connection().execute(select(ownership.c.resource_table).where(ownership.c.company_id==company_id).distinct()).scalars())

    def exclusion(table):
        return ~exists(select(1).where(ownership.c.resource_table==table.name,ownership.c.resource_key==key_expression(table))).correlate(table)

    def blocked(table,identity):
        if identity is None:return False
        keys=list(table.primary_key)
        values=[identity.get(k.key) for k in keys] if isinstance(identity,dict) else list(identity) if isinstance(identity,(tuple,list)) else [identity]
        if len(values)!=len(keys) or any(value is None for value in values):return False
        canonical=[]
        for column,value in zip(keys,values):
            try:kind=column.type.python_type
            except (AttributeError,NotImplementedError):kind=None
            if kind is int:
                try:
                    normalized=int(value)
                    if not isinstance(value,(str,int)) and value!=normalized:deny('Invalid native source identity')
                    value=normalized
                except (ValueError,TypeError,OverflowError):deny('Invalid native source identity')
            canonical.append(value)
        key=resource_key(table,{k.name:v for k,v in zip(keys,canonical)})
        return bool(db.connection().scalar(select(exists().where(ownership.c.resource_table==table.name,ownership.c.resource_key==key))))

    def validate_values(model,values,identity=None):
        table=inspect(model).local_table
        if table.name==ownership.name:deny('Legacy operational requests cannot alter pack ownership')
        if blocked(table,identity) or blocked(table,values):deny()
        # A new unowned child cannot re-expose a private native parent.
        for column in table.c:
            value=values.get(column.key)
            if value is None:continue
            for fk in column.foreign_keys:
                parent=fk.column.table
                if len(parent.primary_key)==1 and fk.column.primary_key and blocked(parent,value):deny('Legacy writes cannot reference a pack-private native source')

    def restrict(execution):
        for mapper in Base.registry.mappers:models.setdefault(mapper.class_,mapper.local_table)
        tables=anchored_tables()
        if not execution.is_orm_statement or isinstance(execution.statement,TextClause):
            statement=execution.statement
            if isinstance(statement,TextClause):
                sql=str(statement)
                if any(re.search(r'(?<![a-zA-Z0-9_])'+re.escape(name)+r'(?![a-zA-Z0-9_])',sql,re.I) for name in tables|{ownership.name}):deny('Raw legacy SQL over private-source tables requires an audited projection')
            elif any(getattr(node,'name',None) in tables|{ownership.name} for node in visitors.iterate(statement) if isinstance(node,FromClause)):
                deny('Core legacy SQL over private-source tables requires an audited projection')
            return
        for node in visitors.iterate(execution.statement):
            if isinstance(node,TextClause) or (isinstance(node,ColumnClause) and getattr(node,'is_literal',False)):
                if any(re.search(r'(?<![a-zA-Z0-9_])'+re.escape(name)+r'(?![a-zA-Z0-9_])',str(node),re.I) for name in tables):
                    deny('Embedded private-source SQL requires an audited legacy projection')
        if execution.is_update or execution.is_delete:
            if any(isinstance(node,Select) for node in visitors.iterate(execution.statement)):
                deny('Legacy bulk writes with source subqueries require an audited adapter')
        if execution.is_insert:
            table=getattr(execution.statement,'table',None)
            if table is not None and table.name in tables|{ownership.name}:deny('Use validated per-record legacy writes')
        if execution.is_update or execution.is_delete:
            table=getattr(execution.statement,'table',None)
            if table is not None:
                if table.name==ownership.name:deny()
                if execution.is_update and execution.bind_mapper is not None:
                    parameters=execution.parameters or {}
                    batch=parameters if isinstance(parameters,list) else [parameters]
                    for params in batch:
                        values=dict(params)
                        for key,expression in (getattr(execution.statement,'_values',None) or {}).items():
                            name=getattr(key,'key',key)
                            if isinstance(expression,BindParameter):
                                values[name]=params.get(expression.key,expression.value)
                            elif isinstance(expression,Null):values[name]=None
                            elif name in table.c and (table.c[name].foreign_keys or table.c[name].primary_key):
                                deny('Legacy source identity updates require literal verified references')
                        validate_values(execution.bind_mapper.class_,values)
                execution.statement=execution.statement.where(exclusion(table))
                execution.update_execution_options(synchronize_session=False)
        if execution.is_column_load:
            state=getattr(execution.load_options,'_refresh_state',None)
            if state is not None and blocked(state.mapper.local_table,state.identity):deny()
        # ORM raw FROM/scalar Core columns can escape loader criteria. Only the
        # affected private-source tables are rejected; unrelated Core is native.
        for node in visitors.iterate(execution.statement) if execution.is_select and not trusted_identity_load and not execution.is_column_load and not execution.is_relationship_load else ():
            table=getattr(node,'table',None)
            name=getattr(table,'name',None)
            while table is not None and name not in tables and (getattr(table,'original',None) is not None or getattr(table,'element',None) is not None):
                table=getattr(table,'original',None) if getattr(table,'original',None) is not None else table.element
                name=getattr(table,'name',None)
            if name in tables and not (node._annotations.get('parententity') or node._annotations.get('parentmapper')):
                deny('Raw private-source columns require an audited legacy projection')
        if execution.is_select:
            options=[with_loader_criteria(model,exclusion(table),include_aliases=True,propagate_to_loaders=False) for model,table in models.items() if table.name in tables]
            execution.statement=execution.statement.options(*options)

    def validate(session,*args):
        for mapper in Base.registry.mappers:models.setdefault(mapper.class_,mapper.local_table)
        for item in session.new|session.dirty|session.deleted:
            state=inspect(item);model=type(item)
            if model in models:
                validate_values(model,{column.key:getattr(item,column.key) for column in state.mapper.columns},state.identity)

    def scoped_get(model,identity,**kwargs):
        nonlocal trusted_identity_load
        mapper=inspect(model,raiseerr=False)
        if mapper is not None and blocked(mapper.local_table,identity):return None
        previous_load=trusted_identity_load;trusted_identity_load=True
        try:return original_get(model,identity,**kwargs)
        finally:trusted_identity_load=previous_load

    def scoped_refresh(item,*args,**kwargs):
        nonlocal trusted_identity_load
        if blocked(inspect(item).mapper.local_table,inspect(item).identity):deny()
        previous_load=trusted_identity_load;trusted_identity_load=True
        try:return original_refresh(item,*args,**kwargs)
        finally:trusted_identity_load=previous_load

    def mapping_wrapper(name):
        def call(model,mappings,*args,**kwargs):
            rows=list(mappings)
            for values in rows:validate_values(model,values)
            return originals[name](model,rows,*args,**kwargs)
        return call

    def save_objects(objects,*args,**kwargs):
        rows=list(objects)
        for row in rows:
            state=inspect(row)
            validate_values(type(row),{c.key:getattr(row,c.key) for c in state.mapper.columns},state.identity)
        return originals['bulk_save_objects'](rows,*args,**kwargs)

    for state in list(db.identity_map.all_states()):
        item=state.obj()
        if item is not None and blocked(state.mapper.local_table,state.identity):
            if item in db.dirty or item in db.deleted:deny()
            db.expire(item)
        elif item is not None:
            private=anchored_tables()
            relationships=[rel.key for rel in state.mapper.relationships if rel.mapper.local_table.name in private]
            if any(state.attrs[key].history.has_changes() for key in relationships):deny('Pending private-source relationships cannot enter a legacy context')
            if relationships:db.expire(item,relationships)
    db.get,db.refresh=scoped_get,scoped_refresh
    db.bulk_insert_mappings=mapping_wrapper('bulk_insert_mappings');db.bulk_update_mappings=mapping_wrapper('bulk_update_mappings');db.bulk_save_objects=save_objects
    db.info['business_pack_legacy_company']=company_id
    event.listen(db,'do_orm_execute',restrict);event.listen(db,'before_flush',validate)
    closed=False
    def cleanup():
        nonlocal closed
        if closed:return
        closed=True
        event.remove(db,'do_orm_execute',restrict);event.remove(db,'before_flush',validate)
        db.get,db.refresh=original_get,original_refresh
        for name,method in originals.items():setattr(db,name,method)
        if previous is None:db.info.pop('business_pack_legacy_company',None)
        else:db.info['business_pack_legacy_company']=previous
    return cleanup


def assert_branch_ownership_change(db,resource_table,resource_key,*,company_id=None,branch_id=None,deleting=False):
    """Public native Connection RPCs must precheck; migration107 is backstop."""
    from app.db.schema_columns import table_columns
    columns=table_columns(db.connection(), SCHEMA_COLUMNS)
    present=set(columns)
    if not present:return
    if present!=set(SCHEMA_COLUMNS) or any(not required<=columns[name] for name,required in SCHEMA_COLUMNS.items()):
        raise HTTPException(503,'Business Pack ownership installation is incomplete')
    table=PackRecordOwnership.__table__
    anchor=db.connection().execute(select(table.c.company_id,table.c.branch_id).where(
        table.c.resource_table==resource_table,table.c.resource_key==str(resource_key))).first()
    if anchor and (deleting or (company_id,branch_id)!=(anchor.company_id,anchor.branch_id)):
        deny('A pack-private source cannot be moved or declassified through branch administration')


def protect_branch_ownership(db,company_id):
    """ORM/Session control guard; durable107 additionally covers Connection SQL."""
    if not installation(db,company_id):return lambda:None
    from app.branches.models import BranchOwnership,BranchRecordShare
    table=BranchOwnership.__table__
    share=BranchRecordShare.__table__
    sidecars={table.name,share.name}
    def check(values,*,deleting=False):
        source=values.get('resource_table');key=values.get('resource_key')
        if source is not None and key is not None:
            assert_branch_ownership_change(db,source,key,company_id=values.get('company_id'),branch_id=values.get('branch_id'),deleting=deleting)
    def validate(session,*args):
        for item in session.new|session.dirty|session.deleted:
            if isinstance(item,(BranchOwnership,BranchRecordShare)):
                state=inspect(item)
                values={c.key:getattr(item,c.key) for c in state.mapper.columns}
                if isinstance(item,BranchRecordShare) and item in session.deleted:continue
                if isinstance(item,BranchOwnership) and state.identity and tuple(state.identity)!=(item.resource_table,item.resource_key):
                    check(dict(zip(('resource_table','resource_key'),state.identity)),deleting=True)
                check(values,deleting=item in session.deleted)
    def restrict(execution):
        statement=execution.statement
        if isinstance(statement,TextClause):
            if re.search(r'\b(?:update|delete\s+from|insert\s+into)\s+["\[]?(?:public\.)?suite_branch_ownership\b',str(statement),re.I):
                deny('Textual branch ownership mutations require an audited native source guard')
            return
        target=getattr(statement,'table',None)
        if target is None or target.name not in sidecars or not (execution.is_insert or execution.is_update or execution.is_delete):return
        is_share=target.name==share.name
        if is_share and execution.is_delete:return
        target_table=share if is_share else table
        supplied={getattr(key,'key',key):getattr(value,'value',None) for key,value in (getattr(statement,'_values',None) or {}).items()}
        parameters=execution.parameters or {}
        batch=parameters if isinstance(parameters,list) else [parameters]
        if execution.is_insert:
            if getattr(statement,'select',None) is not None:deny('Branch ownership INSERT SELECT requires an audited source guard')
            for values in batch:check({**supplied,**values})
            return
        # The native caller's exact WHERE remains authoritative. No user string
        # SQL is executed and no operational source is adopted from metadata.
        rows=db.connection().execute(select(target_table).where(*statement._where_criteria),parameters if isinstance(parameters,dict) else {}).mappings().all()
        for row in rows:
            if execution.is_delete:check(row,deleting=True)
            else:
                for values in batch:
                    changed={**row,**supplied,**values}
                    if not is_share and (changed['resource_table'],changed['resource_key'])!=(row['resource_table'],row['resource_key']):check(row,deleting=True)
                    check(changed)
    names=('bulk_insert_mappings','bulk_update_mappings','bulk_save_objects')
    original_bulk={name:getattr(db,name) for name in names}
    def mapping_guard(name):
        def call(model,rows,*args,**kwargs):
            rows=list(rows)
            if inspect(model).local_table.name in sidecars:
                for values in rows:
                    model_table=inspect(model).local_table
                    existing=None
                    if values.get('resource_table') is not None and values.get('resource_key') is not None:
                        existing=db.connection().execute(select(model_table).where(model_table.c.resource_table==values['resource_table'],model_table.c.resource_key==values['resource_key'])).mappings().first()
                    check({**(existing or {}),**values})
            return original_bulk[name](model,rows,*args,**kwargs)
        return call
    def object_guard(rows,*args,**kwargs):
        rows=list(rows)
        for item in rows:
            if isinstance(item,(BranchOwnership,BranchRecordShare)):
                state=inspect(item)
                if isinstance(item,BranchOwnership) and state.identity and tuple(state.identity)!=(item.resource_table,item.resource_key):check(dict(zip(('resource_table','resource_key'),state.identity)),deleting=True)
                check({c.key:getattr(item,c.key) for c in state.mapper.columns})
        return original_bulk['bulk_save_objects'](rows,*args,**kwargs)
    db.bulk_insert_mappings=mapping_guard('bulk_insert_mappings');db.bulk_update_mappings=mapping_guard('bulk_update_mappings');db.bulk_save_objects=object_guard
    event.listen(db,'before_flush',validate);event.listen(db,'do_orm_execute',restrict)
    closed=False
    def cleanup():
        nonlocal closed
        if closed:return
        closed=True
        event.remove(db,'before_flush',validate);event.remove(db,'do_orm_execute',restrict)
        for name,method in original_bulk.items():setattr(db,name,method)
    return cleanup
