"""
Recommendations engine: data-first with optional AI augmentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import streamlit as st

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore

# Central config
try:
    from GrantScope import config  # type: ignore
except Exception:
    import config  # type: ignore

from loaders.llama_index_setup import get_openai_client
from utils.utils import sanitize_markdown

SourceType = Literal["data", "ai"]


@dataclass
class Recommendation:
    id: str
    title: str
    reason: str
    score: float
    source: SourceType


class GrantRecommender:
    """Generate recommendations from local data; optionally augment with AI."""

    def __init__(self, df):
        self.df = df

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=600)  # Cache for 10 minutes
    def _top_funders(df, n: int = 5) -> list[str]:  # type: ignore[no-redef]
        try:
            if "funder_name" not in df.columns or "amount_usd" not in df.columns:
                return []
            s = (
                df.groupby("funder_name")["amount_usd"]
                .sum()
                .sort_values(ascending=False)
                .head(int(n))
            )
            return list(s.index.astype(str))
        except Exception:
            return []

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=600)  # Cache for 10 minutes
    def _recent_year(df) -> int | None:  # type: ignore[no-redef]
        try:
            if "year_issued" not in df.columns:
                return None
            years = pd.to_numeric(df["year_issued"], errors="coerce").dropna().astype(int)
            if years.empty:
                return None
            return int(years.max())
        except Exception:
            return None

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=600)  # Cache for 10 minutes
    def _amount_stats(df) -> dict[str, float]:  # type: ignore[no-redef]
        try:
            if "amount_usd" not in df.columns:
                return {}
            s = pd.to_numeric(df["amount_usd"], errors="coerce").dropna()
            if s.empty:
                return {}
            return {
                "median": float(s.median()),
                "p25": float(s.quantile(0.25)),
                "p75": float(s.quantile(0.75)),
                "min": float(s.min()),
                "max": float(s.max()),
            }
        except Exception:
            return {}

    def data_first(self, context: dict[str, Any] | None = None) -> list[Recommendation]:
        ctx = context or {}
        recs: list[Recommendation] = []

        # Budget realism suggestion
        stats = self._amount_stats(self.df)
        if stats:
            mid = stats.get("median", 0.0)
            p25, p75 = stats.get("p25", 0.0), stats.get("p75", 0.0)
            budget_note = f"Typical grants in this dataset range around ${p25:,.0f}–${p75:,.0f} (median ${mid:,.0f})."
            recs.append(
                Recommendation(
                    id="budget_range",
                    title="Set a realistic grant size",
                    reason=budget_note + " Pick a target size based on your project scope.",
                    score=0.9,
                    source="data",
                )
            )

        # Top funders suggestion
        funders = self._top_funders(self.df, n=5)
        if funders:
            recs.append(
                Recommendation(
                    id="top_funders",
                    title="Research active funders",
                    reason=(
                        "These funders give the most in your data: "
                        + ", ".join(funders)
                        + ". Check their focus areas and recent awards."
                    ),
                    score=0.85,
                    source="data",
                )
            )

        # Recent activity suggestion
        recent = self._recent_year(self.df)
        if recent:
            recs.append(
                Recommendation(
                    id="recent_year",
                    title="Focus on recent activity",
                    reason=(
                        f"Most recent awards appear in {recent}. Prioritize funders and subjects with activity"
                        " in the last 1–2 years."
                    ),
                    score=0.8,
                    source="data",
                )
            )

        # If distribution clusters context exists, reflect it
        clusters = (ctx.get("selected_clusters") or []) if isinstance(ctx, dict) else []
        if clusters:
            recs.append(
                Recommendation(
                    id="clusters_focus",
                    title="Match your budget to common grant sizes",
                    reason=(
                        "You selected these USD clusters: " + ", ".join(map(str, clusters)) + ". "
                        "Look for funders that often award in these ranges."
                    ),
                    score=0.75,
                    source="data",
                )
            )

        # Keep list short and sorted
        recs.sort(key=lambda r: r.score, reverse=True)
        return recs[:6]

    def augment_with_ai(
        self, base: list[Recommendation], profile: dict[str, Any] | None = None
    ) -> list[Recommendation]:
        # Respect feature flag and key
        if not config.is_enabled("GS_ENABLE_AI_AUGMENTATION"):
            return base
        try:
            client = get_openai_client()
        except Exception:
            return base

        # Build prompt
        audience = "new" if not profile or profile.get("experience_level") == "new" else "pro"
        style = (
            "Explain for a beginner. Use short sentences, plain language, and 3 concrete next steps."
            if audience == "new"
            else "Be concise and specific."
        )
        base_lines = [f"- {r.title}: {r.reason}" for r in base]
        user_prompt = (
            "You are an assistant helping a grant seeker. Improve and add up to 2 actionable recommendations.\n"
            f"Audience style: {style}\n"
            "Recommendations so far:\n" + "\n".join(base_lines)
        )
        try:
            resp = client.chat.completions.create(
                model=config.get_model_name("gpt-5-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "Return clear, safe, realistic suggestions only.",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=400,
            )
            content = resp.choices[0].message.content or ""
            if content.strip():
                # Append as a single AI recommendation
                base.append(
                    Recommendation(
                        id="ai_augmented",
                        title="AI Suggestions",
                        reason=content.strip(),
                        score=0.7,
                        source="ai",
                    )
                )
        except Exception:
            # Silent fallback
            return base
        return base

    @staticmethod
    def render_panel(df, context: dict[str, Any] | None = None) -> None:
        """Convenience UI panel renderer for pages."""
        recommender = GrantRecommender(df)
        recs = recommender.data_first(context)
        # Try to get profile from session if available
        profile = None
        try:
            from utils.app_state import get_session_profile  # deferred import

            prof = get_session_profile()
            profile = prof.to_dict() if hasattr(prof, "to_dict") else None
        except Exception:
            profile = None

        recs = recommender.augment_with_ai(recs, profile)

        with st.expander("💡 Smart Recommendations", expanded=True):
            if not recs:
                st.info("No recommendations available for this view.")
                return
            for r in recs:
                title = sanitize_markdown(r.title)
                reason = sanitize_markdown(r.reason)
                if r.source == "ai":
                    st.markdown(f"**{title}**")
                    st.markdown(reason)
                else:
                    st.success(f"**{title}** — {reason}")
