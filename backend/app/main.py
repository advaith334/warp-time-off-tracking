"""FastAPI application entry point."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import assignments, employees, policies
from app.config import settings
from app.db import get_session
from app.logging_config import RequestIdMiddleware
from app.logging_config import configure as configure_logging

configure_logging()

app = FastAPI(
    title="Warp Time Off",
    version="0.1.0",
    description="Employee time off tracking: policies, accrual, requests, balances, audit.",
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (employees, policies, assignments):
    app.include_router(module.router)


@app.get("/api/health", tags=["meta"])
def health(session: Session = Depends(get_session)) -> dict:
    """Report whether the API can reach PostgreSQL."""
    db_ok = session.execute(text("SELECT 1")).scalar() == 1
    return {"status": "ok", "database": "up" if db_ok else "down"}
