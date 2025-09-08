# Warp guide: setup, update, and indexing

This guide gives you copy-paste commands to prepare a Python 3.12 environment, install all dependencies (including test/dev), and trigger external code indexing in CI. It does not run the application.

Repo: GrantScope2
Location: /Users/aiml/Projects/GrantScope2

## Prerequisites
- Python 3.12 available on your machine
- Git
- This repository cloned locally

## Quickstart: create venv and install
Linux or macOS:

```
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
# Install runtime + dev deps
if [ -f requirements-dev.txt ]; then 
  python -m pip install -r requirements.txt -r requirements-dev.txt
else
  python -m pip install -r requirements.txt
fi
```

Windows PowerShell:

```
py -3.12 -m venv .venv
.\.venv\Scripts\Activate
python -m pip install --upgrade pip setuptools wheel
if (Test-Path requirements-dev.txt -PathType Leaf) { python -m pip install -r requirements.txt -r requirements-dev.txt } else { python -m pip install -r requirements.txt }
```

Optional project extras (if defined):

```
python -m pip install -e .[dev]
python -m pip install -e .[test]
```

## Environment variables
Set these if you plan to use AI features or the Candid fetcher (see README.md and config.py):
- OPENAI_API_KEY
- CANDID_API_KEY
- Optional flags: GS_ENABLE_CHAT_STREAMING, GS_ENABLE_LEGACY_ROUTER

For local dev with a .env file, keys are picked up via python-dotenv.

## Run common tasks
Run tests:

```
pytest -q
```

Run the app:

```
streamlit run app.py
```

CLI fetcher (requires CANDID_API_KEY):

```
python -m fetch.fetch
```

## Update dependency pins (optional)
This project installs from requirements.txt. If you maintain pins with pip-tools, you can:

```
python -m pip install pip-tools
# If you use requirements.in to track top-level deps:
# pip-compile --upgrade --resolver backtracking --output-file requirements.txt requirements.in
```

## External code indexing (no-op locally)
Indexing typically runs in CI or an external service. To request a re-index:

- With GitHub CLI (if a workflow exists):
```
gh workflow list | grep -i index
# Replace code-index.yml with the actual workflow name
gh workflow run code-index.yml
gh run watch
```

- Or push an empty commit to trigger CI:
```
git commit --allow-empty -m "chore: trigger external code index"
git push
```

Locally, there is nothing to run for indexing.

## Clean up or recreate the environment
Linux or macOS:

```
deactivate 2>/dev/null || true
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```
deactivate
Remove-Item -Recurse -Force .\.venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate
```

