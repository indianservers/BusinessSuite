import os

os.environ["COMMERCIAL_QA_DATABASE_NAME"] = "businesssuite-commercial-forms-browser.db"
from scripts.run_forms_browser_qa import app
from app.db.session import SessionLocal
from app.forms.models import SuiteForm, FormReply, FormFile
from app.apps.customization.models import CustomizationField, CustomizationFieldOption
from uuid import uuid4

with SessionLocal() as db:
    if (
        not db.query(CustomizationField)
        .filter_by(field_api_name="qa_interest", module_name="crm.contacts")
        .first()
    ):
        f = CustomizationField(
            module_name="crm.contacts",
            field_api_name="qa_interest",
            field_label="Service interest",
            field_type="picklist",
            visible=True,
            editable=True,
            help_text="Shared global field for reusable form intake",
        )
        db.add(f)
        db.flush()
        for i, value in enumerate(["Consulting", "Implementation", "Support"]):
            db.add(
                CustomizationFieldOption(
                    field_id=f.id, value=value, label=value, order_index=i, active=True
                )
            )
    f = db.query(SuiteForm).filter_by(name="Project request").first()
    if f and not db.query(FormReply).filter_by(form_id=f.id).first():
        fields = f.published["fields"]
        answer = {
            q["id"]: (
                "Synthetic response for browser review"
                if q["type"] == "text"
                else (
                    "Website"
                    if q["type"] == "select"
                    else (
                        "qa@example.invalid"
                        if q["type"] == "email"
                        else "Seeded fixture. Accepted submission validation is exercised by API tests."
                    )
                )
            )
            for q in fields
        }
        db.add(
            FormReply(
                form_id=f.id,
                request_id=str(uuid4()),
                version=f.version,
                answers=answer,
                labels={q["id"]: q["label"] for q in fields},
                status="new",
            )
        )
    db.commit()
print("Seeded synthetic global catalog and browser-review response")
