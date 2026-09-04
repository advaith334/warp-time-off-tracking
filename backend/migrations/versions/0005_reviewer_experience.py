"""Add company-scoped job history and persisted demo clock.

Revision ID: 0005
Revises: 0004
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_runs",
        sa.Column(
            "company_id", sa.String(64), nullable=False, server_default="cmp_warp_demo"
        ),
    )
    op.create_index("ix_job_runs_company_id", "job_runs", ["company_id"])
    op.create_table(
        "demo_state",
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("current_date", sa.Date, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("demo_state")
    op.drop_index("ix_job_runs_company_id", table_name="job_runs")
    op.drop_column("job_runs", "company_id")
