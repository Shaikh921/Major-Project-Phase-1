"""
AI Incident Narrator Pydantic Schemas (Module 5).
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class NarratorQueryRequest(BaseModel):
    query: str = Field(..., json_schema_extra={"example": "What caused the high CPU alert on prod-api-01?"})
    host_id: Optional[int] = None
    environment: Optional[str] = None
    time_window_minutes: int = Field(default=60, ge=5, le=1440)


class EvidenceItem(BaseModel):
    category: str  # "Metric", "Alert", "Security", "Forecast", "Cost"
    timestamp: Optional[datetime] = None
    resource: str
    detail: str
    severity: Optional[str] = None


class NarratorStructuredExplanation(BaseModel):
    observation: str
    evidence_points: List[str]
    possible_root_cause: str
    recommended_investigation: List[str]
    confidence_level: str  # "High", "Medium", "Low"
    affected_resources: List[str]
    timeline_events: List[EvidenceItem]
    cited_data_sources: List[str]


class NarratorQueryResponse(BaseModel):
    query: str
    generated_at: datetime
    structured_explanation: NarratorStructuredExplanation
    raw_markdown_narrative: str
    disclaimer: str = "AI model inferences are analytical suggestions grounded in telemetry and must be validated by operators before taking destructive remediation actions."
