import pytest
from sqlalchemy import select, text, func
from sqlalchemy.orm import aliased
from fastapi import HTTPException
from app.branches.boundary import install
from app.branches.service import context
from app.branches.models import BranchOwnership, BranchGrant, BranchPolicy
from app.branches.migration import backfill
from app.models.company import Company, Branch
from app.models.user import User
from app.apps.crm.models import CRMCompany, CRMContact
from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine
from tests.tenant_test_utils import assign_company


def test_same_person_crm_in_one_branch_srm_in_another_and_company_revocation(db):
    from app.branches.roles import effective_grants
    from app.access.models import AccessPolicy
    from app.access.service import check_background_access
    user, a, b, *_ = setup(db)
    crm = dict(enabled=True, role='admin', permissions=['crm_view_companies'], actions=['view', 'create'], scope='organization')
    srm = dict(enabled=True, role='viewer', permissions=['srm_view_sales'], actions=['view'], scope='organization')
    base = {'crm': crm, 'srm': srm}
    db.query(BranchGrant).filter_by(user_id=user.id, branch_id=a.id).one().module_grants = {'crm': crm}
    db.add(BranchGrant(user_id=user.id, company_id=1, branch_id=b.id, can_write=False, module_grants={'srm': srm}))
    policy = AccessPolicy(user_id=user.id, company_id=1, grants=base, status='active', version=1)
    db.add(policy); db.commit()
    assert effective_grants(db, user, 1, str(a.id), base)['crm']['enabled']
    assert not effective_grants(db, user, 1, str(a.id), base)['srm']['enabled']
    assert effective_grants(db, user, 1, str(b.id), base)['srm']['enabled']
    assert not effective_grants(db, user, 1, str(b.id), base)['crm']['enabled']
    with pytest.raises(HTTPException): check_background_access(db, user, 'crm', branch_id=str(b.id))
    revoked = {**base, 'crm': {**crm, 'enabled': False}}
    assert not effective_grants(db, user, 1, str(a.id), revoked)['crm']['enabled']
    # Explicit empty whitelist means no modules; NULL keeps legacy company roles.
    row = db.query(BranchGrant).filter_by(user_id=user.id, branch_id=b.id).one()
    row.module_grants = {}; db.commit()
    assert not any(g['enabled'] for g in effective_grants(db, user, 1, str(b.id), base).values())
    row.module_grants = None; db.commit()
    assert effective_grants(db, user, 1, str(b.id), base) == base


def setup(db):
    if not db.get(Company, 1):
        db.add(Company(id=1, name="Branch Test Company", is_active=True))
    db.flush()
    a, b = Branch(company_id=1, name="Chennai", code="CHE"), Branch(company_id=1, name="Bengaluru", code="BLR")
    db.add_all([a, b]); db.flush()
    user = User(email="branch.employee@example.test", hashed_password="unused", is_active=True)
    db.add(user); db.flush(); assign_company(db, user, 1)
    db.add(BranchGrant(user_id=user.id, company_id=1, branch_id=a.id, can_write=True))
    first = CRMCompany(organization_id=1, branch_id=a.id, name="Chennai customer")
    second = CRMCompany(organization_id=1, branch_id=b.id, name="Bengaluru secret")
    unknown = CRMCompany(organization_id=1, name="Unresolved historical customer")
    db.add_all([first, second, unknown]); db.flush()
    contact = CRMContact(organization_id=1, branch_id=b.id, company_id=second.id, first_name="Hidden", last_name="Contact", full_name="Hidden Contact")
    db.add(contact); db.commit()
    backfill(db.connection(), 1); db.commit()
    return user, a, b, first, second, contact


def test_lists_counts_aliases_details_and_identity_map_are_scoped(db):
    user, a, b, first, second, contact = setup(db)
    assert db.get(CRMCompany, second.id) is second
    cleanup = install(db, user, context(db, user, 1, str(a.id)))
    try:
        assert [r.name for r in db.query(CRMCompany)] == ["Chennai customer"]
        assert db.query(func.count(CRMCompany.id)).scalar() == 1
        alias = aliased(CRMCompany)
        assert [r.name for r in db.query(alias)] == ["Chennai customer"]
        assert db.get(CRMCompany, second.id) is None
        assert db.get(CRMContact, contact.id) is None
        assert db.query(CRMContact).count() == 0
        with pytest.raises(HTTPException):
            db.execute(text("select * from crm_companies"))
        with pytest.raises(HTTPException):
            db.query(CRMCompany).update({"branch_id": b.id})
    finally:
        cleanup()


def test_write_stamps_legacy_root_and_children_and_blocks_cross_branch_links(db):
    user, a, b, first, second, contact = setup(db)
    cleanup = install(db, user, context(db, user, 1, str(a.id)))
    try:
        item = CRMCompany(organization_id=1, name="New customer")
        db.add(item); db.flush()
        assert item.branch_id == a.id
        owner = db.connection().execute(select(BranchOwnership.branch_id).where(BranchOwnership.resource_table == "crm_companies", BranchOwnership.resource_key == str(item.id))).scalar()
        assert owner == a.id
        sale = SRMSalesOrder(organization_id=1, order_number="CHE-001", title="Branch sale")
        db.add(sale); db.flush()
        assert db.get(SRMSalesOrder, sale.id) is sale
        attack = CRMContact(organization_id=1, branch_id=a.id, company_id=second.id, first_name="Forged", full_name="Forged Contact")
        db.add(attack)
        with pytest.raises(HTTPException):
            db.flush()
        db.rollback()
    finally:
        cleanup()


def test_cached_foreign_object_cannot_be_updated_or_deleted(db):
    user, a, b, first, second, contact = setup(db)
    cleanup = install(db, user, context(db, user, 1, str(a.id)))
    try:
        second.name = "Attempted overwrite"
        with pytest.raises(HTTPException): db.flush()
        db.rollback()
    finally: cleanup()


def test_revocation_read_only_all_and_company_checks(db):
    user, a, b, first, second, contact = setup(db)
    with pytest.raises(HTTPException): context(db, user, 1, str(b.id))
    with pytest.raises(HTTPException): context(db, user, 1, "all")
    db.add(BranchGrant(user_id=user.id, company_id=1, branch_id=b.id, can_write=False)); db.commit()
    cleanup = install(db, user, context(db, user, 1, str(b.id)))
    try:
        assert db.query(CRMCompany).one().name == "Bengaluru secret"
        savepoint = db.begin_nested()
        db.add(CRMCompany(organization_id=1, name="Read-only attack"))
        with pytest.raises(HTTPException): db.flush()
        savepoint.rollback()
    finally: cleanup()
    db.query(BranchGrant).filter_by(user_id=user.id, branch_id=b.id).delete(); db.commit()
    with pytest.raises(HTTPException): context(db, user, 1, str(b.id))
    db.add(BranchPolicy(user_id=user.id, company_id=1, all_branches=True)); db.commit()
    cleanup = install(db, user, context(db, user, 1, "all"))
    try: assert db.query(CRMCompany).count() == 2
    finally: cleanup()
    with pytest.raises(HTTPException): context(db, user, 999, str(a.id))


def test_superadmin_selected_branch_still_filters(db):
    user, a, b, first, second, contact = setup(db)
    user.is_superuser = True; db.commit()
    cleanup = install(db, user, context(db, user, 1, str(a.id)))
    try: assert db.query(CRMCompany).count() == 1
    finally: cleanup()


def test_branch_control_api_creation_grants_revocation_and_auditing(client, db, superuser_headers):
    from app.branches.models import BranchAudit
    if not db.get(Company, 1): db.add(Company(id=1, name="Company", is_active=True)); db.commit()
    created = client.post("/api/v1/branches", headers=superuser_headers, json={"name": "Chennai", "code": "CHE", "reason": "Open Chennai office"})
    assert created.status_code == 201, created.text
    branch = created.json()["id"]
    assert client.post("/api/v1/branches", headers=superuser_headers, json={"name": "Duplicate", "code": "che", "reason": "Duplicate test"}).status_code == 409
    member = User(email="branch.target@example.test", hashed_password="unused", is_active=True)
    db.add(member); db.flush(); assign_company(db, member, 1); db.commit()
    payload = {"grants": [{"branch_id": branch, "can_write": True}], "use_home_branch": False, "expected_version": 0, "reason": "Allow Chennai sales"}
    response = client.put(f"/api/v1/branches/access/{member.id}", headers=superuser_headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 1
    assert client.put(f"/api/v1/branches/access/{member.id}", headers=superuser_headers, json=payload).status_code == 409
    assert db.query(BranchAudit).count() == 2


def test_profile_sharing_does_not_share_sales_or_allow_profile_edits(db):
    from app.branches.models import BranchRecordShare
    user, a, b, first, second, contact = setup(db)
    db.add(BranchGrant(company_id=1, user_id=user.id, branch_id=b.id, can_write=True))
    sale = SRMSalesOrder(organization_id=1, title="Chennai private sale", order_number="PRIVATE-CHE", crm_company_id=first.id)
    db.add(sale); db.flush()
    db.add(BranchOwnership(resource_table="srm_sales_orders", resource_key=str(sale.id), company_id=1, branch_id=a.id, source="test"))
    db.add(BranchRecordShare(company_id=1, resource_table="crm_companies", resource_key=str(first.id), branch_id=b.id))
    db.commit()
    cleanup = install(db, user, context(db, user, 1, str(b.id)))
    try:
        assert db.get(CRMCompany, first.id) is first
        assert db.query(SRMSalesOrder).count() == 0
        own_sale = SRMSalesOrder(organization_id=1, title="Bengaluru own sale", order_number="OWN-BLR", crm_company_id=first.id)
        db.add(own_sale); db.flush()
        stamp = db.connection().execute(select(BranchOwnership.branch_id).where(BranchOwnership.resource_table == "srm_sales_orders", BranchOwnership.resource_key == str(own_sale.id))).scalar()
        assert stamp == b.id
        first.name = "Unauthorized shared profile edit"
        with pytest.raises(HTTPException): db.flush()
        db.rollback()
    finally: cleanup()


def test_parent_backfill_is_repeatable_and_does_not_guess_unknown_ownership(db):
    user, a, b, first, second, contact = setup(db)
    from app.apps.crm.models import CRMNote
    note = CRMNote(organization_id=1, company_id=first.id, body="Inherited private note")
    db.add(note); db.commit()
    result = backfill(db.connection(), 1); db.commit()
    assert result.get("crm_notes") == 1
    assert backfill(db.connection(), 1) == {}
    assert db.query(BranchOwnership).filter_by(resource_table="crm_companies").count() == 2


def test_signed_file_link_rechecks_branch_revocation(db, monkeypatch, tmp_path):
    from urllib.parse import urlsplit, parse_qs
    from app.core.config import settings
    from app.core.storage import signed_file_url, blob_token_path
    from app.core.audit_context import context as audit_context, permission_fingerprint
    user, a, b, first, second, contact = setup(db)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    token = audit_context.set({"actor": {"user_id": user.id, "access_company": 1, "access_branch": a.id, "access_role_id": user.role_id, "access_permissions": permission_fingerprint(user)}})
    try: url = signed_file_url(str(tmp_path / "private-evidence.txt"))
    finally: audit_context.reset(token)
    signed_token = parse_qs(urlsplit(url).query)["token"][0]
    assert blob_token_path(signed_token, db=db).endswith("private-evidence.txt")
    db.query(BranchGrant).filter_by(user_id=user.id, branch_id=a.id).delete(); db.commit()
    with pytest.raises(HTTPException): blob_token_path(signed_token, db=db)


def test_signed_file_link_rechecks_branch_role_downgrade(db, monkeypatch, tmp_path):
    from urllib.parse import urlsplit, parse_qs
    from app.core.config import settings
    from app.core.storage import signed_file_url, blob_token_path
    from app.core.audit_context import context as audit_context, permission_fingerprint
    from app.branches.roles import effective_grants
    from app.access.models import AccessPolicy
    user, a, *_ = setup(db)
    grant = dict(enabled=True, role='editor', permissions=['crm_view_companies'], actions=['view','export'], scope='organization')
    policy = AccessPolicy(user_id=user.id, company_id=1, status='active', grants={'crm':grant}, version=1)
    branch = db.query(BranchGrant).filter_by(user_id=user.id, branch_id=a.id).one()
    branch.module_grants = {'crm':grant}; db.add(policy); db.commit()
    effective_grants(db, user, 1, str(a.id), {'crm':grant})
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    token = audit_context.set({'actor': {'user_id':user.id, 'access_company':1, 'access_branch':a.id,
        'access_module':'crm', 'access_role_id':user.role_id, 'access_policy_version':1,
        'access_permissions':permission_fingerprint(user), 'access_branch_roles':user._suite_branch_roles_fingerprint}})
    try: url = signed_file_url(str(tmp_path / 'branch-role-evidence.txt'))
    finally: audit_context.reset(token)
    capability = parse_qs(urlsplit(url).query)['token'][0]
    assert blob_token_path(capability, db=db).endswith('branch-role-evidence.txt')
    branch.module_grants = {'crm':{**grant, 'actions':['view']}}; db.commit()
    with pytest.raises(HTTPException): blob_token_path(capability, db=db)


def test_superadmin_cannot_stamp_another_companys_record_into_selected_branch(db):
    user, a, b, first, second, contact = setup(db)
    user.is_superuser = True; db.commit()
    cleanup = install(db, user, context(db, user, 1, str(a.id)))
    try:
        db.add(CRMCompany(organization_id=999, branch_id=a.id, name="Wrong company"))
        with pytest.raises(HTTPException): db.flush()
        db.rollback()
    finally: cleanup()


def test_three_branches_two_companies_and_forged_cross_company_grants(db):
    user, a, b, first, second, contact = setup(db)
    db.add(Company(id=2, name="Other company", is_active=True)); db.flush()
    foreign_branch = Branch(company_id=2, name="Hyderabad", code="HYD")
    db.add(foreign_branch); db.flush()
    foreign = CRMCompany(organization_id=2, branch_id=foreign_branch.id, name="Other company customer")
    db.add(foreign); db.flush()
    db.add(BranchGrant(company_id=1, user_id=user.id, branch_id=foreign_branch.id, can_write=True))
    db.commit()
    with pytest.raises(HTTPException): context(db, user, 1, str(foreign_branch.id))
    with pytest.raises(HTTPException): context(db, user, 2, str(foreign_branch.id))
    cleanup = install(db, user, context(db, user, 1, str(a.id)))
    try: assert [r.name for r in db.query(CRMCompany)] == ["Chennai customer"]
    finally: cleanup()


def test_safe_bulk_status_update_cannot_touch_another_branch(db):
    user, a, b, first, second, contact = setup(db)
    cleanup = install(db, user, context(db, user, 1, str(a.id)))
    try:
        changed = db.query(CRMCompany).update({"status": "Inactive"}, synchronize_session=False)
        assert changed == 1
        db.flush()
    finally: cleanup()
    db.expire_all()
    assert db.get(CRMCompany, first.id).status == "Inactive"
    assert db.get(CRMCompany, second.id).status == "Active"


def test_composite_resource_keys_are_unambiguous_in_sql_and_python(db):
    from sqlalchemy import Table, Column, MetaData, String
    from app.branches.catalog import key_expression, resource_key
    table = Table("branch_key_test", MetaData(), Column("left", String, primary_key=True), Column("right", String, primary_key=True))
    table.create(db.connection())
    rows = [{"left": "a:b", "right": "c"}, {"left": "a", "right": "b:c"}]
    db.connection().execute(table.insert(), rows)
    actual = set(db.connection().execute(select(key_expression(table))).scalars())
    assert actual == {resource_key(table, row) for row in rows}
    assert len(actual) == 2


def test_standalone_reminders_are_owned_and_filtered(db):
    from app.apps.srm.models import SRMCollectionReminder
    user, a, b, first, second, contact = setup(db)
    db.add(BranchGrant(company_id=1, user_id=user.id, branch_id=b.id, can_write=True)); db.commit()
    for branch, message in ((a, "Chennai reminder"), (b, "Bengaluru reminder")):
        cleanup = install(db, user, context(db, user, 1, str(branch.id)))
        try:
            db.add(SRMCollectionReminder(organization_id=1, message=message)); db.flush()
        finally: cleanup()
    cleanup = install(db, user, context(db, user, 1, str(a.id)))
    try: assert [r.message for r in db.query(SRMCollectionReminder)] == ["Chennai reminder"]
    finally: cleanup()


def test_accounting_branch_views_do_not_expose_company_materialized_balances(db):
    from datetime import date, datetime, timezone
    from decimal import Decimal
    from app.apps.fam.models import FAMLedgerGroup, FAMLedger, FAMFinancialYear, FAMVoucherType, FAMVoucher, FAMVoucherLine, FAMLedgerEntry
    from app.branches.accounting import ledger_amounts, protect_serialized
    user, a, b, first, second, contact = setup(db)
    group = FAMLedgerGroup(company_id=1, group_code="BRANCH-QA", group_name="Branch QA assets", nature="asset")
    year = FAMFinancialYear(company_id=1, name="QA FY", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31))
    kind = FAMVoucherType(company_id=1, voucher_type_code="QA-JV", voucher_type_name="QA Journal", category="journal", numbering_prefix="QA")
    db.add_all([group, year, kind]); db.flush()
    ledger = FAMLedger(company_id=1, ledger_code="QA-CASH", ledger_name="QA system cash", ledger_group_id=group.id, nature="asset", ledger_type="cash", system_ledger=True, current_balance_dr=9999)
    private = FAMLedger(company_id=1, ledger_code="QA-PRIVATE", ledger_name="Unassigned confidential party", ledger_group_id=group.id, nature="asset", ledger_type="customer", system_ledger=False)
    db.add_all([ledger, private]); db.flush()
    entries = []
    for branch, amount in ((a, 10), (b, 200)):
        voucher = FAMVoucher(company_id=1, financial_year_id=year.id, voucher_type_id=kind.id, voucher_number=f"QA-{branch.id}", voucher_date=date(2026, 11, 2))
        db.add(voucher); db.flush()
        line = FAMVoucherLine(voucher_id=voucher.id, line_number=1, ledger_id=ledger.id, debit_amount=amount)
        db.add(line); db.flush()
        entry = FAMLedgerEntry(company_id=1, financial_year_id=year.id, voucher_id=voucher.id, voucher_line_id=line.id, voucher_number=voucher.voucher_number, voucher_date=voucher.voucher_date, ledger_id=ledger.id, debit_amount=amount, running_balance=9999, posted_at=datetime.now(timezone.utc))
        db.add(entry); db.flush(); entries.append(entry)
        for row in (voucher, line, entry): db.add(BranchOwnership(resource_table=row.__tablename__, resource_key=str(row.id), company_id=1, branch_id=branch.id, source="test"))
    db.commit()
    cleanup = install(db, user, context(db, user, 1, str(a.id)))
    try:
        assert db.query(FAMLedger).count() == 1
        assert ledger_amounts(db, ledger)["current_balance_dr"] == Decimal("10")
        assert protect_serialized(entries[0], {"running_balance": 9999})["running_balance"] == 10
        assert db.query(FAMLedgerEntry).count() == 1
    finally: cleanup()


def test_approved_default_main_migration_preserves_existing_ownership_and_amounts(db):
    from app.branches.default_migration import assign_default, reconcile_snapshot
    user, a, b, first, second, contact = setup(db)
    user.is_superuser = True
    member = User(email="default.main.member@example.com", hashed_password="unused", is_active=True)
    db.add(member); db.flush(); assign_company(db, member, 1); db.commit()
    before = reconcile_snapshot(db.connection())
    result = assign_default(db.connection(), 1, a.id, actor=user)
    assert result["held_total"] == 0
    assert result["assigned"].get("crm_companies") == 1
    assert reconcile_snapshot(db.connection()) == before
    assert db.query(BranchOwnership).filter_by(resource_table="crm_companies", branch_id=b.id).count() == 1
    grants = db.query(BranchGrant).filter_by(user_id=member.id).all()
    assert [(g.branch_id, g.can_write) for g in grants] == [(a.id, True)]
    again = assign_default(db.connection(), 1, a.id, actor=user)
    assert again["assigned_total"] == 0
    assert again["main_only_user_grants"] == 0


def test_company_boundary_honors_approved_null_ownership_without_overriding_explicit_company(db):
    from app.core.tenant_boundary import install as company_boundary
    user, a, b, first, second, contact = setup(db)
    db.add(Company(id=2, name="Second company", is_active=True)); db.flush()
    foreign_branch = Branch(company_id=2, name="Foreign branch", code="FOREIGN")
    db.add(foreign_branch); db.flush()
    null_owned = CRMCompany(organization_id=None, name="Approved second-company null")
    explicit = CRMCompany(organization_id=2, name="Explicit second company")
    db.add_all([null_owned, explicit]); db.flush()
    db.add(BranchOwnership(resource_table="crm_companies", resource_key=str(null_owned.id), company_id=2, branch_id=foreign_branch.id, source="admin-reviewed"))
    # Even a tainted register entry cannot override an explicit tenant marker.
    db.add(BranchOwnership(resource_table="crm_companies", resource_key=str(explicit.id), company_id=1, branch_id=a.id, source="test-taint"))
    db.commit()
    cleanup = company_boundary(db, user, 1)
    try:
        assert db.get(CRMCompany, null_owned.id) is None
        assert db.get(CRMCompany, explicit.id) is None
    finally: cleanup()


def test_all_branch_reports_include_archived_history_but_cannot_modify_it(db):
    user, a, b, first, second, contact = setup(db)
    b.is_active = False
    db.add(BranchPolicy(company_id=1, user_id=user.id, all_branches=True)); db.commit()
    ctx = context(db, user, 1, "all")
    assert b.id in ctx.allowed and b.id not in ctx.writable
    cleanup = install(db, user, ctx)
    try:
        assert db.query(CRMCompany).count() == 2
        assert db.query(CRMCompany).update({"status": "Inactive"}, synchronize_session=False) == 1
    finally: cleanup()
    db.expire_all()
    assert db.get(CRMCompany, second.id).status == "Active"
