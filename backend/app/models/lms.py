from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.sql import func
from app.db.base_class import Base


class LearningCourse(Base):
    __tablename__ = "learning_courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(220), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    delivery_mode = Column(String(40), default="Online")
    duration_hours = Column(Numeric(6, 2), default=0)
    content_standard = Column(String(30), default="Internal")  # Internal, SCORM, xAPI, External
    scorm_package_url = Column(String(500))
    scorm_version = Column(String(40))
    xapi_activity_id = Column(String(300))
    xapi_launch_url = Column(String(500))
    external_launch_url = Column(String(500))
    completion_callback_url = Column(String(500))
    metadata_json = Column(JSON)
    is_mandatory = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LearningAssignment(Base):
    __tablename__ = "learning_assignments"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    due_date = Column(Date)
    status = Column(String(30), default="Assigned", index=True)
    completed_at = Column(DateTime(timezone=True))
    score = Column(Numeric(5, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LearningCertification(Base):
    __tablename__ = "learning_certifications"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("learning_courses.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(220), nullable=False)
    certificate_url = Column(String(500))
    issued_on = Column(Date)
    expires_on = Column(Date, index=True)
    status = Column(String(30), default="Active", index=True)
    renewal_required = Column(Boolean, default=False)
    renewal_due_on = Column(Date, index=True)
    reminder_days = Column(Integer, default=30)
    renewal_status = Column(String(30), default="Not Required", index=True)
    last_reminder_at = Column(DateTime(timezone=True))
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CertificationRenewal(Base):
    __tablename__ = "certification_renewals"

    id = Column(Integer, primary_key=True, index=True)
    certification_id = Column(Integer, ForeignKey("learning_certifications.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    due_on = Column(Date, nullable=False, index=True)
    status = Column(String(30), default="Due", index=True)
    reminder_sent_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    evidence_url = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
