"""initial portable game, command, hand, and unit-ledger schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "players",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
    )
    op.create_table(
        "games",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("invite_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("state", sa.JSON(), nullable=False),
    )
    op.create_table(
        "commands",
        sa.Column(
            "game_id", sa.String(36), sa.ForeignKey("games.id"), primary_key=True
        ),
        sa.Column(
            "actor", sa.String(36), sa.ForeignKey("players.id"), primary_key=True
        ),
        sa.Column("request_id", sa.String(128), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
    )
    op.create_table(
        "hands",
        sa.Column(
            "game_id", sa.String(36), sa.ForeignKey("games.id"), primary_key=True
        ),
        sa.Column("number", sa.Integer(), primary_key=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("boards", sa.JSON(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
    )
    op.create_table(
        "ledger",
        sa.Column("game_id", sa.String(36), primary_key=True),
        sa.Column("hand", sa.Integer(), primary_key=True),
        sa.Column(
            "player", sa.String(36), sa.ForeignKey("players.id"), primary_key=True
        ),
        sa.Column("units", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["game_id", "hand"], ["hands.game_id", "hands.number"]),
    )


def downgrade():
    for table in ("ledger", "hands", "commands", "games", "players"):
        op.drop_table(table)
