# Google and email authentication

This implementation is local work. Do not run its migration against the existing
Supabase database or deploy it until the production change is separately approved.
The ignored `server/.env` currently points at production.

## Develop without changing production

Create an ignored `server/.env.development` with a separate database and a
**development Supabase project**:

```dotenv
OFC_DATABASE_URL=sqlite:///data/auth-development.sqlite3
OFC_SUPABASE_URL=https://YOUR-DEVELOPMENT-PROJECT.supabase.co
OFC_SUPABASE_PUBLISHABLE_KEY=YOUR-PUBLISHABLE-KEY
OFC_AUTH_ENCRYPTION_KEY=YOUR-FERNET-KEY
OFC_PUBLIC_ORIGIN=http://127.0.0.1:5173
```

Generate a Fernet key locally and save it in that file:

```sh
uv run --directory server python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

The encryption key protects Supabase access/refresh tokens and login verifiers at
rest. Keep it stable across application restarts and consistent between instances.
Changing it invalidates existing encrypted sessions. Keep these values out of Git.
The publishable key (or legacy anon key) is sufficient; no service-role key is used.

From the repository root:

```sh
uv run --directory server --env-file .env.development python -m ofc.schema upgrade
uv run --directory server --env-file .env.development uvicorn ofc.api:app --reload
pnpm --dir frontend dev --host 127.0.0.1
```

Visit `http://127.0.0.1:5173`. Use that exact origin: `localhost` is a different
origin and cookie host. Environment variables override values in `server/.env`.
For PostgreSQL development tests, use a dedicated development database, not the
existing live Supabase URL. The automated backend and browser tests use disposable
SQLite files and mock provider responses; they do not sign real users into Google.

## Development Supabase settings

1. Enable Email in Authentication → Sign In / Providers. Keep email verification
   enabled. The app requires a verified email before creating a local account.
2. Enable Google and enter a Google web OAuth client's ID and secret. In Google's
   console, allow the Supabase callback shown by the Google provider settings:
   `https://YOUR-DEVELOPMENT-PROJECT.supabase.co/auth/v1/callback`.
3. In Authentication → URL Configuration, set the development Site URL and allow
   exactly `http://127.0.0.1:5173/api/auth/callback` as a redirect URL. Vite proxies
   this to the backend. This is different from Google's callback to Supabase.
4. Enable manual identity linking to make the Account → Connect Google action
   available. Supabase also supports automatic linking under its verified-email
   policy; the application never merges local players by matching email strings.
5. Configure SMTP for real email verification and recovery. Supabase's default
   sender is limited to project-team addresses. Keep email templates using the
   standard confirmation URL for the PKCE redirect flow.

Email confirmation and password recovery must be completed in the same browser
that started the request. A new flow replaces the previous flow cookie. Expired
or used links require starting again. Callback URLs contain a short-lived code,
never an access or refresh token. Avoid recording callback query strings in any
additional proxy/analytics logs.

References: [Google setup](https://supabase.com/docs/guides/auth/social-login/auth-google),
[redirects](https://supabase.com/docs/guides/auth/redirect-urls),
[identity linking](https://supabase.com/docs/guides/auth/auth-identity-linking),
[SMTP](https://supabase.com/docs/guides/auth/auth-smtp).

## Identity and sessions

`players.id` is the permanent game identity. Migration `0002` adds:

- `auth_identities`: a unique `(issuer, subject)` mapping to a player. The subject
  is the Supabase user UUID. Concurrent first logins converge on one player.
- `auth_sessions`: hashed random cookie IDs, expiration, and encrypted provider
  credentials. Supabase tokens never go into browser storage or API responses.
- `auth_flows`: expiring, one-time PKCE verifiers bound to a browser flow cookie.

Accounts with the same email but different Supabase subjects remain separate.
Connecting Google is an explicit operation from a recently authenticated account;
the returned identity must map back to the same player. A Google user can add an
email password through Account → Save password. Email/name changes never change
the player ID. CPU seats have no auth identity and cannot log in.

Sessions have a seven-day absolute lifetime. Provider credentials refresh under a
session-row lock before their one-hour access token expires. A logout revokes the
local session immediately; password changes revoke all local sessions and request
a global provider logout. Account-security changes require authentication within
the last ten minutes. Recovery sessions last fifteen minutes and cannot play games
or link providers until a new password is saved; saving signs the user out.

Cookies are HttpOnly and SameSite=Lax, with Secure enabled for HTTPS. Non-local
origins require HTTPS. Write requests require the configured Origin and a custom
request header. WebSockets use the same cookie, check Origin, and recheck the
session every five seconds so logout/expiry closes existing connections. Passwords
are forwarded to Supabase, never stored locally. Validation responses omit input
values. Auth responses are not cached. The app has a bounded per-client rate
limiter; Supabase's own limits also apply. If running behind a proxy, configure
trusted proxy handling deliberately before using forwarded addresses for limits.

## Legacy access and future deployment

Legacy `/players` registration and bearer keys are disabled by default. Old keys
are removed from browser storage when account login is used. They do not grant
access to the new account system, and historical guest identities are not claimed
by email or display name. Existing rows are preserved by the migration.

`OFC_ALLOW_LEGACY_KEYS=1` enables the old interface solely for isolated legacy
regression tests when no auth provider is configured. It must not be enabled for
production account login. The standard Playwright config sets it for older game
UI tests; auth UI tests override the provider endpoints locally.

Before a future production deployment: configure auth settings and Google/SMTP,
choose the production origin and redirect, apply `0002`, then deploy the app.
None of those production steps are performed by the local implementation.
