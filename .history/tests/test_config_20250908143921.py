import os
import importlib
import sys
import types
import pytest


def _reload_config():
    """
    Reload GrantScope.config module and return it, ensuring caches are cleared
    and environment changes are visible to getters.
    """
    # Import fresh each time to respect environment/secrets changes
    if "GrantScope.config" in list(sys.modules.keys()):
        importlib.invalidate_caches()
        sys.modules.pop("GrantScope.config", None)
    if "config" in list(sys.modules.keys()):
        # In case tests import as plain 'config' accidentally
        sys.modules.pop("config", None)
    try:
        from GrantScope import config  # noqa: E402
    except Exception:  # pragma: no cover
        import config  # type: ignore  # noqa: E402
    try:
        config.refresh_cache()
    except Exception:
        pass
    return config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    # Ensure a clean slate for the keys we manipulate
    keys = [
        "OPENAI_API_KEY",
        "CANDID_API_KEY",
        "OPENAI_MODEL",
        "GS_ENABLE_CHAT_STREAMING",
        "GS_ENABLE_LEGACY_ROUTER",
    ]
    # Save old values, then unset for a known baseline
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        if k in os.environ:
            monkeypatch.delenv(k, raising=False)
    yield
    # Restore values after each test
    for k, v in saved.items():
        if v is None:
            if k in os.environ:
                monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)


def test_env_when_no_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")
    cfg = _reload_config()

    # Force secrets getter to behave as if no secrets are defined
    monkeypatch.setattr(cfg, "_secrets_getter", lambda k, d=None: None, raising=True)
    cfg.refresh_cache()

    assert cfg.get_openai_api_key() == "env-openai"


def test_st_secrets_precedence_over_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")
    cfg = _reload_config()

    # Simulate st.secrets containing a value
    monkeypatch.setattr(cfg, "_secrets_getter", lambda k, d=None: "secret-openai" if k == "OPENAI_API_KEY" else None, raising=True)
    cfg.refresh_cache()

    assert cfg.get_openai_api_key() == "secret-openai"


def test_missing_returns_none_and_model_default(monkeypatch):
    # No env or secrets for OPENAI_API_KEY
    cfg = _reload_config()
    monkeypatch.setattr(cfg, "_secrets_getter", lambda k, d=None: None, raising=True)
    cfg.refresh_cache()

    assert cfg.get_openai_api_key() is None

    # Model defaults to "gpt-5-mini"
    assert cfg.get_model_name() == "gpt-5-mini"


def test_model_name_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    cfg = _reload_config()
    monkeypatch.setattr(cfg, "_secrets_getter", lambda k, d=None: None, raising=True)
    cfg.refresh_cache()

    assert cfg.get_model_name() == "gpt-4o-mini"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("off", False),
        ("", False),
        (None, False),
    ],
)
def test_feature_flag_parsing_env(monkeypatch, value, expected):
    if value is None:
        # Ensure var not set
        monkeypatch.delenv("GS_ENABLE_CHAT_STREAMING", raising=False)
    else:
        monkeypatch.setenv("GS_ENABLE_CHAT_STREAMING", value)

    cfg = _reload_config()
    monkeypatch.setattr(cfg, "_secrets_getter", lambda k, d=None: None, raising=True)
    cfg.refresh_cache()

    flags = cfg.feature_flags()
    assert flags["GS_ENABLE_CHAT_STREAMING"] is expected


def test_feature_flag_secrets_override_env(monkeypatch):
    # Env suggests disabled
    monkeypatch.setenv("GS_ENABLE_CHAT_STREAMING", "0")

    cfg = _reload_config()
    # Secrets say enabled
    monkeypatch.setattr(
        cfg,
        "_secrets_getter",
        lambda k, d=None: "true" if k == "GS_ENABLE_CHAT_STREAMING" else None,
        raising=True,
    )
    cfg.refresh_cache()

    assert cfg.is_feature_enabled("GS_ENABLE_CHAT_STREAMING") is True
    flags = cfg.feature_flags()
    assert flags["GS_ENABLE_CHAT_STREAMING"] is True


def test_require_raises_when_missing(monkeypatch):
    cfg = _reload_config()
    monkeypatch.setattr(cfg, "_secrets_getter", lambda k, d=None: None, raising=True)
    cfg.refresh_cache()

    with pytest.raises(RuntimeError):
        cfg.require(
            "CANDID_API_KEY",
            cfg.get_candid_key,
            "Set st.secrets['CANDID_API_KEY'] or environment variable CANDID_API_KEY.",
        )


def test_require_returns_value(monkeypatch):
    monkeypatch.setenv("CANDID_API_KEY", "env-candid")
    cfg = _reload_config()
    monkeypatch.setattr(cfg, "_secrets_getter", lambda k, d=None: None, raising=True)
    cfg.refresh_cache()

    assert cfg.require(
        "CANDID_API_KEY",
        cfg.get_candid_key,
        "hint",
    ) == "env-candid"