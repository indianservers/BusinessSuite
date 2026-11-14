"""Archive the exact legacy classifier in server storage before unserving it."""
import hashlib
import json
import argparse
from pathlib import Path
from app.ai_operator.pms_local_router import HASHES,directory,load


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=directory(),help='Private model archive folder; default verifies the installed server archive')
    source=parser.parse_args().source.resolve()
    destination=directory().resolve()
    values={name:(source/name).read_bytes() for name in HASHES}
    if any(hashlib.sha256(raw).hexdigest()!=HASHES[name] for name,raw in values.items()):
        raise ValueError('Source classifier differs from the verified legacy release')
    destination.mkdir(parents=True,exist_ok=True)
    for name,raw in values.items():
        target=destination/name
        if target.exists() and target.read_bytes()!=raw:raise ValueError('Preserve the existing server model; destination differs')
        target.write_bytes(raw)
    load()
    print(json.dumps({'installed':True,'directory':str(destination),'hashes':HASHES,'source_removed':False}))


if __name__=='__main__':main()
