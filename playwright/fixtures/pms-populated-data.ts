const names = [
  "BusinessSuite Website Redesign", "CRM Lead Management Rollout", "Sales Pipeline Automation", "Customer Self-Service Portal",
  "WhatsApp Customer Support", "Inventory Barcode Implementation", "Warehouse Management Upgrade", "Purchase Approval Workflow",
  "Finance & Accounting Integration", "GST Invoicing Automation", "Payroll & Attendance Rollout", "Employee Onboarding Portal",
  "Mobile Sales App", "Field Service Scheduling", "Vendor Onboarding Programme", "Customer Data Migration",
  "E-commerce Store Integration", "Payment Gateway Integration", "Project Billing Automation", "Sales Analytics Dashboard",
  "Helpdesk & SLA Management", "Document Approval System", "Branch Expansion — Hyderabad", "Office Network Modernisation",
  "Asset Tracking Implementation", "Learning Management Portal", "Recruitment Workflow Upgrade", "Performance Review Rollout",
  "Procurement Cost Optimisation", "Delivery Tracking Integration", "Business Continuity Planning", "Security & Access Review",
  "Quality Assurance Automation", "Client Contract Management", "Team Communication Rollout", "Year-End Financial Readiness",
];
export const demoPeople = [
  { id: 100, user_id: 100, name: "Ananya Rao", email: "ananya.rao@example.com", role: "Project Manager" },
  { id: 101, user_id: 101, name: "Priya Sharma", email: "priya.sharma@example.com", role: "Designer" },
  { id: 102, user_id: 102, name: "Rahul Mehta", email: "rahul.mehta@example.com", role: "Developer" },
  { id: 103, user_id: 103, name: "Arjun Reddy", email: "arjun.reddy@example.com", role: "QA Engineer" },
  { id: 104, user_id: 104, name: "Neha Gupta", email: "neha.gupta@example.com", role: "Business Analyst" },
  { id: 105, user_id: 105, name: "Vikram Shah", email: "vikram.shah@example.com", role: "Technical Lead" },
];
const taskNames = ["Confirm requirements and scope", "Approve project plan", "Complete wireframes", "Review homepage design", "Build responsive layouts", "Connect application APIs", "Validate role permissions", "Complete integration testing", "Review accessibility", "Resolve mobile layout issues", "Prepare client demonstration", "Approve release checklist"];
export const demoProjects = names.map((name, i) => ({
  id: 301 + i, workspace_id: 7, client_id: 10, client_name: "Acme Enterprises", name, project_key: `BS${String(i + 1).padStart(2, "0")}`,
  description: i === 0 ? "Refresh the BusinessSuite website with a responsive customer experience, clear product journeys, and faster lead capture. Client: Acme Enterprises." : `Deliver ${name.toLowerCase()} with stakeholder sign-off, phased rollout, and operational handover.`,
  manager_user_id: demoPeople[i % demoPeople.length].id, status: i % 9 === 8 ? "Completed" : i % 7 === 6 ? "On Hold" : "In Progress",
  priority: ["High", "Medium", "High", "Low"][i % 4], health: i % 5 === 3 ? "At Risk" : "On Track",
  progress_percent: i === 0 ? 72 : i % 9 === 8 ? 100 : 20 + ((i * 13) % 70),
  start_date: "2026-10-12", due_date: `2026-11-${String(12 + i % 18).padStart(2, "0")}`,
  budget_amount: 180000 + i * 25000, actual_cost: 112500 + i * 12000,
  can_edit_project: true, can_manage_members: true, can_manage_tasks: true, can_upload_files: true,
  is_archived: false, is_client_visible: true, created_at: "2026-10-10T09:00:00Z", updated_at: "2026-11-07T10:00:00Z",
}));
export function demoTasks(projectId: number) {
  const project = demoProjects.find(p => p.id === projectId)!;
  return taskNames.map((title, i) => ({ id: projectId * 100 + i, project_id: projectId, column_id: i < 7 ? 3 : i < 10 ? 2 : 1, start_date: `2026-10-${String(20 + i).padStart(2, "0")}`, task_key: `${project.project_key}-${i + 1}`, title, description: "Coordinate with the project team and record acceptance evidence.", status: i < 7 ? "Done" : i === 9 ? "Blocked" : i < 10 ? "In Progress" : "To Do", priority: i % 3 ? "Medium" : "High", assignee_user_id: demoPeople[i % 6].id, assignee_name: demoPeople[i % 6].name, due_date: i === 7 || i === 9 ? "2026-11-05" : "2026-11-12", completed_at: i < 7 ? `2026-10-${String(21 + i).padStart(2, "0")}T10:00:00Z` : undefined, updated_at: `2026-11-07T10:${String(i+10)}:00Z`, work_type: "Task", estimated_hours: 8, actual_hours: i < 7 ? 7 : 3 }));
}
export function demoMessages(projectId: number) {
  const name = demoProjects.find(p => p.id === projectId)!.name;
  const entries = [
    [104, `Morning team! Here is today's update for ${name}. Requirements are signed off and the delivery plan is on track.`],
    [101, "The latest designs are ready. I have included the desktop and mobile layouts in the review pack."],
    [101, "Please review the updated design brief before our client walkthrough."],
    [100, "Thanks, Priya. Rahul, please review the responsive layouts and share any blockers here."],
    [102, "The desktop implementation is complete. I am checking the tablet navigation and form validation now."],
    [103, "QA update: 18 of 21 checks passed. Three mobile issues are assigned and ready for retest."],
    [105, "I can help with the API dependency. The updated endpoint will be ready by 3 PM."],
    [100, "Great. Let’s close the mobile issues today and keep tomorrow’s client demo on schedule. 👍"],
    [102, "Confirmed. I’ll post the staging link and screenshots once the fixes are ready."],
  ] as const;
  return entries.map(([author_id, body], i) => ({ id: projectId * 1000 + i + 1, author_id, body, created_at: `2026-11-07T${i < 4 ? "04" : "05"}:${String(5 + i * 5).padStart(2, "0")}:00Z`, deleted_at: null, attachments: i === 2 ? [{ id: 55, name: "Design-review-brief.pdf", size: 245760, mime: "application/pdf" }] : [] }));
}
