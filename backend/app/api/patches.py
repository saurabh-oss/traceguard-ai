from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.patch import Patch, PatchStatus

router = APIRouter(prefix="/api/patches", tags=["patches"])

@router.get("")
def list_patches(db: Session = Depends(get_db)):
    rows = db.query(Patch).order_by(Patch.created_at.desc()).all()
    return [_row(r) for r in rows]

@router.get("/{patch_id}")
def get_patch(patch_id: str, db: Session = Depends(get_db)):
    r = db.query(Patch).filter(Patch.id == patch_id).first()
    if not r:
        raise HTTPException(404)
    return _row(r)

@router.post("/{patch_id}/approve")
def approve_patch(patch_id: str, db: Session = Depends(get_db)):
    r = db.query(Patch).filter(Patch.id == patch_id).first()
    if not r:
        raise HTTPException(404)
    r.status = PatchStatus.approved
    db.commit()
    return {"status": "approved", "patch_id": patch_id}

@router.post("/{patch_id}/reject")
def reject_patch(patch_id: str, body: dict = {}, db: Session = Depends(get_db)):
    r = db.query(Patch).filter(Patch.id == patch_id).first()
    if not r:
        raise HTTPException(404)
    r.status = PatchStatus.rejected
    r.reviewer_notes = body.get("notes", "")
    db.commit()
    return {"status": "rejected", "patch_id": patch_id}

def _row(r):
    return {"id": r.id, "failure_id": r.failure_id,
            "patch_type": r.patch_type, "file_path": r.file_path,
            "original_code": r.original_code, "patched_code": r.patched_code,
            "explanation": r.explanation, "diff": r.diff,
            "pr_url": r.pr_url, "pr_number": r.pr_number,
            "branch_name": r.branch_name, "status": r.status,
            "reviewer_notes": r.reviewer_notes,
            "created_at": str(r.created_at)}