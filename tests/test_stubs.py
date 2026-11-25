from fastapi.testclient import TestClient

from app import app
from db import init_db


def setup_module():
    pass


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr("db.DB_PATH", tmp_path / "stub.db")
    init_db()
    return TestClient(app)


def _auth(c):
    tok = c.post("/api/login", json={"username": "admin", "password": "admin123"}).json()[
        "token"
    ]
    return {"Authorization": "Bearer " + tok}


def test_lab_courier_stub(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    h = _auth(c)
    listed = c.get("/api/stubs/lab-courier", headers=h).json()
    assert listed["stub"] is True
    assert listed["ready"] is False
    job = c.post(
        "/api/stubs/lab-courier",
        headers=h,
        json={"sample_code": "SM-X", "courier_slot": "B2", "mode": "dry_run"},
    ).json()
    assert job["stub"] is True
    assert job["status"] == "演练"


def test_sludge_plan_stub(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    h = _auth(c)
    listed = c.get("/api/stubs/sludge-plan", headers=h).json()
    assert listed["ready"] is False
    job = c.post(
        "/api/stubs/sludge-plan",
        headers=h,
        json={"plant_id": 1, "digester_bay": "D-09", "mode": "dry_run"},
    ).json()
    assert job["status"] == "演练"
