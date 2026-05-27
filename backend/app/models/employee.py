from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, Text, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        Index("idx_employees_active_status", "deleted_at", "status"),
        Index("idx_employees_name", "first_name", "last_name"),
        Index("idx_employees_directory_email", "work_email", "personal_email"),
        Index("idx_employees_department_status", "department_id", "status", "deleted_at"),
        Index("idx_employees_manager_status", "reporting_manager_id", "status", "deleted_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True)

    # Personal Info
    salutation = Column(String(20))  # Mr, Mrs, Ms, Dr, Prof, Er, Adv, Rev, CA, CS, Mx
    first_name = Column(String(80), nullable=False)
    middle_name = Column(String(80))
    last_name = Column(String(80), nullable=False)
    gender = Column(String(20))
    date_of_birth = Column(Date)
    place_of_birth = Column(String(150))
    marital_status = Column(String(20))  # Single, Married, Divorced, Widowed, Separated
    blood_group = Column(String(10))
    nationality = Column(String(50), default="Indian")
    domicile_state = Column(String(100))  # State of domicile (for govt jobs)
    religion = Column(String(50))
    category = Column(String(20))  # General, OBC, SC, ST, EWS
    sub_caste = Column(String(100))
    gender_identity = Column(String(50))
    disability_status = Column(String(50))  # None, Visual, Hearing, Locomotor, Other
    disability_percentage = Column(Numeric(5, 2))  # % disability for certificate/reservation
    disability_certificate_number = Column(String(50))
    ex_serviceman = Column(Boolean, default=False)  # Ex-armed forces personnel
    veteran_status = Column(String(50))

    # Family Info
    father_name = Column(String(150))   # Required for govt forms, BGV, PF nominations
    mother_name = Column(String(150))
    spouse_name = Column(String(150))
    spouse_occupation = Column(String(100))
    number_of_dependants = Column(Integer, default=0)

    # Contact
    work_email = Column(String(150), index=True)
    personal_email = Column(String(150))
    phone_number = Column(String(20))
    alternate_phone = Column(String(20))
    whatsapp_number = Column(String(20))  # May differ from phone
    office_extension = Column(String(20))
    emergency_contact_name = Column(String(100))
    emergency_contact_number = Column(String(20))
    emergency_contact_relation = Column(String(50))

    # Address
    present_address = Column(Text)
    present_city = Column(String(100))
    present_state = Column(String(100))
    present_pincode = Column(String(20))
    present_country = Column(String(80), default="India")
    permanent_address = Column(Text)
    permanent_city = Column(String(100))
    permanent_state = Column(String(100))
    permanent_pincode = Column(String(20))
    permanent_country = Column(String(80), default="India")

    # Identity Documents
    passport_number = Column(String(30))
    passport_expiry = Column(Date)
    passport_issue_place = Column(String(100))
    driving_license_number = Column(String(30))
    driving_license_expiry = Column(Date)
    driving_license_class = Column(String(50))  # LMV, HMV, Transport, etc.
    voter_id_number = Column(String(30))
    ration_card_number = Column(String(30))

    # Job Info
    date_of_joining = Column(Date, nullable=False)
    date_of_confirmation = Column(Date)
    date_of_exit = Column(Date)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    designation_id = Column(Integer, ForeignKey("designations.id", ondelete="SET NULL"), nullable=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True)
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id", ondelete="SET NULL"), nullable=True)
    location_id = Column(Integer, ForeignKey("work_locations.id", ondelete="SET NULL"), nullable=True)
    grade_band_id = Column(Integer, ForeignKey("grade_bands.id", ondelete="SET NULL"), nullable=True)
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="SET NULL"), nullable=True)
    reporting_manager_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    functional_area = Column(String(100))  # Finance, IT, HR, Operations, Teaching, Medical, Legal, Engineering
    employment_type = Column(String(50), default="Full-time")  # Full-time, Part-time, Contract, Intern, Visiting, Deputation
    worker_type = Column(String(50), default="Employee")  # Employee, Contractor, Consultant, Gig, Apprentice, Trainee
    status = Column(String(30), default="Active")  # Active, Probation, On Leave, Resigned, Terminated, Suspended, Absconding
    work_location = Column(String(50), default="Office")  # Office, Remote, Hybrid, Field, On-Site
    shift_id = Column(Integer, ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True)
    probation_period_months = Column(Integer, default=6)
    probation_start_date = Column(Date)
    probation_end_date = Column(Date)
    probation_status = Column(String(30), default="on_probation", index=True)
    notice_period_days = Column(Integer, default=30)
    last_promotion_date = Column(Date)
    next_promotion_due_date = Column(Date)   # Useful for govt/academic cadres
    flexi_timing_applicable = Column(Boolean, default=False)
    work_from_home_eligible = Column(Boolean, default=False)
    desk_code = Column(String(50))
    seat_number = Column(String(50))         # Classroom/ward/cabin seat or room number
    timezone = Column(String(80), default="Asia/Kolkata")
    manager_chain_path = Column(String(500))

    # Contract / Bond (for contract staff and bonded employees)
    contract_start_date = Column(Date)
    contract_end_date = Column(Date)
    contract_reference_number = Column(String(100))
    contractor_company = Column(String(200))  # For third-party contract employees
    bond_applicable = Column(Boolean, default=False)
    bond_amount = Column(Numeric(12, 2))
    bond_end_date = Column(Date)
    bond_remarks = Column(Text)

    # Academic / Teaching Profile (Professor, Lecturer, School Teacher)
    academic_rank = Column(String(80))       # Professor, Assoc. Professor, Asst. Professor, Lecturer, Teaching Asst., Visiting Faculty, Principal, HOD
    subjects_taught = Column(JSON)           # ["Mathematics", "Physics"] — teachers/professors
    class_assigned = Column(String(100))     # Class teacher of "Grade 5 - Section A"
    teaching_experience_years = Column(Numeric(4, 1))
    research_areas = Column(Text)
    publications_count = Column(Integer, default=0)
    h_index = Column(Integer)               # Academic citation metric
    orcid_id = Column(String(50))           # Open Researcher ID
    google_scholar_url = Column(String(300))

    # Medical / Healthcare Profile (Doctor, Nurse, Paramedic)
    medical_specialty = Column(String(150))  # Cardiology, Orthopedics, Pediatrics, General Surgery
    medical_sub_specialty = Column(String(150))
    clinical_grade = Column(String(80))      # Senior Consultant, Consultant, Registrar, House Surgeon, Staff Nurse, Senior Sister

    # Government / Public Sector Profile
    service_number = Column(String(80))      # Govt service number / employee number
    service_type = Column(String(100))       # IAS, IPS, IRS, State Service, Central Service, PSU
    cadre = Column(String(100))              # Allocated state/central cadre
    pay_level = Column(String(20))           # 7th CPC Pay Level (Level 1–18)
    pay_band = Column(String(50))            # For pre-7th CPC employees
    grade_pay = Column(Numeric(10, 2))       # Grade pay amount

    # Industrial / Factory / Trades Worker Profile
    worker_category = Column(String(30))     # Skilled, Semi-Skilled, Unskilled, Highly Skilled
    trade = Column(String(100))              # Electrician, Welder, Fitter, Turner, Machinist, Plumber, Carpenter
    apprentice_type = Column(String(80))     # Type of apprenticeship if applicable
    factory_gate_number = Column(String(50)) # Gate/badge number for shop-floor workers

    # Professional Registration (Doctor, Lawyer, CA, Nurse, Teacher, Engineer)
    professional_reg_number = Column(String(100))   # MCI/NMC no., Bar Council no., ICAI membership, Nursing Council no., CTET
    professional_reg_body = Column(String(200))     # "Maharashtra Medical Council", "Bar Council of India", "ICAI"
    professional_reg_expiry = Column(Date)          # Renewal/expiry date of registration

    # Background Verification
    background_verification_status = Column(String(30), default="Not Started")  # Not Started, In Progress, Completed, Failed, On Hold
    background_verification_date = Column(Date)
    background_verification_agency = Column(String(150))

    # Bank Details (encrypted in production)
    bank_name = Column(String(100))
    bank_branch = Column(String(100))
    account_number = Column(String(100))
    account_type = Column(String(30), default="Savings")  # Savings, Current, NRO, NRE, Salary
    ifsc_code = Column(String(20))
    micr_code = Column(String(20))

    # Tax / Compliance
    pan_number = Column(String(20))
    aadhaar_number = Column(String(20))
    uan_number = Column(String(30))
    pf_number = Column(String(50))
    esic_number = Column(String(50))
    salary_currency = Column(String(3), default="INR")
    is_nri = Column(Boolean, default=False)   # Non-Resident Indian — affects TDS rates
    nri_bank_account_type = Column(String(10))  # NRO or NRE
    tax_regime_preference = Column(String(10))  # Old or New (for TDS computation)
    form_16_delivery = Column(String(20), default="Email")  # Email, Download, Post

    # Professional / Social Profiles
    linkedin_url = Column(String(300))
    github_username = Column(String(100))     # For tech employees
    portfolio_url = Column(String(300))       # For designers, creatives, academics
    research_gate_url = Column(String(300))   # For researchers/academics
    languages_known = Column(JSON)            # [{"language": "Hindi", "proficiency": "Native"}, ...]

    # Profile
    profile_photo_url = Column(String(500))
    preferred_display_name = Column(String(150))
    directory_visibility = Column(String(20), default="public", index=True)  # public, team, hidden
    skills_tags = Column(Text)
    profile_completeness = Column(Integer, default=0)
    bio = Column(Text)
    interests = Column(Text)
    research_work = Column(Text)
    family_information = Column(Text)
    health_information = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="employee", foreign_keys=[user_id])
    branch = relationship("Branch", back_populates="employees")
    department = relationship("Department", back_populates="employees", foreign_keys=[department_id])
    designation = relationship("Designation", back_populates="employees")
    reporting_manager = relationship("Employee", remote_side=[id], foreign_keys=[reporting_manager_id])
    shift = relationship("Shift", back_populates="employees")
    business_unit = relationship("BusinessUnit", foreign_keys=[business_unit_id])
    cost_center = relationship("CostCenter", foreign_keys=[cost_center_id])
    location = relationship("WorkLocation", foreign_keys=[location_id])
    grade_band = relationship("GradeBand", foreign_keys=[grade_band_id])
    position = relationship("Position", foreign_keys=[position_id])

    educations = relationship("EmployeeEducation", back_populates="employee", cascade="all, delete-orphan")
    experiences = relationship("EmployeeExperience", back_populates="employee", cascade="all, delete-orphan")
    skills = relationship("EmployeeSkill", back_populates="employee", cascade="all, delete-orphan")
    certifications = relationship("EmployeeCertification", back_populates="employee", cascade="all, delete-orphan")
    family_members = relationship("EmployeeFamilyMember", back_populates="employee", cascade="all, delete-orphan")
    documents = relationship("EmployeeDocument", back_populates="employee", cascade="all, delete-orphan")
    lifecycle_events = relationship(
        "EmployeeLifecycleEvent",
        foreign_keys="EmployeeLifecycleEvent.employee_id",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeLifecycleEvent.event_date.desc()",
    )

    attendances = relationship("Attendance", back_populates="employee")
    leaves = relationship("LeaveRequest", back_populates="employee", foreign_keys="LeaveRequest.employee_id")
    payrolls = relationship("PayrollRecord", back_populates="employee")
    assets = relationship("AssetAssignment", back_populates="employee")
    goals = relationship("PerformanceGoal", back_populates="employee")
    helpdesk_tickets = relationship("HelpdeskTicket", back_populates="employee")
    exit_record = relationship("ExitRecord", back_populates="employee", uselist=False)


class EmployeeEducation(Base):
    __tablename__ = "employee_educations"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    degree = Column(String(100), nullable=False)     # 10th, 12th, B.Tech, MBBS, B.Ed, M.A., Ph.D, D.Ed, ITI, Diploma
    specialization = Column(String(150))             # Subject/stream/branch
    institution = Column(String(200))
    board_university = Column(String(200))
    pass_year = Column(Integer)
    from_year = Column(Integer)                      # Start year of course
    percentage_cgpa = Column(Numeric(5, 2))
    grade_class = Column(String(30))                 # First Class, Distinction, Pass, Merit
    education_mode = Column(String(30), default="Regular")  # Regular, Distance, Online, Correspondence, Part-time
    is_highest_qualification = Column(Boolean, default=False)
    roll_number = Column(String(50))                 # Board/university roll number
    registration_number = Column(String(50))
    document_url = Column(String(500))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    employee = relationship("Employee", back_populates="educations")


class EmployeeExperience(Base):
    __tablename__ = "employee_experiences"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    company_name = Column(String(200), nullable=False)
    company_industry = Column(String(100))           # IT, Healthcare, Education, Manufacturing, Banking
    company_location = Column(String(150))           # City / Country
    designation = Column(String(150))
    department = Column(String(100))
    employment_type = Column(String(30))             # Full-time, Part-time, Contract, Freelance, Internship
    from_date = Column(Date)
    to_date = Column(Date)
    is_current = Column(Boolean, default=False)
    responsibilities = Column(Text)
    reason_for_leaving = Column(String(200))         # Better opportunity, relocation, layoff, retirement
    last_drawn_salary = Column(Numeric(12, 2))
    last_drawn_currency = Column(String(3), default="INR")
    reference_name = Column(String(150))
    reference_contact = Column(String(30))
    appointment_letter_url = Column(String(500))
    relieving_letter_url = Column(String(500))
    experience_certificate_url = Column(String(500))
    payslip_url = Column(String(500))               # Last payslip for salary proof

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    employee = relationship("Employee", back_populates="experiences")


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    skill_name = Column(String(100), nullable=False)
    proficiency = Column(String(30))  # Beginner, Intermediate, Advanced, Expert
    years_experience = Column(Numeric(4, 1))

    employee = relationship("Employee", back_populates="skills")


class EmployeeCertification(Base):
    """Professional certifications, licenses, and regulatory qualifications."""
    __tablename__ = "employee_certifications"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    certification_name = Column(String(200), nullable=False)  # e.g. AWS Solutions Architect, PMP, CTET, BLS
    issuing_body = Column(String(200))          # Amazon Web Services, PMI, CBSE, AHA
    certification_type = Column(String(50))     # Technical, Medical, Teaching, Trade, Safety, Professional, Language
    certificate_number = Column(String(100))
    issue_date = Column(Date)
    expiry_date = Column(Date)                  # Null means no expiry
    is_renewable = Column(Boolean, default=False)
    score_grade = Column(String(50))            # Score, grade or band achieved
    document_url = Column(String(500))
    verification_url = Column(String(500))      # Online verification link if available

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    employee = relationship("Employee", back_populates="certifications")


class EmployeeFamilyMember(Base):
    """Structured family members — for PF nomination, insurance, emergency contacts."""
    __tablename__ = "employee_family_members"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(150), nullable=False)
    relation = Column(String(50), nullable=False)   # Father, Mother, Spouse, Son, Daughter, Brother, Sister, Guardian
    gender = Column(String(20))
    date_of_birth = Column(Date)
    occupation = Column(String(100))
    phone_number = Column(String(20))
    is_dependent = Column(Boolean, default=True)
    is_emergency_contact = Column(Boolean, default=False)
    is_pf_nominee = Column(Boolean, default=False)
    pf_nominee_share_percent = Column(Numeric(5, 2))   # % share in PF nomination
    is_insurance_covered = Column(Boolean, default=False)  # Group health insurance
    aadhaar_number = Column(String(20))                # For insurance/PF nominee KYC
    address = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    employee = relationship("Employee", back_populates="family_members")


class EmployeeDocument(Base):
    __tablename__ = "employee_documents"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(100), nullable=False)  # ID Proof, Address Proof, etc.
    document_name = Column(String(200))
    document_number = Column(String(100))
    file_url = Column(String(500))
    expiry_date = Column(Date)
    verification_status = Column(String(30), default="Pending", index=True)
    is_verified = Column(Boolean, default=False)
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True))
    verifier_name = Column(String(150))
    verifier_company = Column(String(200))
    verification_notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    employee = relationship("Employee", back_populates="documents")


class EmployeeLifecycleEvent(Base):
    __tablename__ = "employee_lifecycle_events"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    event_date = Column(Date, nullable=False)
    effective_from = Column(Date)
    effective_to = Column(Date)
    from_status = Column(String(30))
    to_status = Column(String(30))
    from_branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    to_branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    from_department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    to_department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    from_designation_id = Column(Integer, ForeignKey("designations.id", ondelete="SET NULL"), nullable=True)
    to_designation_id = Column(Integer, ForeignKey("designations.id", ondelete="SET NULL"), nullable=True)
    from_manager_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    to_manager_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    reason = Column(Text)
    remarks = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee", foreign_keys=[employee_id], back_populates="lifecycle_events")


class EmployeeChangeRequest(Base):
    __tablename__ = "employee_change_requests"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type = Column(String(60), nullable=False, index=True)
    field_name = Column(String(120), nullable=True, index=True)
    effective_date = Column(Date)
    field_changes_json = Column(JSON, nullable=False)
    old_value_json = Column(JSON)
    new_value_json = Column(JSON)
    document_path = Column(String(500))
    status = Column(String(30), default="Pending", index=True)
    reason = Column(Text)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True))
    review_remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee")


class ProbationReview(Base):
    __tablename__ = "probation_reviews"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    manager_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    review_date = Column(Date, nullable=False)
    performance_rating = Column(Integer)
    conduct_rating = Column(Integer)
    attendance_rating = Column(Integer)
    recommendation = Column(String(30), nullable=False)
    comments = Column(Text)
    status = Column(String(30), default="pending", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    employee = relationship("Employee", foreign_keys=[employee_id])
    manager = relationship("Employee", foreign_keys=[manager_id])


class ProbationAction(Base):
    __tablename__ = "probation_actions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(30), nullable=False, index=True)
    effective_date = Column(Date, nullable=False)
    extended_until = Column(Date)
    remarks = Column(Text)
    letter_generated = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee")
