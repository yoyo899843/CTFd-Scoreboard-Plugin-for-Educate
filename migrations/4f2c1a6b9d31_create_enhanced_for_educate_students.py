"""Create enhanced_for_educate_students table

Revision ID: 4f2c1a6b9d31
Revises:
Create Date: 2026-08-08

"""

import sqlalchemy as sa

from CTFd.plugins.migrations import get_all_tables

revision = "4f2c1a6b9d31"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(op=None):
    tables = get_all_tables(op)
    if "enhanced_for_educate_students" not in tables:
        op.create_table(
            "enhanced_for_educate_students",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("school", sa.String(length=128), nullable=True),
            sa.Column("student_class", sa.String(length=128), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )


def downgrade(op=None):
    tables = get_all_tables(op)
    if "enhanced_for_educate_students" in tables:
        op.drop_table("enhanced_for_educate_students")
