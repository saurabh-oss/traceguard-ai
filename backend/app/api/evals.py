from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.eval_case import EvalCase

router = APIRouter(prefix="/api/evals", tags=["evals"])

@router.get("")
def list_evals(db: Session = Depends(get_db)):
    rows = db.query(EvalCase).order_by(EvalCase.created_at.desc()).all()
    return [_row(r) for r in rows]

def _row(r):
    return {"id": r.id, "failure_id": r.failure_id,
            "evaluator_name": r.evaluator_name,
            "evaluator_code": r.evaluator_code,
            "test_input": r.test_input,
            "expected_output": r.expected_output,
            "shadow_score_before": r.shadow_score_before,
            "shadow_score_after": r.shadow_score_after,
            "auto_promoted": r.auto_promoted,
            "created_at": str(r.created_at)}