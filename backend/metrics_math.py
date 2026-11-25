"""排放指标演算与阈值辅助（被采样/对账链路调用）。"""
from __future__ import annotations

from typing import Iterable


METRIC_KEYS = ("cod", "nh3n", "tp")
METRIC_LABELS = {"cod": "COD", "nh3n": "氨氮", "tp": "总磷"}


def as_float_map(metrics: dict | None) -> dict[str, float]:
    raw = metrics or {}
    return {k: float(raw.get(k, 0) or 0) for k in METRIC_KEYS}


def first_exceed(
    metrics: dict, limits: dict, order: Iterable[str] = METRIC_KEYS
) -> tuple[str | None, float, float]:
    m = as_float_map(metrics)
    for key in order:
        measured = m[key]
        limit = float(limits.get(key, 0) or 0)
        if measured > limit:
            return METRIC_LABELS.get(key, key), measured, limit
    return None, 0.0, 0.0


def all_within(metrics: dict, limits: dict, tol: float = 0.0) -> bool:
    m = as_float_map(metrics)
    for key in METRIC_KEYS:
        if m[key] - float(limits.get(key, 0) or 0) > tol:
            return False
    return True


def weighted_load(metrics: dict, flow_m3h: float) -> dict[str, float]:
    """瞬时流量 × 浓度，粗算负荷（mg/L × m3/h）。"""
    m = as_float_map(metrics)
    f = float(flow_m3h)
    return {k: round(m[k] * f, 3) for k in METRIC_KEYS}


def daily_flow_m3(flow_m3h: float) -> float:
    return float(flow_m3h) * 24.0


def quota_headroom(quota_m3d: float, flow_m3h: float) -> float:
    return float(quota_m3d) - daily_flow_m3(flow_m3h)


def format_triplet(metrics: dict) -> str:
    m = as_float_map(metrics)
    return (
        f"COD={m['cod']:.1f} "
        f"NH3-N={m['nh3n']:.2f} "
        f"TP={m['tp']:.3f}"
    )


def compare_to_caps(
    metrics: dict, caps: dict, tol: float = 0.05
) -> list[dict]:
    """返回各指标相对许可帽的差值明细。"""
    m = as_float_map(metrics)
    rows = []
    for key in METRIC_KEYS:
        cap = float(caps.get(key, 0) or 0)
        delta = m[key] - cap
        rows.append(
            {
                "metric": METRIC_LABELS[key],
                "measured": m[key],
                "cap": cap,
                "delta": round(delta, 4),
                "over": delta > tol,
            }
        )
    return rows


def merge_metrics(base: dict, patch: dict) -> dict[str, float]:
    out = as_float_map(base)
    for key in METRIC_KEYS:
        if key in patch and patch[key] is not None:
            out[key] = float(patch[key])
    return out


def generation_bump(current: int) -> int:
    return max(1, int(current)) + 1


def seal_ref_for(sample_code: str, generation: int) -> str:
    return f"SL-{sample_code}-G{int(generation)}"


def release_ref_for(sample_code: str) -> str:
    return f"RL-{sample_code}"


def hold_key_for(sample_code: str, metric_label: str) -> str:
    return f"EX-{sample_code}-{metric_label}"
