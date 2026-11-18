from pathlib import Path
import json,hashlib,shutil,fcntl,subprocess,urllib.request,time,os
base=Path('/srv/business-suite/shared/pos-booking-qa-20261118');release=Path('/srv/business-suite/current/backend').resolve();lock=open('/srv/business-suite/shared/deploy.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
baseline=json.loads((base/'backend-baseline.json').read_text());before=base/'backend-before';before.mkdir(exist_ok=True)
for name,digest in baseline.items():
 target=release/'app/apps/srm'/name;candidate=base/'backend-candidate'/name
 assert hashlib.sha256(target.read_bytes()).hexdigest()==digest,'Backend changed; refusing to overwrite '+name
 compile(candidate.read_bytes(),name,'exec')
 if (before/name).exists():raise RuntimeError('Backup already exists; inspect previous activation')
 shutil.copy2(target,before/name)
def health():
 for attempt in range(24):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=5) as r:
    v=json.load(r)
    if v.get('status')=='healthy' and v.get('db')=='ok':return
  except Exception:pass
  time.sleep(2)
 raise RuntimeError('Backend health check did not recover')
changed=[]
try:
 for name in baseline:
  target=release/'app/apps/srm'/name;pending=target.with_name(target.name+'.booking-next');shutil.copy2(base/'backend-candidate'/name,pending);pending.chmod(target.stat().st_mode & 0o777);os.replace(pending,target);changed.append(name)
 subprocess.run(['systemctl','restart','business-suite.service'],check=True);health();(base/'backend-activation.json').write_text(json.dumps({'status':'ready','changed':changed}));print('READY: bounded booking employee projection; healthy backend',flush=True)
except BaseException:
 for name in changed:shutil.copy2(before/name,release/'app/apps/srm'/name)
 subprocess.run(['systemctl','restart','business-suite.service'],check=True);health();(base/'backend-activation.json').write_text(json.dumps({'status':'rolled_back'}));raise
