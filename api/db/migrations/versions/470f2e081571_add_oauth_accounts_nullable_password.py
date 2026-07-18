"""add oauth_accounts table, make users.password_hash nullable

Revision ID: 470f2e081571
Revises: 2a3c519f79e1
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '470f2e081571'
down_revision: Union[str, Sequence[str], None] = '2a3c519f79e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # OAuth-only signups (Google/Microsoft/GitHub) never set a password -
    # see api/models/user.py.
    op.alter_column('users', 'password_hash',
        existing_type=sa.String(length=255),
        nullable=True,
    )

    op.create_table('oauth_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('provider_user_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_user_id', name='uq_oauth_provider_identity'),
        sa.UniqueConstraint('user_id', 'provider', name='uq_oauth_user_provider'),
    )
    op.create_index(op.f('ix_oauth_accounts_user_id'), 'oauth_accounts', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_oauth_accounts_user_id'), table_name='oauth_accounts')
    op.drop_table('oauth_accounts')

    op.alter_column('users', 'password_hash',
        existing_type=sa.String(length=255),
        nullable=False,
    )
