from sqlalchemy import event
from app.models.company import Company,Branch
from app.apps.crm.models import CRMCompany
from app.branches.models import BranchOwnership
from app.branches.presentation import record_branch_name,prefetch_branch_names


def test_batch_branch_labels_keep_ownership_and_fallback_without_row_queries(db):
    if not db.get(Company,1):db.add(Company(id=1,name='Label company'))
    a=Branch(company_id=1,name='Approved owner',code='LABEL-A')
    b=Branch(company_id=1,name='Fallback owner',code='LABEL-B')
    db.add_all([a,b]);db.flush()
    rows=[CRMCompany(organization_id=1,name=f'Display {i}',branch_id=b.id) for i in range(20)]
    db.add_all(rows);db.flush()
    owners=[BranchOwnership(company_id=1,branch_id=a.id,resource_table='crm_companies',resource_key=str(row.id),source='display-loading-test') for row in rows[:-1]]
    db.add_all(owners);db.flush()
    expected=[record_branch_name(row) for row in rows]
    assert expected==[a.name]*19+[b.name]
    queries=[]
    def count(*args):queries.append(args[2])
    engine=db.get_bind();event.listen(engine,'before_cursor_execute',count)
    try:
        prefetch_branch_names(db,rows)
        assert [record_branch_name(row) for row in rows]==expected
        assert len(queries)<=2
    finally:event.remove(engine,'before_cursor_execute',count)
    owners[0].branch_id=b.id;db.flush()
    db.info['security_write_request']=True
    try:assert record_branch_name(rows[0])==b.name
    finally:db.info.pop('security_write_request',None)
