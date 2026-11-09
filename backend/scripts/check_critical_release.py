"""Run repeatable local release gates; never deploy or contact live providers.

Run with backend/venv/Scripts/python.exe backend/scripts/check_critical_release.py.
Successful local gates do not certify PostgreSQL or deployed provider delivery.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
TESTS = [
    'test_crm_lead_workflow.py',
    'test_crm_quote_to_srm_conversion.py',
    'test_crm_quote_calculation.py',
    'test_crm_quote_approval.py',
    'test_crm_quote_versioning.py',
    'test_crm_quote_rbac.py',
    'test_srm_crm_won_handoff.py',
    'test_crm_integration_controls.py',
    'test_customer_communications.py',
    'test_shared_email.py',
    'test_whatsapp_workspace.py',
    'test_whatsapp_cloud.py',
    'test_communication_email_send.py',
    'test_communication_opt_out.py',
    'test_communication_campaign_consent.py',
    'test_srm_invoice_engine.py',
    'test_srm_invoice_duplicate_prevention.py',
    'test_fam_srm_invoice_posting.py',
    'test_srm_receipts.py',
    'test_srm_receipt_allocation.py',
    'test_fam_srm_receipt_posting.py',
    'test_conditional_action_permissions.py',
    'test_srm_handoff_idempotency.py',
    'test_hrms_operational_foundations.py',
    'test_exit_date_integrity.py',
    'test_hr_workbench.py',
    'test_onboarding.py',
    'test_attendance_punch_api.py',
    'test_leave.py',
    'test_payroll_readiness_gate.py',
    'test_payroll_run_state_machine.py',
    'test_automation_approvals.py',
    'test_srm_collection_reminders.py',
    'test_deployment_readiness.py',
    'test_schema_health.py',
]


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT / '.local' / 'release-readiness' / stamp
    output.mkdir(parents=True)
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        print('Node/npm is required for the production build.', file=sys.stderr)
        return 1
    gates = [
        ('critical-backend', ROOT / 'backend', [sys.executable, '-m', 'pytest',
            *[f'tests/{name}' for name in TESTS], '-q', '--disable-warnings',
            '--tb=short', f'--junitxml={output / "backend.xml"}']),
        ('record-cache-regressions', ROOT / 'frontend', [npm, 'run', 'test:record-cache']),
        ('production-build', ROOT / 'frontend', [npm, 'run', 'build']),
    ]
    results = []
    # Serial execution avoids adding build contention to timed API tests.
    for name, cwd, command in gates:
        print(f'Running {name}; evidence: {output / (name + ".log")}', flush=True)
        with (output / f'{name}.log').open('w', encoding='utf-8') as log:
            try:
                result = subprocess.run(command, cwd=cwd, stdout=log,
                    stderr=subprocess.STDOUT, timeout=1800, check=False)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
                log.write('\nGate exceeded the 30-minute local execution limit.\n')
            except OSError as exc:
                code = 1
                log.write(f'Unable to start gate: {exc.__class__.__name__}\n')
        results.append({'gate': name, 'exit_code': code, 'passed': code == 0})
        print(f'{name}: {"passed" if code == 0 else "failed"}', flush=True)
    summary = {
        'created_at_utc': stamp,
        'scope': 'local automated release gates only',
        'passed': all(item['passed'] for item in results),
        'gates': results,
        'not_certified': [
            'Deployed browser workflows and production configuration',
            'Live SES/WhatsApp delivery and inbound callbacks',
            'PostgreSQL migrations, concurrency and restore drill',
            'Production deployment and rollback',
        ],
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(f'Release evidence: {output / "summary.json"}')
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
