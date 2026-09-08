"""add operator count to receipt definitions

Revision ID: d7e4f9a2c113
Revises: c4d3e8a1b902
Create Date: 2026-09-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7e4f9a2c113"
down_revision: Union[str, Sequence[str], None] = "c4d3e8a1b902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("receipt_definitions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("operator_count", sa.Integer(), nullable=False, server_default="1")
        )


def downgrade() -> None:
    with op.batch_alter_table("receipt_definitions", schema=None) as batch_op:
        batch_op.drop_column("operator_count")