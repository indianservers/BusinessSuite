"""Generate portable validation sources for independently deployed frontends/backend."""
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
targets=[ROOT/'frontend/src/lib/validation',ROOT/'frontend/interns-hub/src/validation']
for target in targets:
    if not args.check:target.mkdir(parents=True,exist_ok=True)
    for filename in ('contract.json','index.ts','PhoneInput.tsx'):
        source=(ROOT/'shared/validation'/filename).read_bytes();destination=target/filename
        if args.check:
            if not destination.exists() or destination.read_bytes()!=source:raise SystemExit(f'Out of date: {destination}')
        else:destination.write_bytes(source)
destination=ROOT/'backend/app/core/validation_contract.json';source=(ROOT/'shared/validation/contract.json').read_bytes()
if args.check:
    if not destination.exists() or destination.read_bytes()!=source:raise SystemExit('Backend validation contract is out of date')
else:destination.write_bytes(source)
print('Validation sources match the shared contract.')
