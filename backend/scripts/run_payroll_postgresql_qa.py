"""Provision and stop an isolated loopback PostgreSQL cluster for payroll QA."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]


def main():
    identity = uuid.uuid4().hex[:12]
    cluster = ROOT / '.local' / ('payroll-qa-pg-' + identity)
    cluster.mkdir(parents=True)
    binary = ROOT / '.local/postgresql/pgsql/bin'
    if not (binary/'initdb.exe').is_file():
        raise RuntimeError('Repository local PostgreSQL binaries required')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0)); port = probe.getsockname()[1]
    name = 'bs_payroll_' + identity + '_test'
    url = URL.create('postgresql+psycopg',username='payroll_qa',host='127.0.0.1',port=port,database=name)
    data = cluster/'data'
    def pg(program,*args):
        with (cluster/'tools.log').open('a',encoding='utf-8') as log:
            subprocess.run([str(binary/program),*map(str,args)],check=True,creationflags=subprocess.CREATE_NO_WINDOW,
                           stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    pg('initdb.exe','-D',data,'-U','payroll_qa','--auth=trust','--encoding=UTF8','--locale=C')
    pg('pg_ctl.exe','-D',data,'-l',cluster/'server.log','-o',f'-h 127.0.0.1 -p {port} -c max_locks_per_transaction=256','-w','start')
    try:
        with psycopg.connect(url.set(drivername='postgresql',database='postgres').render_as_string(hide_password=False),autocommit=True) as admin:
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        environment = dict(os.environ)
        connection = url.render_as_string(hide_password=False)
        environment.update(TEST_DATABASE_URL=connection,DATABASE_URL=connection,PLATFORM_DATABASE_URL=connection,
            TENANT_DATABASES_ENABLED='false',FAST_TEST_PASSWORD_HASHES='1',ENVIRONMENT='test',DEBUG='false')
        print(f'Isolated local PostgreSQL QA: {name}, cluster {cluster.name}',flush=True)
        args = sys.argv[1:]
        if args and args[0]=='--browser':
            with socket.socket() as backend_probe, socket.socket() as frontend_probe:
                backend_probe.bind(('127.0.0.1',0));frontend_probe.bind(('127.0.0.1',0))
                backend_port=backend_probe.getsockname()[1];frontend_port=frontend_probe.getsockname()[1]
            environment['SUITE_QA_POSTGRES_URL']=connection
            environment['PAYROLL_QA_API']=f'http://127.0.0.1:{backend_port}/api/v1'
            environment['PAYROLL_QA_BACKEND_PORT']=str(backend_port)
            environment['PAYROLL_QA_FRONTEND_PORT']=str(frontend_port)
            environment['PAYROLL_QA_VITE_CACHE']=f'../.tmp/payroll-postgres-vite-{identity}'
            environment['PLAYWRIGHT_JSON_OUTPUT_FILE']=str(ROOT/'.tmp/payroll-postgresql-browser-results.json')
            return subprocess.call(['cmd','/c','npx','playwright','test','--config=playwright.payroll-postgresql.config.ts','--reporter=json'],cwd=ROOT/'frontend',env=environment)
        if not args:
            # Committed multi-connection fixtures get their own cluster/run.
            args = [str(path.relative_to(ROOT/'backend')) for path in sorted((ROOT/'backend/tests').glob('test_payroll*.py')) if path.name!='test_payroll_qa_concurrency.py']
            args += ['tests/'+name+'.py' for name in ['test_hrms_leave_payroll_feeds','test_expense_payroll_linkage','test_payslip_workflow','test_leave','test_leave_accrual_carry_forward','test_employees','test_attendance','test_attendance_logging','test_attendance_punch_api','test_salary_structure_versioning','test_security_employee_scope','test_employee_roles_managers','test_hrms_fnf_settlements','test_exit_date_integrity']]
        result_file=os.environ.get('PAYROLL_PG_RESULT_FILE','payroll-postgresql-results.xml')
        return subprocess.call([sys.executable,'-m','pytest',*args,'-q','--tb=short','-o','junit_family=xunit1',f'--junitxml=../.tmp/{result_file}'],cwd=ROOT/'backend',env=environment)
    finally:
        pg('pg_ctl.exe','-D',data,'-m','fast','-w','stop')
        print('Isolated PostgreSQL cluster stopped; logs retained in .local.',flush=True)


if __name__=='__main__':
    raise SystemExit(main())
