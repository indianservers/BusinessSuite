"""Loopback-only connector UI fixture; inherits disposable DB and synthetic users."""
import serve_ux_qa as fixture
from app.apps.power_apps.models import PowerEnvironment

with fixture.qa.SessionLocal() as db:
    for company in (1, 2):
        db.add(PowerEnvironment(organization_id=company, key='development', enabled=True))
    db.commit()

# Synthetic provider fixture is confined to this disposable, loopback-only server.
# It cannot reach provider accounts or consume credits.
from types import SimpleNamespace
import json
from app.apps.power_apps.integrations import adapters,vault
from app.apps.power_apps.integrations.contracts import ConnectionCreate,IntegrationFailure
with fixture.qa.SessionLocal() as db:
    user=db.query(fixture.qa.User).filter_by(email='admin@suiteqa.example.com').one()
    from app.access.service import activate_run_context,release_run_context
    activate_run_context(db,user,SimpleNamespace(scope_key='company:1'))
    connection=vault.create(db,user,'development',ConnectionCreate(connector_id='activecampaign',name='QA ActiveCampaign fixture',auth_type='bearer',secrets={'access_token':'synthetic-qa-token'},config={'provider_host':'qa.api-us1.com'},scopes=[],writes_enabled=True))
    from app.branches.models import BranchOwnership
    from app.apps.power_apps.integrations.models import Credential
    branch=db.query(fixture.Branch).filter_by(company_id=1,name='Navigation QA branch').one()
    for row in (connection,db.get(Credential,connection.credential_id)):
        db.add(BranchOwnership(resource_table=row.__tablename__,resource_key=str(row.id),company_id=1,branch_id=branch.id,source='test-fixture'))
    db.commit()
    release_run_context(db)
class FixtureTransport:
    def request(self,method,url,**kwargs):
        if not url.startswith('https://qa.api-us1.com/'):
            raise IntegrationFailure('qa','This QA server permits only its synthetic provider')
        if method=='GET' and '/contacts' in url:
            data={'contacts':[{'id':'qa-contact-1','firstName':'QA','lastName':'Browser','email':'connector-browser@example.com'}],'meta':{'total':1}}
        else:data={'contact':{'id':'qa-contact-1'},'ok':True}
        return SimpleNamespace(status=200,headers={},body=json.dumps(data).encode())
adapters.HTTP_FACTORY=lambda policy:FixtureTransport()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(fixture.qa.app, host='127.0.0.1', port=1571, log_level='warning')
