"""Add advanced policy settings, tenure tiers, holidays, and rollover values.

Revision ID: 0004
Revises: 0003
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("policy_versions", sa.Column("max_balance_minutes", sa.Integer))
    op.add_column("policy_versions", sa.Column("carryover_cap_minutes", sa.Integer))
    op.add_column(
        "policy_versions",
        sa.Column("expires_at_period_end", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "policy_versions",
        sa.Column(
            "tenure_transition",
            sa.String(32),
            nullable=False,
            server_default="NEXT_PERIOD",
        ),
    )
    op.create_check_constraint(
        "tenure_transition",
        "policy_versions",
        "tenure_transition IN ('NEXT_PERIOD')",
    )
    op.add_column(
        "accrual_rules",
        sa.Column("min_tenure_months", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "holidays",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("observed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("company_id", "date", name="uq_holiday_company_date"),
    )
    op.create_index("ix_holidays_company_id", "holidays", ["company_id"])
    op.drop_constraint("entry_type", "ledger_entries", type_="check")
    op.create_check_constraint(
        "entry_type",
        "ledger_entries",
        "entry_type IN ('ACCRUAL', 'FORFEITURE', 'CARRYOVER', 'EXPIRATION', "
        "'REQUEST_DEBIT', 'REQUEST_REVERSAL')",
    )
    op.drop_constraint("source_type", "ledger_entries", type_="check")
    op.create_check_constraint(
        "source_type",
        "ledger_entries",
        "source_type IN ('SCHEDULED_ACCRUAL', 'PAYROLL_ACCRUAL', 'REQUEST', "
        "'REQUEST_CANCELLATION', 'PERIOD_ROLLOVER')",
    )
    op.drop_constraint("job_kind", "job_runs", type_="check")
    op.create_check_constraint(
        "job_kind", "job_runs", "kind IN ('SCHEDULED', 'PAYROLL', 'ROLLOVER')"
    )


def downgrade() -> None:
    op.drop_constraint("job_kind", "job_runs", type_="check")
    op.drop_constraint("source_type", "ledger_entries", type_="check")
    op.drop_constraint("entry_type", "ledger_entries", type_="check")
    op.drop_table("holidays")
    op.drop_column("accrual_rules", "min_tenure_months")
    op.drop_column("policy_versions", "tenure_transition")
    op.drop_column("policy_versions", "expires_at_period_end")
    op.drop_column("policy_versions", "carryover_cap_minutes")
    op.drop_column("policy_versions", "max_balance_minutes")
