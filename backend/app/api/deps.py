"""Shared FastAPI dependencies."""
from __future__ import annotations

from datetime import date

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import clock
from app.db import get_session
from app.integrations import Employee, employee_service


def get_actor(x_actor_id: str = Header(default="adm_lindsey")) -> Employee:
    """Who is making this call.

    Identity comes from a header set by the frontend's user switcher
    (decision I5). Real authentication is out of scope for the take-home, but
    every write still records `created_by`, so the audit trail is genuine.
    """
    try:
        return employee_service.get(x_actor_id)
    except LookupError:
        raise HTTPException(status_code=401, detail=f"Unknown actor {x_actor_id!r}") from None


def require_admin(actor: Employee = Depends(get_actor)) -> Employee:
    if not actor.is_admin:
        raise HTTPException(status_code=403, detail="This action requires an admin.")
    return actor


def require_self_or_admin(employee_id: str, actor: Employee) -> None:
    """Limit employee-scoped data to its owner unless the actor is an admin."""
    try:
        employee = employee_service.get(employee_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Unknown employee") from None
    if employee.company_id != actor.company_id:
        raise HTTPException(status_code=404, detail="Unknown employee")
    if employee_id != actor.id and not actor.is_admin:
        raise HTTPException(
            status_code=403, detail="You can only access your own employee data."
        )


def get_company_id(actor: Employee = Depends(get_actor)) -> str:
    return actor.company_id


def get_today(session: Session = Depends(get_session)) -> date:
    return clock.today(session)
