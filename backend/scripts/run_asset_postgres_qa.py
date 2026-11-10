"""Run asset QA on a new local disposable PostgreSQL cluster, never the app DB."""
import os, socket, subprocess, sys, uuid
from pathlib import Path
root=Path(__file__).resolve().parents[2]
pg=root/'.local/postgresql/pgsql/bin'
folder=root/'.local'/('asset-lifecycle-pg-'+uuid.uuid4().hex[:10])
folder.mkdir(parents=True)
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
def run(*args):subprocess.run([str(a) for a in args],check=True,**flags)
run(pg/'initdb.exe','-D',folder/'data','-U','asset_qa','-A','trust','-E','UTF8','--no-locale')
started=False
try:
    run(pg/'pg_ctl.exe','-D',folder/'data','-l',folder/'server.log','-o',f'-h 127.0.0.1 -p {port}','-w','start');started=True
    run(pg/'createdb.exe','-h','127.0.0.1','-p',port,'-U','asset_qa','assets_lifecycle_test')
    env=dict(os.environ,TEST_DATABASE_URL=f'postgresql+psycopg://asset_qa@127.0.0.1:{port}/assets_lifecycle_test',FAST_TEST_PASSWORD_HASHES='1',ENVIRONMENT='test')
    tests=sys.argv[1:] or ['tests/test_asset_lifecycle.py','tests/test_asset_controls.py','tests/test_asset_concurrency.py','tests/test_exit_date_integrity.py']
    with (folder/'pytest.log').open('w',encoding='utf-8') as log:
        result=subprocess.call([sys.executable,'-m','pytest',*tests,'-q','--disable-warnings','--tb=short','--junitxml='+str(folder/'results.xml')],cwd=root/'backend',env=env,stdout=log,stderr=subprocess.STDOUT,**flags)
    print((folder/'pytest.log').read_text(encoding='utf-8')[-16000:],flush=True)
    print('Isolated asset QA output:',folder,flush=True)
    raise SystemExit(result)
finally:
    if started:run(pg/'pg_ctl.exe','-D',folder/'data','-m','fast','-w','stop')
