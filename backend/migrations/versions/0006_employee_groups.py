"""Add reusable employee groups and policy audiences.

Revision ID: 0006
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policies",
        sa.Column("all_employees", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "employee_groups",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "company_id", "name", name="uq_employee_group_name_per_company"
        ),
    )
    op.create_index("ix_employee_groups_company_id", "employee_groups", ["company_id"])
    op.create_table(
        "employee_group_members",
        sa.Column(
            "group_id",
            sa.String(64),
            sa.ForeignKey("employee_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("employee_id", sa.String(64), primary_key=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_employee_group_members_employee_id",
        "employee_group_members",
        ["employee_id"],
    )
    op.create_table(
        "policy_group_targets",
        sa.Column(
            "policy_id",
            sa.String(64),
            sa.ForeignKey("policies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "group_id",
            sa.String(64),
            sa.ForeignKey("employee_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("policy_group_targets")
    op.drop_index(
        "ix_employee_group_members_employee_id", table_name="employee_group_members"
    )
    op.drop_table("employee_group_members")
    op.drop_index("ix_employee_groups_company_id", table_name="employee_groups")
    op.drop_table("employee_groups")
    op.drop_column("policies", "all_employees")
