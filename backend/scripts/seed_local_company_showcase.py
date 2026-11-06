"""Idempotent fictional company scenarios, restricted to loopback PostgreSQL.

Run from backend: venv/Scripts/python.exe scripts/seed_local_company_showcase.py
Core inserts avoid outbound integration events. Existing records are preserved.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.db.base import Base
from app.db.session import engine
from app.branches.catalog import SHARED, resource_key
from app.shared import master_data_models  # Register shared extensions.
from app.apps.crm.contact_identity import ContactIdentityLink

MARK = "LOCAL-COMPANIES-20261106"
VENDORS = [
    ("Atlas Office Systems", "Office equipment", "Washington", "DC", "20001", "Emma Carter", "Quarterly printer maintenance and office supplies"),
    ("Meridian Cloud Services", "Cloud infrastructure", "Austin", "TX", "78701", "Liam Bennett", "Managed hosting, backups and uptime reporting"),
    ("Cedar Packaging Solutions", "Packaging", "Chicago", "IL", "60601", "Olivia Brooks", "Recyclable cartons and protective packaging"),
    ("Northstar Freight Partners", "Logistics", "Seattle", "WA", "98101", "Noah Hughes", "Consolidated freight and last-mile delivery"),
    ("Prism Creative Studio", "Design services", "Portland", "OR", "97201", "Ava Foster", "Campaign design and product photography"),
    ("Summit Industrial Tools", "Industrial supplies", "Detroit", "MI", "48201", "Ethan Reed", "Preventive maintenance tools and safety equipment"),
    ("Harbor Facility Services", "Facility management", "Boston", "MA", "02108", "Sophia Hayes", "Office cleaning and scheduled facility inspections"),
    ("Evergreen Network Solutions", "IT networking", "Denver", "CO", "80202", "Lucas Morgan", "Network switches, Wi-Fi installation and support"),
    ("Bluebird Learning Partners", "Training", "Raleigh", "NC", "27601", "Mia Parker", "Team leadership and customer-service training"),
    ("Oakbridge Security Systems", "Security equipment", "Phoenix", "AZ", "85001", "James Ellis", "Access control equipment and maintenance"),
    ("Silverline Print Works", "Printing", "Dallas", "TX", "75201", "Isabella Grant", "Product brochures and exhibition materials"),
    ("Clearwater Business Travel", "Travel services", "Miami", "FL", "33101", "Henry Collins", "Business travel coordination and monthly reconciliation"),
    ("Redwood Software Labs", "Software services", "San Jose", "CA", "95113", "Amelia Ward", "Integration development and application support"),
    ("Brightway Catering Co", "Catering", "Atlanta", "GA", "30303", "Benjamin Stone", "Team lunches and client workshop catering"),
    ("Pinecrest Furniture Supply", "Office furniture", "Nashville", "TN", "37201", "Charlotte Ross", "Workstation furniture and ergonomic seating"),
    ("Beacon Research Partners", "Research services", "Philadelphia", "PA", "19103", "Daniel Price", "Customer interviews and market research reports"),
]


# 120 distinct fictional companies with reserved example domains / 555 numbers.
VENDORS = [
    (f"{['Aster','Lumen','Orion','Nimbus','Maple','Zenith','Coral','Ember','Sterling','Willow','Horizon','Solstice'][i % 12]} {['Retail','Healthcare','Education','Energy','Manufacturing','Foods','Textiles','Media','Consulting','Technology'][i // 12]} Group", *VENDORS[i % len(VENDORS)][1:])
    for i in range(120)
]

def main():
    if engine.url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Partner seed is restricted to loopback databases.")
    engine.echo = False
    tables = Base.metadata.tables
    now = datetime.now(timezone.utc)
    created, existing = [], []
    with engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(20261106)"))
        branch = db.execute(text("SELECT id, company_id FROM branches WHERE name='QA CRUD Branch API 20261026' ORDER BY id LIMIT 1")).mappings().one()
        company, branch_id = branch["company_id"], branch["id"]
        admin = db.execute(text("SELECT id FROM users WHERE email='admin@aihrms.com' AND is_superuser AND is_active")).scalar_one()

        def add(table_name, **values):
            table = tables[table_name]
            ident = db.execute(table.insert().values(**values).returning(table.c.id)).scalar_one()
            if table_name not in SHARED:
                db.execute(tables["suite_branch_ownership"].insert().values(resource_table=table_name, resource_key=resource_key(table, dict(values, id=ident)), company_id=company, branch_id=branch_id, source=MARK))
            return ident

        for i, (name, industry, city, state, postal, person, service) in enumerate(VENDORS):
            slug = name.lower().replace(" ", "-")
            email = f"accounts@{slug}.example.com"
            found = db.execute(select(tables["crm_companies"].c.id).where(tables["crm_companies"].c.organization_id == company, tables["crm_companies"].c.email == email)).scalar_one_or_none()
            if found:
                existing.append(found)
                continue
            status = "Active"
            phone = f"202555{i+400:04d}"
            notes = f"{MARK}: Fictional local demonstration. {service}. Reserved example email and 555 test number; no real recipient."
            common = dict(organization_id=company, branch_id=branch_id, owner_user_id=admin, status=status, created_by_user_id=admin, created_at=now - timedelta(days=i%14), updated_at=now, tags_text=f"{MARK}, Partner, {industry}", notes=notes, city=city, state=state, country="United States", address=f"{100+i} Commerce Avenue", phone=phone, phone_country_code="+1")
            account = add("crm_companies", **common, name=name, email=email, website=f"https://{slug}.example.com", industry=industry, account_type="Partner", employee_count=15+i*7)
            identity = add("crm_contacts", **common, full_name=name, first_name=name, company_id=account, company_name=name, email=email, lifecycle_stage="Partner", source="Local company sample", job_title="Business account", next_follow_up_at=now+timedelta(days=i%5-2))
            first, last = person.split(" ", 1)
            contact = add("crm_contacts", **common, full_name=person, first_name=first, last_name=last, company_id=account, company_name=name, email=f"{first.lower()}.{last.lower()}@{slug}.example.com", lifecycle_stage="Partner", source="Local company sample", job_title="Account Manager", next_follow_up_at=now+timedelta(days=i%5-2))
            add("suite_contact_identity_links", organization_id=company, contact_id=identity, account_id=account)
            db.execute(tables["suite_company_master_details"].insert().values(account_id=account, organization_id=company, legal_name=f"{name} LLC", trade_name=name, business_type="Limited Liability Company", addresses=[dict(type="Office", line1=f"{100+i} Commerce Avenue", city=city, state=state, country="United States", postalCode=postal)], tax_registrations=[], primary_contact_id=contact, version=1))
            db.execute(tables["suite_company_contact_links"].insert().values(account_id=account, contact_id=contact, organization_id=company, relationship="Partner account manager"))
            add("suite_business_relationships", organization_id=company, account_id=account, role="Partner", status=status, category=industry, payment_terms=["Net 30", "Net 45", "Due on receipt", "50% advance, balance on delivery"][i%4], follow_up_at=now+timedelta(days=i%5-2), notes=service)
            for owner in [dict(account_id=account), dict(contact_id=identity), dict(contact_id=contact)]:
                for kind, value in [("email", email if "contact_id" not in owner or owner["contact_id"] == identity else f"{first.lower()}.{last.lower()}@{slug}.example.com"), ("phone", phone)]:
                    add("suite_contact_channels", organization_id=company, **owner, kind=kind, label="Work", value=value, normalized_value=value if kind=="email" else f"+1{phone}", country_code="+1" if kind=="phone" else None, is_primary=True, whatsapp=kind=="phone", verification_status="unverified", notes="Fictional local test destination")
            created.append(dict(company_id=account, contact_id=contact, identity_id=identity, name=name))
        # Extension tables without an id still require branch ownership entries.
        seeded_ids = existing + [row["company_id"] for row in created]
        for name in ["suite_company_master_details", "suite_company_contact_links"]:
            table = tables[name]
            if name not in SHARED:
                for values in db.execute(select(table).where(table.c.account_id.in_(seeded_ids))).mappings():
                    db.execute(pg_insert(tables["suite_branch_ownership"]).values(resource_table=name, resource_key=resource_key(table, values), company_id=company, branch_id=branch_id, source=MARK).on_conflict_do_nothing())
    print(json.dumps(dict(marker=MARK, created=created, existing=existing), indent=2))


if __name__ == "__main__":
    main()
