"""Fit/export the actual local retrieval model and evaluate a separate authored holdout."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    from app.ai_operator.local_nlp import fit,parse
    from app.ai_operator.local_corpus import VERSION
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='../.local/local-nlp-v1')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    output=Path(args.output)
    if not output.is_absolute():output=root/output
    output.mkdir(parents=True,exist_ok=True)
    rows,idf,vectors=fit()
    corpus=json.dumps(rows,ensure_ascii=False,sort_keys=True)
    artifact={'version':VERSION,'type':'TF-IDF nearest-example + typed slot rules','corpus_sha256':hashlib.sha256(corpus.encode()).hexdigest(),
              'examples':rows,'idf':idf,'vectors':vectors}
    (output/'model.json').write_text(json.dumps(artifact,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (output/'commands.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    holdout=json.loads((root/'tests/fixtures/local-nlp-holdout-v1.json').read_text(encoding='utf-8'))
    failed=[]
    for module,text,expected in holdout:
        actual=parse(text,module)
        if actual.intent!=expected:failed.append({'module':module,'text':text,'expected':expected,'actual':actual.intent,'confidence':actual.confidence})
    report={'version':VERSION,'training_commands':dict(Counter(r['module'] for r in rows)),'training_exact_matches':sum(parse(r['text'],r['module']).intent==r['intent'] for r in rows),
            'holdout_cases':len(holdout),'holdout_passed':len(holdout)-len(failed),'failures':failed,
            'evaluation_status':'Authored development paraphrases inspected during implementation; not an untouched generalization benchmark',
            'limits':'Authored finite benchmark, not a general-language accuracy claim or neural weight training. No production data used.'}
    (output/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if not failed else 1


if __name__=='__main__':raise SystemExit(main())
