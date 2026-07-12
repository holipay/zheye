from datetime import datetime

from pydantic import BaseModel


class CompanyDimensionSchema(BaseModel):
    dimension: str
    alpha: float
    beta: float
    mean: float
    variance: float
    std: float
    label: str
    label_en: str
    credible_interval_lower: float
    credible_interval_upper: float


class EvidenceSchema(BaseModel):
    id: int
    news_id: int
    news_title: str
    dimension: str
    direction: str
    strength: float
    confidence: float
    source: str
    created_at: datetime


class BeliefHistoryPoint(BaseModel):
    recorded_at: datetime
    mean: float
    variance: float
    alpha: float
    beta: float


class CompanySummary(BaseModel):
    id: int
    entity_id: int
    company_name: str
    dimensions: list[CompanyDimensionSchema]
    is_active: bool
    updated_at: datetime | None


class CompanyDetail(BaseModel):
    id: int
    entity_id: int
    company_name: str
    dimensions: list[CompanyDimensionSchema]
    recent_evidence: list[EvidenceSchema]
    is_active: bool
    updated_at: datetime | None
