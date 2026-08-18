from __future__ import annotations

import argparse
import json
from pathlib import Path


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Authorize Wolf Research to send newsletters through Gmail OAuth."
    )
    parser.add_argument(
        "client_secrets",
        type=Path,
        help="Path to the downloaded Google Desktop OAuth client JSON.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=PROJECT_ROOT / ".env",
        help="Gitignored environment file to update (default: repository .env).",
    )
    parser.add_argument(
        "--from-email",
        help="Gmail address that will send the newsletter.",
    )
    parser.add_argument(
        "--recipient",
        help="Default newsletter recipient address.",
    )
    args = parser.parse_args()

    client_secrets_path = args.client_secrets.expanduser().resolve()
    client_config = _load_desktop_client_config(client_secrets_path)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise SystemExit(
            "google-auth-oauthlib is required. Run: python -m pip install -r "
            "requirements.txt"
        ) from exc

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_path),
        scopes=[GMAIL_SEND_SCOPE],
    )
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message=(
            "Opening Google authorization for Gmail send-only access..."
        ),
        success_message=(
            "Wolf Research Gmail authorization completed. You may close this tab."
        ),
    )
    if not credentials.refresh_token:
        raise SystemExit(
            "Google did not return a refresh token. Revoke the app grant and rerun "
            "the authorization with consent."
        )

    installed = client_config["installed"]
    updates = {
        "EMAIL_PROVIDER": "gmail_api",
        "GMAIL_CLIENT_ID": installed["client_id"],
        "GMAIL_CLIENT_SECRET": installed["client_secret"],
        "GMAIL_REFRESH_TOKEN": credentials.refresh_token,
    }
    if args.from_email:
        updates["GMAIL_FROM_EMAIL"] = _validate_email(args.from_email)
    if args.recipient:
        updates["NEWSLETTER_TO"] = _validate_email(args.recipient)
    _upsert_env(args.env_file.expanduser().resolve(), updates)
    print(
        "Gmail OAuth authorization complete. Credentials were saved to the "
        "gitignored .env file and were not displayed."
    )


def _load_desktop_client_config(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"OAuth client JSON was not found: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("OAuth client JSON could not be read.") from exc
    installed = config.get("installed")
    required = {"client_id", "client_secret", "auth_uri", "token_uri"}
    if not isinstance(installed, dict) or not required.issubset(installed):
        raise SystemExit(
            "OAuth JSON must be a Google Desktop app client configuration."
        )
    return config


def _upsert_env(path: Path, updates: dict[str, str]) -> None:
    for key, value in updates.items():
        if not value or any(character in value for character in "\r\n"):
            raise SystemExit(f"Refusing to store an invalid value for {key}.")

    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    output_lines: list[str] = []
    written: set[str] = set()
    for line in existing_lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in updates:
            if key not in written:
                output_lines.append(f"{key}={updates[key]}")
                written.add(key)
            continue
        output_lines.append(line)

    if output_lines and output_lines[-1]:
        output_lines.append("")
    for key, value in updates.items():
        if key not in written:
            output_lines.append(f"{key}={value}")

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def _validate_email(value: str) -> str:
    normalized = value.strip()
    if normalized.count("@") != 1 or any(character.isspace() for character in normalized):
        raise SystemExit("A valid email address is required.")
    return normalized


if __name__ == "__main__":
    main()
