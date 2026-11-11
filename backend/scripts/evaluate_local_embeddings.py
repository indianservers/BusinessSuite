"""Synthetic retrieval checks against the installed model; no training or ERP data."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.ai_operator.local_embeddings import MODEL,REVISION,directory
from app.ai_operator.workspace_search import rank_chunks

CASES=[
 ('collections','Customers must settle outstanding invoices within thirty days.','Which bills have not been paid?'),
 ('onboarding','New employees receive laptops and attend orientation during their first week.','What happens when a new colleague joins?'),
 ('leave','Annual leave requests require approval from the reporting manager before absence.','Who authorizes a vacation?'),
 ('delivery','A delayed project milestone must be escalated to the delivery coordinator.','Who handles late delivery dates?'),
 ('passwords','Account passwords must be reset using the identity portal. Never share sign-in credentials.','How do I change my login secret?'),
 ('expenses','Staff can claim reimbursement for approved business travel with receipts.','How can I get money back for a work trip?'),
 ('support','Customer support tickets with critical severity receive immediate incident response.','What happens to an urgent client issue?'),
 ('stock','Warehouse inventory below the reorder threshold requires a purchase request.','What should we do when supplies run low?'),
 ('dependencies','Dependent tasks cannot start until all prerequisite work is completed.','Can the next activity begin before the previous one finishes?'),
 ('probation','Probation reviews occur after ninety days of employment.','When is the initial employment assessment?'),
 ('payment','Supplier bank payments require finance approval and a verified beneficiary.','Who approves sending money to a vendor?'),
 ('privacy','Personal employee medical information is restricted to authorized HR personnel.','Who can see sensitive staff health records?'),
]


def main():
    chunks=[{'text':text,'source':{'id':ident}} for ident,text,_ in CASES]
    start=time.monotonic();results=[]
    for expected,_,query in CASES:
        found,engine=rank_chunks(chunks,query,'semantic')
        predicted=found[0]['id'] if found else None
        results.append({'query':query,'expected':expected,'actual':predicted,'passed':expected==predicted,'semantic_used':engine['semantic_used']})
    report={'model':MODEL,'revision':REVISION,'kind':'authored synthetic English retrieval; not independent real-world evaluation',
        'cases':len(results),'passed':sum(r['passed'] for r in results),'duration_seconds':round(time.monotonic()-start,2),'results':results}
    (directory()/'synthetic-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if report['passed']==len(results) else 1


if __name__=='__main__':raise SystemExit(main())
