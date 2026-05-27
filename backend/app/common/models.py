from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CommonPerson(Base):
    __tablename__ = "common_people"
    __table_args__ = (
        Index("idx_common_people_source", "source_module", "source_record_type", "source_record_id"),
        Index("idx_common_people_org_status", "organization_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True, index=True)
    primary_email = Column(String(150), unique=True, nullable=True, index=True)
    phone_number = Column(String(30), nullable=True)
    first_name = Column(String(80), nullable=True)
    middle_name = Column(String(80), nullable=True)
    last_name = Column(String(80), nullable=True)
    display_name = Column(String(180), nullable=False, index=True)
    status = Column(String(30), default="active", index=True)
    source_module = Column(String(50), nullable=True, index=True)
    source_record_type = Column(String(80), nullable=True)
    source_record_id = Column(Integer, nullable=True, index=True)
    external_refs_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="person")
    profile = relationship("CommonProfile", back_populates="person", uselist=False, cascade="all, delete-orphan")


class CommonProfile(Base):
    __tablename__ = "common_profiles"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("common_people.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    preferred_display_name = Column(String(180), nullable=True)
    profile_photo_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    timezone = Column(String(80), default="Asia/Kolkata")
    locale = Column(String(20), default="en-IN")
    directory_visibility = Column(String(20), default="public", index=True)
    skills_json = Column(JSON, nullable=True)
    profile_data_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    person = relationship("CommonPerson", back_populates="profile")
