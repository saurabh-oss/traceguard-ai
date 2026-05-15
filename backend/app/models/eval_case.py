import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Text, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class EvalCase(Base):
    __tablename__ = "eval_cases"
    id: Mapped[str]         = mapped_column(String, primary_key=True,
                                             default=lambda: str(uuid.uuid4()))
    failure_id: Mapped[str] = mapped_column(String, ForeignKey("failures.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    evaluator_name: Mapped[str]  = mapped_column(String, nullable=True)
    evaluator_code: Mapped[str]  = mapped_column(Text, nullable=True)
    test_input: Mapped[dict]     = mapped_column(JSON, nullable=True)
    expected_output: Mapped[str] = mapped_column(Text, nullable=True)
    shadow_score_before: Mapped[float] = mapped_column(Float, nullable=True)
    shadow_score_after: Mapped[float]  = mapped_column(Float, nullable=True)
    auto_promoted: Mapped[str]   = mapped_column(String, default="pending")