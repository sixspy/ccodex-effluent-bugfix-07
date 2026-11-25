"""effluent-bugfix-07 · 出库未齐仍能封批 —— 复现夹具（三红共用）。

夹具口径：
- 污泥出库登记在途（待出库）= 空桩未齐；
- 夹具直落一条「已出库」= 出库齐套（争用测排除甲路干扰用）。

单独复现：PYTHONPATH=backend:tests python tests/bf07_harness.py
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi.testclient import TestClient

from app import app
from db import init_db

PERMIT_EAST = "DP-2026-E01"
OUTFALL_EAST = "OF-E1-A"


def make_client(tmp_path, monkeypatch, name: str = "bf07"):
    """独立 tmp 库 + TestClient，返回 (client, db_path)。"""
    db_path = tmp_path / f"{name}.db"
    monkeypatch.setattr("db.DB_PATH", db_path)
    init_db()
    return TestClient(app), db_path


def auth(c: TestClient, username: str = "admin", password: str = "admin123") -> dict:
    tok = c.post(
        "/api/login", json={"username": username, "password": password}
    ).json()["token"]
    return {"Authorization": "Bearer " + tok}


def find_outfall(c: TestClient, h: dict, code: str = OUTFALL_EAST) -> dict:
    items = c.get("/api/outfalls", headers=h).json()["items"]
    return next(x for x in items if x["outfall_code"] == code)


def sealable_sample(c: TestClient, h: dict, code: str, outfall_id: int) -> dict:
    """造一批不超标采样（已裁定，可封批）。"""
    r = c.post(
        "/api/samples",
        headers=h,
        json={
            "outfall_id": outfall_id,
            "permit_ref": PERMIT_EAST,
            "sample_code": code,
            "flow_m3h": 1800,
            "metrics": {"cod": 40.0, "nh3n": 3.0, "tp": 0.2},
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def enqueue_outbound(c: TestClient, h: dict, plant_id: int, bay: str) -> int:
    """登记污泥出库（在途=待出库，空桩未齐），返回登记 id。"""
    r = c.post(
        "/api/stubs/sludge-plan",
        headers=h,
        json={"plant_id": plant_id, "digester_bay": bay, "mode": "enqueue"},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def complete_outbound(c: TestClient, h: dict, job_id: int) -> dict:
    """登记出库完成（待出库→已出库），触发影子升正联动。"""
    r = c.post(f"/api/stubs/sludge-plan/outbound?job_id={job_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def force_outbound_done(db_path, plant_id: int, bay: str) -> None:
    """夹具直落一条「已出库」，绕开写口（争用测只验锁，不验出库口）。"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO sludge_plan_jobs(plant_id,digester_bay,mode,status,detail,created_at)
           VALUES (?,?,?,?,?,?)""",
        (
            plant_id,
            bay,
            "enqueue",
            "已出库",
            "夹具直落：出库已齐",
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()


def sample_state(c: TestClient, h: dict, sample_id: int) -> dict:
    return c.get(f"/api/samples/{sample_id}", headers=h).json()["sample"]


def seals_for(c: TestClient, h: dict, sample_id: int) -> list:
    items = c.get("/api/seals", headers=h).json()["items"]
    return [s for s in items if s["sample_id"] == sample_id]


def reconcile(c: TestClient, h: dict, permit: str = PERMIT_EAST) -> dict:
    return c.get(f"/api/reconcile/{permit}", headers=h).json()


def proof(c: TestClient, h: dict, sample_code: str) -> dict:
    return c.get(f"/api/proof/sample/{sample_code}", headers=h).json()


def audit_actions(c: TestClient, h: dict) -> list:
    items = c.get("/api/audit?limit=500", headers=h).json()["items"]
    return [i["action"] for i in items]


if __name__ == "__main__":
    # 复现夹具：出库未齐仍能封批
    import tempfile
    from pathlib import Path

    import db

    tmp = Path(tempfile.mkdtemp(prefix="bf07-repro-"))
    db.DB_PATH = tmp / "repro.db"
    db.init_db()
    client = TestClient(app)
    hdr = auth(client)
    of = find_outfall(client, hdr)
    smp = sealable_sample(client, hdr, "SM-BF07-REPRO-001", of["id"])
    job_id = enqueue_outbound(client, hdr, of["plant_id"], "D-REPRO-01")
    stub = client.get("/api/stubs/sludge-plan", headers=hdr).json()
    resp = client.post("/api/seals", headers=hdr, json={"sample_id": smp["id"]})
    formal = [s for s in seals_for(client, hdr, smp["id"]) if s["status"] == "已封批"]
    print(f"[夹具] 出库登记 id={job_id} 在途（待出库），空桩未齐")
    print(f"[夹具] 空桩口径: status={stub.get('status')} outbound_ready={stub.get('outbound_ready')}")
    print(f"[夹具] 封批响应: {resp.status_code} {resp.text}")
    print(f"[夹具] 正式快照数: {len(formal)}")
    if resp.status_code == 200 and formal:
        print("[夹具] 复现成功：出库未齐仍能封批，正式快照照落（缺陷）")
    else:
        print("[夹具] 已修复：出库未齐封批拒写，正式快照零增")
