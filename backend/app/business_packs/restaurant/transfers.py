"""Move an existing open tab without touching its native source or money."""
from sqlalchemy.exc import IntegrityError
from .models import RestaurantServiceOrder as Order, RestaurantTable as Table
from . import service, tabs


def transfer(ident, data, db, actor, *, commit=True):
    # Both independent pack ceilings and native order rights apply. Capture
    # native facts before the first company-writer wait, not after waiting.
    installed = service.authority(db, actor, 'tables.manage', write=True)
    scope, epoch = tabs.writer(db, actor)
    if installed is not scope:
        service.fail('Restaurant scope changed')
    order = service.scoped(db, Order, scope).filter(Order.id == ident).populate_existing().with_for_update().first()
    if order is None:
        service.fail('Restaurant tab is unavailable',404)
    from .sources import private
    private(db,scope,Order,order.id)
    proof = service.order_source(db, actor, scope, order)
    replay = service.prior(db, actor, scope, 'tab.transfer', ident, data)
    if replay is not None:
        return replay
    if order.source_kind != 'unpaid_tab' or order.state != 'open' or order.revision != data.expected_revision:
        service.fail('Only the current open unpaid tab can move tables',409)
    if proof.get('billing', {}).get('kind') == 'split':
        service.fail('A tab with allocated split bills cannot move tables',409)
    if order.table_id is None or order.table_id == data.destination_table_id:
        service.fail('Choose a different destination for an existing seated tab',409)
    try:
        with db.begin_nested():
            # Lock in stable order. Native company writer also serializes all
            # supported table occupation/close/update commands.
            tables = {}
            for table_id in sorted((order.table_id, data.destination_table_id)):
                row = service.scoped(db, Table, scope).filter(Table.id == table_id).populate_existing().with_for_update().first()
                if row is None:
                    service.fail('Restaurant table is unavailable',404)
                private(db,scope,Table,row.id)
                tables[row.id] = row
            source, destination = tables[order.table_id], tables[data.destination_table_id]
            if (service.authority(db,actor,'tables.manage',write=True) is not scope
                    or tabs._native_epoch(db,actor,scope) != epoch):
                service.fail('Restaurant transfer authority changed while waiting; reload')
            if not destination.active or destination.revision != data.expected_destination_revision or service.occupied(db,scope,destination.id):
                service.fail('Destination table availability changed; reload',409)
            old_source = source.id
            order.table_id = destination.id
            order.revision += 1
            source.revision += 1
            destination.revision += 1
            db.flush()
            result = service.order_result(db,actor,scope,order)
            result['transfer'] = {'source_table': {'id':old_source,'name':source.name,'revision':source.revision},
                'destination_table': {'id':destination.id,'name':destination.name,'revision':destination.revision}}
            result = service.save_command(db,actor,scope,'tab.transfer',ident,data,result,order=order,table=destination)
    except IntegrityError:
        service.fail('Destination table became occupied; reload before moving',409)
    if commit:
        db.commit()
    return result
