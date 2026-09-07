"""add workflow metadata

Revision ID: 9b267465bbc9
Revises: a7d453f2d44f
Create Date: 2026-09-07 12:17:13.958662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b267465bbc9'
down_revision: Union[str, Sequence[str], None] = 'a7d453f2d44f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('receipt_definitions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('template_file_path', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('target_quantity', sa.Integer(), nullable=True))

    with op.batch_alter_table('scan_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('operators', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('target_quantity', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('printed_label_path', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('scan_sessions', schema=None) as batch_op:
        batch_op.drop_column('printed_label_path')
        batch_op.drop_column('target_quantity')
        batch_op.drop_column('operators')

    with op.batch_alter_table('receipt_definitions', schema=None) as batch_op:
        batch_op.drop_column('target_quantity')
        batch_op.drop_column('template_file_path')
