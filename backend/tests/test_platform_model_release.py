import shutil
from tests.test_public_signup import platform_store
from tests.test_platform_nlp_training import trainer,uploaded
from tests.test_model_release import candidate
from app.platform_owner.models import PlatformRecord
from app.ai_operator.model_release import seal,digest

ROOT='/api/v1/platform/nlp-training'

def test_platform_activation_rollback_and_tamper_gates(client,db,platform_store,candidate,monkeypatch):
    root,source,_=candidate;monkeypatch.setenv('LOCAL_NLP_TRAINING_DIR',str(root.parent))
    h=trainer(client,platform_store);dataset_id=uploaded(client,h)
    assert client.post(f'{ROOT}/datasets/{dataset_id}/approve',headers=h,json={'privacy_reviewed':True}).status_code==200
    dataset=platform_store.get(PlatformRecord,dataset_id);jobs=[]
    for i in range(2):
        job=PlatformRecord(kind='nlp_training',title='Verified candidate',state='succeeded',owner_id=dataset.owner_id,
            data={'dataset_id':dataset_id,'epochs':220,'dataset_sha256':digest(dataset.data['samples'])})
        platform_store.add(job);platform_store.commit();jobs.append(job.id)
        folder=root/'runs'/str(job.id)/'model';shutil.copytree(source,folder)
        gate=seal(folder,job.id,digest(dataset.data['samples']))
        job.data={**job.data,'release':gate};platform_store.commit()
        activated=client.post(f'{ROOT}/jobs/{job.id}/activate',headers=h)
        assert activated.status_code==200,activated.text
    assert client.get(ROOT,headers=h).json()['previous_job_id']==jobs[0]
    rolled=client.post(ROOT+'/rollback',headers=h)
    assert rolled.status_code==200 and rolled.json()['active_job_id']==jobs[0]
    (root/'runs'/str(jobs[1])/'model/CRM.keras').write_text('tampered')
    assert client.post(ROOT+'/rollback',headers=h).status_code==409
    assert client.get(ROOT,headers=h).json()['active_job_id']==jobs[0]
    assert client.post(f'{ROOT}/jobs/{jobs[0]}/evaluate',headers=h).status_code==409

def test_training_success_or_editable_gate_flag_cannot_bypass_release(client,db,platform_store,candidate,monkeypatch):
    root,_,_=candidate;monkeypatch.setenv('LOCAL_NLP_TRAINING_DIR',str(root.parent))
    h=trainer(client,platform_store);ident=uploaded(client,h)
    client.post(f'{ROOT}/datasets/{ident}/approve',headers=h,json={'privacy_reviewed':True})
    source=platform_store.get(PlatformRecord,ident)
    job=PlatformRecord(kind='nlp_training',title='Unverified',state='succeeded',owner_id=source.owner_id,
        data={'dataset_id':ident,'epochs':220,'release':{'passed':True}})
    platform_store.add(job);platform_store.commit()
    assert client.post(f'{ROOT}/jobs/{job.id}/activate',headers=h).status_code==409
    assert client.get(ROOT,headers=h).json()['active_job_id'] is None
