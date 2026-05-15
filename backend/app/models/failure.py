import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class FailureSeverity(str, Enum):
    low = "low"; medium = "medium"; high = "high"; critical = "critical"

class FailureStatus(str, Enum):
    new = "new"; classified = "classified"
    patch_pending = "patch_pending"; patched = "patched"; resolved = "resolved"

class Failure(Base):
    __tablename__ = "failures"
    id: Mapped[str] = mapped_column(String, primary_key=True,
                                     default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                  onupdate=datetime.utcnow)
    raw_trace: Mapped[dict]  = mapped_column(JSON, nullable=True)
    run_id: Mapped[str]      = mapped_column(String, nullable=True, index=True)
    failure_type: Mapped[str]    = mapped_column(String, nullable=True)
    failure_category: Mapped[str]= mapped_column(String, nullable=True)
    severity: Mapped[str]        = mapped_column(String, default="medium")
    title: Mapped[str]           = mapped_column(String, nullable=True)
    description: Mapped[str]     = mapped_column(Text, nullable=True)
    root_cause_summary: Mapped[str] = mapped_column(Text, nullable=True)
    trace_evidence: Mapped[list] = mapped_column(JSON, nullable=True)
    status: Mapped[str]          = mapped_column(String, default="new")