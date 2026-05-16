import asyncio, logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.patch import Patch, PatchStatus
from app.models.failure import Failure, FailureStatus
from app.config import settings
from app.api.auth import require_api_key
from app.agents.patch_bot import run_patch_bot_async

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/patches", tags=["patches"])


def _github_repo():
    if not settings.github_token or not settings.github_repo:
        return None
    try:
        from github import Github
        return Github(settings.github_token).get_repo(settings.github_repo)
    except Exception as e:
        log.warning("GitHub client error: %s", e)
        return None


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


@router.post("/{patch_id}/approve", dependencies=[Depends(require_api_key)])
def approve_patch(patch_id: str, db: Session = Depends(get_db)):
    patch = db.query(Patch).filter(Patch.id == patch_id).first()
    if not patch:
        raise HTTPException(404)

    github_result = {}
    if patch.pr_number:
        repo = _github_repo()
        if repo:
            try:
                pr = repo.get_pull(patch.pr_number)
                pr.create_issue_comment(
                    "✅ **Approved by TraceGuard AI human reviewer.**\n\n"
                    "Merging this auto-generated fix."
                )
                merge = pr.merge(
                    commit_title=f"[TraceGuard] Merge fix: {patch.patch_type or 'auto-patch'}",
                    commit_message=patch.explanation or "",
                    merge_method="squash",
                )
                github_result = {"merged": merge.merged, "sha": merge.sha}
            except Exception as e:
                log.warning("PR merge failed (marking approved anyway): %s", e)
                github_result = {"error": str(e)}

    patch.status = PatchStatus.merged if github_result.get("merged") else PatchStatus.approved
    failure = db.query(Failure).filter(Failure.id == patch.failure_id).first()
    if failure:
        failure.status = FailureStatus.resolved
    db.commit()
    return {"status": patch.status, "patch_id": patch_id, "github": github_result}


@router.post("/{patch_id}/reject", dependencies=[Depends(require_api_key)])
async def reject_patch(patch_id: str, body: dict = {}, db: Session = Depends(get_db)):
    patch = db.query(Patch).filter(Patch.id == patch_id).first()
    if not patch:
        raise HTTPException(404)

    notes = body.get("notes", "")
    github_result = {}
    if patch.pr_number:
        repo = _github_repo()
        if repo:
            try:
                pr = repo.get_pull(patch.pr_number)
                comment = "❌ **Rejected by TraceGuard AI human reviewer.**"
                if notes:
                    comment += f"\n\n**Reason:** {notes}\n\n_TraceGuard will generate a revised fix._"
                pr.create_issue_comment(comment)
                pr.edit(state="closed")
                github_result = {"closed": True}
            except Exception as e:
                log.warning("PR close failed (marking rejected anyway): %s", e)
                github_result = {"error": str(e)}

    patch.status = PatchStatus.rejected
    patch.reviewer_notes = notes
    db.commit()

    # If reviewer left notes, re-run the patch bot with that context
    if notes and patch.failure_id:
        asyncio.create_task(run_patch_bot_async(patch.failure_id, rejection_context=notes))
        return {"status": "rejected", "patch_id": patch_id,
                "github": github_result, "retry": "re-patching with reviewer notes"}

    return {"status": "rejected", "patch_id": patch_id, "github": github_result}


def _row(r):
    return {"id": r.id, "failure_id": r.failure_id,
            "patch_type": r.patch_type, "file_path": r.file_path,
            "original_code": r.original_code, "patched_code": r.patched_code,
            "explanation": r.explanation, "diff": r.diff,
            "pr_url": r.pr_url, "pr_number": r.pr_number,
            "branch_name": r.branch_name, "status": r.status,
            "reviewer_notes": r.reviewer_notes,
            "created_at": str(r.created_at)}
