"""ensure notifications table for pre-notification databases

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24

早期数据库可能早于「后台通知」功能创建，未包含 notifications 表。
旧库走 stamp 0001 路径时不会自动补建该表，因此在此按基线定义补齐（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "notifications" in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_category", "notifications", ["category"], unique=False)
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"], unique=False)
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"], unique=False)
    op.create_index("ix_notifications_level", "notifications", ["level"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if "notifications" not in sa.inspect(bind).get_table_names():
        return
    op.drop_table("notifications")
