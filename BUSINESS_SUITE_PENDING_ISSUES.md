# Business Suite pending issues

**Release remains blocked.** A clean run does not create missing functionality.

## Required implementation and reconciliation

- Critical: POS checkout needs one atomic, idempotent workflow that issues the native invoice, persists split/partial receipts, updates stock and posts through existing FAM controls. Current checkout records a sales order and payment-mode metadata, not a financial receipt.
- High: implement employee-backed service appointments, working hours/leave/resource conflicts, lifecycle, common calendar projection and completed-service billing.
- High: implement package/membership entitlement expiry, redemption uniqueness, reversals and history.
- High: complete AMC asset links, HRMS technician identity, visit scheduling and renewal/invoice integration using existing contracts/recurrence/tasks.
- High: reconcile FAM legacy party IDs with canonical CRM customer/vendor identities without automatic name/phone merging.
- High: approve Sales lead-access adapters and complete CRM task/note associations without broadening underlying permissions.
- High: complete effective-dated tax classifications and inclusive-pricing contracts. Existing historical invoice tax values must not be recalculated.
- Full repository regression must finish and all remaining failures must be retested against the final working tree.

## Requested cases still blocked or not run

- TC004: Open Vendors from Sales and FAM — FAM retains its native party/ledger view. Canonical vendor identity reconciliation is not implemented end to end.
- TC007: Open Leads from CRM and Sales — Sales-only users have no approved lead adapter independent of CRM grants; routing alone does not grant CRM access.
- TC008: Open Calendar from all modules — The common PMS calendar exists, but CRM native events and service appointments are not one calendar projection.
- TC013: Create lead in Sales; verify in CRM — A Sales-only lead-write adapter is not implemented; broadening CRM permissions would not be a safe QA fix.
- TC015: Create vendor in Sales; verify in FAM — Vendor-to-FAM canonical identity mapping requires reconciliation of legacy party IDs; no business records were merged.
- TC018: Create task in CRM; verify in common Tasks — CRM-linked task reads are tested; task quick-create still needs explicit CRM associations and origin-aware return navigation.
- TC019: Create note against customer; verify authorized cross-module access — Persistent private notes are tested; a universal customer-to-note association with cross-module visibility is incomplete.
- TC024: Sell products and services in the same invoice — POS checkout posts a sales order; it does not atomically issue an invoice and persist its payment.
- TC029: Accept split payments and partial payments — Split/partial payment inputs are not persisted as native receipts by POS checkout. This is a release blocker.
- TC038: Verify tax-inclusive and tax-exclusive calculations — The current POS/catalog workflow does not expose a complete, verified tax-inclusive pricing contract.
- TC041: Create salon service appointment for an existing customer — Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- TC042: Create appointment for a new customer — Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- TC043: Assign service to an eligible employee — Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- TC044: Verify appointment in common Calendar — Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- TC045: Reschedule appointment and verify all views update — Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- TC046: Cancel appointment and release reserved slot — Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- TC047: Prevent overlapping bookings for same employee — Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- TC048: Prevent booking during employee leave or unavailable hours — Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- TC049: Book multiple services with different durations — Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- TC050: Complete appointment and generate correct POS invoice — Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.
- TC058: Test serial number and batch tracking — Batch/serial master persistence and duplicate rejection are tested; POS allocation, expiry enforcement and serial lifecycle are not certified by those master-data tests.
- TC062: Link AMC to a product or asset — AMC product/asset association is not implemented as a verified canonical relationship.
- TC063: Assign service technician from HRMS employee master — AMC technician assignment does not implement the requested HRMS employee/skill eligibility contract.
- TC064: Schedule AMC visit in common Calendar — AMC service-visit appointment projection into the common calendar is not implemented.
- TC065: Generate renewal reminder — Generic recurring billing exists; an AMC renewal reminder workflow was not verified.
- TC066: Renew AMC without duplicating contract history — Generic renewal status/audit persistence is tested; new AMC coverage terms and renewal history were not exercised end to end.
- TC067: Generate AMC invoice and verify FAM integration — Native FAM invoice posting is tested, but the requested AMC-to-invoice workflow is not complete.
- TC068: Cancel or expire AMC and verify access, status and billing behavior — Contract expiry/status persistence is tested; cancellation/expiry enforcement across AMC visits and billing is not implemented end to end.
- TC085: Run complete regression suite after fixes — Full pre-fix repository regression: 1800 progress entries of 6496; still running/not yet complete. Targeted reruns do not substitute for a clean full run.
- TC094: Expired service packages — Service-package expiry and entitlement storage/redemption workflow is not implemented.
- TC095: Service package partial redemption — Service-package partial redemption and its idempotent ledger are not implemented.
- TC096: Customer cancellation — Customer appointment cancellation is blocked by the missing service-appointment workflow.
- TC097: Employee reassignment — Appointment employee reassignment is blocked by the missing employee-backed appointment workflow.
- TC098: Appointment crossing midnight — Appointment crossing-midnight behavior cannot be certified without the appointment implementation.
- TC099: Employee timezone changes — Employee timezone changes for appointments cannot be certified without the scheduling implementation.
- TC101: Payment gateway timeout — Native POS gateway payment persistence/reconciliation is incomplete; an email/provider timeout test does not establish payment-gateway behavior.
- TC104: Missing GST classification — Configured rates are tested; effective-dated item classification selection and missing-classification policy remain incomplete.