import pytest
from fastapi import HTTPException
from sqlalchemy import event
from app.apps.crm.models import CRMCompany
from app.apps.project_management.models import PMSProjectMember
from app.models.user import Permission,Role
from app.shared.follow_ups import options,followup_customer
from tests.test_record_360 import seeded
from tests.test_pms_workspaces import account,middleware_database
from tests.tenant_test_utils import assign_company


@pytest.mark.parametrize('permission',['crm_view','srm_view','pms_view'])
def test_batched_followup_options_match_native_customer_permissions(db,permission):
    _,_,_,_,project,_,_=seeded(db)
    user,_=account(db,permission+'-loading@test.com')
    grant=db.query(Permission).filter_by(name=permission).first() or Permission(name=permission,module='project_management' if permission=='pms_view' else permission.split('_')[0])
    user.role=Role(name='loading-'+permission,permissions=[grant]);assign_company(db,user,1)
    db.add(PMSProjectMember(project_id=project.id,user_id=user.id,role='Viewer'));db.commit()
    expected=[]
    for company in db.query(CRMCompany).filter_by(organization_id=1,deleted_at=None):
        try:followup_customer(db,company.id,user);expected.append(company.id)
        except HTTPException as error:assert error.status_code in (403,404)
    assert [item['id'] for item in options(db,user)['customers']]==sorted(expected)


def test_followup_options_do_not_query_each_customer(db):
    actor,*_=seeded(db)
    db.add_all([CRMCompany(organization_id=1,name=f'Loading customer {i}') for i in range(40)]);db.commit()
    queries=[]
    def count(*args):queries.append(args[2])
    engine=db.get_bind();event.listen(engine,'before_cursor_execute',count)
    try:
        result=options(db,actor)
        assert len(result['customers'])>=40
        assert len(queries)<25,'Options must use native scoped queries in batches'
    finally:event.remove(engine,'before_cursor_execute',count)
