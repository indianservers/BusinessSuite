from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(220), nullable=False)
    body = Column(Text, nullable=False)
    audience = Column(String(80), default="All")
    target_department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    target_location_id = Column(Integer, ForeignKey("work_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True))
    requires_acknowledgement = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False, index=True)
    published_at = Column(DateTime(timezone=True))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledgements = relationship("AnnouncementAcknowledgement", back_populates="announcement", cascade="all, delete-orphan")


class AnnouncementAcknowledgement(Base):
    __tablename__ = "announcement_acknowledgements"

    id = Column(Integer, primary_key=True, index=True)
    announcement_id = Column(Integer, ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True), server_default=func.now())

    announcement = relationship("Announcement", back_populates="acknowledgements")


class EngagementSurvey(Base):
    __tablename__ = "engagement_surveys"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(220), nullable=False)
    survey_type = Column(String(40), default="Pulse")
    question = Column(Text)
    options_json = Column(JSON)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String(30), default="Draft", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EngagementSurveyResponse(Base):
    __tablename__ = "engagement_survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("engagement_surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Numeric(5, 2))
    comments = Column(Text)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())


class Recognition(Base):
    __tablename__ = "recognitions"

    id = Column(Integer, primary_key=True, index=True)
    from_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    to_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    message = Column(Text)
    badge = Column(String(80))
    points = Column(Integer, default=0)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RecognitionReaction(Base):
    __tablename__ = "recognition_reactions"

    id = Column(Integer, primary_key=True, index=True)
    recognition_id = Column(Integer, ForeignKey("recognitions.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    emoji = Column(String(20), default="clap")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
