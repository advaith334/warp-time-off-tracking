"""Read-through to the Employee Service stub (decision I6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_company_id
from app.api.responses import EmployeeOut
from app.integrations import employee_service

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeOut])
def list_employees(company_id: str = Depends(get_company_id)):
    return employee_service.list_for_company(company_id)


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: str):
    try:
        return employee_service.get(employee_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Unknown employee") from None
