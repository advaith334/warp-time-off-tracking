"""Add accrual inputs, ledger, snapshots, and job history.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policy_versions",
        sa.Column(
            "new_hire_proration",
            sa.String(32),
            nullable=False,
            server_default="PRORATE",
        ),
    )
    op.create_check_constraint(
        "new_hire_proration",
        "policy_versions",
        "new_hire_proration IN ('PRORATE', 'FULL', 'NONE')",
    )
    op.add_column("accrual_rules", sa.Column("per_minutes_worked", sa.Integer))
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("employee_id", sa.String(64), nullable=False),
        sa.Column("policy_id", sa.String(64), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("policy_version_id", sa.String(64), sa.ForeignKey("policy_versions.id"), nullable=False),
        sa.Column("entry_type", sa.String(32), nullable=False),
        sa.Column("amount_minutes", sa.Integer, nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_type", "source_id", name="uq_ledger_source"),
        sa.CheckConstraint("entry_type IN ('ACCRUAL')", name="entry_type"),
        sa.CheckConstraint(
            "source_type IN ('SCHEDULED_ACCRUAL', 'PAYROLL_ACCRUAL')",
            name="source_type",
        ),
    )
    op.create_index("ix_ledger_entries_company_id", "ledger_entries", ["company_id"])
    op.create_index("ix_ledger_entries_employee_id", "ledger_entries", ["employee_id"])
    op.create_table(
        "balance_snapshots",
        sa.Column("employee_id", sa.String(64), primary_key=True),
        sa.Column("policy_id", sa.String(64), sa.ForeignKey("policies.id"), primary_key=True),
        sa.Column("balance_minutes", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("entries_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('SCHEDULED', 'PAYROLL')", name="job_kind"),
    )


def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_table("balance_snapshots")
    op.drop_table("ledger_entries")
    op.drop_column("accrual_rules", "per_minutes_worked")
    op.drop_column("policy_versions", "new_hire_proration")
