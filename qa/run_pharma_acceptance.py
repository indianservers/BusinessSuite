"""Run Pharma acceptance against a new, owned local PostgreSQL database."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url, URL

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--public-returns-only', action='store_true')
    parser.add_argument('--report-name', choices=['pharma-postgresql', 'pharma-public-returns', 'pharma-recall-browser', 'pharma-three-decimal-postgresql'])
    args, extra = parser.parse_known_args()
    values = dotenv_values(args.env_file)
    source = make_url(values['DATABASE_URL']) if values.get('DATABASE_URL') else URL.create(
        'postgresql+psycopg', username=values.get('POSTGRES_USER', 'business_suite'),
        password=values.get('POSTGRES_PASSWORD', ''), host=values.get('POSTGRES_SERVER', '127.0.0.1'),
        port=int(values.get('POSTGRES_PORT', 5432)), database='postgres')
    if source.get_backend_name() != 'postgresql' or source.host not in {'localhost', '127.0.0.1', '::1'}:
        raise RuntimeError('A loopback PostgreSQL test administrator is required')
    name = 'business_suite_pharma_' + uuid4().hex + '_test'
    admin = create_engine(source.set(database='postgres'), isolation_level='AUTOCOMMIT', hide_parameters=True)
    quote = admin.dialect.identifier_preparer.quote_identifier
    created = False
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE {quote(name)}')
            created = True
        env = dict(os.environ, TEST_DATABASE_URL=source.set(database=name).render_as_string(hide_password=False),
                   FAST_TEST_PASSWORD_HASHES='1', RUN_CONTROL_BROWSER='1', ENVIRONMENT='test', DEBUG='false',
                   PLATFORM_DATABASE_URL='', TENANT_DATABASES_ENABLED='false', TENANT_REGISTRY_URL='',
                   TENANT_PROVISIONING_URL='', TENANT_ALLOW_REMOTE_OPERATIONS='false')
        tests = ['test_pharma_catalog', 'test_pharma_receipts', 'test_pharma_fefo', 'test_pharma_recalls',
                 'test_pharma_trace', 'test_pharma_legacy_stock_guards', 'test_pharma_recall_concurrency',
                 'test_pharma_allocation_concurrency', 'test_pharma_return_sources', 'test_pharma_browser',
                 'test_pharma_recall_browser', 'test_pharma_legacy_fam_browser', 'test_pharma_dispensing_precision',
                 'test_pharma_quantity_migration', 'test_pharma_precision_browser', 'test_pharma_precision_accounting', 'test_service_checkout',
                 'test_srm_native_transaction_operations', 'test_fam_srm_invoice_posting',
                 'test_fam_srm_posting_idempotency', 'test_fam_srm_receipt_posting']
        if args.public_returns_only:
            tests = ['test_pharma_return_sources', 'test_pharma_return_models', 'test_pharma_return_plan', 'test_return_quantity_precision']
        else:
            browser_tests = ['test_pharma_browser', 'test_pharma_recall_browser', 'test_pharma_legacy_fam_browser', 'test_pharma_precision_browser']
            tests = [name for name in tests if name not in browser_tests] + browser_tests
        report = 'pharma-public-returns' if args.public_returns_only else 'pharma-postgresql'
        report = args.report_name or report
        return subprocess.call([sys.executable, '-m', 'pytest', *['tests/'+name+'.py' for name in tests],
                                '-q', '--tb=short', '--junitxml=../outputs/'+report+'.xml', *extra],
                               cwd=ROOT/'backend', env=env)
    finally:
        if created:
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE {quote(name)} WITH (FORCE)')
        admin.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
