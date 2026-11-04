"""Scoped relationship loads must stay isolated without duplicating guard trees."""
from contextlib import ExitStack
import pytest
from sqlalchemy import event
from sqlalchemy.orm import selectinload
from app.access.scope import install_scope
from app.core.tenant_boundary import install
from app.branches.boundary import install as install_branch
from app.branches.service import BranchContext
from app.branches.models import BranchOwnership
from app.branches.catalog import resource_key
from app.apps.project_management.models import PMSTask, PMSTaskAssignee
from tests.test_company_security_boundary import tenants


@pytest.mark.parametrize('central',[False,True])
def test_eager_relationship_guards_are_unique_and_hide_foreign_parents(db,tenants,central):
    actor,foreign=tenants['users'][:2]
    own_task,foreign_task=tenants['tasks']
    own_id,foreign_id=actor.id,foreign.id
    task_id=own_task.id
    branches=tenants['branches']
    assignments=[PMSTaskAssignee(task_id=task_id,user_id=own_id),
                 PMSTaskAssignee(task_id=foreign_task.id,user_id=foreign_id),
                 PMSTaskAssignee(task_id=task_id,user_id=foreign_id)]
    db.add_all(assignments);db.flush()
    for index,row in enumerate(assignments):
        company=2 if index==1 else 1
        db.add(BranchOwnership(company_id=company,branch_id=branches[company-1].id,
            resource_table=row.__tablename__,resource_key=resource_key(row.__table__,{'task_id':row.task_id,'user_id':row.user_id}),source='query-load-regression'))
    db.commit()
    branch_id=branches[0].id
    actor.organization_id=1
    actor._suite_current_module='project_management'
    observed=[]
    with ExitStack() as cleanup:
        if central:
            cleanup.callback(install_scope(db,actor,1,{'project_management':{'enabled':True,'scope':'organization','actions':['view'],'permissions':['pms_view']}}))
        cleanup.callback(install(db,actor,1))
        cleanup.callback(install_branch(db,actor,BranchContext(1,branch_id,frozenset([branch_id]),frozenset([branch_id]),False,False,False)))
        def capture(execution):
            if execution.is_relationship_load:
                options=getattr(execution.statement,'_with_options',())
                observed.append((len(options),len({id(option) for option in options})))
        event.listen(db,'do_orm_execute',capture)
        cleanup.callback(event.remove,db,'do_orm_execute',capture)
        db.expire_all()
        rows=db.query(PMSTask).options(selectinload(PMSTask.assignments)).all()
        assert [row.id for row in rows]==[task_id]
        assert [item.user_id for item in rows[0].assignments]==[own_id]
        assert observed and all(total==unique for total,unique in observed)
