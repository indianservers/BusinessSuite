"""Install or verify the pinned model from a private archive; no network calls."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from app.ai_operator.server_local_llm import folder,verify,HASHES,MODEL,REVISION


def checksum(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=folder());args=parser.parse_args()
    source=args.source.resolve();target=folder().resolve()
    if any(checksum(source/name)!=expected for name,expected in HASHES.items()):raise ValueError('Archive integrity check failed')
    target.mkdir(parents=True,exist_ok=True)
    for name,expected in HASHES.items():
        destination=target/name
        if destination.exists():
            if checksum(destination)!=expected:raise ValueError('Preserve the differing installed model; review deployment before replacement')
            continue
        partial=target/(name+'.installing')
        shutil.copyfile(source/name,partial)
        if checksum(partial)!=expected:raise ValueError('Copied model integrity check failed')
        partial.replace(destination)
    verify()
    print(json.dumps({'installed':True,'model':MODEL,'revision':REVISION,'server_directory':str(target),'network_calls':0}))


if __name__=='__main__':main()
