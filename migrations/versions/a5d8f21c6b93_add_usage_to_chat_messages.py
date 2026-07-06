"""add usage/cost columns to chat_messages

Revision ID: a5d8f21c6b93
Revises: 3f6b8d1c9a42
Create Date: 2026-07-06 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5d8f21c6b93'
down_revision: Union[str, Sequence[str], None] = '3f6b8d1c9a42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chat_messages', sa.Column('input_tokens', sa.Integer(), nullable=True))
    op.add_column('chat_messages', sa.Column('output_tokens', sa.Integer(), nullable=True))
    op.add_column('chat_messages', sa.Column('cache_creation_input_tokens', sa.Integer(), nullable=True))
    op.add_column('chat_messages', sa.Column('cache_read_input_tokens', sa.Integer(), nullable=True))
    op.add_column('chat_messages', sa.Column('cost_usd', sa.Numeric(12, 6), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_messages', 'cost_usd')
    op.drop_column('chat_messages', 'cache_read_input_tokens')
    op.drop_column('chat_messages', 'cache_creation_input_tokens')
    op.drop_column('chat_messages', 'output_tokens')
    op.drop_column('chat_messages', 'input_tokens')
