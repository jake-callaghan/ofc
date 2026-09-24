"""stage github environment secrets for the next fly deployment without logging values."""

import base64
import os
import subprocess
from urllib.parse import urlsplit


def main():
    names = (
        "OFC_SUPABASE_URL",
        "OFC_SUPABASE_PUBLISHABLE_KEY",
        "OFC_AUTH_ENCRYPTION_KEY",
        "OFC_PUBLIC_ORIGIN",
    )
    values = {name: os.environ.get(name, "") for name in names}
    for name, value in {**values, "FLY_API_TOKEN": os.environ.get("FLY_API_TOKEN", "")}.items():
        if not value.strip() or any(c in value for c in "\r\n\x00"):
            raise SystemExit(f"Set {name} to a nonempty, single-line GitHub secret.")
    try:
        key = base64.b64decode(
            values["OFC_AUTH_ENCRYPTION_KEY"], altchars=b"-_", validate=True
        )
        if len(key) != 32:
            raise ValueError
    except ValueError:
        raise SystemExit("OFC_AUTH_ENCRYPTION_KEY must be a Fernet key.") from None
    for name in ("OFC_SUPABASE_URL", "OFC_PUBLIC_ORIGIN"):
        url = urlsplit(values[name])
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
        ):
            raise SystemExit(f"{name} must be an HTTPS origin without a path.")
    # override the old remote database secret on every deployment.
    values["OFC_DATABASE_URL"] = "sqlite:////data/ofc.sqlite3"
    # stdin keeps credentials out of command arguments; staging does not restart the app.
    subprocess.run(
        ["flyctl", "secrets", "import", "--app", "ofc", "--stage"],
        input="".join(f"{name}={value}\n" for name, value in values.items()),
        text=True,
        check=True,
    )


if __name__ == "__main__":
    main()
