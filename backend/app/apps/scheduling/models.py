from sqlalchemy import Column, Integer, String, JSON, UniqueConstraint
from app.db.base_class import Base


class ScheduleBoard(Base):
    __tablename__ = "schedule_boards"
    __table_args__ = (UniqueConstraint("tenant_key", "module", "source", name="uq_schedule_board_scope"),)
    id = Column(Integer, primary_key=True)
    tenant_key = Column(String(100), nullable=False)
    module = Column(String(30), nullable=False)
    source = Column(String(60), nullable=False)
    revision = Column(Integer, nullable=False, default=0)
    # Only CRM records without a native start field need supplementary planning dates.
    starts = Column(JSON, nullable=False, default=dict)
    links = Column(JSON, nullable=False, default=list)
