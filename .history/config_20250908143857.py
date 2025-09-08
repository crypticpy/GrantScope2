"""
Centralized configuration and secrets loader for GrantScope.

Precedence:
    Streamlit st.secrets > environment variables (including those loaded from .env) > defaults

Notes:
- Safe to import in both Streamlit and non-Streamlit contexts.
- Loads a .env file once at import time (does not override existing environment values).
- Provides typed getters and feature flag helpers.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, Optional

# Optional Streamlit import (module must work in non-Streamlit contexts, e.g., CLI tools)
try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover - environment without streamlit
    st = None  # type: ignore

# Load environment variables from .env once (do not override existing env)
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - should be available via requirements, but keep safe
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

# Read .env if present; do not override already-set variables
load_dotenv(override=False)


def _secrets_get(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Read a value from st.secrets if Streamlit is available; otherwise return default.
    """
    if st is None:
        return default
    try:
        secrets_obj = getattr(st, "secrets", None)
        if secrets_obj is None:
            return default
        # st.secrets behaves mapping-like; prefer dict-style access
        try:
            return secrets_obj.get(key, default)  # type: ignore[attr-defined]
        except Exception:
            # Fallback for implementations that act like plain dict
            if isinstance(secrets_obj, dict):
                return secrets_obj.get(key, default)
            return default
    except Exception:
        return default


def _get_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Fetch config value with precedence: st.secrets -> os.environ -> default.
    Empty strings are treated as unset.

    Note: uses _secrets_getter indirection so tests can monkeypatch secrets source.
    """
    val = _secrets_getter(key, None)
    if isinstance(val, str) and val.strip() != "":
        return val

    env_val = os.getenv(key)
    if env_val is not None and env_val.strip() != "":
        return env_val

    return default


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    val = str(value).strip().lower()
    return val in {"1", "true", "yes", "on", "y", "t"}


@lru_cache(maxsize=None)
def get_openai_api_key() -> Optional[str]:
    """
    Return OpenAI API key or None if not set anywhere.
    """
    return _get_value("OPENAI_API_KEY")


@lru_cache(maxsize=None)
def get_candid_key() -> Optional[str]:
    """
    Return Candid API key (CANDID_API_KEY) or None if not set.
    """
    return _get_value("CANDID_API_KEY")


@lru_cache(maxsize=None)
def get_model_name(default: str = "gpt-5-mini") -> str:
    """
    Return model name used by LLMs. Defaults to 'gpt-5-mini' when not set.
    Key: OPENAI_MODEL
    """
    return _get_value("OPENAI_MODEL", default) or default


@lru_cache(maxsize=None)
def is_feature_enabled(flag_name: str, default: bool = False) -> bool:
    """
    Return True/False for a feature flag, using precedence and tolerant parsing.

    Note: uses _secrets_getter indirection so tests can monkeypatch secrets source.
    """
    sec_val = _secrets_getter(flag_name, None)
    if sec_val is not None:
        return _parse_bool(str(sec_val), default)

    env_val = os.getenv(flag_name)
    if env_val is not None:
        return _parse_bool(env_val, default)

    return default


@lru_cache(maxsize=None)
def feature_flags() -> Dict[str, bool]:
    """
    Return a dict of known feature flags with resolved boolean values.
    """
    return {
        "GS_ENABLE_CHAT_STREAMING": is_feature_enabled("GS_ENABLE_CHAT_STREAMING", False),
        "GS_ENABLE_LEGACY_ROUTER": is_feature_enabled("GS_ENABLE_LEGACY_ROUTER", False),
        "GS_ENABLE_NEWBIE_MODE": is_feature_enabled("GS_ENABLE_NEWBIE_MODE", False),
        "GS_ENABLE_PLAIN_HELPERS": is_feature_enabled("GS_ENABLE_PLAIN_HELPERS", False),
        "GS_ENABLE_NEW_PAGES": is_feature_enabled("GS_ENABLE_NEW_PAGES", False),
        "GS_ENABLE_AI_AUGMENTATION": is_feature_enabled("GS_ENABLE_AI_AUGMENTATION", False),
    }


def require(key_name: str, getter, hint: str) -> str:
    """
    Fetch a required secret/config using the provided getter function.
    Raises RuntimeError with a clear hint if missing.
    """
    val = getter()
    if not val:
        raise RuntimeError(f"Missing required configuration: {key_name}. {hint}")
    return str(val)


def is_enabled(flag_name: str) -> bool:
    """
    Convenient alias for is_feature_enabled with default False.
    """
    return is_feature_enabled(flag_name, False)


def require_flag(flag_name: str, ui_msg: str = "Feature is disabled") -> bool:
    """
    Check if a feature flag is enabled and show a user-friendly message if not.
    Returns True if enabled, False if disabled.
    Intended for UI contexts where st is available.
    """
    if is_enabled(flag_name):
        return True
    
    # Try to show message via Streamlit if available
    try:
        import streamlit as st  # type: ignore
        st.info(f"{ui_msg}. Set {flag_name}=1 to enable.")
    except Exception:
        pass
    
    return False


def refresh_cache() -> None:
    """
    Clear cached values from lru_cache-enabled getters.
    Useful for tests or when environment/secrets change at runtime.
    """
    get_openai_api_key.cache_clear()
    get_candid_key.cache_clear()
    get_model_name.cache_clear()
    is_feature_enabled.cache_clear()
    feature_flags.cache_clear()


# Expose internal getter for testing/mocking
_secrets_getter = _secrets_get

__all__ = [
    "get_openai_api_key",
    "get_candid_key",
    "get_model_name",
    "is_feature_enabled",
    "is_enabled",
    "require_flag",
    "feature_flags",
    "require",
    "refresh_cache",
    "_secrets_getter",
]
