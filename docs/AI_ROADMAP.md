# AI Roadmap

Date: 2026-06-04

## Executive Verdict

The suite already has an AI Agents application surface, but product competitiveness in 2026 requires AI to be embedded in daily CRM, PMS, HRMS, and executive workflows. AI should not be a separate novelty page. It should qualify leads, draft follow-ups, summarize meetings, predict project risk, reconcile attendance/payroll exceptions, explain reports, and route approvals with traceable evidence.

AI competitiveness score today: 55/100

## AI Principles

1. AI suggestions must be tied to real records.
2. Every AI action must show evidence, confidence, and owner.
3. High-impact actions must require approval.
4. AI must leave an audit trail.
5. AI should reduce clicks in daily workflows, not add a parallel chat-only experience.

## Roadmap

| Phase | Feature | Module | Impact |
|---|---|---|---|
| 1 | Lead qualification assistant | CRM | Scores/enriches leads, explains why, suggests owner and next step |
| 1 | Email and WhatsApp reply drafter | CRM | Drafts follow-ups from customer timeline |
| 1 | Meeting summary and action extraction | CRM/PMS | Converts transcript/notes into tasks, follow-ups, risks |
| 1 | Project risk predictor | PMS | Flags slipping milestones, blocked dependencies, overloaded owners |
| 1 | Payroll/attendance exception explainer | HRMS | Explains missing punches, payroll blockers, statutory issues |
| 2 | Next-best-action engine | CRM | Suggests call/email/quote/discount/escalation |
| 2 | Project plan generator | PMS | Creates milestones/tasks from goal, quote, or template |
| 2 | Resource allocation recommender | PMS/HRMS | Recommends staffing by skill, availability, workload |
| 2 | Approval summarizer | Suite | Summarizes why approval is needed and risks |
| 2 | Report explainer | Suite | Natural language answers over CRM/PMS/HRMS dashboards |
| 3 | Sales forecast anomaly detection | CRM | Flags risky pipeline, stale deals, forecast movement |
| 3 | Workflow builder assistant | Suite | Converts natural language into automation rule drafts |
| 3 | Customer health agent | CRM/PMS/Support | Combines deals, projects, tickets, invoices, sentiment |
| 3 | Executive daily digest | Suite | Revenue, delivery, HR, approvals, risks |
| 3 | Integration monitoring agent | Platform | Detects broken syncs, failed webhooks, credential expiry |

## Required Trust Controls

| Control | Why It Matters |
|---|---|
| Approval gates | Prevents AI from sending messages, changing stages, approving payroll, or billing without authorization |
| Evidence links | Users need to inspect source records behind recommendations |
| Confidence and uncertainty | Reduces blind trust |
| Audit log | Required for enterprise and regulated use |
| Prompt/version tracking | Supports reproducibility and debugging |
| Permission-aware retrieval | AI must only see data the user can access |
| Human handoff | AI should escalate unclear/high-risk cases |

## Top AI Builds

| Rank | AI Feature | Revenue Impact | Ease | Competitive Advantage |
|---:|---|---:|---:|---:|
| 1 | CRM lead qualification and next-best action | High | Medium | High |
| 2 | PMS project risk predictor | High | Medium | High |
| 3 | Suite approval summarizer | Medium | High | Medium |
| 4 | HRMS payroll/attendance exception assistant | High | Medium | High |
| 5 | CRM/PMS meeting summary to tasks | Medium | Medium | Medium |
| 6 | Executive daily digest | Medium | Medium | High |
| 7 | Natural language workflow builder | High | Hard | High |
| 8 | Customer health agent | High | Hard | High |

