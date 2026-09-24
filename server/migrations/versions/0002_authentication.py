"""stable supabase identities, revocable browser sessions, and one-time login flows."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("players") as batch:
        batch.alter_column("token_hash", existing_type=sa.String(64), nullable=True)
    op.create_table(
        "auth_identities",
        sa.Column("issuer", sa.String(255), primary_key=True),
        sa.Column("subject", sa.String(128), primary_key=True),
        sa.Column(
            "player_id",
            sa.String(36),
            sa.ForeignKey("players.id"),
            nullable=False,
            unique=True,
        ),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "player_id", sa.String(36), sa.ForeignKey("players.id"), nullable=False
        ),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("provider_tokens", sa.Text(), nullable=False),
        sa.Column("recovery", sa.Boolean(), nullable=False),
        sa.Column("authenticated_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_auth_sessions_player_id", "auth_sessions", ["player_id"])
    op.create_table(
        "auth_flows",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("verifier", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("player_id", sa.String(36), sa.ForeignKey("players.id")),
    )


def downgrade():
    op.drop_table("auth_flows")
    op.drop_table("auth_sessions")
    op.drop_table("auth_identities")
    # invalidate account sessions without removing players or their game history.
    players = sa.table("players", sa.column("id"), sa.column("token_hash"))
    op.execute(
        players.update()
        .where(players.c.token_hash.is_(None))
        .values(token_hash=players.c.id)
    )
    with op.batch_alter_table("players") as batch:
        batch.alter_column("token_hash", existing_type=sa.String(64), nullable=False)
