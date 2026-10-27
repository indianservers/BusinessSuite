"""Shared enforcement state. Keys are HMAC digests, never account names or tokens."""

from sqlalchemy import Column, String, BigInteger, Integer, CheckConstraint, ForeignKey
from app.db.base_class import Base


class SecurityRateBucket(Base):
    __tablename__ = "security_rate_buckets"
    __table_args__ = (
        CheckConstraint("count >= 1", name="ck_security_rate_count_positive"),
    )
    key = Column(String(64), primary_key=True)
    window = Column(BigInteger, primary_key=True)
    count = Column(Integer, nullable=False)
    expires = Column(BigInteger, nullable=False, index=True)


class SecurityWorkLease(Base):
    __tablename__ = "security_work_leases"
    __table_args__ = (
        CheckConstraint("slot >= 0", name="ck_security_work_slot_nonnegative"),
    )
    key = Column(String(64), primary_key=True)
    slot = Column(Integer, primary_key=True)
    token = Column(String(64), nullable=False)
    expires = Column(BigInteger, nullable=False, index=True)


class SecurityResourceOwnership(Base):
    __tablename__ = "security_resource_ownership"
    resource_table = Column(String(100), primary_key=True)
    resource_id = Column(BigInteger, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
