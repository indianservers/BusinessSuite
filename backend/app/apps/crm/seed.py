from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.apps.crm.models import (
    CRMActivity,
    CRMCompany,
    CRMContact,
    CRMDeal,
    CRMLead,
    CRMOwner,
    CRMPipeline,
    CRMPipelineStage,
    CRMProduct,
    CRMQuotation,
    CRMTask,
    CRMTeam,
    CRMTerritory,
)
from app.models.user import User


PIPELINE_STAGES = [
    ("Prospecting", 10),
    ("Qualification", 25),
    ("Needs Analysis", 40),
    ("Proposal Sent", 55),
    ("Negotiation", 70),
    ("Contract Sent", 85),
    ("Won", 100),
    ("Lost", 0),
]


def seed_crm_demo_data(db: Session, organization_id: int = 1) -> None:
    if db.query(CRMLead).filter(CRMLead.organization_id == organization_id).first():
        return

    admin = db.query(User).filter(User.email == "admin@vyaparacrm.com").first() or db.query(User).first()
    admin_id = admin.id if admin else None

    territory = CRMTerritory(
        organization_id=organization_id,
        owner_user_id=admin_id,
        name="India South",
        code="IN-S",
        country="India",
        state="Karnataka",
        city="Bengaluru",
        status="Active",
        created_by_user_id=admin_id,
        updated_by_user_id=admin_id,
    )
    db.add(territory)
    db.flush()

    team = CRMTeam(
        organization_id=organization_id,
        owner_user_id=admin_id,
        name="Enterprise Sales",
        team_type="Sales",
        status="Active",
        created_by_user_id=admin_id,
        updated_by_user_id=admin_id,
    )
    db.add(team)
    db.flush()

    owners = [
        CRMOwner(organization_id=organization_id, user_id=admin_id, team_id=team.id, territory_id=territory.id, full_name="Ananya Rao", email="ananya@vyaparacrm.com", role="Sales Manager", status="Active"),
        CRMOwner(organization_id=organization_id, team_id=team.id, territory_id=territory.id, full_name="Karan Shah", email="karan@vyaparacrm.com", role="Sales Executive", status="Active"),
        CRMOwner(organization_id=organization_id, team_id=team.id, territory_id=territory.id, full_name="Meera Iyer", email="meera@vyaparacrm.com", role="Sales Executive", status="Active"),
    ]
    for owner in owners:
        owner.created_by_user_id = admin_id
        owner.updated_by_user_id = admin_id
        db.add(owner)

    pipeline = CRMPipeline(
        organization_id=organization_id,
        name="Default Sales Pipeline",
        description="Standard CRM sales flow",
        is_default=True,
        created_by_user_id=admin_id,
        updated_by_user_id=admin_id,
    )
    db.add(pipeline)
    db.flush()

    stage_map: dict[str, CRMPipelineStage] = {}
    for index, (name, probability) in enumerate(PIPELINE_STAGES):
        stage = CRMPipelineStage(
            organization_id=organization_id,
            pipeline_id=pipeline.id,
            name=name,
            probability=probability,
            position=index,
            is_won=name == "Won",
            is_lost=name == "Lost",
            created_by_user_id=admin_id,
            updated_by_user_id=admin_id,
        )
        db.add(stage)
        db.flush()
        stage_map[name] = stage

    companies = [
        CRMCompany(organization_id=organization_id, owner_user_id=admin_id, name="Apex Digital Solutions", industry="Software Services", email="hello@apexdigital.in", city="Bengaluru", account_type="Prospect", status="Active", annual_revenue=24000000),
        CRMCompany(organization_id=organization_id, owner_user_id=admin_id, name="GreenField Realty", industry="Real Estate", email="hello@greenfield.example", city="Hyderabad", account_type="Customer", status="Active", annual_revenue=18000000),
        CRMCompany(organization_id=organization_id, owner_user_id=admin_id, name="Nova Manufacturing", industry="Manufacturing", email="hello@novamfg.example", city="Chennai", account_type="Customer", status="Active", annual_revenue=65000000),
    ]
    for company in companies:
        company.created_by_user_id = admin_id
        company.updated_by_user_id = admin_id
        db.add(company)
    db.flush()

    company_map = {company.name: company for company in companies}
    leads = [
        ("Rahul", "Mehta", "Apex Digital Solutions", "rahul@apexdigital.in", "Website", "Qualified", "Hot", 850000),
        ("Priya", "Nair", "GreenField Realty", "priya@greenfield.example", "Referral", "Contacted", "Warm", 420000),
        ("Arjun", "Reddy", "Nova Manufacturing", "arjun@novamfg.example", "Partner", "Qualified", "Hot", 1200000),
    ]
    for first, last, company, email, source, lead_status, rating, value in leads:
        db.add(
            CRMLead(
                organization_id=organization_id,
                owner_user_id=admin_id,
                first_name=first,
                last_name=last,
                full_name=f"{first} {last}",
                email=email,
                company_name=company,
                source=source,
                status=lead_status,
                rating=rating,
                estimated_value=value,
                industry=company_map[company].industry,
                expected_close_date=date(2026, 6, 15),
                next_follow_up_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
                created_by_user_id=admin_id,
                updated_by_user_id=admin_id,
            )
        )

    contacts = [
        CRMContact(organization_id=organization_id, owner_user_id=admin_id, company_id=company_map["Apex Digital Solutions"].id, first_name="Rahul", last_name="Mehta", full_name="Rahul Mehta", email="rahul@apexdigital.in", lifecycle_stage="Lead", source="Website", status="Active"),
        CRMContact(organization_id=organization_id, owner_user_id=admin_id, company_id=company_map["GreenField Realty"].id, first_name="Priya", last_name="Nair", full_name="Priya Nair", email="priya@greenfield.example", lifecycle_stage="Customer", source="Referral", status="Active"),
    ]
    for contact in contacts:
        contact.created_by_user_id = admin_id
        contact.updated_by_user_id = admin_id
        db.add(contact)
    db.flush()

    from app.apps.srm.models import SRMProduct
    products = [
        SRMProduct(organization_id=organization_id, item_name="CRM Starter", sku="CRM-ST", category_name="Software", sales_rate=49999, active=True, product_type="stock"),
        SRMProduct(organization_id=organization_id, item_name="Implementation Package", sku="IMP-PRO", category_name="Services", sales_rate=175000, active=True, product_type="service", track_inventory=False),
    ]
    for product in products:
        product.created_by_user_id = admin_id
        db.add(product)

    deal = CRMDeal(
        organization_id=organization_id,
        owner_user_id=admin_id,
        company_id=company_map["GreenField Realty"].id,
        contact_id=contacts[1].id,
        pipeline_id=pipeline.id,
        stage_id=stage_map["Negotiation"].id,
        name="Real Estate CRM Setup",
        amount=650000,
        probability=70,
        expected_revenue=455000,
        expected_close_date=date(2026, 6, 20),
        status="Open",
        lead_source="Referral",
        created_by_user_id=admin_id,
        updated_by_user_id=admin_id,
    )
    db.add(deal)
    db.flush()

    db.add(CRMQuotation(organization_id=organization_id, deal_id=deal.id, company_id=deal.company_id, contact_id=deal.contact_id, owner_user_id=admin_id, quote_number="QT-1001", issue_date=date(2026, 5, 11), expiry_date=date(2026, 5, 25), status="Sent", total_amount=650000, created_by_user_id=admin_id, updated_by_user_id=admin_id))
    db.add(CRMActivity(organization_id=organization_id, owner_user_id=admin_id, deal_id=deal.id, activity_type="Meeting", subject="Product demo", status="Scheduled", priority="High", due_date=datetime(2026, 5, 18, tzinfo=timezone.utc), created_by_user_id=admin_id, updated_by_user_id=admin_id))
    db.add(CRMTask(organization_id=organization_id, owner_user_id=admin_id, deal_id=deal.id, title="Send revised quote", status="To Do", priority="High", due_date=datetime(2026, 5, 19, tzinfo=timezone.utc), created_by_user_id=admin_id, updated_by_user_id=admin_id))
    db.commit()
