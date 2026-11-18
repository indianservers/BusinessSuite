from pathlib import Path
import hashlib,json,os,shutil,sys
root=Path('/srv/business-suite/current/backend').resolve()
base=Path('/srv/business-suite/shared/employee-taxonomy-20261118')
manifest=json.loads((base/'backend-manifest.json').read_text())
source=base/'backend-next'
for name,wanted in manifest['original'].items():
 target=(root/name).resolve()
 if not target.is_relative_to(root) or hashlib.sha256(target.read_bytes()).hexdigest()!=wanted:
  raise SystemExit('Production source changed; refusing to overwrite '+name)
for name,wanted in manifest['files'].items():
 target=(root/name).resolve();candidate=source/name
 if not target.is_relative_to(root) or hashlib.sha256(candidate.read_bytes()).hexdigest()!=wanted:
  raise SystemExit('Invalid candidate '+name)
for name in manifest['files']:
 target=root/name;temporary=target.with_name(target.name+'.taxonomy-next')
 target.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(source/name,temporary);os.chmod(temporary,0o644);os.replace(temporary,target)
print('Installed scoped HRMS taxonomy backend; existing schema retained')
