"""Simple projections must produce exactly the original guarded SQL."""
import pytest
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import aliased, joinedload, with_loader_criteria
from app.db.loader_options import simple_loader_options
from app.db.base_class import Base
from app.branches.boundary import _read_guards
from app.models.user import User, UserSession, Permission
from app.models.employee import Employee
from app.access.models import AccessPolicy
from app.apps.srm.models import SRMProduct


def guards():
    models={m.local_table.name:m.class_ for m in Base.registry.mappers}
    return _read_guards(tuple(sorted(models.items())),1,1,1,(1,),False,False)[1]


def sql(statement):
    return str(statement.compile(dialect=postgresql.dialect(),compile_kwargs={"literal_binds":True}))


@pytest.mark.parametrize("model",[User,UserSession,Permission,Employee,AccessPolicy,SRMProduct])
def test_simple_table_sql_and_current_scope_match_complete_guard_graph(model):
    options=guards()
    query=select(model).where(model.id==7).order_by(model.id)
    projected=simple_loader_options(query,options)
    assert len(projected)<=1
    assert sql(query.options(*projected))==sql(query.options(*options))


@pytest.mark.parametrize("shape",["alias","join","subquery","eager","raw","from"])
def test_complex_or_opaque_shapes_keep_all_guards(shape):
    options=guards()
    query={
        "alias":lambda:select(aliased(User)),
        "join":lambda:select(User).join(Employee,Employee.user_id==User.id),
        "subquery":lambda:select(User).where(User.id.in_(select(Employee.user_id))),
        "eager":lambda:select(User).options(joinedload(User.role)),
        "raw":lambda:select(User).where(text("1=1")),
        "columns":lambda:select(User.id),
        "from":lambda:select(User).select_from(User),
    }[shape]()
    assert simple_loader_options(query,options) is options


def test_existing_guard_with_another_orm_entity_is_not_projected():
    options=guards()
    query=select(User).options(with_loader_criteria(User,User.id.in_(select(Employee.user_id))))
    assert simple_loader_options(query,options) is options


def test_implicit_mapped_expressions_and_boolean_joined_load_keep_all_guards():
    from sqlalchemy import Column,Integer,ForeignKey
    from sqlalchemy.orm import declarative_base,column_property,relationship
    Local=declarative_base()
    class Target(Local):
        __tablename__="projection_target"
        id=Column(Integer,primary_key=True)
    class ExpressionOwner(Local):
        __tablename__="projection_expression_owner"
        id=Column(Integer,primary_key=True)
        target=column_property(select(Target.id).limit(1).scalar_subquery())
    class JoinedOwner(Local):
        __tablename__="projection_joined_owner"
        id=Column(Integer,primary_key=True)
        target_id=Column(ForeignKey(Target.id))
        target=relationship(Target,lazy=False)
    options=(with_loader_criteria(Target,Target.id==9),)
    for model in (ExpressionOwner,JoinedOwner):
        assert simple_loader_options(select(model),options) is options


def test_independent_cte_and_nested_limit_keep_all_guards():
    options=guards()
    query=select(User).add_cte(select(Employee).cte())
    assert simple_loader_options(query,options) is options
    query=select(User).limit(select(Employee.id).limit(1).scalar_subquery())
    assert simple_loader_options(query,options) is options


@pytest.mark.parametrize("module,company,actor,administrative",[("srm",1,1,False),("srm",1,1,True),("hrms",2,2,False)])
def test_every_registered_simple_model_matches_full_company_and_branch_sql(module,company,actor,administrative):
    from app.core.tenant_boundary import _company_plan
    models={mapper.local_table.name:mapper.class_ for mapper in Base.registry.mappers}
    branch=_read_guards(tuple(sorted(models.items())),actor,company,1,(1,),False,False)[1]
    company_options=_company_plan(tuple(models.values()),company,actor,module,administrative,company)[1]
    optimized=0
    def signature(query):
        compiled=query.compile(dialect=postgresql.dialect())
        return str(compiled),{key:(type(value).__name__,repr(value)) for key,value in compiled.params.items()}
    for model in models.values():
        query=select(model)
        chosen_company=simple_loader_options(query,company_options)
        chosen_branch=simple_loader_options(query.options(*chosen_company),branch)
        if chosen_company is company_options and chosen_branch is branch:continue
        assert signature(query.options(*chosen_company,*chosen_branch))==signature(query.options(*company_options,*branch)),model.__tablename__
        optimized+=1
    assert optimized>100


def test_lazy_simple_read_and_count_never_construct_unrelated_plans():
    from sqlalchemy import func,literal_column
    from app.apps.crm.models import CRMLead
    from app.db.loader_options import GuardPlan
    from app.branches.boundary import _single_read_guard
    models={mapper.local_table.name:mapper.class_ for mapper in Base.registry.mappers}
    context=(tuple(sorted(models.items())),1,1,1,(1,),False,False,False)
    calls=[]
    def full():
        calls.append("full")
        return _read_guards(*context)
    plan=GuardPlan(models.values(),full,lambda model:_single_read_guard(*context,model))
    query=select(CRMLead).where(CRMLead.id>1)
    for statement in (query,select(func.count(literal_column('*'))).select_from(query.subquery())):
        chosen=plan.read_options(statement)
        assert len(chosen)==1
        assert sql(statement.options(*chosen))==sql(statement.options(*full()[1]))
    assert calls==["full","full"]  # Only the explicit oracle constructed a full plan.
    assert CRMLead in plan
    assert plan[CRMLead] is not None
    plan.read_options(select(User).join(Employee,Employee.user_id==User.id))
    assert calls==["full","full","full"]


@pytest.mark.parametrize("module,administrative",[("srm",False),("srm",True),("hrms",False)])
def test_lazy_company_and_branch_factories_match_full_sql_for_every_model(module,administrative):
    from app.core.tenant_boundary import _company_plan,_single_company_plan
    from app.branches.boundary import _single_read_guard
    from app.db.loader_options import GuardPlan
    from sqlalchemy import func,literal_column
    models={mapper.local_table.name:mapper.class_ for mapper in Base.registry.mappers}
    company_context=(tuple(models.values()),1,1,module,administrative,1)
    branch_context=(tuple(sorted(models.items())),1,1,1,(1,),False,False,False)
    company=GuardPlan(models.values(),lambda:_company_plan(*company_context),lambda model:_single_company_plan(*company_context,model))
    branch=GuardPlan(models.values(),lambda:_read_guards(*branch_context),lambda model:_single_read_guard(*branch_context,model))
    complete_company=_company_plan(*company_context)[1]
    complete_branch=_read_guards(*branch_context)[1]
    def signature(query):
        compiled=query.compile(dialect=postgresql.dialect())
        return str(compiled),{key:(type(value).__name__,repr(value)) for key,value in compiled.params.items()}
    for model in models.values():
        query=select(model)
        keys=[getattr(model,model.__mapper__.get_property_by_column(column).key) for column in model.__mapper__.primary_key]
        for statement in (query,select(*keys),select(func.count(literal_column('*'))).select_from(query.subquery())):
            own=company.read_options(statement)
            chosen=branch.read_options(statement.options(*own))
            assert signature(statement.options(*own,*chosen))==signature(statement.options(*complete_company,*complete_branch)),model.__tablename__
