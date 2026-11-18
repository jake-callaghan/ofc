"""backfill leaderboard units at 10p, then preserve actual hand units."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ledger", sa.Column("leaderboard_unit_tenths", sa.BigInteger(), nullable=True)
    )
    # at the historical 10p rate, one penny represents one tenth of a unit.
    op.execute(
        "UPDATE ledger SET leaderboard_unit_tenths = leaderboard_pence WHERE leaderboard_pence IS NOT NULL"
    )


def downgrade():
    op.drop_column("ledger", "leaderboard_unit_tenths")
