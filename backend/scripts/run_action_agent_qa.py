"""Launch live QA on a fresh local PostgreSQL database and remove it on exit."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from action_release_postgres import isolated_environment


def main():
    folder = Path(__file__).resolve().parents[2] / '.local/action-agent-live-postgres'
    folder.mkdir(parents=True, exist_ok=True)
    with isolated_environment(folder, 'action', fast_disposable_evaluation=True) as isolated:
        return serve(isolated)


def serve(isolated):
    source = make_url(isolated['DATABASE_URL'])
    name = 'bs_payroll_action_agent_' + uuid4().hex[:16] + '_test'
    assert name != source.database
    admin = create_engine(source.set(database='postgres'), isolation_level='AUTOCOMMIT')
    quoted = admin.dialect.identifier_preparer.quote_identifier(name)
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE {quoted}')
    print('Created disposable live QA database', flush=True)
    env = dict(os.environ, SUITE_QA_POSTGRES_URL=source.set(database=name).render_as_string(hide_password=False))
    try:
        return subprocess.call([sys.executable, '-u', str(Path(__file__).with_name('action_agent_qa_server.py'))], env=env)
    finally:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE {quoted} WITH (FORCE)')
        admin.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
