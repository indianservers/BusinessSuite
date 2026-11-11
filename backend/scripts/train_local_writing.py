"""Fit additive writing retrieval using the action agent's existing features."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ai_operator.local_writing import ARTIFACT, train

if __name__ == '__main__':
    bundle = train()
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(bundle, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'version': bundle['version'], 'examples': len(bundle['examples']),
                      'skills': len({r['intent'] for r in bundle['examples']}),
                      'vocabulary': len(bundle['idf']), 'artifact': str(ARTIFACT)}))
