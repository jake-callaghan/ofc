"""freeze per-hand stakes and record exact gbp scores without repricing history."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hands", sa.Column("accounting", sa.JSON(), nullable=True))
    op.add_column("ledger", sa.Column("amount_pence", sa.BigInteger(), nullable=True))
    op.add_column(
        "ledger", sa.Column("leaderboard_pence", sa.BigInteger(), nullable=True)
    )


def downgrade():
    op.drop_column("ledger", "leaderboard_pence")
    op.drop_column("ledger", "amount_pence")
    op.drop_column("hands", "accounting")
