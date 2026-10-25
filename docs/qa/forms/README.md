# Forms visual editor

Open any module's Forms → Create form → Build. The default view is now a visual canvas using the same FormResponse renderer as published forms. Click a question to select it; edit its label directly on the canvas or change its rules, placeholder, help, options and width in the properties panel. Arrange fields retains drag ordering, keyboard ordering, duplication and deletion, including existing conditional dependency checks.

Layout & appearance controls one/two/three columns, minimal/soft/gradient surfaces, brand color and an optional introduction with editable badge, headline and description. Full-row questions span the grid. The introduction hides on mobile, where fields collapse to one column. Preview offers desktop and 390px modes with live answer controls and the existing validators. Conditional fields are all visible while editing so hidden questions remain selectable; actual conditions apply in Preview and published forms.

The internship application template provides a starting layout inspired by the supplied reference, without a required résumé upload. It creates a generic form, not an automatic intern onboarding integration. Existing workflow and response collection behavior is retained.

## Persistence and compatibility

Presentation settings are bounded, typed properties of the existing JSON form definition, and field width is an optional/defaulted question property. No database migration is required. Older definitions default to one column without an introduction. Draft save and published snapshots retain presentation settings. No arbitrary HTML, JavaScript or CSS is accepted by the new controls.

## Verification

- `../forms-tests.log`: 25 shared Forms/PMS backend tests passed. Added tests verify public snapshot persistence and reject unsupported columns, surfaces and oversized text.
- `../forms-build.log`: TypeScript and production Vite build passed.
- Browser QA used disposable SQLite fixtures with providers disabled, not the configured business database. Verified template creation, inline label editing, draft save, production-build reopen, three-column desktop layout, 390px single-column preview, hidden introduction and invalid phone inline feedback.
- Evidence: `visual-editor.png`, `desktop-preview.png`, `mobile-preview.png`.
- The visual preview at 390px was verified; this is not a claim that every browser/device or field interaction was individually tested.

## Changed implementation

- `frontend/src/features/forms/FormBuilder.tsx`: visual canvas and arrangement views, field selection, inline labels, template and properties.
- `frontend/src/features/forms/FormAppearance.tsx`: shared layout and introduction controls.
- `frontend/src/features/forms/FormResponse.tsx`: shared presentation renderer with editing hooks.
- `frontend/src/features/forms/FormsPage.tsx`, `FormsPage.css`, `formsTypes.ts`: design integration, responsive styling, preview device controls and definition types.
- `backend/app/forms/settings.py`, `schema.py`: validated, backward-compatible presentation properties.
- `backend/tests/test_shared_forms.py`: design snapshot and input validation tests.
