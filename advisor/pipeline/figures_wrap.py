from __future__ import annotations

from typing import Any

import pandas as pd

from .cache import cache_key_for
from .convert import _safe_to_dict
from .ids import _stable_fig_id
from .imports import ChartSummary, FigureArtifact, _interpret_chart_cached


def _wrap_plot_as_figure(
    label: str,
    plot_obj: Any,
    summary: ChartSummary | None = None,
    interpretation_text: str | None = None,
) -> FigureArtifact:
    """Wrap a Plotly-like object into a FigureArtifact with PNG (kaleido) or HTML fallback."""
    png_b64: str | None = None
    html: str | None = None
    try:
        to_image = getattr(plot_obj, "to_image", None)
        if callable(to_image):
            try:
                png_bytes_obj = to_image(format="png", engine="kaleido")
                import base64

                if isinstance(png_bytes_obj, (bytes, bytearray)):
                    png_b64 = base64.b64encode(png_bytes_obj).decode("utf-8")
                else:
                    png_b64 = None
            except Exception:
                png_b64 = None
    except Exception:
        png_b64 = None

    if png_b64 is None:
        try:
            to_html = getattr(plot_obj, "to_html", None)
            if callable(to_html):
                html_obj = to_html(full_html=False, include_plotlyjs="cdn")
                if isinstance(html_obj, str):
                    html = html_obj
                elif html_obj is not None:
                    html = str(html_obj)
                else:
                    html = None
        except Exception:
            html = None

    return FigureArtifact(
        id=_stable_fig_id(label),
        label=label,
        png_base64=png_b64,
        html=html,
        summary=summary,
        interpretation_text=interpretation_text,
    )


def _figures_default(df: pd.DataFrame, interview, needs) -> list[FigureArtifact]:
    """Build a minimal figure set using figures module with summaries and interpretations."""
    out: list[FigureArtifact] = []
    try:
        try:
            from GrantScope.advisor import figures as figs  # type: ignore
        except Exception:  # pragma: no cover
            import advisor.figures as figs  # type: ignore

        interview_dict = _safe_to_dict(interview)

        def _chart_cache_key(kind: str, summary_dict: dict[str, Any]) -> str:
            try:
                base = cache_key_for(interview, df)
            except Exception:
                base = f"{len(df)}::{','.join(map(str, getattr(df, 'columns', [])))}"
            return f"{base}::{kind}"

        # Top funders by amount
        if "funder_name" in df.columns and "amount_usd" in df.columns:
            func = getattr(figs, "figure_top_funders_bar", None)
            prep = getattr(figs, "_prep_top_funders", None)
            if callable(func):
                plot_obj = func(df, needs)
                try:
                    top_df = prep(df, needs) if callable(prep) else None
                except Exception:
                    top_df = None
                highlights: list[str] = []
                stats: dict[str, Any] = {}
                try:
                    if isinstance(top_df, pd.DataFrame) and not top_df.empty:
                        n = int(len(top_df))
                        stats["n_bars"] = n
                        top_name = str(top_df.iloc[0]["funder_name"])
                        _val0 = pd.to_numeric(top_df.iloc[0]["amount_usd"], errors="coerce")
                        top_val = float(_val0) if pd.notna(_val0) else 0.0
                        stats["top_funder"] = top_name
                        stats["top_amount"] = top_val
                        if top_val > 0:
                            highlights.append(f"{top_name} leads in total awarded amount")
                    else:
                        stats["n_bars"] = 0
                except Exception:
                    pass
                summary = ChartSummary(label="Top Funders", highlights=highlights, stats=stats)
                sdict = _safe_to_dict(summary)
                interp = _interpret_chart_cached(
                    _chart_cache_key("top_funders", sdict), sdict, interview_dict
                )
                out.append(
                    _wrap_plot_as_figure(
                        "Top Funders", plot_obj, summary=summary, interpretation_text=interp
                    )
                )

        # Distribution of amounts
        if "amount_usd" in df.columns:
            func2 = getattr(figs, "figure_amount_distribution", None)
            prep2 = getattr(figs, "_prep_distribution", None)
            if callable(func2):
                plot_obj2 = func2(df, needs)
                try:
                    ddf = prep2(df, needs) if callable(prep2) else None
                except Exception:
                    ddf = None
                highlights2: list[str] = []
                stats2: dict[str, Any] = {}
                try:
                    if (
                        isinstance(ddf, pd.DataFrame)
                        and not ddf.empty
                        and "amount_usd" in ddf.columns
                    ):
                        series = pd.to_numeric(ddf["amount_usd"], errors="coerce").dropna()
                        stats2["count"] = int(series.shape[0])
                        stats2["median"] = float(series.median())
                        stats2["p90"] = float(series.quantile(0.9))
                        try:
                            med = float(series.median())
                            mean = float(series.mean())
                            if med > 0.0 and mean / med > 1.1:
                                highlights2.append("Amounts are right-skewed")
                            elif mean > 0.0 and med / mean > 1.1:
                                highlights2.append("Amounts are left-skewed")
                            else:
                                highlights2.append("Amounts are roughly symmetric")
                        except Exception:
                            pass
                    else:
                        stats2["count"] = 0
                except Exception:
                    pass
                summary2 = ChartSummary(
                    label="Amount Distribution", highlights=highlights2, stats=stats2
                )
                sdict2 = _safe_to_dict(summary2)
                interp2 = _interpret_chart_cached(
                    _chart_cache_key("amount_distribution", sdict2), sdict2, interview_dict
                )
                out.append(
                    _wrap_plot_as_figure(
                        "Amount Distribution",
                        plot_obj2,
                        summary=summary2,
                        interpretation_text=interp2,
                    )
                )

        # Time trend by year
        if "year_issued" in df.columns and "amount_usd" in df.columns:
            func3 = getattr(figs, "figure_time_trend", None)
            prep3 = getattr(figs, "_prep_time_trend", None)
            if callable(func3):
                plot_obj3 = func3(df, needs)
                try:
                    tdf = prep3(df, needs) if callable(prep3) else None
                except Exception:
                    tdf = None
                highlights3: list[str] = []
                stats3: dict[str, Any] = {}
                try:
                    if isinstance(tdf, pd.DataFrame) and not tdf.empty:
                        stats3["n_points"] = int(len(tdf))
                        sorted_df = tdf.sort_values("year_issued")
                        first_row = sorted_df.iloc[0]
                        last_row = sorted_df.iloc[-1]
                        fy = (
                            int(first_row["year_issued"])
                            if pd.notna(first_row["year_issued"])
                            else None
                        )
                        ly = (
                            int(last_row["year_issued"])
                            if pd.notna(last_row["year_issued"])
                            else None
                        )
                        _fv = pd.to_numeric(first_row["amount_usd"], errors="coerce")
                        _lv = pd.to_numeric(last_row["amount_usd"], errors="coerce")
                        fv = float(_fv) if pd.notna(_fv) else 0.0
                        lv = float(_lv) if pd.notna(_lv) else 0.0
                        stats3.update(
                            {"first_year": fy, "last_year": ly, "first_total": fv, "last_total": lv}
                        )
                        if lv > fv:
                            highlights3.append("Total awarded amount increased over time")
                        elif lv < fv:
                            highlights3.append("Total awarded amount decreased over time")
                        else:
                            highlights3.append("Total awarded amount remained flat")
                    else:
                        stats3["n_points"] = 0
                except Exception:
                    pass
                summary3 = ChartSummary(label="Time Trend", highlights=highlights3, stats=stats3)
                sdict3 = _safe_to_dict(summary3)
                interp3 = _interpret_chart_cached(
                    _chart_cache_key("time_trend", sdict3), sdict3, interview_dict
                )
                out.append(
                    _wrap_plot_as_figure(
                        "Time Trend", plot_obj3, summary=summary3, interpretation_text=interp3
                    )
                )
    except Exception:
        return out
    return out
