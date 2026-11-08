"""Disposable real HTTP acceptance app; no production database or delivery."""
import os
os.environ.update(TENANT_DATABASES_ENABLED='false', PLATFORM_DATABASE_URL='', TENANT_REGISTRY_URL='', TENANT_PROVISIONING_URL='')
import serve_ux_qa as fixture
from app.models.company import Company
from app.shared.follow_ups import start_worker
qa=fixture.qa
with qa.SessionLocal() as db:
    seller=db.get(Company,1)
    seller.legal_name='Synthetic acceptance seller Ltd'
    seller.address='Acceptance test seller address'
    seller.country='India'
    uae_seller=db.get(Company,2)
    uae_seller.legal_name='Synthetic UAE acceptance seller LLC'
    uae_seller.address='Acceptance test UAE seller address'
    uae_seller.country='United Arab Emirates'
    db.commit()
if __name__=='__main__':
    import uvicorn
    worker=start_worker()
    try: uvicorn.run(qa.app,host='127.0.0.1',port=1568,log_level='warning')
    finally: worker[0].set()
