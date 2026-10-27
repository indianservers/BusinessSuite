# Phase 5 security verification

## Automated cases

- Unauthorized decision and cross-company access are denied. Requesters cannot approve their own requests. Workflow authorship alone grants no decision authority.
- Explicit participation permits linked execution history reads without granting generic execution mutation or resume authority. Generic resume cannot bypass an approval wait.
- Signed evidence verifies row timestamps, actor identity, policy/request snapshots, previous hashes, decision state and document hashes. Direct record tampering is detected and cannot be repaired by submitting another vote.
- Completed assignment seats and audit events reject ORM mutation. Idempotent decision replays do not create duplicate votes. Concurrent independent PostgreSQL decision transactions yield a single valid winner for any-one approval.
- Delegation checks eligible independent identities, time windows and authority. Expiration removes delegated authority. Missing groups cannot be repaired by silently shrinking the quorum.
- Documents require authenticated participant access, company/environment isolation and hash verification. Downloads use attachment disposition, nosniff and a sandbox policy. Public upload serving does not expose approval blobs.
- A real worker subprocess can stop with an outstanding wait and a replacement worker resumes the approved workflow from the persisted queue.
- Both migration variants preserve existing approval request data through isolated upgrade/downgrade tests.

## Limits of this report

These are source-level, API, isolated PostgreSQL and browser checks, not an independent penetration test. Signing-key compromise, production infrastructure, malware scanning, external notification delivery and qualified-signature compliance are outside this verification. Production migrations and native business integrations were not executed.

The broader regression suite passed 243 checks during implementation. After the final backend changes, the focused PostgreSQL run passed 23 checks and encountered one request timeout in the three-stage scenario; that scenario passed on an isolated rerun. Frontend typecheck, targeted ESLint and production build passed. The final browser run passed all three checks: desktop approval/worker resume, mobile document download/rejection and guided designer save/reload with unsaved-publication protection. The combined navigation/designer test required a 120-second overall budget for repeated full-page loads in the serialized SQLite QA server.
