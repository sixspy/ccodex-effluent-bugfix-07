"""Pydantic 入参模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PlantIn(BaseModel):
    plant_code: str = Field(min_length=3, max_length=32)
    name: str
    basin: str
    design_cap_m3d: float = Field(gt=0, lt=1_000_000)
    status: str = "运行"


class OutfallIn(BaseModel):
    outfall_code: str
    plant_id: int
    river_reach: str
    cod_limit: float = Field(gt=0, lt=500)
    nh3n_limit: float = Field(gt=0, lt=50)
    tp_limit: float = Field(gt=0, lt=10)
    status: str = "开放"


class MetricsIn(BaseModel):
    cod: float = Field(ge=0)
    nh3n: float = Field(ge=0)
    tp: float = Field(ge=0)


class SampleIn(BaseModel):
    outfall_id: int
    permit_ref: str
    metrics: MetricsIn
    flow_m3h: float = Field(gt=0, lt=50000)
    sample_code: str | None = None


class ExceedOpenIn(BaseModel):
    sample_id: int
    note: str = ""


class ExceedCloseIn(BaseModel):
    hold_id: int
    note: str = ""


class ReleaseIn(BaseModel):
    sample_id: int
    officer: str = "值班员"


class SealIn(BaseModel):
    sample_id: int
    snapshot: str | None = None


class PermitIn(BaseModel):
    permit_code: str
    plant_id: int
    quota_m3d: float
    cod_cap: float
    nh3n_cap: float
    tp_cap: float
    period_label: str


class LineageIn(BaseModel):
    from_sample_id: int
    to_sample_id: int | None = None
    edge_type: str
    detail: str


class StubJobIn(BaseModel):
    mode: str = "dry_run"
    detail: str = ""


class LabCourierIn(StubJobIn):
    sample_code: str
    courier_slot: str = "A1"


class SludgePlanIn(StubJobIn):
    plant_id: int | None = None
    digester_bay: str = "D-01"
