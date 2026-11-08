from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class ExitRecord(Base):
    __tablename__ = "exit_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    exit_type = Column(String(30))  # Resignation, Termination, Retirement, Absconding
    resignation_date = Column(Date)
    last_working_date = Column(Date)
    notice_period_days = Column(Integer)
    notice_waived = Column(Boolean, default=False)
    reason = Column(Text)
    status = Column(String(30), default="Initiated")  # Initiated, In Progress, Completed, Cancelled
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    final_settlement_amount = Column(Numeric(14, 2))
    final_settlement_date = Column(Date)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    employee = relationship("Employee", back_populates="exit_records")
    checklist_items = relationship("ExitChecklistItem", back_populates="exit_record", cascade="all, delete-orphan")
    interviews = relationship("ExitInterview", back_populates="exit_record", cascade="all, delete-orphan")


class ExitChecklistItem(Base):
    __tablename__ = "exit_checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    exit_record_id = Column(Integer, ForeignKey("exit_records.id", ondelete="CASCADE"), nullable=False)
    task_name = Column(String(200), nullable=False)
    assigned_to_role = Column(String(50))  # HR, IT, Finance, Manager
    assigned_to_user = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True))
    remarks = Column(Text)

    exit_record = relationship("ExitRecord", back_populates="checklist_items")


class ExitInterview(Base):
    __tablename__ = "exit_interviews"

    id = Column(Integer, primary_key=True, index=True)
    exit_record_id = Column(Integer, ForeignKey("exit_records.id", ondelete="CASCADE"), nullable=False)
    conducted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    interview_date = Column(Date)
    reason_for_leaving = Column(String(100))
    job_satisfaction = Column(Integer)  # 1-10
    management_satisfaction = Column(Integer)
    work_environment_satisfaction = Column(Integer)
    growth_satisfaction = Column(Integer)
    would_rejoin = Column(Boolean)
    feedback = Column(Text)
    suggestions = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    exit_record = relationship("ExitRecord", back_populates="interviews")
