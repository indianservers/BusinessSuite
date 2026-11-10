"""Disposable HTTP fixture for the HRMS document vault browser regression."""

import serve_ux_qa

qa = serve_ux_qa.qa
from datetime import date, timedelta
from pathlib import Path
from app.models.employee import Employee
from app.models.company import Department, Designation
from app.models.document import EmployeeCertificate
from reportlab.pdfgen.canvas import Canvas
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from tests.rich_text_test_utils import workflow_seed_scope

with qa.SessionLocal() as db, workflow_seed_scope(db):
    department = Department(name="Technology", branch_id=1)
    db.add(department)
    db.flush()
    designation = Designation(name="Software Engineer", department_id=department.id)
    db.add(designation)
    db.flush()
    people = []
    for i, (first, last) in enumerate(
        [("Amit", "Sharma"), ("Priya", "Verma"), ("Neha", "Iyer")], 1
    ):
        person = Employee(
            employee_id=f"VAULT-{i:03}",
            first_name=first,
            last_name=last,
            branch_id=1,
            department_id=department.id,
            designation_id=designation.id,
            date_of_joining=date(2024, 1, 1),
            work_email=f"{first.lower()}@vault.example.com",
            employment_type="Full-time",
        )
        db.add(person)
        db.flush()
        people.append(person)
    for i, (title, category, status, expiry) in enumerate(
        [
            ("Degree Certificate", "Study", "Verified", None),
            ("Passport", "Identity", "Pending", date.today() + timedelta(days=15)),
            (
                "Health Certificate",
                "Compliance",
                "Verified",
                date.today() - timedelta(days=1),
            ),
            ("Employment Letter", "Old Company", "Rejected", None),
        ],
        1,
    ):
        employee = people[(i - 1) % len(people)]
        folder = Path(qa.temporary.name) / "uploads" / "certificates" / str(employee.id)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"qa-{i}.pdf"
        canvas = Canvas(str(target))
        canvas.drawString(60, 780, title)
        canvas.drawString(
            60, 750, f"Employee: {employee.first_name} {employee.last_name}"
        )
        canvas.save()
        db.add(
            EmployeeCertificate(
                employee_id=employee.id,
                title=title,
                category=category,
                certificate_type=title,
                certificate_number=f"QA-{i}",
                verification_status=status,
                expiry_date=expiry,
                file_url=f"/uploads/certificates/{employee.id}/qa-{i}.pdf",
                original_filename=f"qa-{i}.pdf",
                content_type="application/pdf",
                file_size_bytes=target.stat().st_size,
            )
        )
    db.commit()
    from app.branches.migration import backfill

    backfill(db.connection(), 1)
    db.commit()
if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run(qa.app, host="127.0.0.1", port=1564, log_level="warning")
    finally:
        qa.engine.dispose()
        qa.temporary.cleanup()
