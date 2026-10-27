"""Disabled configurable definitions only; no business module actions or assignments."""

NAMES = [
    "Purchase Request",
    "Expense Reimbursement",
    "Employee Leave",
    "Travel Request",
    "Recruitment Approval",
    "New Employee Hiring",
    "Salary Adjustment",
    "Invoice Approval",
    "Vendor Onboarding",
    "Customer Credit Limit",
    "Discount Approval",
    "Contract Approval",
    "Project Budget Approval",
    "Change Request Approval",
    "Timesheet Approval",
    "Intern Completion Approval",
    "Internship Certificate Approval",
    "Asset Purchase",
    "Document Publication",
    "Administrative Access Request",
]
TEMPLATES = [
    {
        "id": str(i + 1),
        "name": name,
        "enabled": False,
        "definition": {
            "stages": [
                {
                    "id": "review",
                    "name": "Independent review",
                    "mode": "all",
                    "selectors": [{"kind": "user", "ids": []}],
                }
            ],
            "fields": [
                {
                    "key": "amount",
                    "label": "Amount",
                    "kind": "number",
                    "required": False,
                },
                {
                    "key": "currency",
                    "label": "Currency",
                    "kind": "text",
                    "required": False,
                },
                {
                    "key": "department",
                    "label": "Department",
                    "kind": "text",
                    "required": False,
                },
                {
                    "key": "details",
                    "label": "Details",
                    "kind": "text",
                    "required": True,
                },
            ],
            "prohibit_self_approval": True,
            "documents_required": False,
        },
        "setup_required": [
            "Choose authorized approvers",
            "Review request fields, SLA and delegation policy",
            "Publish and explicitly activate",
        ],
    }
    for i, name in enumerate(NAMES)
]
