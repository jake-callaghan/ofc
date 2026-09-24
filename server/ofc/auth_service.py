"""map verified supabase accounts to stable players and encrypted server sessions."""

import base64
import hashlib
import json
import secrets
import time
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from ofc.auth_provider import AuthError
from ofc.persistence.models import (
    AuthFlowRow,
    AuthIdentityRow,
    AuthSessionRow,
    PlayerRow,
)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class AuthService:
    def __init__(self, repository, provider, *, clock=time.time):
        self.repository = repository
        self.provider = provider
        self.settings = provider.settings
        self.cipher = Fernet(self.settings.encryption_key.encode())
        self.clock = clock

    def encrypt(self, value):
        return self.cipher.encrypt(json.dumps(value).encode()).decode()

    def decrypt(self, value):
        try:
            return json.loads(self.cipher.decrypt(value.encode()))
        except (InvalidToken, ValueError):
            raise AuthError(
                "Your session has expired. Please sign in again.", 401
            ) from None

    def verified(self, tokens):
        if not tokens.get("access_token") or not tokens.get("refresh_token"):
            raise AuthError("Please verify your email before signing in.", 401)
        user = self.provider.user(tokens["access_token"])
        try:
            subject = str(UUID(user["id"]))
        except (KeyError, ValueError, TypeError):
            raise AuthError("Invalid account identity.", 401) from None
        if not user.get("email") or not user.get("email_confirmed_at"):
            raise AuthError("Please verify your email before signing in.", 401)
        return {
            "subject": subject,
            "email": user["email"],
            "name": str(
                user.get("user_metadata", {}).get("name")
                or user.get("user_metadata", {}).get("full_name")
                or user["email"].split("@")[0]
            )[:80],
            "providers": sorted(
                {
                    i.get("provider")
                    for i in user.get("identities", [])
                    if i.get("provider")
                }
            ),
        }

    def pack(self, tokens, user):
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "refresh_at": int(self.clock()) + int(tokens.get("expires_in", 3600)) - 60,
            "user": user,
        }

    def login(self, tokens, *, recovery=False, expected_player=None, old_token=None):
        user = self.verified(tokens)
        issuer = self.settings.url + "/auth/v1"
        # the unique issuer/subject key makes concurrent first logins converge.
        for attempt in range(2):
            try:
                with self.repository.transaction(write=True) as uow:
                    db = uow.session
                    identity = db.get(AuthIdentityRow, (issuer, user["subject"]))
                    if expected_player and (
                        identity is None or identity.player_id != expected_player
                    ):
                        raise AuthError(
                            "That login belongs to a different account. No accounts were merged.",
                            409,
                        )
                    if identity is None:
                        player = PlayerRow(
                            id=str(uuid4()), name=user["name"], token_hash=None
                        )
                        db.add(player)
                        db.flush()
                        identity = AuthIdentityRow(
                            issuer=issuer, subject=user["subject"], player_id=player.id
                        )
                        db.add(identity)
                        db.flush()
                    if old_token:
                        db.execute(
                            delete(AuthSessionRow).where(
                                AuthSessionRow.token_hash == digest(old_token)
                            )
                        )
                    now = int(self.clock())
                    db.execute(
                        delete(AuthSessionRow).where(AuthSessionRow.expires_at <= now)
                    )
                    token = secrets.token_urlsafe(32)
                    row = AuthSessionRow(
                        token_hash=digest(token),
                        player_id=identity.player_id,
                        expires_at=now
                        + (900 if recovery else self.settings.session_seconds),
                        provider_tokens=self.encrypt(self.pack(tokens, user)),
                        recovery=recovery,
                        authenticated_at=now,
                    )
                    db.add(row)
                    return token, self.profile(db, row, user)
            except IntegrityError:
                if attempt:
                    raise
        raise AuthError()

    def profile(self, db, row, user):
        return {
            "player_id": row.player_id,
            "name": db.get(PlayerRow, row.player_id).name,
            "email": user["email"],
            "providers": user["providers"],
            "recovery": row.recovery,
        }

    def session(self, token, *, allow_recovery=False, recent=False):
        if not token:
            raise AuthError("Please sign in.", 401)
        with self.repository.transaction(write=True) as uow:
            db = uow.session
            row = db.scalar(
                select(AuthSessionRow)
                .where(AuthSessionRow.token_hash == digest(token))
                .with_for_update()
            )
            if row is None or row.expires_at <= self.clock():
                raise AuthError("Your session has expired. Please sign in again.", 401)
            if row.recovery and not allow_recovery:
                raise AuthError("Set your new password before continuing.", 403)
            if recent and self.clock() - row.authenticated_at > 600:
                raise AuthError(
                    "Sign in again before changing your login methods.", 401
                )
            data = self.decrypt(row.provider_tokens)
            if data["refresh_at"] <= self.clock():
                tokens = self.provider.token(
                    "refresh_token", refresh_token=data["refresh_token"]
                )
                user = self.verified(tokens)
                if user["subject"] != data["user"]["subject"]:
                    raise AuthError("Account verification failed.", 401)
                data = self.pack(tokens, user)
                row.provider_tokens = self.encrypt(data)
            return self.profile(db, row, data["user"]), data["access_token"]

    def logout(self, token):
        if token:
            with self.repository.transaction(write=True) as uow:
                uow.session.execute(
                    delete(AuthSessionRow).where(
                        AuthSessionRow.token_hash == digest(token)
                    )
                )

    def flow(self, kind, player_id=None):
        token, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        with self.repository.transaction(write=True) as uow:
            uow.session.execute(
                delete(AuthFlowRow).where(AuthFlowRow.expires_at <= self.clock())
            )
            uow.session.add(
                AuthFlowRow(
                    token_hash=digest(token),
                    verifier=self.encrypt(verifier),
                    kind=kind,
                    player_id=player_id,
                    expires_at=int(self.clock()) + 3600,
                )
            )
        return token, challenge

    def callback(self, flow_token, code, session_token=None):
        if not flow_token or not code:
            raise AuthError("This sign-in link has expired. Please start again.")
        with self.repository.transaction(write=True) as uow:
            row = uow.session.scalar(
                select(AuthFlowRow)
                .where(AuthFlowRow.token_hash == digest(flow_token))
                .with_for_update()
            )
            if row is None or row.expires_at <= self.clock():
                raise AuthError("This sign-in link has expired. Please start again.")
            verifier, kind, expected = (
                self.decrypt(row.verifier),
                row.kind,
                row.player_id,
            )
            uow.session.delete(row)
        if expected:
            profile, _ = self.session(session_token, recent=True)
            if profile["player_id"] != expected:
                raise AuthError("Sign in to the account you are linking first.", 401)
        tokens = self.provider.token("pkce", auth_code=code, code_verifier=verifier)
        return self.login(
            tokens,
            recovery=kind == "recovery",
            expected_player=expected,
            old_token=session_token,
        )

    def password(self, token, password):
        profile, access = self.session(token, allow_recovery=True, recent=True)
        self.provider.request("PUT", "/user", token=access, data={"password": password})
        # all existing local sessions must stop working after a password change.
        with self.repository.transaction(write=True) as uow:
            uow.session.execute(
                delete(AuthSessionRow).where(
                    AuthSessionRow.player_id == profile["player_id"]
                )
            )
        try:
            self.provider.request(
                "POST", "/logout", token=access, params={"scope": "global"}
            )
        except AuthError:
            # local credentials are already revoked; a provider logout failure
            # must not report the completed password change as a failed update.
            pass
