from pydantic import BaseModel, Field
from typing import List, Optional


class Brief(BaseModel):
    topic: str
    agenda: List[str]
    beginner_pct: int = Field(ge=0, le=100)
    advanced_pct: int = Field(ge=0, le=100)
    duration: int = Field(gt=0)
    content_pct: int = Field(ge=0, le=100)
    code_pct: int = Field(ge=0, le=100)
    prior_topics: Optional[List[str]] = None


class RegenerateRequest(BaseModel):
    script_id: str
    segment_id: str
    feedback: str


class ApproveRequest(BaseModel):
    script_id: str
