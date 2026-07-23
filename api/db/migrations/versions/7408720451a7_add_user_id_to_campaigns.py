"""add user_id to campaigns

Revision ID: 7408720451a7
Revises: 470f2e081571
Create Date: 2026-07-23 21:00:04.643952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7408720451a7'
down_revision: Union[str, Sequence[str], None] = '470f2e081571'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaigns', sa.Column('user_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_campaigns_user_id', 'campaigns', 'users', ['user_id'], ['id']
    )
    op.create_index(op.f('ix_campaigns_user_id'), 'campaigns', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_campaigns_user_id'), table_name='campaigns')
    op.drop_constraint('fk_campaigns_user_id', 'campaigns', type_='foreignkey')
    op.drop_column('campaigns', 'user_id')
