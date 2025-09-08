"""
Renderer for Advisor Report.

APIs:
- render_report_streamlit(report: ReportBundle) -> None
- render_report_html(report: ReportBundle) -> str
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING
from html import escape
import re
import unicodedata

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None  # type: ignore

# Components (for embedding HTML) — use guarded import for static analyzers and test envs
try:
    import streamlit.components.v1 as components  # type: ignore
except Exception:  # pragma: no cover
    components = None  # type: ignore

# Flexible type imports to avoid circular analysis issues in some environments
if TYPE_CHECKING:
    try:
        from GrantScope.advisor.schemas import ReportBundle, FigureArtifact  # type: ignore
    except Exception:  # pragma: no cover
        from advisor.schemas import ReportBundle, FigureArtifact  # type: ignore

try:
    from GrantScope.utils.utils import download_text  # type: ignore
except Exception:  # pragma: no cover
    try:
        from utils.utils import download_text  # type: ignore
    except Exception:
        download_text = None  # type: ignore


def _clean_interpretation_text(text: str, for_markdown: bool = True) -> str:
    """
    Normalize and sanitize interpretation text for consistent rendering.
    - Strip leading 'What this means:' to avoid duplication with our label.
    - Normalize Unicode (NFKC) and convert non-breaking spaces to regular spaces.
    - Insert spaces around dashes and collapse excessive whitespace.
    - If for_markdown is True, escape Markdown control characters to prevent unintended formatting.
    """
    try:
        t = unicodedata.normalize("NFKC", str(text))
    except Exception:
        t = str(text)

    # Convert NBSP variants to normal spaces
    t = t.replace("\u00A0", " ").replace("\u202F", " ")

    # Remove duplicate leading label
    t = re.sub(r"^\s*what\s+this\s+means\s*:\s*", "", t, flags=re.IGNORECASE)

    # Normalize dashes: ensure spaces around -, –, —
    t = re.sub(r"\s*[–—-]\s*", " — ", t)

    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()

    if for_markdown:
        # Escape Markdown special characters to avoid unintended styling in st.markdown
        # Characters: \ ` * _ { } [ ] ( ) # + - . ! | >
        def _esc(m: re.Match) -> str:
            return "\\" + m.group(0)
        t = re.sub(r"([\\`*_{}\[\]()#+\-\.!|>])", _esc, t)
    return t


def _figure_html(fig: FigureArtifact) -> str:
    """Return HTML for a figure artifact, using PNG if available else inline HTML string."""
    if fig.png_base64:
        return f'<img alt="{escape(fig.label or fig.id)}" src="data:image/png;base64,{fig.png_base64}" style="max-width:100%;height:auto;" />'
    if fig.html:
        # Wrap interactive HTML so print still shows a static fallback when possible
        return f'<div class="figure-embed">{fig.html}</div>'
    # Fallback simple placeholder
    safe_label = escape(fig.label or fig.id or "Figure")
    return f'<div class="figure-embed figure-missing">[No figure content available for {safe_label}]</div>'


def render_report_html(report: ReportBundle) -> str:
    """Compose a single-file HTML document with inline CSS and embedded figures."""
    parts: List[str] = []
    parts.append(
        """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>GrantScope Advisor Report</title>
<style>
  :root {
    --text: #111;
    --muted: #555;
    --border: #ddd;
    --accent: #2b6cb0;
  }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; color: var(--text); margin: 1.25rem; line-height: 1.45; }
  header { margin-bottom: 1.5rem; }
  h1, h2, h3 { color: var(--accent); margin: 0.75rem 0 0.5rem; }
  h1 { font-size: 1.6rem; }
  h2 { font-size: 1.25rem; }
  h3 { font-size: 1.1rem; }
  .meta { color: var(--muted); font-size: 0.9rem; margin-bottom: 0.75rem; }
  .section { margin: 1rem 0 1.25rem; padding-bottom: 0.75rem; border-bottom: 1px solid var(--border); }
  .figure-embed { margin: 0.75rem 0; }
  .figure-missing { color: var(--muted); font-style: italic; border: 1px dashed var(--border); padding: 0.5rem; }
  .interpretation { color: var(--muted); font-size: 0.95rem; margin: 0.25rem 0 0.75rem; }
  .dp { padding-left: 0.5rem; border-left: 3px solid var(--border); margin: 0.5rem 0; }
  .rec-list { margin: 0.5rem 0 0.75rem; }
  .rec-list li { margin: 0.25rem 0; }
  .md-pre { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; background: #fafafa; border: 1px solid var(--border); padding: 0.5rem; overflow: auto; }
  @media print {
    a[href]::after { content: ""; }
    body { margin: 0.5in; }
    .section { page-break-inside: avoid; }
  }
</style>
</head>
<body>
<header>
  <h1>GrantScope Advisor Report</h1>
"""
    )
    parts.append(
        f'<div class="meta">Version {escape(report.version)} • Created {escape(str(report.created_at))}</div>'
    )

    # Overview: include first section if named Intake Summary, else synthesize quick overview
    if report.sections:
        parts.append('<div class="section">')
        parts.append("<h2>Overview</h2>")
        parts.append(report.sections[0].markdown_body)
        parts.append("</div>")

    # Data Evidence summary with inline tables
    if report.datapoints:
        parts.append('<div class="section">')
        parts.append("<h2>Data Evidence</h2>")
        for dp in report.datapoints:
            parts.append(f'<div class="dp"><strong>{escape(dp.id)}</strong>: {escape(dp.title)}</div>')
            try:
                if dp.table_md:
                    parts.append(f'<pre class="md-pre">{escape(dp.table_md)}</pre>')
            except Exception:
                pass
            try:
                if dp.notes:
                    parts.append(f'<div class="interpretation">{escape(dp.notes)}</div>')
            except Exception:
                pass
        parts.append("</div>")

    # Recommendations
    if report.recommendations:
        parts.append('<div class="section">')
        parts.append("<h2>Recommendations</h2>")
        if report.recommendations.funder_candidates:
            parts.append("<h3>Funder Candidates (Top 5)</h3><ol class='rec-list'>")
            for fc in report.recommendations.funder_candidates[:5]:
                grounded = f" — cites {', '.join(fc.grounded_dp_ids)}" if getattr(fc, "grounded_dp_ids", None) else ""
                parts.append(
                    f"<li><strong>{escape(fc.name)}</strong> (score {fc.score:.2f}) — "
                    f"{escape(fc.rationale)}{escape(grounded)}</li>"
                )
            parts.append("</ol>")
        if report.recommendations.response_tuning:
            parts.append("<h3>Response Tuning Tips</h3><ul class='rec-list'>")
            for tip in report.recommendations.response_tuning[:5]:
                grounded = f" — cites {', '.join(tip.grounded_dp_ids)}" if getattr(tip, "grounded_dp_ids", None) else ""
                parts.append(f"<li>{escape(tip.text)}{escape(grounded)}</li>")
            parts.append("</ul>")
        parts.append("</div>")

    # Figures
    if report.figures:
        parts.append('<div class="section">')
        parts.append("<h2>Figures</h2>")
        for fig in report.figures:
            parts.append(f"<h3>{escape(fig.label or fig.id)}</h3>")
            parts.append(_figure_html(fig))
            # Add a short interpretation when available, escaped for safe HTML
            try:
                text = getattr(fig, "interpretation_text", None)
                if text:
                    cleaned = _clean_interpretation_text(str(text), for_markdown=False)
                    parts.append(
                        f'<div class="interpretation"><strong>What this means:</strong> {escape(cleaned)}</div>'
                    )
            except Exception:
                # Do not block render on interpretation issues
                pass
        parts.append("</div>")

    # Full narrative sections
    if len(report.sections) > 1:
        parts.append('<div class="section">')
        parts.append("<h2>Narrative</h2>")
        for sec in report.sections[1:]:
            parts.append(f"<h3>{escape(sec.title)}</h3>")
            parts.append(sec.markdown_body)
        parts.append("</div>")

    parts.append("</body></html>")
    return "\n".join(parts)


def render_report_streamlit(report: ReportBundle) -> None:
    """Render the report within Streamlit using tabs."""
    if st is None:  # pragma: no cover
        return

    tab_overview, tab_evidence, tab_recs, tab_downloads = st.tabs(
        ["Overview", "Data Evidence", "Recommendations", "Downloads"]
    )

    with tab_overview:
        st.subheader("Overview")
        if report.sections:
            st.markdown(report.sections[0].markdown_body)
        else:
            st.info("No overview available.")

        if report.figures:
            st.markdown("### Figures")
            for fig in report.figures:
                label = (fig.label or fig.id) or "Figure"
                if fig.png_base64:
                    st.image(f"data:image/png;base64,{fig.png_base64}", caption=label, use_container_width=True)
                elif fig.html:
                    try:
                        if components:
                            components.html(fig.html, height=420, scrolling=True)  # type: ignore
                        else:
                            raise RuntimeError("components unavailable")
                    except Exception:
                        st.caption(f"[Interactive figure not supported in this environment for {label}]")
                # Per-chart interpretation under the chart when available
                try:
                    text2 = getattr(fig, "interpretation_text", None)
                    if text2:
                        cleaned = _clean_interpretation_text(str(text2))
                        st.markdown(f"**What this means:** {cleaned}")
                except Exception:
                    pass

    with tab_evidence:
        st.subheader("Data Evidence")
        if not report.datapoints:
            st.info("No data points were collected.")
        else:
            for dp in report.datapoints:
                st.markdown(f"**{dp.id} — {dp.title}**")
                if dp.table_md:
                    st.markdown(dp.table_md)
                if dp.notes:
                    st.caption(dp.notes)

    with tab_recs:
        st.subheader("Recommendations")
        recs = report.recommendations
        if not recs:
            st.info("No recommendations available.")
        else:
            if recs.funder_candidates:
                st.markdown("##### Funder Candidates")
                for fc in recs.funder_candidates[:5]:
                    st.markdown(f"- **{fc.name}** (score {fc.score:.2f}): {fc.rationale}")
            else:
                st.caption("No funder candidates.")

            if recs.response_tuning:
                st.markdown("##### Response Tuning")
                for tip in recs.response_tuning[:5]:
                    st.markdown(f"- {tip.text}")
            else:
                st.caption("No tuning tips.")

    with tab_downloads:
        st.subheader("Downloads")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Download JSON"):
                json_text = report.to_json()
                if download_text:
                    download_text(json_text, "advisor_report.json", mime="application/json")
                else:
                    st.code(json_text, language="json")
        with col2:
            if st.button("Download HTML"):
                html_text = render_report_html(report)
                if download_text:
                    download_text(html_text, "advisor_report.html", mime="text/html")
                else:
                    st.code(html_text, language="html")
        with col3:
            if st.button("Open Print View"):
                html_text = render_report_html(report)
                try:
                    if components:
                        components.html(html_text, height=800, scrolling=True)  # type: ignore
                    else:
                        raise RuntimeError("components unavailable")
                except Exception:
                    st.code(html_text[:5000] + ("\n... (truncated)" if len(html_text) > 5000 else ""), language="html")