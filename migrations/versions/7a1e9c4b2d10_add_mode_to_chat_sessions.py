"""add mode to chat sessions

Revision ID: 7a1e9c4b2d10
Revises: 662415373662
Create Date: 2026-07-06 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1e9c4b2d10'
down_revision: Union[str, Sequence[str], None] = '662415373662'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'chat_sessions',
        sa.Column('mode', sa.String(length=16), nullable=False, server_default='discussion'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_sessions', 'mode')
