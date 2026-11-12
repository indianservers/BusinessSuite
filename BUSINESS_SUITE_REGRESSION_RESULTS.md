# Business Suite regression results

Unique latest backend test nodes: 465 — {'PASS': 462, 'BLOCKED': 3}.
Frontend harnesses: 26 — {'PASS': 26}.

## Completed runs

- `business-suite-postgres-regression.xml`: 104 test nodes — {'PASS': 103, 'FAIL': 1}.
- `business-suite-pos-after.xml`: 18 test nodes — {'PASS': 17, 'FAIL': 1}.
- `business-suite-postgres-fixes-verified.xml`: 17 test nodes — {'PASS': 16, 'FAIL': 1}.
- `business-suite-gst-after.xml`: 61 test nodes — {'PASS': 61}.
- `business-suite-masterdata-after.xml`: 37 test nodes — {'PASS': 36, 'BLOCKED': 1}.
- `business-suite-crossmodule-security.xml`: 209 test nodes — {'PASS': 208, 'BLOCKED': 1}.
- `business-suite-postgres-acceptance.xml`: 193 test nodes — {'PASS': 193}.
- `business-suite-final-fixes.xml`: 77 test nodes — {'PASS': 77}.
- `business-suite-postgres-final.xml`: 82 test nodes — {'PASS': 81, 'FAIL': 1}.
- `business-suite-live-browser.xml`: 1 test nodes — {'PASS': 1}.
- `business-suite-pos-latest.xml`: 22 test nodes — {'PASS': 22}.
- `business-suite-commercial-links.xml`: 1 test nodes — {'PASS': 1}.
- `business-suite-postgres-closure.xml`: 24 test nodes — {'PASS': 24}.
- `business-suite-operator-after.xml`: 48 test nodes — {'PASS': 43, 'BLOCKED': 2, 'FAIL': 3}.
- `business-suite-regression-repairs.xml`: 48 test nodes — {'PASS': 46, 'BLOCKED': 2}.
- `business-suite-knowledge-retest.xml`: 6 test nodes — {'PASS': 6}.

## Full repository baseline

Observed progress: 1800 / 6496. Completed: False.
The baseline began before fixes. Targeted current-code reruns override matching nodes in the deduplicated totals; unverified failures remain failures.

## Reproduce

`powershell -File backend/scripts/run_business_suite_postgres_qa.ps1` creates a fresh localhost-only QA cluster, runs the selected real PostgreSQL scenarios, stops it, and retains artifacts.
`backend/venv/Scripts/python.exe backend/scripts/run_business_suite_frontend_qa.py` runs all selected isolated frontend harnesses.
From `backend`: `venv/Scripts/python.exe -m pytest -q --junitxml=outputs/full-regression.xml` runs the full repository suite. It is considerably larger than the business acceptance matrix.
From `frontend`: `npm run test:common-routes` and `npx tsc --noEmit`.

No production migration, verified production backup or deployment was performed; none was needed for these code-only fixes.