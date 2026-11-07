"""Run the customization runtime suite in a new, disposable LOCAL database."""
import os
from pathlib import Path
import subprocess
import sys
import uuid
import socket

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy.engine import URL
import psycopg
from psycopg import sql


def main():
    identity = uuid.uuid4().hex[:12]
    name = 'bs_customization_' + identity + '_test'
    binaries = ROOT.parent / '.local' / 'postgresql' / 'pgsql' / 'bin'
    if not (binaries / 'initdb.exe').is_file():
        raise SystemExit('The repository local PostgreSQL binaries are required.')
    cluster = ROOT.parent / '.local' / ('customization-pg-' + identity)
    cluster.mkdir()
    data = cluster / 'data'
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    def pg(program, *args):
        # A detached Windows postgres process can inherit a captured pipe and
        # keep communicate() waiting after pg_ctl has exited. Use a log file.
        with (cluster / 'tools.log').open('a', encoding='utf-8') as log:
            result = subprocess.run([str(binaries / program), *map(str, args)], creationflags=flags, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError('Local PostgreSQL tool failed; inspect the isolated cluster tools.log')
    pg('initdb.exe', '-D', data, '-U', 'customization_test', '--auth=trust', '--encoding=UTF8', '--locale=C')
    pg('pg_ctl.exe', '-D', data, '-l', cluster / 'server.log', '-o', f'-h 127.0.0.1 -p {port} -c max_locks_per_transaction=256', '-w', 'start')
    url = URL.create('postgresql+psycopg', username='customization_test', host='127.0.0.1', port=port, database=name)
    admin_url = url.set(drivername='postgresql', database='postgres')
    tests = sys.argv[1:] or ['tests/test_customization_runtime.py']
    output = ROOT.parent / 'outputs' / ('industry-packs-phase-2' if any('industry_packs' in name for name in tests) else 'customization-phase-1')
    output.mkdir(parents=True, exist_ok=True)
    try:
        with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as admin:
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            environment = dict(os.environ)
            test_url = url.set(database=name).render_as_string(hide_password=False)
            environment.update(TEST_DATABASE_URL=test_url, PLATFORM_DATABASE_URL=test_url,
                TENANT_DATABASES_ENABLED='false', FAST_TEST_PASSWORD_HASHES='1')
            print('Running customization tests in an isolated local PostgreSQL database.', flush=True)
            return subprocess.call([sys.executable, '-m', 'pytest', *tests,
                '-q', '--disable-warnings', '--tb=short', f'--junitxml={output / "postgresql.xml"}'], cwd=ROOT, env=environment)
    finally:
        pg('pg_ctl.exe', '-D', data, '-m', 'fast', '-w', 'stop')
        print('Stopped the isolated PostgreSQL test cluster. Logs remain in the ignored .local directory.', flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
