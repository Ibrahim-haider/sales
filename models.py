
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MappingRequest(BaseModel):
    session_id: str
    mapping: Dict[str, str]


class FilterRule(BaseModel):
    column: str
    operator: str
    value: Any = None
    value2: Any = None


class FilterRequest(BaseModel):
    session_id: str
    filters: List[FilterRule] = Field(default_factory=list)
    sort_by: Optional[str] = None
    sort_direction: str = "asc"
    page: int = 1
    page_size: int = 100


class CalculatedColumnRequest(BaseModel):
    session_id: str
    name: str
    expression: str


class AggregateRequest(BaseModel):
    session_id: str
    group_by: List[str] = Field(default_factory=list)
    metrics: List[Dict[str, str]] = Field(default_factory=list)
    filters: List[FilterRule] = Field(default_factory=list)


class ExportRequest(BaseModel):
    session_id: str
    filters: List[FilterRule] = Field(default_factory=list)
    format: str = "csv"
