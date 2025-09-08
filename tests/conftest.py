import os
import sys

# Ensure both the package root (this directory) and the repository root are importable.
_THIS_DIR = os.path.dirname(__file__)
_PKG_ROOT = os.path.abspath(os.path.join(_THIS_DIR, ".."))      # GrantScope/
_REPO_ROOT = os.path.abspath(os.path.join(_PKG_ROOT, ".."))     # repo root containing GrantScope/

for p in (_PKG_ROOT, _REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)