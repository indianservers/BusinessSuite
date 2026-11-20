"""Disposable real-HTTP browser QA environment; never uses the developer DB."""
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
QA = ROOT / '.local' / 'offerings-browser-qa'
QA.mkdir(parents=True, exist_ok=True)
DATABASE = QA / 'audit.sqlite'
REUSE = "--reuse" in sys.argv
if REUSE and not DATABASE.exists():
    raise RuntimeError("No disposable QA database exists to reuse")
if DATABASE.exists() and not REUSE:
    raise RuntimeError('QA database already exists; reuse the running server or choose a new isolated directory')
os.environ.update(DATABASE_URL='sqlite:///' + DATABASE.as_posix(), ENVIRONMENT='test',
    SECRET_KEY=secrets.token_urlsafe(48), REFRESH_SECRET_KEY=secrets.token_urlsafe(48),
    SERVERLESS='false', TENANT_DATABASES_ENABLED='false', PLATFORM_DATABASE_URL='',
    INSTALLED_APPS='hrms,crm,project_management,srm,fam', STORAGE_BACKEND='local',
    EMAIL_NOTIFICATIONS_ENABLED='false', EMAIL_WORKER_ENABLED='false', ACCOUNTING_SYNC_WORKER_ENABLED='false',
    SEED_DEMO_DATA='false', UPLOAD_DIR=str(QA / 'uploads'),
    OPENAI_API_KEY='', ANTHROPIC_API_KEY='', GEMINI_API_KEY='', MAIL_PASSWORD='', MAIL_USERNAME='',
    BLOB_READ_WRITE_TOKEN='', S3_ACCESS_KEY_ID='', S3_SECRET_ACCESS_KEY='', RECAPTCHA_SECRET_KEY='')

from app.main import app
from app.db.base import Base
from app.db.session import engine, LegacySessionLocal
from app.models.user import User, Role
from app.core.security import get_password_hash
from test_identity_utils import attach_test_identity, attach_workflow_branch, provision_workflow_workspace
from tests.srm_test_utils import seed_invoice_parties

assert engine.url.get_backend_name() == 'sqlite' and Path(engine.url.database).resolve() == DATABASE.resolve()
Base.metadata.create_all(engine)
if not REUSE:
    with LegacySessionLocal() as db:
        role = Role(name='super_admin', is_system=True)
        db.add(role); db.flush()
        user = User(email='browser-audit@example.com', hashed_password=get_password_hash('BrowserAudit@2026'),
            is_active=True, is_superuser=True, role_id=role.id)
        db.add(user); db.flush()
        attach_test_identity(db, user)
        branch = attach_workflow_branch(db, user)
        provision_workflow_workspace(db, user)
        db.commit()
        seed_invoice_parties(db)
        (QA / 'environment.json').write_text(__import__('json').dumps({
            'database': str(DATABASE), 'branch_id': branch.id, 'user_id': user.id,
            'api': 'http://127.0.0.1:8799', 'frontend': 'http://127.0.0.1:5198', 'disposable': True}), encoding='utf-8')

with LegacySessionLocal() as db:
    from app.models.user import Permission
    from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember
    from app.apps.srm.models import SRMProduct
    from app.shared.catalog_models import CatalogDetails
    from test_identity_utils import own_workflow_records
    admin = db.query(User).filter_by(email='browser-audit@example.com').one()
    reader = db.query(User).filter_by(email='browser-reader@example.com').first()
    if reader is None:
        role = Role(name='srm_viewer', is_system=True)
        db.add(role); db.flush()
        for name in ['srm_view','pms_view','crm_view','crm_products_view']:
            permission = db.query(Permission).filter_by(name=name).first()
            if permission is None:
                permission = Permission(name=name, module=name.split('_')[0]); db.add(permission); db.flush()
            role.permissions.append(permission)
        reader = User(email='browser-reader@example.com', hashed_password=get_password_hash('BrowserAudit@2026'), is_active=True, is_superuser=False, role_id=role.id)
        db.add(reader); db.flush(); attach_test_identity(db,reader); attach_workflow_branch(db,reader)
    if not db.query(SRMProduct).filter_by(sku='BQA-PRIVATE-WORKSPACE').first():
        workspace = PMSWorkspace(name='Browser QA private workspace', organization_id=1)
        db.add(workspace); db.flush(); own_workflow_records(db,workspace)
        member = PMSWorkspaceMember(workspace_id=workspace.id,user_id=admin.id,role='Owner')
        db.add(member); db.flush(); own_workflow_records(db,member)
        product = SRMProduct(organization_id=1,sku='BQA-PRIVATE-WORKSPACE',item_name='Browser QA private offering',product_type='membership',active=True,track_inventory=False,created_by=admin.id,
            metadata_json={'plan':{'duration':{'unit':'month','count':1},'activation':'purchase','benefits':[]}})
        db.add(product); db.flush(); own_workflow_records(db,product)
        db.add(CatalogDetails(organization_id=1,product_id=product.id,workspace_id=workspace.id))
    if not db.query(User).filter_by(email='browser-foreign@example.com').first():
        foreign = User(email='browser-foreign@example.com',hashed_password=get_password_hash('BrowserAudit@2026'),is_active=True,is_superuser=True,role_id=admin.role_id)
        db.add(foreign);db.flush();attach_test_identity(db,foreign,company_id=2);attach_workflow_branch(db,foreign,company_id=2)
    from app.models.company import Company
    db.get(Company,2).name = "Browser QA foreign company"
    db.commit()

if __name__ == '__main__' and '--seed-only' not in sys.argv:
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8799, lifespan='off', log_level='warning')
