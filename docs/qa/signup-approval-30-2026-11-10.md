# Signup and approval journey: 30 improvements

Release: `signup-journey-30`, 10 November 2026. Target: BestERP, with the
shared suite frontend mirrored to app.indianservers.com. Changes use existing
owner records and customer subscription JSON; no schema migration is required.
Existing approval-time trial contracts retain their start/end rules.

## Implemented scope

1. **Google-assisted signup:** verified identity prefill and an expiring,
   email-bound proof; a changed email clears verification.
2. **Email confirmation:** prominent final review and common-domain typo hints;
   suggestions never silently replace the address.
3. **Field errors:** linked error summary, stable accessible field names,
   field-level feedback and preserved answers after server rejection.
4. **Guided form:** Identity, Workspace needs and Review steps with Back actions.
5. **Drafts:** explicit device-local opt-in, 24-hour expiry, restoration,
   deletion, storage-error handling and clearing after submission. Passwords,
   consent selections and identity proofs are not stored in drafts.
6. **Policies:** linked operational application terms and privacy information;
   essential communications, optional marketing and optional analytics are distinct.
7. **Receipts:** durable reference, selected applications and private status link.
   Repeated public submissions remain non-enumerating.
8. **Progress:** applicant-safe timeline, business-hour review target and clear
   wording that the target is not a guaranteed decision time.
9. **Status refresh:** bounded polling while visible, last-checked time and
   terminal-state stop; refresh does not repeatedly announce loading.
10. **Outcome guidance:** separate approval, correction, rejection and withdrawal
    copy, applicant-facing messages and Help links.
11. **Status discovery:** visible entry on login/signup and direct
    `/login?application=1` access without a pending-account password.
12. **Targeted corrections:** reviewer-selected fields, per-field instructions,
    prior-value preview, single-use correction link and audited changes.
13. **Review summary:** identity, verified-email status, requested apps, age,
    review ownership and duplicate findings in the decision workspace.
14. **Atomic checklist:** save checklist with the decision; independent review
    draft saving remains available.
15. **Decision preview:** recipient, workspace, company-scoped administrator
    grant, applications, seats, exact/readable storage and trial-start rule.
16. **Routing:** configurable module reviewer/least-loaded fallback and
    business-hour overdue escalation; existing unassigned filters remain available.
17. **Concurrent decisions:** modern operator review requires the inspected
    version. Stale decisions are blocked; authorization is checked first.
18. **Duplicates:** navigable candidate records and auditable resolutions;
    matched/existing-customer decisions block duplicate workspace provisioning.
19. **Communications:** owner-side durable intent bridges to the existing
    transactional outbox for receipts, corrections, decisions, acknowledgements,
    reminders and explicit resends. Stable event keys protect bridge retries.
20. **Delivery truth:** separate review/workspace/sign-in/email states, provider
    acceptance wording, failure/reconciliation states and guarded fresh-link actions.
21. **Reviewer alerts:** configurable reviewer email, assignment-aware alerts,
    notification preferences and deduplicated overdue reminders.
22. **Link recovery:** expired setup/status links lead to a uniform-response,
    throttled fresh-link request; approved applicants can request fresh password setup.
23. **Sign-in choice:** approved invitation shows matching Google identity and
    one-time email/password setup as alternatives; workspace hints are preserved.
24. **Private/public reasons:** internal assessment and applicant message are
    distinct; internal notes are not copied into applicant mail/status responses.
25. **Activation recovery:** approved requests expose incomplete-step retry and
    readable failure records. Existing receipts prevent duplicate workspaces;
    recovery never reactivates an intentionally restricted customer.
26. **Workspace discovery:** verified social identities resolve approved dedicated
    placements; choices include an eligible existing shared workspace. Arbitrary
    client-selected destinations are rejected and tenant-bound sessions are retained.
27. **Trial rules:** configurable approval-time or first-successful-sign-in
    start, with an activation deadline. Repeated sign-ins do not extend a trial.
28. **Welcome checklist:** company profile, team and first useful action, with
    optional skip and approved-module links. Requested sample data remains an
    explicit, confirmed, reversible import rather than an automatic write.
29. **Accessibility:** keyboard error navigation, explicit labels, live status,
    focused/native decision modal with Tab containment and focus restoration,
    mobile layout and larger applicant action targets.
30. **Funnel:** scoped submission/decision/sign-in/checklist milestones, source
    counts and deduplicated opt-in coarse form events. First useful action is
    explicitly labelled customer-reported. A durable cursor cycles milestone
    synchronization without starving older approved customers.

## Validation

- **99 backend regression tests passed:** public signup, operator portal,
  Firebase module login, platform security boundaries and new journey tests.
- **Compiled browser journey passed, 19 checkpoints:** signup, error focus,
  draft recovery, receipt, mobile pending page, owner login, correction,
  atomic checklist, modal keyboard containment, stale decision, approval,
  invitation choice, password setup, customer sign-in, welcome checklist,
  rejection, withdrawal and expired-link recovery.
- **PostgreSQL API verification passed:** the isolated candidate source used
  the production PostgreSQL schema/runtime roles inside two outer rollback-only
  transactions. It exercised signup, targeted correction, versioned approval,
  invitation preview, password setup, sign-in and authorized onboarding. After
  rollback, no QA account, application or queued recipient email remained.
- TypeScript check and production frontend build passed. Visual inspection
  covered applicant mobile layout and the operator approval workspace.
- Deployed backend file hashes, API health, policies/options endpoints and
  frontend release metadata were verified after activation.
- Live browser checks passed on both besterp.app and app.indianservers.com:
  Google prefill entry, validation focus, policy content, visible status access,
  expired invitation recovery and anonymous rejection by the operator API.
  Neither tested mobile viewport overflowed horizontally; no JavaScript errors
  were observed. The production signup-mail worker initialized successfully.

Synthetic QA does not send email to real applicants. Delivery is verified to
the durable outbox, including idempotent bridging and provider-acceptance state
propagation. The existing provider worker performs actual delivery. Google
identity rules use signed test identities; QA does not sign in to a real user's
Google account. Keyboard/mobile checks are not a full accessibility certification.
New instrumentation does not reconstruct unrecorded historical conversion events.

## Reproduce

From `backend`, run the five regression files:

```text
venv/Scripts/python -m pytest tests/test_signup_journey.py tests/test_public_signup.py tests/test_platform_portal.py tests/test_firebase_pms_login.py tests/test_security_platform_boundary.py -q
```

The browser runner is `qa/signup_approval_30.cjs`. Start a candidate frontend
preview, set `RUN_SIGNUP_BROWSER=1` and `SIGNUP_FRONTEND_ORIGIN` to that preview,
then run `tests/test_signup_browser_journey.py`. The localhost bridge forwards
to the full ASGI application using the isolated test stores; it does not replace
the signup/approval endpoints with response mocks.

## Rollout and recovery

The build is based on the previous live frontend with only the 14 journey files
overlaid. Backend candidates preserve full relative paths, have before/after
hashes, and exclude unrelated in-progress development imports. Application
credentials and hosting configuration are unchanged.

The private server release record is
`/srv/business-suite/shared/signup-30-20261110`. It contains the backend manifest,
prior backend files, verified platform dump, frontend archive and previous/current
frontend links. Prior frontend assets are retained for open tabs. Activation
checks the expected live hashes and uses the deployment lock. Backend failure
restores the previous source files; data is never automatically rolled back,
so valid submissions arriving after deployment are preserved.
