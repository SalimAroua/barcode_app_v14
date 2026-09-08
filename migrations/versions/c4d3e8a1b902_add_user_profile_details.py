"""add employee and leadership details to users

Revision ID: c4d3e8a1b902
Revises: 9b267465bbc9
Create Date: 2026-09-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d3e8a1b902"
down_revision: Union[str, Sequence[str], None] = "9b267465bbc9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("employee_id", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("team_leader", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("shift_leader", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("shift_leader")
        batch_op.drop_column("team_leader")
        batch_op.drop_column("employee_id")