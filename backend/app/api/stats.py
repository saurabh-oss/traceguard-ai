from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.failure import Failure, FailureStatus
from app.models.patch import Patch, PatchStatus

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats(db: Session = Depends(get_db)):
    total    = db.query(func.count(Failure.id)).scalar() or 0
    resolved = db.query(func.count(Failure.id)).filter(
        Failure.status == FailureStatus.resolved
    ).scalar() or 0

    by_severity = {
        s: (db.query(func.count(Failure.id)).filter(Failure.severity == s).scalar() or 0)
        for s in ("critical", "high", "medium", "low")
    }

    by_type = {
        ft: cnt
        for ft, cnt in db.query(Failure.failure_type, func.count(Failure.id))
                          .group_by(Failure.failure_type).all()
        if ft
    }

    # Daily failure counts — last 7 days (UTC)
    now = datetime.utcnow()
    daily = []
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        cnt = db.query(func.count(Failure.id)).filter(
            Failure.created_at >= day_start,
            Failure.created_at <  day_end,
        ).scalar() or 0
        daily.append({"date": day_start.strftime("%m/%d"), "count": cnt})

    total_patches  = db.query(func.count(Patch.id)).scalar() or 0
    merged_patches = db.query(func.count(Patch.id)).filter(
        Patch.status.in_([PatchStatus.merged, PatchStatus.approved])
    ).scalar() or 0

    return {
        "total":           total,
        "resolved":        resolved,
        "resolution_rate": round(resolved / total * 100) if total else 0,
        "by_severity":     by_severity,
        "by_type":         by_type,
        "daily":           daily,
        "total_patches":   total_patches,
        "merged_patches":  merged_patches,
    }
