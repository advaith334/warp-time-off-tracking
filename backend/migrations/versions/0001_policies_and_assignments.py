"""Add policies, immutable versions, rules, and assignments.

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ExcludeConstraint

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "time_off_categories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("icon", sa.String(16)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "name", name="uq_category_name_per_company"),
    )
    op.create_index("ix_time_off_categories_company_id", "time_off_categories", ["company_id"])
    op.create_table(
        "policies",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("category_id", sa.String(64), sa.ForeignKey("time_off_categories.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "name", name="uq_policy_name_per_company"),
    )
    op.create_index("ix_policies_company_id", "policies", ["company_id"])
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("policy_id", sa.String(64), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("change_reason", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("policy_id", "version_no", name="uq_policy_version_number"),
        sa.UniqueConstraint("policy_id", "effective_from", name="uq_policy_version_effective_date"),
        sa.CheckConstraint("kind IN ('UNLIMITED', 'ACCRUAL')", name="policy_kind"),
    )
    op.create_index("ix_policy_versions_policy_id", "policy_versions", ["policy_id"])
    op.create_table(
        "accrual_rules",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("policy_version_id", sa.String(64), sa.ForeignKey("policy_versions.id"), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("frequency", sa.String(32)),
        sa.Column("accrues_at", sa.String(32)),
        sa.CheckConstraint("method IN ('TIME', 'HOURS_WORKED')", name="accrual_method"),
        sa.CheckConstraint("unit IN ('DAY', 'HOUR', 'MINUTE')", name="rate_unit"),
        sa.CheckConstraint("frequency IS NULL OR frequency IN ('MONTHLY', 'YEARLY')", name="accrual_schedule"),
        sa.CheckConstraint("accrues_at IS NULL OR accrues_at IN ('START_OF_PERIOD', 'END_OF_PERIOD')", name="accrues_at"),
    )
    op.create_index("ix_accrual_rules_policy_version_id", "accrual_rules", ["policy_version_id"])
    op.create_table(
        "policy_assignments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("employee_id", sa.String(64), nullable=False),
        sa.Column("policy_id", sa.String(64), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("category_id", sa.String(64), sa.ForeignKey("time_off_categories.id"), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ExcludeConstraint(
            ("employee_id", "="),
            ("category_id", "="),
            (sa.text("daterange(effective_from, coalesce(effective_to, 'infinity'::date), '[]')"), "&&"),
            name="ex_no_overlapping_assignment_per_category",
            using="gist",
        ),
    )
    op.create_index("ix_policy_assignments_company_id", "policy_assignments", ["company_id"])
    op.create_index("ix_policy_assignments_employee_id", "policy_assignments", ["employee_id"])


def downgrade() -> None:
    op.drop_table("policy_assignments")
    op.drop_table("accrual_rules")
    op.drop_table("policy_versions")
    op.drop_table("policies")
    op.drop_table("time_off_categories")
