"""Company holiday calendar endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.deps import get_company_id, require_admin
from app.api.responses import HolidayOut
from app.db import get_session
from app.integrations import Employee
from app.models import Holiday
from app.schemas import HolidayIn
from app.services import holiday_service

router = APIRouter(prefix="/api/holidays", tags=["holidays"])


@router.get("", response_model=list[HolidayOut])
def list_holidays(
    year: int,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
):
    return holiday_service.list_for_year(session, company_id=company_id, year=year)


@router.post("", response_model=HolidayOut, status_code=201)
def add_holiday(
    payload: HolidayIn,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    _actor: Employee = Depends(require_admin),
):
    holiday_id = session.scalar(
        insert(Holiday)
        .values(company_id=company_id, **payload.model_dump())
        .on_conflict_do_update(
            index_elements=["company_id", "date"],
            set_={"name": payload.name, "observed": payload.observed},
        )
        .returning(Holiday.id)
    )
    session.commit()
    return session.get(Holiday, holiday_id)


@router.post("/sync", response_model=list[HolidayOut])
def sync_holidays(
    year: int,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    _actor: Employee = Depends(require_admin),
):
    holiday_service.ensure_year(session, company_id=company_id, year=year)
    session.commit()
    return holiday_service.list_for_year(session, company_id=company_id, year=year)
