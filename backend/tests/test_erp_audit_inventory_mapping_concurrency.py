"""Deterministic independent PostgreSQL transactions for product ownership."""
from concurrent.futures import ThreadPoolExecutor,TimeoutError
from threading import Event,local
from sqlalchemy import event
from fastapi import HTTPException
from starlette.requests import Request
from tests.test_power_runtime_postgres import durable_store
from app.apps.fam.api import router as routes
from app.apps.fam.schemas import InventoryIntegrationLinkPayload
from app.apps.fam.models import FAMStockItem,FAMInventoryIntegrationLink
from app.apps.srm.models import SRMProduct
from app.models.user import User
from test_identity_utils import own_workflow_records


def test_mapping_and_unlink_races_preserve_one_active_product_owner(durable_store):
    factory,_,actor_id,engine=durable_store
    request=Request({'type':'http','method':'POST','path':'/qa-mapping','headers':[]})
    with factory() as db:
        actor=db.get(User,actor_id);routes.bootstrap(db,actor)
        items=[FAMStockItem(company_id=101,sku='QA-RACE-'+str(i),item_name='Race '+str(i)) for i in range(2)]
        product=SRMProduct(organization_id=101,sku='QA-RACE',item_name='Race product',product_type='product',active=True)
        db.add_all([*items,product]);own_workflow_records(db,*items,product,company_id=101);db.commit()
        item_ids=[row.id for row in items];product_id=product.id
    locked=Event();release=Event();attempted=Event();state=local()
    def after_execute(conn,cursor,statement,parameters,context,executemany):
        if getattr(state,'hold',False) and 'srm_products' in statement and 'FOR UPDATE' in statement:
            state.hold=False;locked.set()
            assert release.wait(15),'Test coordinator did not release product lock'
    def before_execute(conn,cursor,statement,parameters,context,executemany):
        if getattr(state,'waiter',False) and 'srm_products' in statement and 'FOR UPDATE' in statement:
            attempted.set()
    event.listen(engine,'before_cursor_execute',before_execute)
    event.listen(engine,'after_cursor_execute',after_execute)
    def link(item_id,hold=False):
        state.hold=hold;state.waiter=not hold
        with factory() as db:
            try:
                result=routes.link_inventory_item(item_id,InventoryIntegrationLinkPayload(stock_item_id=item_id,target_module='srm',target_record_type='product',target_record_id=str(product_id)),request,db,db.get(User,actor_id))
                return 200,result['id']
            except HTTPException as error:
                db.rollback();return error.status_code,None
    def unlink(link_id,item_id):
        state.hold=True;state.waiter=False
        with factory() as db:
            return routes.unlink_inventory_sales_product(item_id,link_id,request,db,db.get(User,actor_id))
    def must_block(future):
        try:future.result(timeout=.25)
        except TimeoutError:return
        raise AssertionError('Competing writer did not block on the held product row')
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(link,item_ids[0],True)
            try:
                assert locked.wait(15),'First mapper did not acquire product lock'
                second=pool.submit(link,item_ids[1]);assert attempted.wait(15),'Competing mapper never attempted the product lock';must_block(second)
            finally:release.set()
            winner=first.result(timeout=15);loser=second.result(timeout=15)
            assert winner[0]==200 and loser[0]==409,(winner,loser)
            locked.clear();release.clear();attempted.clear()
            removal=pool.submit(unlink,winner[1],item_ids[0])
            try:
                assert locked.wait(15),'Unlink did not acquire product lock'
                replacement=pool.submit(link,item_ids[1]);assert attempted.wait(15),'Replacement mapper never attempted the product lock';must_block(replacement)
            finally:release.set()
            assert removal.result(timeout=15)['active'] is False
            moved=replacement.result(timeout=15);assert moved[0]==200,moved
            repeats=[pool.submit(link,item_ids[1]) for _ in range(2)]
            assert [future.result(timeout=15) for future in repeats]==[moved,moved]
        with factory() as db:
            links=db.query(FAMInventoryIntegrationLink).filter_by(company_id=101,target_module='srm',target_record_type='product',target_record_id=str(product_id)).all()
            assert [(row.stock_item_id,row.active) for row in sorted(links,key=lambda row:row.stock_item_id)]==[(item_ids[0],False),(item_ids[1],True)]
    finally:
        release.set();event.remove(engine,'after_cursor_execute',after_execute);event.remove(engine,'before_cursor_execute',before_execute)
