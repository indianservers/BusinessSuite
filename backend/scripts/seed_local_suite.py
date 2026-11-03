"""Add a connected fictional dataset to loopback PostgreSQL only.

Run with venv/Scripts/python.exe scripts/seed_local_suite.py from backend.
Uses Core inserts to avoid ORM email/integration events. One transaction, an
advisory lock, and a database marker make retries safe. Existing data is kept.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select, text, func
from app.db.base import Base
from app.db.session import engine
from app.core.security import get_password_hash
from app.branches.catalog import SHARED, resource_key
from app.apps.power_apps.contracts import WorkflowDefinition

MARK = 'LOCAL-SUITE-20261103'
TODAY = date(2026, 11, 3)
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
MANIFEST = Path(__file__).resolve().parents[1] / 'backups/local_suite_manifest.json'


def main():
    if engine.url.host not in {'localhost', '127.0.0.1', '::1'}:
        raise RuntimeError('This script only writes to a loopback database.')
    engine.echo = False
    counts, ids = Counter(), defaultdict(list)
    tables = Base.metadata.tables
    with engine.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock(20261103)'))
        if db.execute(select(tables['departments'].c.id).where(tables['departments'].c.code == 'LS26-ENG')).first():
            print(json.dumps({'status': 'already_seeded', 'manifest': str(MANIFEST)}))
            return
        company = db.execute(text("SELECT id FROM companies ORDER BY id LIMIT 1")).scalar_one()
        branch = db.execute(text("SELECT id FROM branches WHERE company_id=:c AND name='Main Branch'"), {'c': company}).scalar_one()
        admin = db.execute(text("SELECT id FROM users WHERE email='admin@aihrms.com' AND is_superuser=true AND is_active=true")).scalar_one()
        role = db.execute(text("SELECT id FROM roles WHERE name='employee'")).scalar_one()
        accounting_branch = None

        def stamp(t, values):
            if t.name not in SHARED:
                db.execute(tables['suite_branch_ownership'].insert().values(resource_table=t.name, resource_key=resource_key(t, values), company_id=company, branch_id=branch, source=MARK))

        def add(table_name, **values):
            t = tables[table_name]
            for key, value in {'organization_id': company, 'company_id': company,
                               'branch_id': branch, 'created_by': admin,
                               'created_by_user_id': admin, 'created_at': NOW}.items():
                if key in t.c:
                    if key == 'branch_id' and any(f.target_fullname == 'fam_branches.id' for f in t.c.branch_id.foreign_keys):
                        value = accounting_branch
                    values.setdefault(key, value)
            unknown = set(values) - set(t.c.keys())
            if unknown:
                raise RuntimeError(f'{table_name}: unknown columns {unknown}')
            if 'id' not in t.c:
                db.execute(t.insert().values(**values))
                stamp(t, values)
                counts[table_name] += 1
                return None
            rid = db.execute(t.insert().values(**values).returning(t.c.id)).scalar_one()
            counts[table_name] += 1
            ids[table_name].append(rid)
            stamp(t, dict(values, id=rid))
            # Legacy HR/portal rows use the shared ownership registry for tenancy.
            if table_name not in {'users', 'common_people'} and 'company_id' not in t.c and 'organization_id' not in t.c:
                db.execute(tables['security_resource_ownership'].insert().values(resource_table=table_name, resource_id=rid, company_id=company))
            return rid

        accounting_branch = add('fam_branches', branch_code='LS26-MAIN', branch_name='Main Branch')
        db.execute(tables['suite_accounting_branch_map'].insert().values(accounting_branch_id=accounting_branch, company_id=company, branch_id=branch))
        departments, designations = [], []
        for code, name, title in [('ENG','Engineering','Software Engineer'),('SAL','Sales','Account Executive'),('OPS','Operations','Operations Analyst'),('HR','People & Culture','HR Specialist'),('FIN','Finance','Finance Analyst'),('CS','Customer Success','Customer Success Specialist')]:
            dep = add('departments', name=name, code=f'LS26-{code}', description=f'{MARK}: fictional operating team')
            departments.append(dep)
            designations.append(add('designations', name=title, code=f'LS26-{code}-01', department_id=dep, grade='L2', level=2))
        first = ['Ananya','Arjun','Priya','Rohan','Meera','Kabir','Aditi','Vikram','Neha','Kiran','Tara','Dev','Isha','Rahul','Maya','Sanjay','Nora','Nikhil','Diya','Varun']
        last = ['Rao','Mehta','Shah','Nair','Iyer','Patel','Gupta','Desai','Joshi','Kapoor','Sethi','Malhotra']
        employees, users = [], []
        password_hash = get_password_hash(secrets.token_urlsafe(36))
        cycle = add('appraisal_cycles', name='Local sample · Q4 2026', cycle_type='Quarterly', start_date=date(2026,10,1), end_date=date(2026,12,31), review_period_start=date(2026,10,1), review_period_end=date(2026,12,31), status='Active')
        category = add('helpdesk_categories', name='Local sample · IT & workplace', sla_hours=24, assigned_team='Operations')
        asset_category = add('asset_categories', name='Local sample · Workstations')
        courses = [add('learning_courses', code=f'LS26-LMS-{i+1}', title=title, description=f'{MARK}: sample learning curriculum', category='Professional Development', duration_hours=4+i, delivery_mode='Online') for i,title in enumerate(['Security awareness','Customer discovery','Project delivery essentials','Data analysis foundations','Workplace communication','Finance for teams','Product quality','Leadership essentials'])]
        leave_type = db.execute(text('SELECT id FROM leave_types ORDER BY id LIMIT 1')).scalar_one()
        for i in range(180):
            fn, ln = first[i%20], last[i//20]
            email = f'{fn.lower()}.{ln.lower()}.{i+1}@local-suite.example.com'
            uid = add('users', email=email, hashed_password=password_hash, role_id=role, is_active=True, is_superuser=False)
            users.append(uid)
            eid = add('employees', employee_id=f'LS26-{i+1:04}', user_id=uid, first_name=fn, last_name=ln, work_email=email, date_of_joining=TODAY-timedelta(days=60+i*3), department_id=departments[i%6], designation_id=designations[i%6], employment_type='Intern' if i>=156 else 'Full-time', worker_type='Intern' if i>=156 else 'Employee', status='Active', work_location='Hybrid' if i%3==0 else 'Office', probation_status='confirmed' if i<150 else 'on_probation', bio=f'{MARK}: fictional employee for local testing', present_city=['Bengaluru','Chennai','Hyderabad'][i%3], skills_tags=['Python, SQL','Sales, Negotiation','Operations, Excel'][i%3])
            employees.append(eid)
            add('common_people', user_id=uid, primary_email=email, first_name=fn, last_name=ln, display_name=f'{fn} {ln}', source_module='hrms', source_record_type='employee', source_record_id=eid, status='active')
            gross = Decimal(35000 + (i%15)*4500)
            add('employee_salaries', employee_id=eid, ctc=gross*12, basic=gross/2, hra=gross/5, effective_from=date(2026,4,1), is_active=True)
            for offset in range(65):
                day = TODAY-timedelta(days=offset)
                if day.weekday()>=5:
                    continue
                absent = (i+offset)%29==0
                checkin = datetime.combine(day,time(9,15 if (i+offset)%11==0 else 0),tzinfo=timezone.utc)
                add('attendances', employee_id=eid, attendance_date=day, check_in=None if absent else checkin, check_out=None if absent or offset==0 else checkin+timedelta(hours=8), total_hours=0 if absent else 8, status='Absent' if absent else 'Present', source='Manual', is_late=(i+offset)%11==0 and not absent, late_minutes=15 if (i+offset)%11==0 and not absent else 0, remarks=f'{MARK}: synthetic attendance')
            add('leave_requests', employee_id=eid, leave_type_id=leave_type, from_date=TODAY+timedelta(days=i%21+1), to_date=TODAY+timedelta(days=i%21+2), days_count=2, reason=f'{MARK}: planned personal leave', status=['Pending','Approved','Rejected'][i%3])
            add('expense_claims', employee_id=eid, claim_number=f'LS26-EXP-{i+1:04}', claim_type=['Travel','Meals','Internet'][i%3], expense_date=TODAY-timedelta(days=i%28), amount=Decimal(500+i*75), approved_amount=Decimal(500+i*75) if i%3==1 else None, description=f'{MARK}: customer visit or office expense', status=['Submitted','Approved','Pending'][i%3], submitted_by=uid)
            add('learning_assignments', course_id=courses[i%8], employee_id=eid, assigned_by=admin, due_date=TODAY+timedelta(days=i%20), status='Completed' if i%3==0 else 'Assigned', completed_at=NOW-timedelta(days=3) if i%3==0 else None, score=85 if i%3==0 else None)
            add('performance_goals', employee_id=eid, cycle_id=cycle, title=['Improve delivery predictability','Increase customer satisfaction','Complete skills certification'][i%3], target_date=date(2026,12,20), weightage=100, status='In Progress', target_value='100', achieved_value=str(20+i%70), set_by=admin)
            if i<72:
                add('helpdesk_tickets', ticket_number=f'LS26-HD-{i+1:04}', employee_id=eid, category_id=category, subject=['Laptop setup assistance','VPN connection issue','Access request','Payroll clarification'][i%4], description=f'{MARK}: sample support request with reproducible details.', priority=['Low','Medium','High'][i%3], status=['Open','In Progress','Resolved'][i%3], assigned_to=admin, resolution_due_at=NOW+timedelta(hours=24), resolved_at=NOW-timedelta(days=1) if i%3==2 else None)
                add('assets', asset_tag=f'LS26-ASSET-{i+1:04}', name=f'Business laptop {i+1:03}', category_id=asset_category, brand=['Lenovo','Dell','HP'][i%3], model='Business Pro 14', serial_number=f'LOCAL26-{i+1:06}', purchase_date=TODAY-timedelta(days=100), purchase_cost=65000, status='Available', condition='Good', location='Main Branch')
        for month in [9,10]:
            gross_total=sum(Decimal(35000+(i%15)*4500) for i in range(180))
            deductions=Decimal(180*2000)
            run=add('payroll_runs', month=month, year=2026, pay_period_start=date(2026,month,1), pay_period_end=date(2026,month+1,1)-timedelta(days=1), status='Draft', total_gross=gross_total, total_deductions=deductions, total_net=gross_total-deductions, remarks=f'{MARK}: sample draft payroll, not a statutory calculation')
            for i,eid in enumerate(employees):
                gross=Decimal(35000+(i%15)*4500)
                add('payroll_records', payroll_run_id=run, employee_id=eid, working_days=22, present_days=22, paid_days=22, basic=gross/2, hra=gross/5, other_allowances=gross*Decimal('.3'), gross_salary=gross, pf_employee=1800, professional_tax=200, total_deductions=2000, net_salary=gross-2000, status='Draft')
        for i,title in enumerate(['Software Engineer','Sales Executive','Finance Analyst','Operations Coordinator','Product Designer','Customer Success Associate']):
            job=add('jobs', title=title, code=f'LS26-JOB-{i+1}', department_id=departments[i%6], designation_id=designations[i%6], job_type='Full-time', location='Bengaluru', openings=3, status='Open', posted_date=TODAY-timedelta(days=10), closing_date=TODAY+timedelta(days=25), description=f'{MARK}: fictional vacancy', is_published=False)
            for j in range(12):
                add('candidates', job_id=job, first_name=first[j], last_name=last[i], email=f'candidate.{i}.{j}@local-suite.example.com', total_experience=2+j%6, expected_ctc=600000+j*50000, source=['Referral','Website','Job Portal'][j%3], status=['Applied','Screening','Interview','Offered'][j%4])

        workspace=add('pms_workspaces', name='Local sample · Business Delivery')
        for uid in [admin]+users[:36]:
            add('pms_workspace_members', workspace_id=workspace, user_id=uid, role='Admin' if uid==admin else 'Member')
        projects=[]
        task_titles=['Confirm stakeholder requirements','Design customer workflow','Implement core functionality','Review security permissions','Integrate customer data','Validate acceptance criteria','Prepare training materials','Complete release readiness','Improve mobile experience','Resolve pilot feedback']
        for i in range(36):
            client=add('pms_clients', name=f'Local sample customer {i+1:02}', company_name=f'Local sample customer {i+1:02} Pvt Ltd', email=f'client.{i+1}@local-suite.example.com')
            project=add('pms_projects', workspace_id=workspace, client_id=client, manager_user_id=admin, owner_user_id=admin, department_id=departments[i%6], name=f'{["Aurora","Cedar","Meridian","Prism","Nimbus","Atlas"][i%6]} · { ["Customer Portal","Operations Upgrade","Analytics Platform","Mobile Rollout","Service Launch","Cloud Migration"][i//6]}', project_key=f'LS26P{i+1:02}', description=f'{MARK}: connected project delivery scenario', status=['Active','Active','Planned','Completed','On Hold','Active'][i%6], priority=['High','Medium','Low'][i%3], health=['On Track','At Risk','On Track'][i%3], start_date=TODAY-timedelta(days=40), due_date=TODAY+timedelta(days=i*2-8), budget_amount=300000+i*25000, estimated_hours=240, progress_percent=100 if i%6==3 else 10+i%70)
            projects.append(project)
            for uid in [admin]+users[i%20:i%20+6]:
                add('pms_project_members', project_id=project, user_id=uid, role='Manager' if uid==admin else 'Member', allocation_percent=20)
            board=add('pms_boards', project_id=project, name='Delivery board', board_type='Kanban')
            statuses=[('Backlog','BACKLOG'),('To Do','TODO'),('In Progress','IN_PROGRESS'),('In Review','IN_REVIEW'),('Blocked','BLOCKED'),('Done','DONE')]
            columns=[add('pms_board_columns', board_id=board, name=s, status_key=k, position=j) for j,(s,k) in enumerate(statuses)]
            milestone=add('pms_milestones', project_id=project, owner_user_id=admin, name='Pilot release', due_date=TODAY+timedelta(days=14), status='In Progress', progress_percent=50)
            for j in range(32):
                status=statuses[j%6][0]
                task=add('pms_tasks', project_id=project, board_id=board, column_id=columns[j%6], milestone_id=milestone, assignee_user_id=users[(i+j)%36], reporter_user_id=admin, title=f'{task_titles[j%10]} · phase {j//10+1}', task_key=f'LS26P{i+1:02}-{j+1}', description=f'{MARK}: sample task with deliverable and acceptance review.', status=status, priority=['High','Medium','Low'][j%3], start_date=TODAY-timedelta(days=14), due_date=TODAY+timedelta(days=j-10), completed_at=NOW-timedelta(days=j%8) if status=='Done' else None, estimated_hours=8, actual_hours=8 if status=='Done' else 2, story_points=[2,3,5,8][j%4], position=j)
                add('pms_task_assignees', task_id=task, user_id=users[(i+j)%36])
                add('pms_time_logs', user_id=users[(i+j)%36], project_id=project, task_id=task, log_date=TODAY-timedelta(days=j%20), duration_minutes=120, description=f'{MARK}: delivery implementation', is_billable=True, approval_status='Pending')

        pipeline=db.execute(text('SELECT id FROM crm_pipelines WHERE organization_id=:c ORDER BY id LIMIT 1'),{'c':company}).scalar_one()
        stages=db.execute(text('SELECT id,probability,is_won,is_lost FROM crm_pipeline_stages WHERE pipeline_id=:p ORDER BY position'),{'p':pipeline}).mappings().all()
        warehouse=add('srm_warehouses', warehouse_code='LS26-MAIN', warehouse_name='Local sample · Main Warehouse', branch='Main Branch')
        products=[]
        for i in range(60):
            cost=Decimal(500+i*125)
            qty=Decimal(20+i*3)
            product=add('srm_products', sku=f'LS26-SKU-{i+1:04}', item_name=f'{["Business Laptop","Office Monitor","Network Router","Desk Accessory","Conference Device","Storage Drive"][i%6]} · model {i//6+1}', default_warehouse_id=warehouse, product_type='goods', category_name='Office & Technology', unit_code='NOS', gst_rate=18, purchase_rate=cost, sales_rate=cost*Decimal('1.4'), mrp=cost*Decimal('1.6'), current_quantity=qty, average_cost=cost, reorder_level=25, track_inventory=True)
            products.append((product,cost*Decimal('1.4')))
            add('srm_inventory_balances', product_id=product, warehouse_id=warehouse, quantity=qty, average_cost=cost)
            add('srm_inventory_movements', movement_number=f'LS26-OPEN-{i+1:04}', movement_type='opening', movement_date=TODAY-timedelta(days=45), product_id=product, warehouse_id=warehouse, quantity_in=qty, quantity_out=0, rate=cost, value=qty*cost, notes=f'{MARK}: sample opening stock')
        for i in range(120):
            brand=f'{["Aurora","Cedar","Meridian","Prism","Nimbus","Atlas","Lumen","Orbit","Summit","Maple"][i%10]} { ["Retail","Logistics","Health","Learning","Energy","Foods","Textiles","Media","Consulting","Systems","Travel","Industries"][i//10]}'
            account=add('crm_companies', name=brand+' Pvt Ltd', owner_user_id=admin, industry=['Retail','Services','Manufacturing'][i%3], city=['Bengaluru','Chennai','Hyderabad'][i%3], country='India', email=f'buyer.{i+1}@local-suite.example.com', account_type='Customer' if i%3==0 else 'Prospect', tags_text=MARK, annual_revenue=5000000+i*250000)
            contact=add('crm_contacts', company_id=account, company_name=brand, first_name=first[i%20], last_name=last[i%12], full_name=f'{first[i%20]} {last[i%12]}', email=f'contact.{i+1}@local-suite.example.com', owner_user_id=admin, job_title='Operations Director', lifecycle_stage='Customer' if i%3==0 else 'Lead', tags_text=MARK)
            stage=stages[i%len(stages)]
            amount=Decimal(50000+i*5000)
            deal=add('crm_deals', company_id=account, contact_id=contact, pipeline_id=pipeline, stage_id=stage['id'], name=f'{brand} · digital workspace', amount=amount, probability=stage['probability'], expected_revenue=amount*stage['probability']/100, status='Won' if stage['is_won'] else 'Lost' if stage['is_lost'] else 'Open', expected_close_date=TODAY+timedelta(days=i%45-10), owner_user_id=admin, tags_text=MARK, actual_close_date=TODAY-timedelta(days=i%20) if stage['is_won'] or stage['is_lost'] else None)
            for j in range(3):
                lead=add('crm_leads', first_name=first[(i+j)%20], last_name=last[i%12], full_name=f'{first[(i+j)%20]} {last[i%12]}', company_name=brand, email=f'lead.{i+1}.{j}@local-suite.example.com', owner_user_id=admin, status=['New','Contacted','Qualified'][j], source=['Website','Referral','Trade Show'][j], rating=['Hot','Warm','Cold'][j], lead_score=35+(i+j)%65, estimated_value=amount, next_follow_up_at=NOW+timedelta(days=i%12-3), tags_text=MARK)
                add('crm_activities', lead_id=lead, company_id=account, contact_id=contact, deal_id=deal, entity_type='lead', entity_id=lead, activity_type=['Call','Meeting','Task'][j], title=['Discovery call','Solution walkthrough','Send proposal'][j], subject=['Discovery call','Solution walkthrough','Send proposal'][j], description=f'{MARK}: follow up on customer requirements', status='Completed' if i%3==0 else 'Planned', due_date=NOW+timedelta(days=i%10-3), owner_user_id=admin)
            product,rate=products[i%60]
            subtotal=rate*10
            tax=subtotal*Decimal('.18')
            total=subtotal+tax
            order=add('srm_sales_orders', order_number=f'LS26-SO-{i+1:04}', title=f'{brand} · office technology rollout', crm_company_id=account, crm_contact_id=contact, crm_deal_id=deal, customer_id=account, assigned_user_id=admin, status='draft', subtotal=subtotal, tax_amount=tax, total_amount=total, expected_start_date=TODAY, expected_end_date=TODAY+timedelta(days=30))
            add('srm_sales_order_lines', sales_order_id=order, product_id=product, description='Business technology package', quantity=10, unit_price=rate, tax_amount=tax, line_total=total)
            add('srm_engagements', engagement_number=f'LS26-ENG-{i+1:04}', sales_order_id=order, customer_id=account, crm_deal_id=deal, pms_project_id=projects[i%36], assigned_user_id=admin, project_manager_user_id=admin, name=f'{brand} · delivery engagement', status='planned', billing_type='fixed', budget_amount=subtotal, planned_start_date=TODAY, planned_end_date=TODAY+timedelta(days=30))
            # These invoices are local sample business history; no send or handoff occurs.
            paid=total if i%3==0 else total/2 if i%3==1 else Decimal(0)
            invoice=add('srm_invoices', invoice_number=f'LS26-INV-{i+1:04}', sales_order_id=order, customer_id=account, status='paid' if i%3==0 else 'partially_paid' if i%3==1 else 'approved', issue_date=TODAY-timedelta(days=30+i%20), due_date=TODAY+timedelta(days=i%30-15), subtotal=subtotal, tax_amount=tax, total_amount=total, paid_amount=paid, balance_amount=total-paid)
            add('srm_invoice_lines', invoice_id=invoice, description='Business technology package', quantity=10, unit_price=rate, tax_amount=tax, line_total=total)
            if paid:
                receipt=add('srm_receipts', receipt_number=f'LS26-RCPT-{i+1:04}', customer_id=account, status='confirmed', receipt_date=TODAY-timedelta(days=i%15), payment_method='bank_transfer', amount=paid, unallocated_amount=0, reference_number=f'LOCAL-SAMPLE-{i+1}')
                add('srm_receipt_allocations', receipt_id=receipt, invoice_id=invoice, amount=paid, allocated_by=admin)
            add('fam_parties', party_type='customer', party_code=f'LS26-CUST-{i+1:04}', legal_name=brand+' Pvt Ltd', email=f'buyer.{i+1}@local-suite.example.com', payment_terms_days=30, credit_limit=500000)

        fy=db.execute(text('SELECT id FROM fam_financial_years WHERE company_id=:c AND is_current=true'),{'c':company}).scalar_one()
        voucher_type=db.execute(text("SELECT id FROM fam_voucher_types WHERE company_id=:c AND voucher_type_code='JV'"),{'c':company}).scalar_one()
        ledgers=dict(db.execute(text('SELECT ledger_code,id FROM fam_ledgers WHERE company_id=:c'),{'c':company}).all())
        # Keep sample balances on dedicated, branch-owned ledgers. Shared setup
        # ledgers have no branch stamp and are invisible in a selected branch.
        for code in ['CASH', 'SALES']:
            source=db.execute(select(tables['fam_ledgers']).where(tables['fam_ledgers'].c.id==ledgers[code])).mappings().one()
            ledgers[code]=add('fam_ledgers', ledger_code=f'LS26-{code}', ledger_name=f'Local sample · {source["ledger_name"]}', ledger_group_id=source['ledger_group_id'], nature=source['nature'], ledger_type=source['ledger_type'], system_ledger=False)
        for i in range(120):
            amount=Decimal(10000+i*750)
            voucher=add('fam_vouchers', financial_year_id=fy, voucher_type_id=voucher_type, voucher_number=f'LS26-JV-{i+1:04}', voucher_date=TODAY-timedelta(days=i%60), narration=f'{MARK}: sample cash sale, non-tax illustration', total_debit=amount, total_credit=amount, status='posted', posted_by=admin, posted_at=NOW, source_module='local_sample')
            for line,code,dr,cr in [(1,'CASH',amount,Decimal(0)),(2,'SALES',Decimal(0),amount)]:
                voucher_line=add('fam_voucher_lines', voucher_id=voucher, line_number=line, ledger_id=ledgers[code], debit_amount=dr, credit_amount=cr, narration=f'{MARK}: sample cash sale')
                add('fam_ledger_entries', financial_year_id=fy, voucher_id=voucher, voucher_line_id=voucher_line, voucher_number=f'LS26-JV-{i+1:04}', voucher_date=TODAY-timedelta(days=i%60), ledger_id=ledgers[code], debit_amount=dr, credit_amount=cr, running_balance=sum(Decimal(10000+j*750) for j in range(i+1))*(1 if code=='CASH' else -1), narration=f'{MARK}: sample cash sale', source_module='local_sample', posted_at=NOW)
                ledger=tables['fam_ledgers']
                db.execute(ledger.update().where(ledger.c.id==ledgers[code]).values(current_balance_dr=func.coalesce(ledger.c.current_balance_dr,0)+dr,current_balance_cr=func.coalesce(ledger.c.current_balance_cr,0)+cr))

        intern_courses=[add('intern_hub_courses', title=f'Local sample · {title}', description=f'{MARK}: intern learning path', level='Beginner', lessons=[{'id':'intro','title':'Introduction','content':'Review the team delivery process.'}], questions=[]) for title in ['Team onboarding','Python foundations','Quality assurance','Customer operations']]
        for i,eid in enumerate(employees[156:]):
            add('intern_hub_enrollments', employee_id=eid, course_id=intern_courses[i%4], completed_lessons=['intro'] if i%2==0 else [], score=90 if i%2==0 else None)
            for j in range(5):
                add('intern_hub_tasks', employee_id=eid, title=f'{task_titles[j]} · internship', description=f'{MARK}: supervised intern assignment', due_date=TODAY+timedelta(days=j+1))
                add('intern_hub_reports', employee_id=eid, report_date=TODAY-timedelta(days=j), work='Reviewed requirements and completed assigned implementation work.', learning='Practised testing, documentation and stakeholder communication.')
        for i in range(12):
            add('communication_email_templates', name=f'Local sample · { ["Welcome","Project update","Invoice reminder","Meeting follow-up"][i%4]} {i//4+1}', subject=f'Local sample: { ["Welcome to the workspace","Weekly delivery update","Payment due reminder","Next steps"][i%4]}', body_text='Hello {{name}}, please sign in to review your workspace update.', module_name=['crm','srm','project_management'][i%3], active=True)
            add('power_apps_resources', environment='development', application_id='automations', name=f'Local sample · { ["Customer onboarding","Purchase request","Equipment request","Delivery checklist"][i%4]} {i//4+1}', owner_user_id=admin, status='draft', definition=WorkflowDefinition().model_dump())
        for i in range(24):
            add('portal_users', email=f'portal.{i+1}@local-suite.example.com', display_name=f'Local sample customer {i+1}', portal_type='customer', status='inactive')
        for module in ['hrms','crm','srm','fam','project_management','communication','power_apps','inventory','interns_hub']:
            for i in range(4):
                add('notifications', user_id=admin, title=f'Local sample · {module} workspace update', message=f'{MARK}: sample records are available for review in Main Branch.', module=module, is_read=i%2==0, priority='normal', channels=['in_app'])
            conversation=add('ai_conversations', user_id=admin, module=module, title=f'Local sample · Explore {module}', status='active')
            add('ai_messages', conversation_id=conversation, role='user', content=f'Sample prompt: summarize the {module} records in this local workspace.')
        add('announcements', title='Local sample · November operations update', body='Review current delivery milestones, learning assignments and customer follow-ups. This is fictional local testing data.', audience='all', is_published=True, published_at=NOW)

        # Fail before committing if arithmetic or key relationships are inconsistent.
        checks={
            'invoice_arithmetic': "SELECT count(*) FROM srm_invoices WHERE invoice_number LIKE 'LS26-%' AND (subtotal+tax_amount-discount_amount<>total_amount OR paid_amount+balance_amount<>total_amount)",
            'voucher_balance': "SELECT count(*) FROM (SELECT v.id FROM fam_vouchers v JOIN fam_voucher_lines l ON l.voucher_id=v.id WHERE v.voucher_number LIKE 'LS26-%' GROUP BY v.id HAVING sum(l.debit_amount)<>sum(l.credit_amount)) q",
            'payroll_arithmetic': "SELECT count(*) FROM payroll_records r JOIN payroll_runs p ON p.id=r.payroll_run_id WHERE p.remarks LIKE 'LOCAL-SUITE-%' AND r.gross_salary-r.total_deductions<>r.net_salary",
        }
        for name,query in checks.items():
            if db.execute(text(query)).scalar_one():
                raise RuntimeError(f'Validation failed: {name}')
        manifest={'marker':MARK,'date':str(TODAY),'database':engine.url.database,'company_id':company,'branch_id':branch,'workspace_id':workspace,'counts':dict(counts),'total_records':sum(counts.values()),'ids':dict(ids),'validation':{key:'passed' for key in checks}}
    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in manifest.items() if key!='ids'},indent=2))


if __name__=='__main__':
    main()
