"""排放指标与状态校验。"""
from __future__ import annotations

from fastapi import HTTPException

from metrics_math import (
    as_float_map,
    compare_to_caps,
    daily_flow_m3,
    first_exceed,
    format_triplet,
    quota_headroom,
)


def validate_outfall_open(status: str) -> None:
    if status != "开放":
        raise HTTPException(400, f"排放口状态不可采样：{status}")


def validate_plant_running(status: str) -> None:
    if status != "运行":
        raise HTTPException(400, f"处理厂未运行：{status}")


def adjudicate_exceed(metrics: dict, limits: dict) -> tuple[bool, str | None, float, float]:
    """对照排放口限值，返回是否超标及首个超标指标。"""
    label, measured, limit = first_exceed(metrics, limits)
    if label:
        return True, label, measured, limit
    return False, None, 0.0, 0.0


def validate_metrics_nonneg(metrics: dict) -> None:
    for key, val in as_float_map(metrics).items():
        if val < 0:
            raise HTTPException(400, f"指标 {key} 不可为负")


def validate_flow_cap(flow_m3h: float, design_cap_m3d: float) -> None:
    # 设计日处理量粗换算小时流量上限（按 24h 均分 *1.5 峰值）
    hourly_cap = float(design_cap_m3d) / 24.0 * 1.5
    if flow_m3h > hourly_cap:
        raise HTTPException(
            400, f"瞬时流量 {flow_m3h} 超过处理厂峰值 {hourly_cap:.1f} m3/h"
        )


def validate_permit_match(
    permit_caps: dict, sample_metrics: dict, flow_m3h: float, quota_m3d: float, tol: float = 0.05
) -> bool:
    """许可册与采样指标是否账实对齐（粗阈值）。"""
    overs = [r for r in compare_to_caps(sample_metrics, permit_caps, tol=tol) if r["over"]]
    if overs:
        return False
    if quota_headroom(quota_m3d, flow_m3h) < -(tol * 100):
        return False
    _ = daily_flow_m3(flow_m3h)
    return True


def validate_sample_releasable(status: str) -> None:
    if status != "已裁定":
        raise HTTPException(400, f"当前状态不可准排：{status}")


def validate_sample_sealable(status: str) -> None:
    if status not in ("已裁定", "已准排"):
        raise HTTPException(400, f"当前状态不可封批：{status}")


def metric_summary(metrics: dict) -> str:
    return format_triplet(metrics)
