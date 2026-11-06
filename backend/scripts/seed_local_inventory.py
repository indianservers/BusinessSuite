"""Seed 120 sample inventory products in the local suite, preserving existing rows."""
import sys
from pathlib import Path
from datetime import date
from decimal import Decimal
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select, text, func
from app.db.base import Base
from app.db.session import engine
from app.branches.catalog import resource_key, SHARED

MARK = 'LOCAL-INV-20261106'
def main():
    if engine.url.host not in {'localhost','127.0.0.1','::1'}:
        raise RuntimeError('Only loopback databases are allowed.')
    engine.echo=False
    tables=Base.metadata.tables
    with engine.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock(20261106)'))
        company=db.execute(text('SELECT id FROM companies ORDER BY id LIMIT 1')).scalar_one()
        branch=db.execute(text("SELECT id FROM branches WHERE company_id=:c AND name='Main Branch'"),{'c':company}).scalar_one()
        admin=db.execute(text('SELECT id FROM users WHERE is_superuser=true AND is_active=true ORDER BY id LIMIT 1')).scalar_one()
        def add(name, **values):
            t=tables[name]
            if 'organization_id' in t.c: values.setdefault('organization_id',company)
            if 'created_by' in t.c: values.setdefault('created_by',admin)
            rid=db.execute(t.insert().values(**values).returning(t.c.id)).scalar_one()
            if name not in SHARED:
                db.execute(tables['suite_branch_ownership'].insert().values(resource_table=name,resource_key=resource_key(t,dict(values,id=rid)),company_id=company,branch_id=branch,source=MARK))
            return rid
        warehouse=db.execute(text('SELECT id FROM srm_warehouses WHERE organization_id=:c ORDER BY id LIMIT 1'),{'c':company}).scalar_one()
        categories=[('Computers',['Business Laptop','Mini Desktop','Workstation','Chromebook','Tablet','All-in-One PC'],28000),('Accessories',['Wireless Mouse','Mechanical Keyboard','USB-C Hub','Laptop Stand','Webcam','Headset'],650),('Networking',['Wi-Fi Router','Network Switch','Access Point','Ethernet Cable','USB Wi-Fi Adapter','Firewall Appliance'],1200),('Office Supplies',['A4 Paper Pack','Notebook Set','Ballpoint Pen Box','Desk Organizer','Document Folder','Whiteboard Marker Set'],120),('Storage',['Portable SSD','External Hard Drive','USB Flash Drive','Memory Card','NAS Drive','SSD Enclosure'],900),('Office Equipment',['Office Chair','Standing Desk','Monitor Arm','LED Desk Lamp','Paper Shredder','Label Printer'],1800)]
        added=0
        for i in range(120):
            sku=f'LOCAL-INV-{i+1:04d}'
            if db.execute(select(tables['srm_products'].c.id).where(tables['srm_products'].c.organization_id==company,tables['srm_products'].c.sku==sku)).first(): continue
            cat,names,base=categories[i//20]
            cost=Decimal(base+(i%20)*125)
            qty=Decimal(0 if i%19==0 else 5 if i%11==0 else 25+(i*7)%180)
            pid=add('srm_products',sku=sku,item_name=f'{names[i%6]} - { ["Essential","Pro","Plus","Premium"][i%4]} {i+1:03d}',description=f'{MARK}: fictional local inventory sample',default_warehouse_id=warehouse,product_type='goods',category_name=cat,unit_code='NOS',gst_rate=18,purchase_rate=cost,sales_rate=cost*Decimal('1.35'),mrp=cost*Decimal('1.5'),current_quantity=qty,average_cost=cost,reorder_level=15,min_stock=10,max_stock=250,track_inventory=True)
            add('srm_inventory_balances',product_id=pid,warehouse_id=warehouse,quantity=qty,average_cost=cost)
            add('srm_inventory_movements',movement_number=f'{MARK}-{i+1:04d}',movement_type='opening',movement_date=date(2026,11,6),product_id=pid,warehouse_id=warehouse,quantity_in=qty,quantity_out=0,rate=cost,value=qty*cost,notes=f'{MARK}: sample opening balance')
            added+=1
        total=db.execute(select(func.count()).select_from(tables['srm_products'])).scalar_one()
        print(f'Added {added} products; total inventory products: {total}; branch: {branch}')
if __name__=='__main__': main()
