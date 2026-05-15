import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class PatchStatus(str, Enum):
    pending = "pending"; pr_opened = "pr_opened"
    approved = "approved"; rejected = "rejected"; merged = "merged"

class Patch(Base):
    __tablename__ = "patches"
    id: Mapped[str]         = mapped_column(String, primary_key=True,
                                             default=lambda: str(uuid.uuid4()))
    failure_id: Mapped[str] = mapped_column(String, ForeignKey("failures.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                  onupdate=datetime.utcnow)
    patch_type: Mapped[str]    = mapped_column(String, nullable=True)
    file_path: Mapped[str]     = mapped_column(String, nullable=True)
    original_code: Mapped[str] = mapped_column(Text, nullable=True)
    patched_code: Mapped[str]  = mapped_column(Text, nullable=True)
    explanation: Mapped[str]   = mapped_column(Text, nullable=True)
    diff: Mapped[str]          = mapped_column(Text, nullable=True)
    pr_url: Mapped[str]        = mapped_column(String, nullable=True)
    pr_number: Mapped[int]     = mapped_column(nullable=True)
    branch_name: Mapped[str]   = mapped_column(String, nullable=True)
    status: Mapped[str]        = mapped_column(String, default="pending")
    reviewer_notes: Mapped[str]= mapped_column(Text, nullable=True)