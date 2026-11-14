"""One disposable local PostgreSQL database per release evaluation invocation."""
import os
import socket
import subprocess
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from sqlalchemy.engine import make_url


def environment(folder,kind,database_uri=None):
    if kind not in {'action','message'}:raise ValueError('Unsupported release evaluation kind')
    if database_uri is None:
        from app.core.config import settings
        database_uri=str(settings.SQLALCHEMY_DATABASE_URI)
    url=make_url(database_uri)
    if url.get_backend_name()!='postgresql' or url.host not in {'127.0.0.1','localhost','::1'}:
        raise ValueError('Release evaluation requires disposable local PostgreSQL')
    # A fresh name prevents a concurrent evaluator from dropping another run's
    # database. Provisioning credentials exist only in the child environment.
    name='business_suite_'+kind+'_release_'+uuid4().hex[:20]+'_test'
    if name==url.database:raise ValueError('Evaluation cannot target the application database')
    folder=Path(folder).resolve()
    env=dict(os.environ,DATABASE_URL=url.render_as_string(hide_password=False),POSTGRES_TEST_DATABASE=name,
             LOCAL_NLP_MODEL_DIR=str(folder),LOCAL_NLP_TRAINING_DIR=str(folder/('isolated-'+kind+'-evaluation')),ENVIRONMENT='test',POSTGRES_TEST_CLEANUP='1',FAST_TEST_PASSWORD_HASHES='1',UPLOAD_DIR=str(folder/('isolated-'+kind+'-uploads')))
    env.pop('TEST_DATABASE_URL',None)
    return env


@contextmanager
def isolated_environment(folder,kind):
    """Reuse the bundled QA PostgreSQL runtime without granting the app CREATEDB.

    Each evaluator owns its cluster, loopback port and retained diagnostic files.
    No application database or application database credential is used.
    """
    folder=Path(folder).resolve()
    if kind not in {'action','message'}:raise ValueError('Unsupported release evaluation kind')
    binary=Path(__file__).resolve().parents[2]/'.local/postgresql/pgsql/bin'
    suffix='.exe' if os.name=='nt' else ''
    initdb=binary/('initdb'+suffix);pgctl=binary/('pg_ctl'+suffix)
    if not initdb.is_file() or not pgctl.is_file():
        raise ValueError('Bundled local PostgreSQL QA runtime is unavailable')
    root=folder/('isolated-'+kind+'-postgres-'+uuid4().hex[:16])
    root.mkdir(parents=True,exist_ok=False)
    data=root/'data'
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    def run(arguments,log):
        with (root/log).open('wb') as output:
            subprocess.run(arguments,stdout=output,stderr=subprocess.STDOUT,check=True,timeout=60,**flags)
    run([str(initdb),'-D',str(data),'-U','qa_suite','--auth=trust','--encoding=UTF8','--no-locale'],'initdb.log')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    with (data/'postgresql.conf').open('a',encoding='utf-8') as config:
        config.write(f"\nlisten_addresses = '127.0.0.1'\nport = {port}\nmax_locks_per_transaction = 512\n")
    # A failed start may still leave our child alive; stop only this exact data dir.
    try:
        run([str(pgctl),'-D',str(data),'-l',str(root/'server.log'),'-w','start'],'start.log')
        yield environment(folder,kind,f'postgresql+psycopg://qa_suite@127.0.0.1:{port}/postgres')
    finally:
        if (data/'postmaster.pid').exists():
            run([str(pgctl),'-D',str(data),'-m','fast','-w','stop'],'stop.log')
