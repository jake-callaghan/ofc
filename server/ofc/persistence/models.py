"""sqlalchemy mappings, isolated from game logic and transport schemas."""

from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlayerRow(Base):
    __tablename__ = "players"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)


class GameRow(Base):
    __tablename__ = "games"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    invite_hash: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON)


class CommandRow(Base):
    __tablename__ = "commands"
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), primary_key=True)
    actor: Mapped[str] = mapped_column(ForeignKey("players.id"), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(BigInteger)


class HandRow(Base):
    __tablename__ = "hands"
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), primary_key=True)
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)
    boards: Mapped[dict[str, Any]] = mapped_column(JSON)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON)


class LedgerRow(Base):
    __tablename__ = "ledger"
    __table_args__ = (
        ForeignKeyConstraint(["game_id", "hand"], ["hands.game_id", "hands.number"]),
    )
    game_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    hand: Mapped[int] = mapped_column(Integer, primary_key=True)
    player: Mapped[str] = mapped_column(ForeignKey("players.id"), primary_key=True)
    units: Mapped[int] = mapped_column(BigInteger)


class AuthIdentityRow(Base):
    __tablename__ = "auth_identities"
    issuer: Mapped[str] = mapped_column(String(255), primary_key=True)
    subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), unique=True)


class AuthSessionRow(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), index=True)
    expires_at: Mapped[int] = mapped_column(BigInteger)
    provider_tokens: Mapped[str] = mapped_column(Text)
    recovery: Mapped[bool] = mapped_column(default=False)
    authenticated_at: Mapped[int] = mapped_column(BigInteger)


class AuthFlowRow(Base):
    __tablename__ = "auth_flows"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    verifier: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[int] = mapped_column(BigInteger)
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"))
