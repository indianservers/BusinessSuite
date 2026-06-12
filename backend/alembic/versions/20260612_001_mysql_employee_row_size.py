"""Reduce MySQL employee row size

Revision ID: 20260612_001
Revises: 20260607_021
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260612_001"
down_revision = "20260607_021"
branch_labels = None
depends_on = None


EMPLOYEE_TEXT_COLUMNS = [
    "middle_name",
    "gender",
    "place_of_birth",
    "marital_status",
    "blood_group",
    "nationality",
    "domicile_state",
    "religion",
    "category",
    "sub_caste",
    "gender_identity",
    "disability_status",
    "disability_certificate_number",
    "veteran_status",
    "father_name",
    "mother_name",
    "spouse_name",
    "spouse_occupation",
    "alternate_phone",
    "whatsapp_number",
    "office_extension",
    "emergency_contact_name",
    "emergency_contact_relation",
    "present_city",
    "present_state",
    "present_pincode",
    "present_country",
    "permanent_city",
    "permanent_state",
    "permanent_pincode",
    "permanent_country",
    "passport_number",
    "passport_issue_place",
    "driving_license_number",
    "driving_license_class",
    "voter_id_number",
    "ration_card_number",
    "functional_area",
    "employment_type",
    "worker_type",
    "work_location",
    "desk_code",
    "seat_number",
    "timezone",
    "manager_chain_path",
    "contract_reference_number",
    "contractor_company",
    "academic_rank",
    "class_assigned",
    "orcid_id",
    "google_scholar_url",
    "medical_specialty",
    "medical_sub_specialty",
    "clinical_grade",
    "service_number",
    "service_type",
    "cadre",
    "worker_category",
    "trade",
    "apprentice_type",
    "factory_gate_number",
    "professional_reg_number",
    "professional_reg_body",
    "background_verification_status",
    "background_verification_agency",
    "bank_name",
    "bank_branch",
    "account_number",
    "account_type",
    "ifsc_code",
    "micr_code",
    "pan_number",
    "aadhaar_number",
    "uan_number",
    "pf_number",
    "esic_number",
    "salary_currency",
    "nri_bank_account_type",
    "tax_regime_preference",
    "form_16_delivery",
    "linkedin_url",
    "github_username",
    "portfolio_url",
    "research_gate_url",
    "profile_photo_url",
    "preferred_display_name",
]

PREVIOUS_TYPES = {
    "middle_name": sa.String(length=80),
    "gender": sa.String(length=20),
    "place_of_birth": sa.String(length=150),
    "marital_status": sa.String(length=20),
    "blood_group": sa.String(length=10),
    "nationality": sa.String(length=50),
    "domicile_state": sa.String(length=100),
    "religion": sa.String(length=50),
    "category": sa.String(length=20),
    "sub_caste": sa.String(length=100),
    "gender_identity": sa.String(length=50),
    "disability_status": sa.String(length=50),
    "disability_certificate_number": sa.String(length=50),
    "veteran_status": sa.String(length=50),
    "father_name": sa.String(length=150),
    "mother_name": sa.String(length=150),
    "spouse_name": sa.String(length=150),
    "spouse_occupation": sa.String(length=100),
    "alternate_phone": sa.String(length=20),
    "whatsapp_number": sa.String(length=20),
    "office_extension": sa.String(length=20),
    "emergency_contact_name": sa.String(length=100),
    "emergency_contact_relation": sa.String(length=50),
    "present_city": sa.String(length=100),
    "present_state": sa.String(length=100),
    "present_pincode": sa.String(length=20),
    "present_country": sa.String(length=80),
    "permanent_city": sa.String(length=100),
    "permanent_state": sa.String(length=100),
    "permanent_pincode": sa.String(length=20),
    "permanent_country": sa.String(length=80),
    "passport_number": sa.String(length=30),
    "passport_issue_place": sa.String(length=100),
    "driving_license_number": sa.String(length=30),
    "driving_license_class": sa.String(length=50),
    "voter_id_number": sa.String(length=30),
    "ration_card_number": sa.String(length=30),
    "functional_area": sa.String(length=100),
    "employment_type": sa.String(length=50),
    "worker_type": sa.String(length=50),
    "work_location": sa.String(length=50),
    "desk_code": sa.String(length=50),
    "seat_number": sa.String(length=50),
    "timezone": sa.String(length=80),
    "manager_chain_path": sa.String(length=500),
    "contract_reference_number": sa.String(length=100),
    "contractor_company": sa.String(length=200),
    "academic_rank": sa.String(length=80),
    "class_assigned": sa.String(length=100),
    "orcid_id": sa.String(length=50),
    "google_scholar_url": sa.String(length=300),
    "medical_specialty": sa.String(length=150),
    "medical_sub_specialty": sa.String(length=150),
    "clinical_grade": sa.String(length=80),
    "service_number": sa.String(length=80),
    "service_type": sa.String(length=100),
    "cadre": sa.String(length=100),
    "worker_category": sa.String(length=30),
    "trade": sa.String(length=100),
    "apprentice_type": sa.String(length=80),
    "factory_gate_number": sa.String(length=50),
    "professional_reg_number": sa.String(length=100),
    "professional_reg_body": sa.String(length=200),
    "background_verification_status": sa.String(length=30),
    "background_verification_agency": sa.String(length=150),
    "bank_name": sa.String(length=100),
    "bank_branch": sa.String(length=100),
    "account_number": sa.String(length=100),
    "account_type": sa.String(length=30),
    "ifsc_code": sa.String(length=20),
    "micr_code": sa.String(length=20),
    "pan_number": sa.String(length=20),
    "aadhaar_number": sa.String(length=20),
    "uan_number": sa.String(length=30),
    "pf_number": sa.String(length=50),
    "esic_number": sa.String(length=50),
    "salary_currency": sa.String(length=3),
    "nri_bank_account_type": sa.String(length=10),
    "tax_regime_preference": sa.String(length=10),
    "form_16_delivery": sa.String(length=20),
    "linkedin_url": sa.String(length=300),
    "github_username": sa.String(length=100),
    "portfolio_url": sa.String(length=300),
    "research_gate_url": sa.String(length=300),
    "profile_photo_url": sa.String(length=500),
    "preferred_display_name": sa.String(length=150),
}


def _existing_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("employees")}


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    existing = _existing_columns()

    for column_name in EMPLOYEE_TEXT_COLUMNS:
        if column_name in existing:
            op.alter_column("employees", column_name, existing_type=PREVIOUS_TYPES[column_name], type_=sa.Text(), existing_nullable=True)

    if dialect == "mysql":
        op.execute("ALTER TABLE employees ROW_FORMAT=DYNAMIC")


def downgrade() -> None:
    existing = _existing_columns()
    for column_name in EMPLOYEE_TEXT_COLUMNS:
        if column_name in existing:
            op.alter_column("employees", column_name, existing_type=sa.Text(), type_=PREVIOUS_TYPES[column_name], existing_nullable=True)
