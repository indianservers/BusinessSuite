"""Explicit tenant setup for ordinary authenticated workflow fixtures only.

Security tests that intentionally exercise unverified identities do not call this.
"""
def attach_test_identity(db, user, company_id=1):
    from app.models.company import Company
    from app.common.services.identity import SharedIdentityService
    if not db.get(Company, company_id):
        db.add(Company(id=company_id, name='Workflow Test Company', is_active=True))
        db.flush()
    db.flush()
    return SharedIdentityService.ensure_person_for_user(db, user, organization_id=company_id)
