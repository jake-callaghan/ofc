# Email authentication

## Production through GitHub Actions

No local app is required. In GitHub repository Settings → Environments →
production → Environment secrets, add:

| Name | Value |
| --- | --- |
| `OFC_SUPABASE_URL` | `https://bhtmeykhjybqpajkeuto.supabase.co` |
| `OFC_SUPABASE_PUBLISHABLE_KEY` | production Supabase Settings → API Keys → publishable key |
| `OFC_AUTH_ENCRYPTION_KEY` | a Fernet key generated once and retained |
| `OFC_PUBLIC_ORIGIN` | `https://ofcpoker.live` |
| `FLY_API_TOKEN` | existing Fly deployment token (repository secret also works) |

Generate the encryption key with Python, without running the app:

```sh
python3 -c 'import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
```

Save the output directly as the GitHub secret, not in source control. Do not
regenerate it for every deployment. The workflow validates these settings and
stages them on Fly via stdin, then deploys. Missing settings stop the deployment.
The workflow sets the Fly database secret to `sqlite:////data/ofc.sqlite3`. Deployments are serialized so
staged settings cannot race another deployment from this workflow.

In the production Supabase project, go to Authentication → Sign In / Providers.
Enable Email and new-user signups, and turn **Confirm email off**. Set Site URL
to `https://ofcpoker.live`. No SMTP or authentication callback URL is needed.
Signup creates the account and immediately starts a browser session. The app does
not verify email ownership and does not offer emailed password resets.

After these settings and the application changes are ready, pushing/merging the
changes to `main` runs tests and deploys automatically. The app startup command
applies migrations on the mounted SQLite volume before accepting traffic. Saving GitHub secrets
alone does not deploy anything. Verify immediate signup, login, logout and signed-in
password changes after release. Existing player keys do not become email accounts.

## Identity and sessions

Supabase handles email/password credentials. The app validates the returned
access token with Supabase and maps the account UUID to a permanent `players.id`.
Disabling confirmation in Supabase auto-confirms accounts; this does not prove
ownership of the email address. Matching email strings never merges local players.

The browser receives a random HttpOnly, SameSite=Lax cookie, Secure on HTTPS.
Only its hash is stored in the database; provider tokens are encrypted with the
stable Fernet key. Sessions last up to seven days and provider tokens refresh
as needed. Write requests require the configured origin and a custom header.
WebSockets recheck sessions every five seconds, so logout closes open connections.

Account → Save password requires a login within the last ten minutes and signs
out all local sessions. Forgotten passwords cannot be recovered through the app
without email delivery. There are no Google, email recovery, or callback endpoints.
Migration `0002` retains its original schema, including the now-unused flow table,
so databases that already applied it do not require rewriting migration history.

## Optional isolated development

Production deployment does not require running the app locally. For development,
use a separate Supabase project with Email enabled and Confirm email disabled.
Create an ignored `server/.env.development`:

```dotenv
OFC_DATABASE_URL=sqlite:///data/auth-development.sqlite3
OFC_SUPABASE_URL=https://YOUR-DEVELOPMENT-PROJECT.supabase.co
OFC_SUPABASE_PUBLISHABLE_KEY=YOUR-PUBLISHABLE-KEY
OFC_AUTH_ENCRYPTION_KEY=YOUR-FERNET-KEY
OFC_PUBLIC_ORIGIN=http://127.0.0.1:5173
```

From the repository root:

```sh
uv run --directory server --env-file .env.development python -m ofc.schema upgrade
uv run --directory server --env-file .env.development uvicorn ofc.api:app --reload
pnpm --dir frontend dev --host 127.0.0.1
```

The ignored `server/.env` points at production; use the explicit development
configuration for local migrations. Automated tests use disposable databases and
mock provider responses, so they do not create real Supabase accounts.

Legacy player keys are disabled by default and do not become email accounts.
`OFC_ALLOW_LEGACY_KEYS=1` exists only for isolated legacy regression tests when
Supabase authentication is not configured.

Reference: [Supabase email confirmation configuration](https://supabase.com/docs/guides/auth/general-configuration).

## Local login bypass

For everyday development without Supabase or email/password login, run from the
repository root:

```sh
uv run --directory server python -m ofc.dev
```

In a second terminal:

```sh
pnpm --dir frontend dev
```

Open `http://127.0.0.1:5173` and enter a display name. Use a separate browser
profile or private window for a second player. The player key persists in that
browser's local storage.

This launcher migrates and uses only `server/data/development.sqlite3`, ignoring
`OFC_DATABASE_URL` and all Supabase auth settings. It binds to loopback, supports
backend reload, and refuses to run on Fly or with the production volume setting.
The normal backend and production entrypoints do not enable this bypass.
