"""supabase auth transport; passwords and provider responses are never logged."""

import os
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

import httpx
from dotenv import dotenv_values

from ofc.database import ROOT


class AuthError(Exception):
    def __init__(self, message="Sign-in failed. Please try again.", status=400):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class AuthSettings:
    url: str
    key: str
    encryption_key: str
    origin: str
    session_seconds: int = 7 * 24 * 3600

    @property
    def callback(self):
        return self.origin + "/api/auth/callback"

    @property
    def secure(self):
        return self.origin.startswith("https://")

    @classmethod
    def load(cls):
        values = {**dotenv_values(ROOT / ".env", interpolate=False), **os.environ}
        names = (
            "OFC_SUPABASE_URL",
            "OFC_SUPABASE_PUBLISHABLE_KEY",
            "OFC_AUTH_ENCRYPTION_KEY",
            "OFC_PUBLIC_ORIGIN",
        )
        if not any(values.get(n) for n in names):
            return None
        if not all(values.get(n) for n in names):
            raise RuntimeError(
                "configure all OFC_SUPABASE_URL, OFC_SUPABASE_PUBLISHABLE_KEY, OFC_AUTH_ENCRYPTION_KEY and OFC_PUBLIC_ORIGIN settings"
            )
        result = cls(
            *(
                values[n].rstrip("/") if n != "OFC_AUTH_ENCRYPTION_KEY" else values[n]
                for n in names
            )
        )
        for value in (result.url, result.origin):
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise RuntimeError(
                    "auth URLs must be absolute origins without paths or credentials"
                )
            if parsed.scheme != "https" and parsed.hostname not in {
                "localhost",
                "127.0.0.1",
                "::1",
            }:
                raise RuntimeError("auth requires HTTPS outside localhost")
        return result


class SupabaseAuth:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=15, follow_redirects=False)

    def close(self):
        self.client.close()

    def request(self, method, path, *, data=None, params=None, token=None):
        headers = {"apikey": self.settings.key}
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            response = self.client.request(
                method,
                self.settings.url + "/auth/v1" + path,
                json=data,
                params=params,
                headers=headers,
            )
        except httpx.HTTPError:
            raise AuthError(
                "Login service is unavailable. Please try again.", 503
            ) from None
        if response.status_code == 429:
            raise AuthError("Too many attempts. Please wait and try again.", 429)
        if response.status_code >= 500:
            raise AuthError("Login service is unavailable. Please try again.", 503)
        if response.status_code >= 400:
            raise AuthError(
                "Unable to authenticate. Check your details or try signing in again.",
                401,
            )
        if not response.content:
            return {}
        try:
            result = response.json()
        except ValueError:
            raise AuthError("Invalid response from login service.", 502) from None
        if not isinstance(result, dict):
            raise AuthError("Invalid response from login service.", 502)
        return result

    def token(self, grant, **data):
        return self.request("POST", "/token", params={"grant_type": grant}, data=data)

    def user(self, token):
        return self.request("GET", "/user", token=token)

    def google_url(self, challenge, access_token=None):
        params = {
            "provider": "google",
            "redirect_to": self.settings.callback,
            "code_challenge": challenge,
            "code_challenge_method": "s256",
            "scopes": "email profile",
        }
        if access_token:
            params["skip_http_redirect"] = "true"
            result = self.request(
                "GET", "/user/identities/authorize", params=params, token=access_token
            )
            url = result.get("url", "")
            if urlsplit(url).scheme != "https":
                raise AuthError("Unable to connect Google. Please try again.")
            return url
        return self.settings.url + "/auth/v1/authorize?" + urlencode(params)
