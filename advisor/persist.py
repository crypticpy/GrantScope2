"""
Persistence helpers for the Advisor pipeline.

APIs:
- export_bundle(report: ReportBundle) -> str
- import_bundle(text: str) -> ReportBundle

Optional helpers for UI:
- export_bundle_download(report: ReportBundle, filename: str = "advisor_report.json") -> str
- import_bundle_from_upload(uploaded_file) -> ReportBundle
"""

from __future__ import annotations

from typing import Any

import json as _json

try:
    # Local/relative import path when running inside the GrantScope package
    from GrantScope.advisor.schemas import ReportBundle  # type: ignore
except Exception:  # pragma: no cover
    # Fallback when executing from repo root where top-level imports are used
    from advisor.schemas import ReportBundle  # type: ignore

# Download helper (Streamlit link). Prefer relative 'utils' import as in existing code.
try:
    from utils.utils import download_text  # type: ignore
except Exception:  # pragma: no cover
    try:
        from GrantScope.utils.utils import download_text  # type: ignore
    except Exception:
        download_text = None  # type: ignore


def export_bundle(report: ReportBundle) -> str:
    """Return a stable, compact JSON string for the given ReportBundle."""
    # schemas.ReportBundle already provides a stable serializer, reuse it.
    return report.to_json()


def export_bundle_download(report: ReportBundle, filename: str = "advisor_report.json") -> str:
    """Render a Streamlit download link for the given ReportBundle JSON and return the href.

    If Streamlit download helper is unavailable, returns the JSON string so callers can handle it.
    """
    json_text = export_bundle(report)
    if download_text is None:  # In non-Streamlit or test environments, just return the JSON
        return json_text
    return download_text(json_text, filename, mime="application/json")


def import_bundle(text: str) -> ReportBundle:
    """Parse a JSON string into a ReportBundle instance."""
    try:
        data = _json.loads(text)
    except Exception as e:  # pragma: no cover - defensive
        raise ValueError(f"Invalid JSON for ReportBundle: {e}") from e
    return ReportBundle(**data)


def import_bundle_from_upload(uploaded_file: Any) -> ReportBundle:
    """Convenience: read a Streamlit UploadedFile and parse into a ReportBundle.

    The caller is responsible for validating the file type and size before calling.
    """
    try:
        raw = uploaded_file.read()
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    except Exception as e:  # pragma: no cover - defensive
        raise ValueError(f"Unable to read uploaded file: {e}") from e
    return import_bundle(text)