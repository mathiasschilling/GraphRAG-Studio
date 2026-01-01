"""add key_usage to runs

Revision ID: 20250102_add_key_usage
Revises: 
Create Date: 2025-01-02 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20250102_add_key_usage"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("key_usage", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "key_usage")
