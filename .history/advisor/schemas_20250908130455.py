"""
Pydantic data models for GrantScope Advisor pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Literal

import hashlib
import json as _json

from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict  # type: ignore

    _P2 = True
except ImportError:  # pydantic v1
    ConfigDict = None  # type: ignore
    _P2 = False


class _BaseModel(BaseModel):
    if "ConfigDict" in globals() and _P2:
        model_config = ConfigDict(extra="ignore")  # type: ignore
    else:

        class Config:
            extra = "ignore"


def _json_dumps_stable(obj: Any) -> str:
    return _json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash_for_obj(obj: Any) -> str:
    return hashlib.sha256(_json_dumps_stable(obj).encode("utf-8")).hexdigest()[:16]


class InterviewInput(_BaseModel):
    program_area: str = ""
    populations: List[str] = Field(default_factory=list)
    geography: List[str] = Field(default_factory=list)
    timeframe_years: Optional[int] = None
    budget_usd_range: Optional[Tuple[Optional[float], Optional[float]]] = None
    outcomes: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    preferred_funder_types: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    notes: str = ""
    user_role: str = "Grant Analyst/Writer"

    def model_as_dict(self) -> Dict[str, Any]:
        try:
            return self.model_dump(mode="json")  # pydantic v2
        except AttributeError:
            return self.dict()  # pydantic v1

    def stable_hash(self) -> str:
        return stable_hash_for_obj(self.model_as_dict())


class StructuredNeeds(_BaseModel):
    subjects: List[str] = Field(default_factory=list)
    populations: List[str] = Field(default_factory=list)
    geographies: List[str] = Field(default_factory=list)
    weights: Dict[str, float] = Field(default_factory=dict)


class MetricRequest(_BaseModel):
    tool: Literal[
        "df_describe",
        "df_groupby_sum",
        "df_top_n",
        "df_value_counts",
        "df_unique",
        "df_filter_equals",
        "df_filter_in",
        "df_filter_range",
        "df_pivot_table",
        "df_corr_top",
        "df_sql_select",
        "get_chart_state",
    ]
    params: Dict[str, Any] = Field(default_factory=dict)
    title: str = ""
    id: Optional[str] = None


class AnalysisPlan(_BaseModel):
    metric_requests: List[MetricRequest] = Field(default_factory=list)
    narrative_outline: List[str] = Field(default_factory=list)


class DataPoint(_BaseModel):
    id: str
    title: str
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)
    table_md: str = ""
    notes: str = ""


class FunderCandidate(_BaseModel):
    name: str
    score: float = 0.0
    rationale: str = ""
    grounded_dp_ids: List[str] = Field(default_factory=list)


class TuningTip(_BaseModel):
    text: str
    grounded_dp_ids: List[str] = Field(default_factory=list)


class SearchQuery(_BaseModel):
    query: str
    notes: str = ""


class Recommendations(_BaseModel):
    funder_candidates: List[FunderCandidate] = Field(default_factory=list)
    response_tuning: List[TuningTip] = Field(default_factory=list)
    search_queries: List[SearchQuery] = Field(default_factory=list)


class Attachment(_BaseModel):
    kind: Literal["figure", "table", "text", "link", "datapoint_ref"] = "text"
    ref_id: Optional[str] = None
    content: Optional[str] = None


class ReportSection(_BaseModel):
    title: str
    markdown_body: str
    attachments: List[Attachment] = Field(default_factory=list)


class ChartSummary(_BaseModel):
    """Lightweight, model-safe summary of a chart for LLM interpretation."""

    label: str = ""
    highlights: List[str] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class FigureArtifact(_BaseModel):
    id: str
    label: str = ""
    png_base64: Optional[str] = None
    html: Optional[str] = None
    # Optional structured summary of the chart content (grounding for LLM)
    summary: Optional[ChartSummary] = None
    # Optional short interpretation (1–3 sentences), grounded in summary + interview profile
    interpretation_text: Optional[str] = None


class ReportBundle(_BaseModel):
    interview: InterviewInput
    needs: StructuredNeeds
    plan: AnalysisPlan
    datapoints: List[DataPoint] = Field(default_factory=list)
    recommendations: Recommendations = Field(default_factory=Recommendations)
    sections: List[ReportSection] = Field(default_factory=list)
    figures: List[FigureArtifact] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    version: str = "1.0"

    def index_by_id(self) -> Dict[str, DataPoint]:
        return {dp.id: dp for dp in self.datapoints}

    def to_json(self) -> str:
        try:
            data = self.model_dump(mode="json")
        except AttributeError:
            data = self.dict()
        return _json_dumps_stable(data)

    @classmethod
    def from_json(cls, text: str) -> "ReportBundle":
        data = _json.loads(text)
        return cls(**data)


# Ensure a single module identity for schemas regardless of import path
from contextlib import suppress as _suppress  # type: ignore

with _suppress(Exception):
    import sys as _sys  # type: ignore

    _mod = _sys.modules.get(__name__)
    if _mod is not None:
        _sys.modules.setdefault("advisor.schemas", _mod)
        _sys.modules.setdefault("GrantScope.advisor.schemas", _mod)
