# Business Suite regression results

Unique latest backend test nodes: 6657 — {'PASS': 6598, 'BLOCKED': 59}.
Frontend harnesses: 27 — {'PASS': 27}.

## Completed runs

- Frontend `npm run typecheck`: exit 0; main app, Node and interns-hub configurations. Evidence: `backend/outputs/business-suite-frontend-typecheck.json` and `.log`.
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
- `business-suite-full-final.xml`: 6612 test nodes — {'PASS': 6541, 'BLOCKED': 62, 'FAIL': 9}.
- `business-suite-full-failures-after.xml`: 9 test nodes — {'PASS': 8, 'FAIL': 1}.
- `business-suite-adjacent-regression.xml`: 207 test nodes — {'PASS': 205, 'BLOCKED': 1, 'FAIL': 1}.
- `business-suite-postgres-final-repairs.xml`: 3 test nodes — {'PASS': 3}.
- `business-suite-inventory-final.xml`: 1 test nodes — {'PASS': 1}.
- `business-suite-full-verified.xml`: 6655 test nodes — {'PASS': 6588, 'BLOCKED': 63, 'FAIL': 4}.
- `business-suite-request-limits-final.xml`: 18 test nodes — {'PASS': 17, 'BLOCKED': 1}.
- `business-suite-presentations-final.xml`: 15 test nodes — {'PASS': 15}.
- `business-suite-analytics-final.xml`: 9 test nodes — {'PASS': 9}.
- `business-suite-pms-timezone-final.xml`: 20 test nodes — {'PASS': 20}.
- `business-suite-postgres-pms-timezone.xml`: 3 test nodes — {'PASS': 3}.
- `business-suite-live-browser-final.xml`: 1 test nodes — {'PASS': 1}.

## Full repository regression

Observed progress: 6655. Completed: True.
The final verification uses six isolated workers after the full-run corrections. Its results take precedence over targeted runs. The earlier completed run found nine failures; its XML is retained as business-suite-full-final.xml. The stopped serial pre-fix baseline reached 28%; its log is also retained.

## Reproduce

`powershell -File backend/scripts/run_business_suite_postgres_qa.ps1` creates a fresh localhost-only QA cluster, runs the selected real PostgreSQL scenarios, stops it, and retains artifacts.
`backend/venv/Scripts/python.exe backend/scripts/run_business_suite_frontend_qa.py` runs all selected isolated frontend harnesses.
From `backend`: `venv/Scripts/python.exe -m pytest -q --junitxml=outputs/full-regression.xml` runs the full repository suite. It is considerably larger than the business acceptance matrix.
From `frontend`: `npm run test:common-routes` and `npx tsc --noEmit`.

No production migration, verified production backup or deployment was performed; none was needed for these code-only fixes.