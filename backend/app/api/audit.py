"""Admin-only operational history."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_company_id, require_admin
from app.api.responses import JobRunOut
from app.db import get_session
from app.integrations import Employee
from app.models import JobRun

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/job-runs", response_model=list[JobRunOut])
def job_runs(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    _actor: Employee = Depends(require_admin),
):
    return list(
        session.scalars(
            select(JobRun)
            .where(JobRun.company_id == company_id)
            .order_by(JobRun.created_at.desc())
            .limit(limit)
        )
    )
