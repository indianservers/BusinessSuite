# Shared Forms browser audit — 2026-10-24

## Result

Production frontend build passed. `pytest tests/test_shared_forms.py tests/test_pms_forms.py -q --disable-warnings --tb=short` passed: **21 tests** (17 shared tests, including two migration parametrizations; four existing PMS tests). TypeScript checking passed as part of the build. Focused ESLint (`npx eslint src/features/forms --ext ts,tsx`) passed with no output. The final audit also corrected and regression-tested numeric condition comparisons without rounding. The existing Browserslist dataset warning is unrelated to Forms.

All browser data was synthetic, using a dedicated temporary SQLite database named `businesssuite-commercial-forms-browser.db`, loopback API port 8776, and a dedicated Vite server on port 5176. The pre-existing server on port 5191 was left untouched. No deployed database was modified.

## Browser checks completed

- Created/saved a form, searched the palette, added/configured dropdowns, edited required fields and help/options.
- Added, duplicated and deleted questions; moved them with up/down buttons, keyboard drag and pointer drag. Read the resulting DOM order after dragging.
- Published, copied the public URL, inspected embed code, and opened the actual `/f/<slug>` route without the management shell. Explicit logged-out harness also opened the public form.
- Submitted an incorrect security code: server rejected it and stored no response. Refreshed codes. Positive anonymous CAPTCHA, expiry, single-use, replay, rate-limit, quota and failure paths were covered by API tests. The browser audit did not solve a CAPTCHA.
- Reused a real global field definition and options; inspected the Custom fields reference page and management link.
- Published an upload field and native PMS task action. Submitted through the authenticated internal response page with an actual PNG file and a global-field answer. The real UI showed Response received; response details showed the attachment, selected global option, and created task #1.
- Marked the response reviewed. Downloaded its private attachment; SHA-256 matched the original fixture. Downloaded CSV and verified the browser-created response and reviewed status.
- Duplicated the form as a draft with public access disabled. Configured a page break, multipage navigation and serif styling; completed the preview and verified **zero responses** for that copy.
- Closed the public form; actual public URL showed “This form is closed”. Republished and verified the public form reopened.
- Opened shared Forms routes under PMS, SRM, CRM, HRMS and FAM. Sidebar Forms entry and page navigation were present.
- Builder at 390px and anonymous public responder at 320px had no horizontal overflow. The 320px iframe's document client/scroll widths were both 314px after scrollbar space.
- Final builder and actual public-page browser error logs were empty. Earlier temporary harness load errors occurred while restarting the isolated QA server, then cleared on reload.

## Screenshots

- [Builder](builder-desktop.png) and [field editing detail](builder-fields.png)
- [Public publishing and embed](public-publishing.png)
- [Actual public URL](public-url.png)
- [Mobile public form](public-mobile-320.png)
- [Response with task and attachment](responses-with-task.png)
- [Global field reference](global-fields-reference.png)
- [Multipage preview](multipage-preview.png)
- [Closed public form](closed-public-form.png)

The first response was seeded for response-list testing. The second response, uploaded image, and linked PMS task were created through the browser. Positive anonymous spam verification was tested with a deterministic code fixture at the API layer, not a CAPTCHA bypass in the browser. Live Turnstile requires configured site keys and remains unverified against the external provider.

## Reproduce

From `backend`, start `venv/Scripts/python.exe -m uvicorn scripts.run_forms_browser_qa:app --host 127.0.0.1 --port 8776`. The runner restricts itself to a named synthetic temporary database. Optionally run `venv/Scripts/python.exe -m scripts.seed_forms_browser_qa` after creating the example form.

From `frontend`, run `node scripts/prepare-forms-browser-qa.cjs`, then start Vite on 127.0.0.1:5176 with `VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:8776`. Open `/__forms-qa.html?path=/pms/forms`, or `/__forms-qa.html?public=1&path=/f/<slug>`. The helper can create a synthetic authenticated QA session; never deploy the QA server. Remove the generated `__forms-qa.html` and `__forms-mobile-qa.html` after auditing.

The production frontend build does not include these temporary HTML harnesses. The synthetic upload fixture is in `fixtures/project-brief.png`.
