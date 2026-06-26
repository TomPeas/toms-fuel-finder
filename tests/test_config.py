"""Unit tests for the Settings configuration object.

`config` instantiates `settings = Settings()` at import time, so these tests set
the environment first and (re)load the module rather than importing it at the top.
"""

import importlib

import pytest
from pydantic import ValidationError

_ENV_VARS = ("GOV_CLIENT_ID", "GOV_CLIENT_SECRET", "GOV_BASE_URL")


def test_settings_reads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOV_CLIENT_ID", "id123")
    monkeypatch.setenv("GOV_CLIENT_SECRET", "secret123")
    monkeypatch.setenv("GOV_BASE_URL", "https://example.gov")

    import config

    importlib.reload(config)

    assert config.settings.gov_client_id == "id123"
    assert config.settings.gov_client_secret == "secret123"
    assert config.settings.gov_base_url == "https://example.gov"


def test_missing_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Set values so the module imports cleanly, then grab the class and assert it
    # rejects a build with the required vars absent (ignoring any .env file).
    for var in _ENV_VARS:
        monkeypatch.setenv(var, "placeholder")

    import config

    importlib.reload(config)

    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ValidationError):
        config.Settings()
