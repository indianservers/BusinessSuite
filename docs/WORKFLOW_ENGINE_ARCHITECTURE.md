# Workflow Engine Architecture

Date: 2026-06-04

## Vision

Build a workflow engine that behaves like Zoho Flow, Power Automate, and Zapier, but is natively aware of CRM, PMS, HRMS, finance, approvals, mobile, and AI. The engine should be a platform primitive, not a module feature.

## Core Objects

| Object | Purpose |
|---|---|
| Workflow Definition | Versioned graph of triggers, conditions, actions, approvals, timers, and AI steps |
| Workflow Run | Runtime execution instance with state, logs, retries, and audit |
| Trigger | Event, schedule, webhook, record change, form submission, SLA, AI signal |
| Condition | Boolean expression over record fields, roles, dates, risk, amount, sentiment, or AI classification |
| Action | Create/update records, send message, create task, generate document, call API, assign owner |
| Approval | Human decision node with SLA, delegation, escalation, evidence, and comments |
| Timer | Delay, wait-until, business-hours calendar, recurring schedule, SLA timer |
| Escalation | Reassign, notify, increase priority, create exception, trigger fallback |
| AI Action | Classify, summarize, draft, predict, extract, recommend, explain |

## Trigger Catalog

| Trigger Type | Examples |
|---|---|
| CRM | Lead created, deal stage changed, quote sent, approval requested, customer inactive |
| PMS | Project approved, milestone overdue, task blocked, timesheet submitted, risk becomes high |
| HRMS | Employee joined, leave approved, payroll ready, missing punch detected, appraisal due |
| Finance | Invoice drafted, collection overdue, margin below threshold, payment received |
| Platform | Webhook received, file uploaded, scheduled run, import completed, connector failed |
| AI | Risk predicted, anomaly detected, sentiment negative, document extracted, forecast variance |

## Condition Catalog

| Condition | Example |
|---|---|
| Field condition | Deal amount greater than 500000 |
| Role condition | Approver is sales head or CFO |
| Time condition | More than 2 business days since quote sent |
| Relationship condition | Customer has open high-risk project |
| Risk condition | Project health is red and margin below threshold |
| AI condition | Lead intent confidence above 80 percent |
| Compliance condition | Payroll run has no statutory blockers |

## Action Catalog

| Action | Example |
|---|---|
| Create record | Create PMS project from won deal |
| Update record | Move lead to qualified after score threshold |
| Assign owner | Route lead by territory and workload |
| Send communication | WhatsApp reminder, email sequence, push notification |
| Generate document | Quote, offer letter, invoice draft, audit packet |
| Call integration | Accounting export, payment gateway, calendar sync |
| Create approval | Discount, payroll, milestone, leave, purchase |
| Create AI output | Draft proposal, summarize meeting, explain anomaly |

## Runtime Architecture

1. Event bus receives module events.
2. Workflow matcher identifies active definitions and trigger filters.
3. Execution engine creates workflow runs and node states.
4. Action executor runs idempotent tasks with retries and dead-letter logging.
5. Approval service pauses execution until decision/SLA/escalation.
6. AI service executes permission-aware model calls with evidence logging.
7. Audit ledger records definition version, inputs, outputs, user, and timestamps.
8. Observability dashboard shows failures, bottlenecks, SLA breaches, and ROI.

## Required Governance

| Governance Area | Requirement |
|---|---|
| Versioning | Draft, published, archived versions; running workflows keep old version |
| Simulation | Test workflow against sample records before publishing |
| Permissions | Only authorized admins can build workflows for specific objects/actions |
| Audit | Every node input/output and approval must be traceable |
| Safety | Destructive actions require confirmation or approval nodes |
| AI | AI-generated actions need confidence thresholds and human checks for high risk |
| Limits | Rate limits, loop detection, max runtime, max retries |

## MVP Workflow Templates

| Template | Trigger | Outcome |
|---|---|---|
| Deal won to project | CRM deal closed won | PMS project, budget, kickoff tasks, team suggestion |
| Discount approval | Quote discount above threshold | Sales head/CFO approval with margin explanation |
| Timesheet to invoice | Timesheet approved | Invoice draft/export and profitability update |
| Missing punch correction | Attendance exception detected | Employee/manager notification and HR approval |
| Project risk escalation | Risk score high | Notify PMO, create mitigation tasks, update dashboard |
| Overdue collection | Invoice overdue | Reminder sequence and sales/finance escalation |

