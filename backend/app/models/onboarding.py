from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class OnboardingTemplate(Base):
    __tablename__ = "onboarding_templates"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    applicable_for = Column(String(30), default="all", index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    tasks = relationship(
        "OnboardingTemplateTask",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="OnboardingTemplateTask.order_index",
    )
    employee_onboardings = relationship("EmployeeOnboarding", back_populates="template")


class OnboardingTemplateTask(Base):
    __tablename__ = "onboarding_template_tasks"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("onboarding_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    task_name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50), default="other", index=True)
    due_day_offset = Column(Integer, default=1)
    assigned_to_role = Column(String(50), default="employee", index=True)
    is_mandatory = Column(Boolean, default=True)
    order_index = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    template = relationship("OnboardingTemplate", back_populates="tasks")
    employee_tasks = relationship("EmployeeOnboardingTask", back_populates="template_task")


class EmployeeOnboarding(Base):
    __tablename__ = "employee_onboardings"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("onboarding_templates.id", ondelete="SET NULL"), nullable=True)
    start_date = Column(Date)
    target_completion_date = Column(Date)
    status = Column(String(30), default="not_started", index=True)
    completion_percentage = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    employee = relationship("Employee")
    template = relationship("OnboardingTemplate", back_populates="employee_onboardings")
    tasks = relationship(
        "EmployeeOnboardingTask",
        back_populates="employee_onboarding",
        cascade="all, delete-orphan",
        order_by="EmployeeOnboardingTask.due_date",
    )


class EmployeeOnboardingTask(Base):
    __tablename__ = "employee_onboarding_tasks"

    id = Column(Integer, primary_key=True, index=True)
    employee_onboarding_id = Column(
        Integer,
        ForeignKey("employee_onboardings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_task_id = Column(Integer, ForeignKey("onboarding_template_tasks.id", ondelete="SET NULL"), nullable=True)
    task_name = Column(String(200), nullable=False)
    category = Column(String(50), default="other", index=True)
    due_date = Column(Date, index=True)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="pending", index=True)
    completed_at = Column(DateTime(timezone=True))
    completed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee_onboarding = relationship("EmployeeOnboarding", back_populates="tasks")
    template_task = relationship("OnboardingTemplateTask", back_populates="employee_tasks")


class PolicyAcknowledgement(Base):
    __tablename__ = "policy_acknowledgements"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    policy_name = Column(String(200), nullable=False)
    policy_document_url = Column(String(500))
    acknowledged_at = Column(DateTime(timezone=True))
    ip_address = Column(String(50))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
