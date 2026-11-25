import pytest
from fastapi.testclient import TestClient

from app import app
from db import init_db


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr("db.DB_PATH", tmp_path / "t.db")
    init_db()
    yield


def _auth(c: TestClient, user="admin", password="admin123") -> dict:
    tok = c.post(
        "/api/login", json={"username": user, "password": password}
    ).json()["token"]
    return {"Authorization": "Bearer " + tok}


def test_health_and_seed():
    c = TestClient(app)
    health = c.get("/api/health").json()
    assert health["product"] == "污水排放批"
    assert health["plants"] >= 4
    assert health["outfalls"] >= 5
    assert health["samples"] >= 4
    assert "lab_courier_stub" in health["meta"]["stubs"]


def test_sample_exceed_release_seal_flow():
    c = TestClient(app)
    h = _auth(c)
    outfalls = c.get("/api/outfalls", headers=h).json()["items"]
    of = next(x for x in outfalls if x["outfall_code"] == "OF-E1-A")
    created = c.post(
        "/api/samples",
        headers=h,
        json={
            "outfall_id": of["id"],
            "permit_ref": "DP-2026-E01",
            "sample_code": "SM-FLOW-001",
            "flow_m3h": 2000,
            "metrics": {"cod": 62.0, "nh3n": 3.0, "tp": 0.2},
        },
    ).json()
    assert created["exceed"] is True
    assert created["status"] == "旁路挂起"
    holds = c.get("/api/exceeds?status=开放", headers=h).json()["items"]
    hold = next(x for x in holds if x["sample_code"] == "SM-FLOW-001")
    close = c.post(
        "/api/exceeds/close",
        headers=h,
        json={"hold_id": hold["id"], "note": "加药回调"},
    )
    assert close.status_code == 200
    assert close.json()["sample_adjudicated"] is True
    release = c.post(
        "/api/releases",
        headers=h,
        json={"sample_id": created["id"], "officer": "验收员"},
    )
    assert release.status_code == 200
    seal = c.post("/api/seals", headers=h, json={"sample_id": created["id"]})
    assert seal.status_code == 200
    assert seal.json()["generation"] == 2
    proof = c.get("/api/proof/sample/SM-FLOW-001", headers=h).json()
    assert proof["released"] is True
    assert proof["sealed"] is True


def test_viewer_cannot_write():
    c = TestClient(app)
    h = _auth(c, "viewer", "viewer123")
    r = c.post(
        "/api/plants",
        headers=h,
        json={
            "plant_code": "PL-X",
            "name": "x",
            "basin": "b",
            "design_cap_m3d": 1000,
        },
    )
    assert r.status_code == 403


def test_reconcile_seed_permit():
    c = TestClient(app)
    h = _auth(c)
    data = c.get("/api/reconcile/DP-2026-E01", headers=h).json()
    assert data["permit_code"] == "DP-2026-E01"
    assert "samples" in data
