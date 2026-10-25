# Lead assignment to employees

Updated 26 October 2026.

Leads now have an **Assign to employee** selector during creation. Assignment is also available in the lead drawer, table, bulk actions, classic lead workspace and full record header. Names include the HRMS employee code when an employee is linked.

The stored owner remains the employee's **login user ID**, not their independent HRMS employee ID. This preserves lead visibility, My day, notifications, activity ownership and conversion. CRM-only accounts remain supported when no HRMS employee is linked.

Eligible employees must be active or on probation, have an active linked login, belong to the same organization and have CRM lead access. Inactive/deleted employees, inactive identities, disabled accounts and accounts without CRM access are rejected by the APIs. The creation form explains which otherwise active employees need account/access setup; it does not create accounts or grant permissions automatically.

Administrators and sales managers can choose eligible employees. Other CRM users retain the existing self-assignment restriction. An explicit `crm_admin` permission now works with custom role names as well.

An explicit manual choice takes precedence over round-robin and territory routing. On reassignment, pending follow-ups owned by the previous assignee transfer to the new assignee; completed history and independently delegated activities stay unchanged. The new assignee receives an in-app notification, and an assignment event is recorded. Saving the same assignee again does not duplicate notifications.

Existing leads are not reassigned automatically. No schema migration is required by this assignment fix.

Validation covers differing employee/user ID sequences, linked employee display names, missing-account guidance, CRM access, inactive and cross-organization identities, notifications, the assignee's My day queue, follow-up transfer, manual choices under automatic routing and custom administrator roles. Browser coverage includes choosing an employee during creation and assignment from a full lead record.

Verified: 58 PostgreSQL-backed backend tests and 13 browser tests passed.
