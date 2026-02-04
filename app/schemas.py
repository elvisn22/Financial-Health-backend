from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(min_length=6)


class UserRead(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AssessmentCreate(BaseModel):
    business_name: Optional[str] = None
    industry: Optional[str] = None
    locale: Optional[str] = Field(default="en")


class Metric(BaseModel):
    key: str
    label: str
    value: float | None = None
    unit: Optional[str] = None
    interpretation: Optional[str] = None


class BenchmarkMetric(BaseModel):
    key: str
    label: str
    business_value: float | None = None
    benchmark_value: float | None = None
    status: str  # "good", "ok", "risk"
    note: Optional[str] = None


class AssessmentResult(BaseModel):
    overall_score: float
    risk_level: str
    metrics: list[Metric]
    narrative: str
    raw_stats: Dict[str, Any]
    benchmarks: list[BenchmarkMetric] = []


class AssessmentRead(BaseModel):
    id: int
    business_name: Optional[str]
    industry: Optional[str]
    locale: Optional[str]
    created_at: datetime
    summary: Optional[AssessmentResult] = None

    class Config:
        from_attributes = True

