"""Add connected fictional CRM data. Re-running never duplicates this dataset.

Run from backend: venv/Scripts/python.exe scripts/seed_crm_showcase.py
Uses one database transaction; does not send messages or invoke integrations.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.base import Base  # noqa: F401
from app.db.session import SessionLocal, engine
from app.models.user import User
from app.apps.crm import models as m
from app.apps.srm.services.commercial import tenant

MARK = 'CRM-DEMO-20261026'
TODAY = date(2026, 10, 26)
NOW = datetime(2026, 10, 26, 10)
MANIFEST = Path(__file__).resolve().parents[1] / 'backups/crm_demo_manifest.json'


def main():
    engine.echo = False
    counts, ids = defaultdict(int), defaultdict(list)
    with SessionLocal() as db:
        admin = db.query(User).filter_by(email='admin@vyaparacrm.com').one()
        org = tenant(admin)
        existing = db.query(m.CRMCompany).filter_by(organization_id=org, tags_text=MARK).count()
        if existing:
            if existing != 18:
                raise RuntimeError('Demo dataset has changed; inspect before adding more records.')
            print(json.dumps({'status': 'already_seeded', 'accounts': existing}))
            return

        def add(cls, **values):
            columns = cls.__table__.columns
            for key, value in {'organization_id':org, 'created_by_user_id':admin.id}.items():
                if key in columns:
                    values.setdefault(key, value)
            row = cls(**values)
            db.add(row)
            db.flush()
            counts[cls.__tablename__] += 1
            ids[cls.__tablename__].append(row.id)
            return row

        pipeline = add(m.CRMPipeline, name='Enterprise Solutions', description='Demo: discovery through commercial approval and delivery handover', is_default=True)
        stage_names = [('Qualification',15),('Discovery',30),('Solution Demo',50),('Proposal',65),('Negotiation',85),('Closed Won',100),('Closed Lost',0)]
        stages = [add(m.CRMPipelineStage, pipeline_id=pipeline.id, name=n, probability=p, position=i, order_index=i, stage_type='won' if i==5 else 'lost' if i==6 else 'open', is_won=i==5, is_lost=i==6, color=['#64748b','#6366f1','#8b5cf6','#0891b2','#f59e0b','#10b981','#ef4444'][i]) for i,(n,p) in enumerate(stage_names)]
        products = [add(m.CRMProduct,name=n,sku=f'DEMO-SW-{i+1:03}',product_code=f'DEMO-SW-{i+1:03}',category='Business Software',description=f'Demo: {n}, annual subscription',unit_price=price,list_price=price,cost_price=price*Decimal('.4'),tax_rate=18) for i,(n,price) in enumerate([('Sales Workspace Professional',Decimal(24000)),('Customer Service Suite',Decimal(18000)),('Revenue Analytics',Decimal(36000)),('Partner Portal',Decimal(48000)),('Workflow Automation',Decimal(30000)),('Enterprise Integration Pack',Decimal(60000))])]
        services = [add(m.CRMService,service_code=f'DEMO-SVC-{i+1}',name=n,category='Professional Services',default_rate=rate,default_cost=rate*Decimal('.5'),tax_rate=18) for i,(n,rate) in enumerate([('Implementation & onboarding',Decimal(150000)),('Data migration',Decimal(90000)),('Sales team enablement',Decimal(45000))])]
        book = add(m.CRMPriceBook,name='Demo · India Enterprise FY2026',currency='INR',region='India',customer_segment='Enterprise',effective_from=TODAY.replace(month=4,day=1),effective_to=date(2027,3,31))
        for product in products:
            add(m.CRMPriceBookItem,price_book_id=book.id,item_type='product',product_id=product.id,unit_price=product.unit_price,cost_price=product.cost_price,tax_rate=18)
        for service in services:
            add(m.CRMPriceBookItem,price_book_id=book.id,item_type='service',service_id=service.id,unit_price=service.default_rate,cost_price=service.default_cost,tax_rate=18)
        brands=['Aster Retail','Meridian Logistics','Cedar Health','Prism Learning','Nimbus Manufacturing','Saffron Hospitality','Orbit Fintech','Evergreen Energy','Summit Foods','Lumen Media','Atlas Textiles','Horizon Travel','Bluebird Commerce','Vertex Engineering','Nova Labs','Cobalt Systems','Crescent Realty','Maple Consulting']
        industries=['Retail','Logistics','Healthcare','Education','Manufacturing','Hospitality']
        cities=['Bengaluru','Mumbai','Hyderabad','Pune','Chennai','Delhi']
        names=[('Ananya','Rao'),('Rohan','Mehta'),('Priya','Shah'),('Arjun','Nair'),('Meera','Iyer'),('Kabir','Sethi'),('Aditi','Gupta'),('Vikram','Patel'),('Neha','Joshi'),('Kiran','Desai'),('Tara','Kapoor'),('Dev','Malhotra')]
        owners=[admin]
        for email in ['manager@vyaparacrm.com','executive@vyaparacrm.com']:
            user=db.query(User).filter_by(email=email).first()
            if user and tenant(user)==org:
                owners.append(user)
        for i, brand in enumerate(brands):
            owner=owners[i%len(owners)]
            created=NOW-timedelta(days=75-i*3)
            company=add(m.CRMCompany,name=brand+' Pvt Ltd',industry=industries[i%6],website=f'https://customer{i+1}.example.com',email=f'procurement@customer{i+1}.example.com',city=cities[i%6],country='India',employee_count=80+i*45,annual_revenue=15000000+i*7500000,account_type='Customer' if i%7==5 else 'Prospect',owner_user_id=owner.id,tags_text=MARK,notes='Fictional CRM showcase account.',created_at=created)
            contacts=[]
            for j in range(2):
                first,last=names[(i*2+j)%len(names)]
                contacts.append(add(m.CRMContact,company_id=company.id,company_name=company.name,first_name=first,last_name=last,full_name=f'{first} {last}',email=f'{first.lower()}.{i+1}.{j}@example.com',job_title=['Head of Operations','Finance Director'][j],city=company.city,lifecycle_stage='Customer' if i%7==5 else 'Lead',source='Referral',owner_user_id=owner.id,tags_text=MARK,created_at=created))
            stage=stages[i%7]
            amount=Decimal(240000+i*65000)
            closed=i%7 in (5,6)
            deal=add(m.CRMDeal,name=f'{brand} · sales transformation',company_id=company.id,contact_id=contacts[0].id,pipeline_id=pipeline.id,stage_id=stage.id,amount=amount,expected_revenue=amount*stage.probability/100,probability=stage.probability,status='Won' if i%7==5 else 'Lost' if i%7==6 else 'Open',currency='INR',expected_close_date=TODAY+timedelta(days=i*3-8),actual_close_date=TODAY-timedelta(days=i) if closed else None,won_at=NOW-timedelta(days=i) if i%7==5 else None,lost_at=NOW-timedelta(days=i) if i%7==6 else None,closed_at=NOW-timedelta(days=i) if closed else None,loss_reason='Budget deferred to next quarter' if i%7==6 else None,lost_reason='Budget deferred to next quarter' if i%7==6 else None,win_reason='Best fit for multi-branch rollout' if i%7==5 else None,lead_source=['Website','Referral','Trade Show'][i%3],source=['Website','Referral','Trade Show'][i%3],next_follow_up_at=NOW+timedelta(days=i%6-2),last_activity_at=NOW-timedelta(days=i%9),owner_user_id=owner.id,tags_text=MARK,created_at=created)
            for j,contact in enumerate(contacts):
                add(m.CRMDealContact,deal_id=deal.id,contact_id=contact.id,role='Decision Maker' if j else 'Champion',is_primary=j==0)
            product=products[i%6]
            quantity=10+i
            subtotal=product.unit_price*quantity
            discount=(subtotal*Decimal('.1')).quantize(Decimal('.01'))
            tax=((subtotal-discount)*Decimal('.18')).quantize(Decimal('.01'))
            total=subtotal-discount+tax
            approval_status=['pending','approved','rejected'][i%3]
            quote=add(m.CRMQuotation,quote_number=f'DEMO-QT-2026-{i+1:03}',deal_id=deal.id,company_id=company.id,account_id=company.id,contact_id=contacts[0].id,owner_user_id=owner.id,owner_id=owner.id,issue_date=TODAY-timedelta(days=i%10),quote_date=TODAY-timedelta(days=i%10),expiry_date=TODAY+timedelta(days=30-i),valid_until=TODAY+timedelta(days=30-i),status='Submitted' if approval_status=='pending' else 'Approved' if approval_status=='approved' else 'Rejected',approval_status=approval_status,currency='INR',subtotal=subtotal,discount_amount=discount,discount_total=discount,tax_amount=tax,tax_total=tax,total_amount=total,grand_total=total,estimated_cost=product.cost_price*quantity,expected_margin=subtotal-discount-product.cost_price*quantity,margin_percentage=Decimal('55.56'),terms='Annual subscription. Net 30 payment terms. Implementation scoped separately.',notes=MARK,created_at=created)
            add(m.CRMQuotationItem,quotation_id=quote.id,quote_id=quote.id,product_id=product.id,item_type='product',name=product.name,quantity=quantity,unit_price=product.unit_price,discount_type='percentage',discount_value=10,discount_amount=discount,tax_rate=18,line_total=total,total_amount=total,estimated_cost=product.cost_price*quantity)
            add(m.CRMQuoteApproval,quote_id=quote.id,status=approval_status,reason='Review 10% annual commitment discount',submitted_by=owner.id,approver_user_id=admin.id,submitted_at=NOW-timedelta(days=i%5+1),decided_at=None if approval_status=='pending' else NOW-timedelta(hours=i),approved_by=admin.id if approval_status=='approved' else None,comments='Pending commercial review' if approval_status=='pending' else 'Annual commitment confirmed' if approval_status=='approved' else 'Revise discount and payment schedule')
            for j,subject in enumerate(['Confirm rollout scope','Review commercial proposal']):
                due=NOW+timedelta(days=(i+j)%8-3)
                add(m.CRMTask,title=f'{subject} · {brand}',description='Demo: agree next steps with the account champion.',company_id=company.id,contact_id=contacts[0].id,deal_id=deal.id,owner_user_id=owner.id,status='Done' if j and i%3==0 else 'To Do',priority='High' if i%3==0 else 'Medium',due_date=due,completed_at=NOW-timedelta(days=1) if j and i%3==0 else None)
                add(m.CRMActivity,subject=f'{subject} · {brand}',title=f'{subject} · {brand}',activity_type='Call' if j else 'Meeting',entity_type='deals',entity_id=deal.id,company_id=company.id,contact_id=contacts[0].id,deal_id=deal.id,owner_user_id=owner.id,status='Completed' if j else 'Pending',activity_date=due,due_date=due,body='Discuss adoption goals, procurement timeline, and next milestones.')
            start=NOW+timedelta(days=i%10,hours=i%4)
            add(m.CRMMeeting,title=f'{brand} · solution workshop',description='Demo workshop: workflow walkthrough and success criteria.',location='Video conference',company_id=company.id,contact_id=contacts[0].id,deal_id=deal.id,owner_user_id=owner.id,start_time=start,end_time=start+timedelta(hours=1),status='Scheduled',sync_status='not_synced')
            add(m.CRMNote,company_id=company.id,deal_id=deal.id,author_user_id=owner.id,body=f'{MARK}: {brand} needs a phased rollout across {3+i%5} branches. Operations sponsors the project; finance reviews annual pricing.',is_pinned=True)
            add(m.CRMTimelineEvent,record_type='deal',record_id=deal.id,event_type='note',title='Discovery workshop completed',description='Confirmed business goals and identified buying committee.',actor_user_id=owner.id,occurred_at=NOW-timedelta(days=i%8+1))
            if i<8:
                add(m.CRMTicket,ticket_number=f'DEMO-CS-{i+1:03}',subject=f'{brand} · onboarding access assistance',description='Demo support request: configure sales team permissions.',company_id=company.id,contact_id=contacts[0].id,owner_user_id=admin.id,status=['Open','In Progress','Resolved'][i%3],priority=['High','Medium','Low'][i%3],category='Onboarding',source='Email',due_date=NOW+timedelta(days=i%4-1),resolved_at=NOW-timedelta(days=1) if i%3==2 else None)
        for i in range(60):
            first,last=names[i%12]
            score=20+(i*7)%80
            add(m.CRMLead,first_name=first,last_name=last,full_name=f'{first} {last}',email=f'prospect.{i+1}@example.com',company_name=brands[i%18]+' Ventures',job_title=['Sales Director','Operations Manager','Founder'][i%3],industry=industries[i%6],city=cities[i%6],source=['Website','Referral','Trade Show','LinkedIn','Partner'][i%5],status=['New','Contacted','Qualified','Nurturing'][i%4],rating='Hot' if score>=70 else 'Warm' if score>=40 else 'Cold',lead_score=score,lead_score_label='Hot' if score>=70 else 'Warm' if score>=40 else 'Cold',lead_score_mode='manual',estimated_value=180000+i*15000,expected_close_date=TODAY+timedelta(days=i%45+5),last_contacted_at=NOW-timedelta(days=i%12),next_follow_up_at=NOW+timedelta(days=i%10-3),owner_user_id=owners[i%len(owners)].id,tags_text=MARK,notes='Fictional prospect for CRM demonstrations.',created_at=NOW-timedelta(days=i%60))
        for owner in owners:
            add(m.CRMSalesTarget,period_type='monthly',period_start=TODAY.replace(day=1),period_end=date(2026,10,31),target_owner_type='user',target_owner_id=owner.id,target_amount=2500000,currency='INR')
        for i,name in enumerate(['Enterprise Growth Webinar','Customer Referral Drive','Regional Industry Roundtable']):
            add(m.CRMCampaign,name='Demo · '+name,campaign_type=['Webinar','Referral','Event'][i],status='Active',start_date=TODAY-timedelta(days=14),end_date=TODAY+timedelta(days=21),budget_amount=75000+i*25000,actual_cost=30000+i*10000,expected_revenue=1200000+i*400000,description='Fictional campaign for demo reporting.',owner_user_id=admin.id)
        # Commit once: a failed insert rolls back the complete dataset.
        db.commit()
        manifest={'marker':MARK,'organization_id':org,'seed_date':str(TODAY),'counts':dict(counts),'ids':dict(ids),'total_records':sum(counts.values())}
        MANIFEST.parent.mkdir(parents=True,exist_ok=True)
        MANIFEST.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        print(json.dumps({'status':'seeded','total_records':manifest['total_records'],'counts':dict(counts)},indent=2))


if __name__=='__main__':
    main()
