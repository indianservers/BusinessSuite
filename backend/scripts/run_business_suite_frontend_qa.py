"""Run existing isolated frontend harnesses, retaining every result and error."""
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    'test-common-routes.cjs', 'test-search-navigation.cjs',
    'test-navigation-workspaces.cjs', 'test-navigation-categories.cjs',
    'test-operations-workspaces.cjs', 'test-pms-personal-navigation.cjs',
    'test-navigation-guards.cjs', 'test-desktop-navigation.cjs',
    'test-navigation-branding.cjs', 'test-mobile-navigation.cjs',
    'test-background-refresh.cjs', 'test-record-cache.cjs',
    'test-record-list-refresh.cjs', 'test-record-mutations.cjs',
    'test-contact-picker.cjs', 'test-relationship-hub.cjs',
    'test-record-360.cjs', 'test-task-record-links.cjs',
    'test-validation.cjs', 'test-phone-selector.cjs',
    'test-currency-selector.cjs', 'test-accounting-connected.cjs',
    'test-inventory-edit-window.cjs', 'test-mobile-fam-workflows.cjs',
    'test-mobile-pms-notes.cjs', 'test-note-optimistic-save.cjs',
]


if __name__ == '__main__':
    output = ROOT / 'backend/outputs/business-suite-frontend-results.json'
    records = []
    for script in SCRIPTS:
        start = time.monotonic()
        try:
            result = subprocess.run(['node', 'scripts/'+script], cwd=ROOT/'frontend',
                                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
            record = {'script': script, 'status': 'PASS' if result.returncode == 0 else 'FAIL',
                      'exit_code': result.returncode, 'output': result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            record = {'script': script, 'status': 'BLOCKED', 'output': 'Harness exceeded 120 seconds'}
        record['seconds'] = round(time.monotonic()-start, 3)
        records.append(record)
        output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{record['status']}: {script} ({record['seconds']}s)", flush=True)
    raise SystemExit(1 if any(r['status'] != 'PASS' for r in records) else 0)
