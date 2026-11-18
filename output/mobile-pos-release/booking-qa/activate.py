import os,sys,json,tarfile,shutil,hashlib,fcntl,time,urllib.request,subprocess
from pathlib import Path
base=Path(sys.argv[1]); mode=sys.argv[2]
lock=open('/srv/business-suite/shared/deploy.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
release=Path('/srv/business-suite/current').resolve()
manifest=json.loads((base/'manifest.json').read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def health():
 with urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=20) as r:
  value=json.load(r);assert value['status']=='healthy' and value['db']=='ok',value
health()
if mode=='primary':
 assert str(release)==manifest['release'],'Production release changed; regenerate candidate'
 for name,checksum in manifest['baseline'].items():assert digest(release/name)==checksum,'Production source changed: '+name
 with tarfile.open(base/'backend.tar.gz') as t:t.extractall(base/'candidate',filter='data')
 for name in set(manifest['candidate'])-set(manifest['baseline']):assert not (release/name).exists(),'New source already exists: '+name
 for name,checksum in manifest['candidate'].items():
  assert digest(base/'candidate'/name)==checksum
  compile((base/'candidate'/name).read_bytes(),name,'exec')
new=Path('/srv/business-suite/suite-builds')/manifest['name'];new.mkdir(parents=True,exist_ok=False)
with tarfile.open(base/'frontend.tar.gz') as t:t.extractall(new,filter='data')
assert (new/'index.html').is_file()
static=release/'frontend/dist';old_target=static.resolve()
assert str(old_target)==manifest['previous_frontend'],'Production frontend changed; regenerate candidate'
if (old_target/'app-config.js').is_file():shutil.copy2(old_target/'app-config.js',new/'app-config.js')
# Retain hashed assets needed by tabs already open on the previous release.
for folder in ['assets','models']:
 source=old_target/folder
 if source.exists():
  for old in source.rglob('*'):
   if old.is_file():
    target=new/folder/old.relative_to(source)
    if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);os.link(old,target)
subprocess.run(['chmod','-R','u=rwX,go=rX',str(new)],check=True)
backup=base/'before';backup.mkdir(exist_ok=True)
state={'release':str(release),'old_static':str(old_target),'new_static':str(new),'mode':mode}
(base/'activation.json').write_text(json.dumps(state))
changed=[];switched=False;old_directory=None
try:
 if mode=='primary':
  for name in manifest['candidate']:
   target=release/name;before=backup/name;before.parent.mkdir(parents=True,exist_ok=True)
   if target.exists():shutil.copy2(target,before)
   pending=target.with_name(target.name+'.appointments-next');shutil.copy2(base/'candidate'/name,pending);pending.chmod(target.stat().st_mode & 0o777 if target.exists() else 0o644);os.replace(pending,target);changed.append(name)
  subprocess.run(['systemctl','restart','business-suite.service'],check=True)
  for attempt in range(30):
   try:
    with urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3) as r:
     value=json.load(r);assert value.get('status')=='healthy' and value.get('db')=='ok'
    break
   except Exception:
    if attempt==29:raise
    time.sleep(1)
 if static.is_symlink():
  pending=static.with_name('dist.appointments-next');pending.symlink_to(new);os.replace(pending,static)
 else:
  old_directory=static.with_name('dist.before-'+manifest['name']);os.rename(static,old_directory);static.symlink_to(new)
 switched=True
 health()
 state.update(status='ready',old_directory=str(old_directory) if old_directory else None)
 (base/'activation.json').write_text(json.dumps(state))
 print(json.dumps(state))
except BaseException:
 if switched:
  if old_directory:static.unlink();os.rename(old_directory,static)
  else:
   pending=static.with_name('dist.appointments-rollback');pending.symlink_to(old_target);os.replace(pending,static)
 for name in changed:
  if (backup/name).exists():shutil.copy2(backup/name,release/name)
  else:(release/name).unlink()
 if changed:subprocess.run(['systemctl','restart','business-suite.service'],check=True)
 state['status']='rolled_back';(base/'activation.json').write_text(json.dumps(state));raise
