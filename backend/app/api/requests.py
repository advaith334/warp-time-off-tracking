"""Employee request and admin decision endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock, enums
from app.api.deps import get_actor, require_admin, require_self_or_admin
from app.api.responses import RequestPreviewOut, TimeOffRequestOut
from app.db import get_session
from app.domain.requests import RequestError
from app.integrations import Employee, employee_service
from app.models import TimeOffRequest
from app.schemas import DecisionIn, RequestIn
from app.services import request_service

router = APIRouter(prefix="/api/requests", tags=["requests"])


def _out(row: TimeOffRequest) -> TimeOffRequestOut:
    return TimeOffRequestOut.of(row, employee_service.get(row.employee_id).name)


def _request(session: Session, request_id: str) -> TimeOffRequest:
    row = session.get(TimeOffRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown request")
    return row


def _arguments(payload: RequestIn) -> dict:
    return {
        "employee_id": payload.employee_id,
        "category_id": payload.category_id,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "partial_minutes": payload.partial_minutes,
    }


@router.post("/preview", response_model=RequestPreviewOut)
def preview(
    payload: RequestIn,
    session: Session = Depends(get_session),
    actor: Employee = Depends(get_actor),
):
    require_self_or_admin(payload.employee_id, actor)
    try:
        result = request_service.preview(session, **_arguments(payload))
    except RequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {
        "total_minutes": result["total_minutes"],
        "available_minutes": result["available_minutes"],
        "days": [
            {"date": day, "minutes": minutes} for day, minutes in result["days"]
        ],
    }


@router.post("", response_model=TimeOffRequestOut, status_code=201)
def submit(
    payload: RequestIn,
    session: Session = Depends(get_session),
    actor: Employee = Depends(get_actor),
):
    require_self_or_admin(payload.employee_id, actor)
    try:
        row = request_service.submit(
            session,
            actor_id=actor.id,
            reason=payload.reason,
            **_arguments(payload),
        )
    except RequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    session.commit()
    return _out(row)


@router.get("", response_model=list[TimeOffRequestOut])
def list_requests(
    employee_id: str | None = Query(default=None),
    status: enums.RequestStatus | None = Query(default=None),
    session: Session = Depends(get_session),
    actor: Employee = Depends(get_actor),
):
    if employee_id:
        require_self_or_admin(employee_id, actor)
    elif not actor.is_admin:
        employee_id = actor.id
    query = select(TimeOffRequest)
    if employee_id:
        query = query.where(TimeOffRequest.employee_id == employee_id)
    if status:
        query = query.where(TimeOffRequest.status == status)
    return [_out(row) for row in session.scalars(query.order_by(TimeOffRequest.created_at.desc()))]


def _decide(
    request_id: str,
    payload: DecisionIn,
    approve: bool,
    session: Session,
    actor: Employee,
):
    try:
        row = request_service.decide(
            session,
            request=_request(session, request_id),
            approve=approve,
            actor_id=actor.id,
            note=payload.note,
        )
    except RequestError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    session.commit()
    return _out(row)


@router.post("/{request_id}/approve", response_model=TimeOffRequestOut)
def approve(
    request_id: str,
    payload: DecisionIn,
    session: Session = Depends(get_session),
    actor: Employee = Depends(require_admin),
):
    return _decide(request_id, payload, True, session, actor)


@router.post("/{request_id}/deny", response_model=TimeOffRequestOut)
def deny(
    request_id: str,
    payload: DecisionIn,
    session: Session = Depends(get_session),
    actor: Employee = Depends(require_admin),
):
    return _decide(request_id, payload, False, session, actor)


@router.post("/{request_id}/cancel", response_model=TimeOffRequestOut)
def cancel(
    request_id: str,
    session: Session = Depends(get_session),
    actor: Employee = Depends(get_actor),
):
    row = _request(session, request_id)
    require_self_or_admin(row.employee_id, actor)
    try:
        request_service.cancel(
            session, request=row, actor_id=actor.id, today=clock.today(session)
        )
    except RequestError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    session.commit()
    return _out(row)
