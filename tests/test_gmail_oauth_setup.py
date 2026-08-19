from __future__ import annotations

import json

import pytest

from scripts.configure_gmail_oauth import _load_desktop_client_config, _upsert_env


def test_load_desktop_client_config_rejects_non_desktop_json(tmp_path):
    config_path = tmp_path / "client.json"
    config_path.write_text(json.dumps({"web": {"client_id": "id"}}), encoding="utf-8")

    with pytest.raises(SystemExit, match="Desktop app"):
        _load_desktop_client_config(config_path)


def test_upsert_env_replaces_values_without_duplicates(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=keep-me\nEMAIL_PROVIDER=gmail_smtp\nGMAIL_CLIENT_ID=old\n",
        encoding="utf-8",
    )

    _upsert_env(
        env_path,
        {
            "EMAIL_PROVIDER": "gmail_api",
            "GMAIL_CLIENT_ID": "new-client-id",
            "GMAIL_CLIENT_SECRET": "new-client-secret",
            "GMAIL_REFRESH_TOKEN": "new-refresh-token",
        },
    )

    text = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=keep-me" in text
    assert "EMAIL_PROVIDER=gmail_api" in text
    assert text.count("GMAIL_CLIENT_ID=") == 1
    assert "GMAIL_CLIENT_SECRET=new-client-secret" in text
    assert "GMAIL_REFRESH_TOKEN=new-refresh-token" in text
