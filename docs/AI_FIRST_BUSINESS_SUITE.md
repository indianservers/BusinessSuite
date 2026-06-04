# AI-First Business Suite

Date: 2026-06-04

## Vision

AI should be embedded into records, approvals, dashboards, workflows, and mobile moments. The product should feel like every lead, project, employee, payroll run, invoice, and approval has a silent analyst watching for risk and proposing action.

## CRM AI

| Use Case | Embedded Location | AI Output | Human Control |
|---|---|---|---|
| Lead qualification | Lead detail, lead queue | Fit score, urgency, next action, owner suggestion | Sales accepts/rejects |
| Lead prediction | Pipeline dashboard | Conversion likelihood, stale-lead alert, source quality | Manager review |
| Meeting summary | Activity/meeting page | Summary, objections, tasks, follow-up email | Rep edits before send |
| Proposal drafting | Quote/deal page | Proposal narrative, scope, assumptions, exclusions | Sales/finance approval |
| Forecast coaching | Forecast dashboard | Risky deals, commit changes, next actions | Manager override |

## PMS AI

| Use Case | Embedded Location | AI Output | Human Control |
|---|---|---|---|
| Risk prediction | Project dashboard | Slippage, budget, dependency, workload risk | PM confirms mitigation |
| Project prediction | Portfolio dashboard | Delivery date confidence, burn forecast, milestone variance | PMO review |
| Resource allocation | Planning/resource page | Recommended staff, substitutes, capacity conflicts | Resource manager approves |
| Plan generation | Project intake/handoff | WBS, milestones, tasks, dependencies | PM edits and publishes |
| Meeting to tasks | Project meeting notes | Tasks, decisions, owners, due dates | Team confirms |

## HRMS AI

| Use Case | Embedded Location | AI Output | Human Control |
|---|---|---|---|
| Resume screening | Recruitment pipeline | Candidate fit, missing skills, interview focus | Recruiter shortlists |
| Attrition prediction | HR dashboard | Risk drivers, retention actions, manager prompts | HR/manager action |
| Payroll validation | Payroll run | Anomalies, statutory blockers, bank readiness | Payroll admin approves |
| Attendance exception | Attendance dashboard | Missing punch explanation, probable fix | Employee/manager confirms |
| Performance summary | Appraisal page | Evidence summary, bias warning, growth suggestions | Manager edits |

## Management AI

| Use Case | Embedded Location | AI Output |
|---|---|---|
| Daily digest | CEO/COO/CFO dashboards | What changed, what is risky, what needs decision |
| CEO dashboard | Executive cockpit | Revenue, people, delivery, cash, risk narratives |
| Insights | Reports | Plain-English explanation, anomaly roots, recommended action |
| Board pack | Reporting center | Monthly summary, charts, risks, decisions needed |
| Command agent | Global command palette | Creates reports, workflows, projects, approvals from natural language |

## AI Architecture Requirements

| Layer | Requirement |
|---|---|
| Retrieval | Permission-aware retrieval over module records, documents, comments, emails, events |
| Evidence | Every answer links to source records and confidence |
| Action | AI can draft actions, but critical actions require approval |
| Memory | Account/project/employee context with retention rules |
| Monitoring | Cost, latency, hallucination reports, feedback, model versioning |
| Security | No cross-tenant leakage, field-level enforcement, redaction policies |

