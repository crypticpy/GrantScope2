# CRUSH

- Setup:
  - python -m venv .venv && source .venv/bin/activate
  - pip install -r requirements.txt
  - pip install -U pytest

- Run app: streamlit run app.py

- Tests:
  - pytest
  - pytest -q tests/test_config.py
  - pytest -q tests/test_config.py::test_env_when_no_secrets
  - pytest -q -k "advisor and not slow"
  - Pytest config: pytest.ini sets testpaths=tests and pythonpath=.

- Lint/format (optional; not preconfigured):
  - pip install ruff black mypy
  - ruff check .
  - black --check .
  - mypy .

- Imports: stdlib, third-party, local; prefer absolute imports from repo root (see pytest.ini pythonpath=.).
- Types: annotate functions and returns; use Optional[...] where appropriate; avoid Any except at boundaries; prefer Dict[str, Any].
- Naming: snake_case functions/vars, PascalCase classes, UPPER_SNAKE constants; tests start with test_.
- Error handling: do not print/exit; raise clear exceptions; use config.require for mandatory secrets; in UI prefer st.error/warning/info.
- Config: read via config getters (get_openai_api_key, get_candid_key, is_feature_enabled, feature_flags); never use os.getenv directly in app code; call refresh_cache() in tests when env changes.
- Style: keep pure functions; small modules; pragmatic 100-120 char lines; Black-compatible formatting encouraged.
- Cursor/Copilot rules: none found in .cursor/rules/, .cursorrules, or .github/copilot-instructions.md.