"""Add request workflow, pending holds, and negative-balance controls.

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policy_versions",
        sa.Column("allow_negative", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "policy_versions",
        sa.Column("negative_floor_minutes", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "balance_snapshots",
        sa.Column("pending_hold_minutes", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "time_off_requests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("employee_id", sa.String(64), nullable=False),
        sa.Column("policy_id", sa.String(64), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("policy_version_id", sa.String(64), sa.ForeignKey("policy_versions.id"), nullable=False),
        sa.Column("category_id", sa.String(64), sa.ForeignKey("time_off_categories.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("total_minutes", sa.Integer, nullable=False),
        sa.Column("is_partial_day", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("decided_by", sa.String(64)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'DENIED', 'CANCELLED')",
            name="request_status",
        ),
    )
    op.create_index("ix_time_off_requests_company_id", "time_off_requests", ["company_id"])
    op.create_index("ix_time_off_requests_employee_id", "time_off_requests", ["employee_id"])
    op.create_table(
        "request_days",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("request_id", sa.String(64), sa.ForeignKey("time_off_requests.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("minutes", sa.Integer, nullable=False),
        sa.UniqueConstraint("request_id", "date", name="uq_request_day"),
    )
    op.create_table(
        "request_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("request_id", sa.String(64), sa.ForeignKey("time_off_requests.id"), nullable=False),
        sa.Column("from_status", sa.String(32)),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN ('PENDING', 'APPROVED', 'DENIED', 'CANCELLED')",
            name="request_event_from_status",
        ),
        sa.CheckConstraint(
            "to_status IN ('PENDING', 'APPROVED', 'DENIED', 'CANCELLED')",
            name="request_event_to_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("request_events")
    op.drop_table("request_days")
    op.drop_table("time_off_requests")
    op.drop_column("balance_snapshots", "pending_hold_minutes")
    op.drop_column("policy_versions", "negative_floor_minutes")
    op.drop_column("policy_versions", "allow_negative")
