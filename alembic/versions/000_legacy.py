"""Legacy schema base: all 18 SQL migrations (001-018) already applied.

Revision ID: 000_legacy
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "000_legacy"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """No-op: schema already exists from legacy SQL migrations (001-018).

    Run `python scripts/stamp_migrations.py` after creating the database
    to mark this revision as applied.
    """
    pass


def downgrade():
    """No-op: cannot safely reverse the full legacy schema."""
    pass
