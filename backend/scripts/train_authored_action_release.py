"""Reproducible local-only release from the reviewed synthetic action corpus."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    from sqlalchemy.engine import make_url
    from app.core.config import settings
    from app.platform_owner.session import platform_factory
    from app.platform_owner.models import PlatformAdmin,PlatformRecord
    from app.platform_owner import service as s
    from app.ai_operator.expanded_corpus import examples
    from app.ai_operator.action_repairs import cases
    from app.ai_operator.training_storage import root
    from app.platform_owner.nlp_training import process
    parser=argparse.ArgumentParser();parser.add_argument('--release',required=True);parser.add_argument('--owner',required=True);parser.add_argument('--epochs',type=int,default=400)
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]{1,80}',args.release):parser.error('Use a short lowercase release name')
    if not 50<=args.epochs<=400:parser.error('Use 50–400 epochs')
    if make_url(settings.PLATFORM_DATABASE_URL).host not in {'127.0.0.1','localhost','::1'}:raise RuntimeError('This authoring helper only supports the local database')
    rows=examples(60);counts={'total':len(rows),'modules':dict(Counter(r['module'] for r in rows)),'splits':{'train':len(rows)}}
    folder=root().parent/'datasets'/args.release;folder.mkdir(parents=True,exist_ok=True)
    (folder/'commands.json').write_text(json.dumps({'version':args.release,'counts':counts,'examples':rows},indent=2),encoding='utf-8')
    (folder/'conversation-repairs.json').write_text(json.dumps(cases(),indent=2),encoding='utf-8')
    with platform_factory()() as db:
        actor=db.query(PlatformAdmin).filter_by(email=args.owner.lower(),role='owner',is_active=True).one();s.require(actor,'nlp.train')
        dataset=PlatformRecord(kind='nlp_dataset',title=f'{args.release} · 1200 commands per module',state='approved',owner_id=actor.id,
            data={'samples':[{**r,'split':'train'} for r in rows],'counts':counts,'privacy_reviewed':True,'reviewed_by':actor.id,'basis':'Synthetic source-controlled examples'})
        db.add(dataset);db.flush()
        job=PlatformRecord(kind='nlp_training',title=dataset.title,state='queued',owner_id=actor.id,data={'dataset_id':dataset.id,'epochs':args.epochs,'counts':counts})
        db.add(job);db.flush();s.event(db,actor,'nlp.authored_release.queued',entity_id=job.id,after={'release':args.release,'counts':counts});db.commit()
        (folder/'job.json').write_text(json.dumps({'job_id':job.id,'dataset_id':dataset.id}),encoding='utf-8')
        print('Training job',job.id,flush=True);process(db,job.id);db.expire_all();job=db.get(PlatformRecord,job.id)
        print('Status:',job.state,flush=True)
        if job.state!='succeeded':raise RuntimeError(job.data.get('error'))
        print(json.dumps(job.data['metrics'],indent=2),flush=True)


if __name__=='__main__':main()
