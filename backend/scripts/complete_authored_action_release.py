"""Complete a locally reevaluated authored job only after all release gates pass.

Use after a source routing correction, when weight fitting succeeded but the
original job stopped at evaluation. Does not weaken gates or refit test probes.
Run benchmark_action_dialogue, benchmark_unseen_dialogue and
evaluate_action_release against that job's model directory first.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--job',type=int,required=True)
    parser.add_argument('--owner',required=True);parser.add_argument('--activate',action='store_true')
    args=parser.parse_args()
    from app.core.config import settings
    from sqlalchemy.engine import make_url
    if make_url(settings.PLATFORM_DATABASE_URL).host not in {'127.0.0.1','localhost','::1'}:
        raise RuntimeError('Local authored jobs only')
    from app.platform_owner.session import platform_factory
    from app.platform_owner.models import PlatformAdmin
    from app.platform_owner import nlp_training as training,service
    from app.ai_operator.training_storage import root
    from app.ai_operator.model_release import seal,digest,read
    from app.ai_operator.reviewed_data import load_reviewed
    from app.ai_operator.local_tensorflow import validate
    with platform_factory()() as db:
        training.release_lock(db)
        actor=db.query(PlatformAdmin).filter_by(email=args.owner.lower(),role='owner',is_active=True).one()
        service.require(actor,'nlp.train')
        job=training.record(db,args.job,'nlp_training')
        if job.state!='failed' or job.owner_id!=actor.id:raise ValueError('Use your failed, locally reevaluated job')
        _,dataset=training.valid_source(db,job)
        folder=root()/'platform/runs'/str(job.id)/'model'
        bundle=validate(read(folder/'bundle.json'))
        rows,scope,source_hash=load_reviewed(folder.parent/'reviewed.json')
        expected=[{k:r[k] for k in ('module','intent','text')} for r in dataset.data['samples'] if r['split']=='train']
        if scope!={'platform':True} or rows!=expected or source_hash!=bundle.get('reviewed_dataset_sha256'):
            raise ValueError('Candidate does not match the approved source')
        gate=seal(folder,job.id,digest(dataset.data['samples']),training.baseline_release())
        if not gate['passed']:raise ValueError('Release gates failed: '+str([r for r in gate['checks'] if not r['passed']]))
        report=read(folder/'evaluation.json')
        metrics={k:report[k] for k in ('modules','uploaded_evaluation','tensorflow_version') if k in report}
        metrics['common_actions']=read(folder/'conversation-evaluation.json')['common_actions']
        metrics['native_tests']=read(folder/'action-release-evaluation.json')
        job.state='succeeded';job.data={**job.data,'metrics':metrics,'release':gate,'error':None,
            'evaluation':{'state':'succeeded','basis':'Source routing corrected; unchanged approved weights reevaluated against all release gates'}}
        service.event(db,actor,'nlp.authored_release.evaluation_completed',entity_id=job.id,
            after={'release_passed':True,'unchanged_weights':True});db.commit()
        result={'job_id':job.id,'status':job.state,'gate_passed':gate['passed']}
        if args.activate:result['activation']=training.activate(job.id,actor=actor,db=db)
        print(json.dumps(result,indent=2))

if __name__=='__main__':main()
