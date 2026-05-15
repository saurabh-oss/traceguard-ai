from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.failure import Failure

router = APIRouter(prefix="/api/failures", tags=["failures"])

@router.get("")
def list_failures(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(Failure).order_by(Failure.created_at.desc()).offset(skip).limit(limit).all()
    return [_row(r) for r in rows]

@router.get("/{failure_id}")
def get_failure(failure_id: str, db: Session = Depends(get_db)):
    r = db.query(Failure).filter(Failure.id == failure_id).first()
    if not r:
        raise HTTPException(404)
    return _row(r)

def _row(r):
    return {"id": r.id, "created_at": str(r.created_at),
            "run_id": r.run_id, "failure_type": r.failure_type,
            "failure_category": r.failure_category, "severity": r.severity,
            "title": r.title, "description": r.description,
            "root_cause_summary": r.root_cause_summary,
            "trace_evidence": r.trace_evidence, "status": r.status}