# -*- coding: utf-8 -*-
"""生成 14-effluent 污水排放批母仓全部业务源码。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def w(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n") if text.startswith("\n") else text, encoding="utf-8")
    if not text.endswith("\n"):
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")


def main() -> None:
    write_root()
    write_backend()
    write_fixtures()
    write_frontend()
    write_tests()
    print("built", ROOT)


def write_root() -> None:
    w(
        "README.md",
        """# 污水排放批（effluent）

数据工程母仓：处理厂采样入库 → 超标旁路挂起 → 准排放裁定 → 封批升代 → 排放许可对账。

## 骨架一句话

采样批次入库后裁定超标才准排放封批，驳回进旁路挂起，指标血缘与排放许可对账。

## 一键起环境

```bash
docker compose up -d --build
```

浏览器访问 http://localhost:11600

- 管理账号：`admin` / `admin123`
- 读写账号：`writer` / `writer123`
- 只读账号：`viewer` / `viewer123`

## 本地开发

```powershell
cd projects/14-effluent
$env:PYTHONPATH="backend"
python -m uvicorn app:app --app-dir backend --reload --port 8000
```

## 自测

```powershell
$env:PYTHONPATH="backend"
python -m pytest
python scripts/count_loc.py
```
""",
    )
    w(
        "Dockerfile",
        """FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -r requirements.txt
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY fixtures/ ./fixtures/
COPY tests/ ./tests/
COPY pytest.ini .
RUN mkdir -p /app/data
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
""",
    )
    w(
        "docker-compose.yml",
        """name: effluent
services:
  app:
    build: .
    ports:
      - "11600:8000"
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]
      interval: 5s
      timeout: 5s
      retries: 12
""",
    )
    w(
        "requirements.txt",
        """fastapi==0.115.6
uvicorn[standard]==0.32.1
pydantic==2.10.3
pytest>=8
httpx>=0.27
""",
    )
    w(
        "pytest.ini",
        """[pytest]
testpaths = tests
pythonpath = backend
""",
    )
    w("data/.gitkeep", "")
    w(
        ".gitignore",
        """__pycache__/
.pytest_cache/
*.pyc
data/app.db
.venv/
""",
    )
    w(
        "scripts/count_loc.py",
        '''"""统计业务源码行数（不含 vendor / tests / Docker / README）。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "tests",
    "scripts",
    ".git",
    "data",
}
SKIP_NAMES = {"vue.global.prod.js", "README.md", "Dockerfile"}
SKIP_SUFFIX = {".md"}


def iter_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        parts = set(p.relative_to(ROOT).parts)
        if parts & SKIP_PARTS:
            continue
        if p.name in SKIP_NAMES or p.name.startswith("_build"):
            continue
        if p.suffix in SKIP_SUFFIX:
            continue
        if p.suffix in {".py", ".js", ".html", ".css", ".json"}:
            if p.suffix == ".json" and "fixtures" not in p.parts:
                continue
            yield p


def main() -> None:
    total = 0
    by_ext: dict[str, int] = {}
    for p in sorted(iter_files()):
        n = len(p.read_text(encoding="utf-8").splitlines())
        total += n
        by_ext[p.suffix] = by_ext.get(p.suffix, 0) + n
    print("业务 LOC 合计:", total)
    for ext, n in sorted(by_ext.items()):
        print(f"  {ext}: {n}")
    print("达标:" if total >= 3000 else "未达标（须 >= 3000）", total >= 3000)


if __name__ == "__main__":
    main()
''',
    )


def write_backend() -> None:
    w("backend/__init__.py", '"""污水排放批后端包。"""\n')
    w(
        "backend/db.py",
        '''"""SQLite：污水排放批母仓公共库层。"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB_PATH = DATA / "app.db"
FIXTURES = ROOT / "fixtures"
FRONTEND = ROOT / "frontend"

PRODUCT_META = {
    "product": "污水排放批",
    "skeleton": "采样批次入库后裁定超标才准排放封批，驳回进旁路挂起，指标血缘与排放许可对账",
    "modules": [
        "plants",
        "outfalls",
        "samples",
        "exceed",
        "release",
        "seal",
        "permits",
        "metric_lineage",
        "reconcile",
        "locks",
        "audit",
    ],
    "stubs": ["lab_courier_stub", "sludge_plan_stub"],
}


def connect() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def sha_password(password: str) -> str:
    import hashlib

    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def now_iso() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  username TEXT PRIMARY KEY,
  password_sha TEXT NOT NULL,
  role TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plants(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant_code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  basin TEXT NOT NULL,
  design_cap_m3d REAL NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outfalls(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  outfall_code TEXT UNIQUE NOT NULL,
  plant_id INTEGER NOT NULL,
  river_reach TEXT NOT NULL,
  cod_limit REAL NOT NULL,
  nh3n_limit REAL NOT NULL,
  tp_limit REAL NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(plant_id) REFERENCES plants(id)
);
CREATE TABLE IF NOT EXISTS discharge_permits(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  permit_code TEXT UNIQUE NOT NULL,
  plant_id INTEGER NOT NULL,
  quota_m3d REAL NOT NULL,
  cod_cap REAL NOT NULL,
  nh3n_cap REAL NOT NULL,
  tp_cap REAL NOT NULL,
  period_label TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(plant_id) REFERENCES plants(id)
);
CREATE TABLE IF NOT EXISTS sample_batches(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sample_code TEXT UNIQUE NOT NULL,
  outfall_id INTEGER NOT NULL,
  permit_ref TEXT NOT NULL,
  metrics TEXT NOT NULL,
  flow_m3h REAL NOT NULL,
  generation INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL,
  adjudicated_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(outfall_id) REFERENCES outfalls(id)
);
CREATE TABLE IF NOT EXISTS exceed_holds(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sample_id INTEGER NOT NULL,
  hold_key TEXT NOT NULL,
  exceed_metric TEXT NOT NULL,
  measured REAL NOT NULL,
  limit_value REAL NOT NULL,
  status TEXT NOT NULL,
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  note TEXT,
  FOREIGN KEY(sample_id) REFERENCES sample_batches(id)
);
CREATE TABLE IF NOT EXISTS discharge_releases(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sample_id INTEGER NOT NULL,
  outfall_id INTEGER NOT NULL,
  release_ref TEXT NOT NULL,
  status TEXT NOT NULL,
  officer TEXT NOT NULL,
  released_at TEXT NOT NULL,
  FOREIGN KEY(sample_id) REFERENCES sample_batches(id),
  FOREIGN KEY(outfall_id) REFERENCES outfalls(id)
);
CREATE TABLE IF NOT EXISTS discharge_seals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sample_id INTEGER NOT NULL,
  sample_generation INTEGER NOT NULL,
  snapshot TEXT NOT NULL,
  seal_ref TEXT NOT NULL,
  status TEXT NOT NULL,
  sealed_at TEXT NOT NULL,
  FOREIGN KEY(sample_id) REFERENCES sample_batches(id)
);
CREATE TABLE IF NOT EXISTS metric_lineage(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_sample_id INTEGER NOT NULL,
  to_sample_id INTEGER,
  edge_type TEXT NOT NULL,
  detail TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(from_sample_id) REFERENCES sample_batches(id)
);
CREATE TABLE IF NOT EXISTS effluent_locks(
  lock_key TEXT PRIMARY KEY,
  holder TEXT NOT NULL,
  acquired_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contention_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lock_key TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_trail(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT,
  payload TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_courier_jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sample_code TEXT NOT NULL,
  courier_slot TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sludge_plan_jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant_id INTEGER,
  digester_bay TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);
"""


def write_audit(
    conn: sqlite3.Connection, actor: str, action: str, target: str, payload: dict
) -> None:
    conn.execute(
        """INSERT INTO audit_trail(actor,action,target,payload,created_at)
           VALUES (?,?,?,?,?)""",
        (actor, action, target, json.dumps(payload, ensure_ascii=False), now_iso()),
    )


def _load_json(name: str):
    path = FIXTURES / name
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def seed_users(conn: sqlite3.Connection) -> None:
    seeds = (
        ("admin", sha_password("admin123"), "admin"),
        ("writer", sha_password("writer123"), "clerk"),
        ("viewer", sha_password("viewer123"), "viewer"),
    )
    for u, pw, role in seeds:
        conn.execute(
            "INSERT OR IGNORE INTO users(username,password_sha,role) VALUES (?,?,?)",
            (u, pw, role),
        )


def _plant_id(conn, code: str) -> int | None:
    row = conn.execute("SELECT id FROM plants WHERE plant_code=?", (code,)).fetchone()
    return int(row["id"]) if row else None


def seed_plants(conn: sqlite3.Connection) -> None:
    for row in _load_json("plants.json"):
        if conn.execute(
            "SELECT id FROM plants WHERE plant_code=?", (row["plant_code"],)
        ).fetchone():
            continue
        conn.execute(
            """INSERT INTO plants(plant_code,name,basin,design_cap_m3d,status,created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                row["plant_code"],
                row["name"],
                row["basin"],
                float(row["design_cap_m3d"]),
                row.get("status", "运行"),
                row.get("created_at", now_iso()),
            ),
        )


def seed_outfalls(conn: sqlite3.Connection) -> None:
    for row in _load_json("outfalls.json"):
        if conn.execute(
            "SELECT id FROM outfalls WHERE outfall_code=?", (row["outfall_code"],)
        ).fetchone():
            continue
        plant = _plant_id(conn, row["plant_code"])
        if not plant:
            continue
        conn.execute(
            """INSERT INTO outfalls(outfall_code,plant_id,river_reach,cod_limit,nh3n_limit,
               tp_limit,status,created_at) VALUES (?,?,?,?,?,?,?,?)""",
            (
                row["outfall_code"],
                plant,
                row["river_reach"],
                float(row["cod_limit"]),
                float(row["nh3n_limit"]),
                float(row["tp_limit"]),
                row.get("status", "开放"),
                row.get("created_at", now_iso()),
            ),
        )


def seed_permits(conn: sqlite3.Connection) -> None:
    for row in _load_json("permits.json"):
        if conn.execute(
            "SELECT id FROM discharge_permits WHERE permit_code=?",
            (row["permit_code"],),
        ).fetchone():
            continue
        plant = _plant_id(conn, row["plant_code"])
        if not plant:
            continue
        conn.execute(
            """INSERT INTO discharge_permits(permit_code,plant_id,quota_m3d,cod_cap,nh3n_cap,
               tp_cap,period_label,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                row["permit_code"],
                plant,
                float(row["quota_m3d"]),
                float(row["cod_cap"]),
                float(row["nh3n_cap"]),
                float(row["tp_cap"]),
                row["period_label"],
                row.get("status", "有效"),
                row.get("created_at", now_iso()),
            ),
        )


def _outfall_id(conn, code: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM outfalls WHERE outfall_code=?", (code,)
    ).fetchone()
    return int(row["id"]) if row else None


def seed_samples(conn: sqlite3.Connection) -> None:
    for row in _load_json("samples.json"):
        if conn.execute(
            "SELECT id FROM sample_batches WHERE sample_code=?", (row["sample_code"],)
        ).fetchone():
            continue
        outfall = _outfall_id(conn, row["outfall_code"])
        if not outfall:
            continue
        conn.execute(
            """INSERT INTO sample_batches(sample_code,outfall_id,permit_ref,metrics,flow_m3h,
               generation,status,adjudicated_at,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                row["sample_code"],
                outfall,
                row["permit_ref"],
                json.dumps(row.get("metrics", {}), ensure_ascii=False),
                float(row["flow_m3h"]),
                int(row.get("generation", 1)),
                row.get("status", "已裁定"),
                row.get("adjudicated_at"),
                row.get("created_at", now_iso()),
            ),
        )


def seed_exceeds(conn: sqlite3.Connection) -> None:
    for row in _load_json("exceeds.json"):
        sample = conn.execute(
            "SELECT id FROM sample_batches WHERE sample_code=?", (row["sample_code"],)
        ).fetchone()
        if not sample:
            continue
        if conn.execute(
            "SELECT id FROM exceed_holds WHERE hold_key=?", (row["hold_key"],)
        ).fetchone():
            continue
        conn.execute(
            """INSERT INTO exceed_holds(sample_id,hold_key,exceed_metric,measured,limit_value,
               status,opened_at,closed_at,note) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                sample["id"],
                row["hold_key"],
                row["exceed_metric"],
                float(row["measured"]),
                float(row["limit_value"]),
                row.get("status", "开放"),
                row["opened_at"],
                row.get("closed_at"),
                row.get("note", ""),
            ),
        )


def seed_releases(conn: sqlite3.Connection) -> None:
    for row in _load_json("releases.json"):
        sample = conn.execute(
            "SELECT id, outfall_id FROM sample_batches WHERE sample_code=?",
            (row["sample_code"],),
        ).fetchone()
        if not sample:
            continue
        if conn.execute(
            "SELECT id FROM discharge_releases WHERE release_ref=?",
            (row["release_ref"],),
        ).fetchone():
            continue
        conn.execute(
            """INSERT INTO discharge_releases(sample_id,outfall_id,release_ref,status,officer,released_at)
               VALUES (?,?,?,?,?,?)""",
            (
                sample["id"],
                sample["outfall_id"],
                row["release_ref"],
                row.get("status", "已准排"),
                row.get("officer", "值班员"),
                row["released_at"],
            ),
        )


def seed_seals(conn: sqlite3.Connection) -> None:
    for row in _load_json("seals.json"):
        sample = conn.execute(
            "SELECT id, generation FROM sample_batches WHERE sample_code=?",
            (row["sample_code"],),
        ).fetchone()
        if not sample:
            continue
        if conn.execute(
            "SELECT id FROM discharge_seals WHERE seal_ref=?", (row["seal_ref"],)
        ).fetchone():
            continue
        conn.execute(
            """INSERT INTO discharge_seals(sample_id,sample_generation,snapshot,seal_ref,status,sealed_at)
               VALUES (?,?,?,?,?,?)""",
            (
                sample["id"],
                int(row.get("sample_generation", sample["generation"])),
                row["snapshot"],
                row["seal_ref"],
                row.get("status", "已封批"),
                row["sealed_at"],
            ),
        )


def seed_lineage(conn: sqlite3.Connection) -> None:
    for row in _load_json("lineage.json"):
        fr = conn.execute(
            "SELECT id FROM sample_batches WHERE sample_code=?", (row["from_sample"],)
        ).fetchone()
        if not fr:
            continue
        to_id = None
        if row.get("to_sample"):
            to_row = conn.execute(
                "SELECT id FROM sample_batches WHERE sample_code=?", (row["to_sample"],)
            ).fetchone()
            to_id = to_row["id"] if to_row else None
        if conn.execute(
            """SELECT id FROM metric_lineage WHERE from_sample_id=? AND edge_type=? AND detail=?""",
            (fr["id"], row["edge_type"], row["detail"]),
        ).fetchone():
            continue
        conn.execute(
            """INSERT INTO metric_lineage(from_sample_id,to_sample_id,edge_type,detail,created_at)
               VALUES (?,?,?,?,?)""",
            (
                fr["id"],
                to_id,
                row["edge_type"],
                row["detail"],
                row.get("created_at", now_iso()),
            ),
        )


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        seed_users(conn)
        seed_plants(conn)
        seed_outfalls(conn)
        seed_permits(conn)
        seed_samples(conn)
        seed_exceeds(conn)
        seed_releases(conn)
        seed_seals(conn)
        seed_lineage(conn)
        conn.commit()


def dashboard_stats(conn: sqlite3.Connection) -> dict:
    plants = conn.execute("SELECT COUNT(*) c FROM plants").fetchone()["c"]
    outfalls = conn.execute("SELECT COUNT(*) c FROM outfalls").fetchone()["c"]
    samples = conn.execute("SELECT COUNT(*) c FROM sample_batches").fetchone()["c"]
    open_holds = conn.execute(
        "SELECT COUNT(*) c FROM exceed_holds WHERE status='开放'"
    ).fetchone()["c"]
    released = conn.execute(
        "SELECT COUNT(*) c FROM discharge_releases WHERE status='已准排'"
    ).fetchone()["c"]
    sealed = conn.execute(
        "SELECT COUNT(*) c FROM discharge_seals WHERE status='已封批'"
    ).fetchone()["c"]
    permits = conn.execute("SELECT COUNT(*) c FROM discharge_permits").fetchone()["c"]
    pending = conn.execute(
        "SELECT COUNT(*) c FROM sample_batches WHERE status='旁路挂起'"
    ).fetchone()["c"]
    stubs = {
        "lab_courier_jobs": conn.execute(
            "SELECT COUNT(*) c FROM lab_courier_jobs"
        ).fetchone()["c"],
        "sludge_plan_jobs": conn.execute(
            "SELECT COUNT(*) c FROM sludge_plan_jobs"
        ).fetchone()["c"],
    }
    return {
        "plants": plants,
        "outfalls": outfalls,
        "samples": samples,
        "open_exceeds": open_holds,
        "discharge_releases": released,
        "discharge_seals": sealed,
        "permits": permits,
        "side_pending": pending,
        "stubs": stubs,
        "meta": PRODUCT_META,
    }
''',
    )

    w(
        "backend/models.py",
        '''"""Pydantic 入参模型。"""
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
''',
    )

    w(
        "backend/validators.py",
        '''"""排放指标与状态校验。"""
from __future__ import annotations

from fastapi import HTTPException


def validate_outfall_open(status: str) -> None:
    if status != "开放":
        raise HTTPException(400, f"排放口状态不可采样：{status}")


def validate_plant_running(status: str) -> None:
    if status != "运行":
        raise HTTPException(400, f"处理厂未运行：{status}")


def adjudicate_exceed(metrics: dict, limits: dict) -> tuple[bool, str | None, float, float]:
    """对照排放口限值，返回是否超标及首个超标指标。"""
    order = ("cod", "nh3n", "tp")
    labels = {"cod": "COD", "nh3n": "氨氮", "tp": "总磷"}
    for key in order:
        measured = float(metrics.get(key, 0))
        limit = float(limits.get(key, 0))
        if measured > limit:
            return True, labels[key], measured, limit
    return False, None, 0.0, 0.0


def validate_metrics_nonneg(metrics: dict) -> None:
    for key in ("cod", "nh3n", "tp"):
        if float(metrics.get(key, -1)) < 0:
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
    for key in ("cod", "nh3n", "tp"):
        if float(sample_metrics.get(key, 0)) - float(permit_caps.get(key, 0)) > tol:
            return False
    daily_flow = flow_m3h * 24.0
    if daily_flow - float(quota_m3d) > tol * 100:
        return False
    return True


def validate_sample_releasable(status: str) -> None:
    if status != "已裁定":
        raise HTTPException(400, f"当前状态不可准排：{status}")


def validate_sample_sealable(status: str) -> None:
    if status not in ("已裁定", "已准排"):
        raise HTTPException(400, f"当前状态不可封批：{status}")


def metric_summary(metrics: dict) -> str:
    return (
        f"COD={float(metrics.get('cod', 0)):.1f} "
        f"NH3-N={float(metrics.get('nh3n', 0)):.2f} "
        f"TP={float(metrics.get('tp', 0)):.3f}"
    )
''',
    )

    w(
        "backend/auth.py",
        '''"""登录与角色鉴权。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from db import connect, sha_password, write_audit

router = APIRouter(tags=["auth"])
SECRET = b"effluent-dev-secret-not-for-prod"
AuthHeader = Annotated[str | None, Header(alias="Authorization")]


class LoginIn(BaseModel):
    username: str
    password: str


def _sign(payload: dict) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    sig = hmac.new(SECRET, body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _parse(token: str) -> dict:
    try:
        body, sig = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(401, "令牌无效") from exc
    expect = hmac.new(SECRET, body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        raise HTTPException(401, "令牌签名错误")
    data = json.loads(base64.urlsafe_b64decode(body.encode("ascii")))
    if data.get("exp", 0) < time.time():
        raise HTTPException(401, "令牌已过期")
    return data


def require_user(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    data = _parse(authorization[7:].strip())
    return data["u"]


def require_writer(authorization: str | None) -> str:
    user = require_user(authorization)
    with connect() as conn:
        row = conn.execute(
            "SELECT role FROM users WHERE username=?", (user,)
        ).fetchone()
    if not row:
        raise HTTPException(401, "用户不存在")
    if row["role"] == "viewer":
        raise HTTPException(403, "只读账号禁止写入")
    return user


@router.post("/api/login")
def login(body: LoginIn):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=?", (body.username,)
        ).fetchone()
        if not row or row["password_sha"] != sha_password(body.password):
            raise HTTPException(401, "用户名或密码错误")
        token = _sign(
            {"u": row["username"], "r": row["role"], "exp": time.time() + 86400}
        )
        write_audit(
            conn, row["username"], "login", row["username"], {"role": row["role"]}
        )
        conn.commit()
        return {"token": token, "username": row["username"], "role": row["role"]}


@router.get("/api/me")
def me(authorization: AuthHeader = None):
    user = require_user(authorization)
    with connect() as conn:
        row = conn.execute(
            "SELECT username, role FROM users WHERE username=?", (user,)
        ).fetchone()
    if not row:
        raise HTTPException(401, "用户不存在")
    return dict(row)


@router.get("/api/dashboard")
def dashboard(authorization: AuthHeader = None):
    require_user(authorization)
    from db import dashboard_stats

    with connect() as conn:
        return dashboard_stats(conn)
''',
    )

    w(
        "backend/locks.py",
        '''"""排放批争用锁。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit

router = APIRouter(tags=["locks"])


def require_lock(conn, lock_key: str, holder: str) -> None:
    row = conn.execute(
        "SELECT holder FROM effluent_locks WHERE lock_key=?", (lock_key,)
    ).fetchone()
    if row and row["holder"] != holder:
        conn.execute(
            """INSERT INTO contention_log(lock_key,actor,action,detail,created_at)
               VALUES (?,?,?,?,?)""",
            (lock_key, holder, "争用失败", f"持有人={row['holder']}", now_iso()),
        )
        raise HTTPException(409, f"锁被占用：{lock_key} 持有人 {row['holder']}")
    if not row:
        conn.execute(
            "INSERT INTO effluent_locks(lock_key,holder,acquired_at) VALUES (?,?,?)",
            (lock_key, holder, now_iso()),
        )


def release(conn, lock_key: str, holder: str) -> None:
    conn.execute(
        "DELETE FROM effluent_locks WHERE lock_key=? AND holder=?",
        (lock_key, holder),
    )


@router.get("/api/locks")
def list_locks(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        locks = [dict(r) for r in conn.execute("SELECT * FROM effluent_locks").fetchall()]
        logs = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM contention_log ORDER BY id DESC LIMIT 50"
            ).fetchall()
        ]
        return {"locks": locks, "contention": logs}


@router.post("/api/locks/acquire")
def acquire(lock_key: str, authorization: AuthHeader = None):
    user = require_writer(authorization)
    with connect() as conn:
        require_lock(conn, lock_key, user)
        write_audit(conn, user, "lock_acquire", lock_key, {})
        conn.commit()
        return {"ok": True, "lock_key": lock_key, "holder": user}


@router.post("/api/locks/release")
def release_api(lock_key: str, authorization: AuthHeader = None):
    user = require_writer(authorization)
    with connect() as conn:
        release(conn, lock_key, user)
        write_audit(conn, user, "lock_release", lock_key, {})
        conn.commit()
        return {"ok": True}
''',
    )

    # Service modules — each substantial
    for name, body in _service_modules().items():
        w(f"backend/{name}", body)

    w(
        "backend/app.py",
        '''"""污水排放批 — FastAPI 入口。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from audit_svc import router as audit_router
from auth import router as auth_router
from db import FRONTEND, PRODUCT_META, init_db
from exceed_svc import router as exceed_router
from lab_courier_stub_svc import router as lab_router
from locks import router as locks_router
from metric_lineage_svc import router as lineage_router
from outfalls_svc import router as outfalls_router
from permits_svc import router as permits_router
from plants_svc import router as plants_router
from reconcile_svc import router as reconcile_router
from release_svc import router as release_router
from samples_svc import router as samples_router
from seal_svc import router as seal_router
from sludge_plan_stub_svc import router as sludge_router

PRODUCT = "污水排放批"
SKELETON = PRODUCT_META["skeleton"]

app = FastAPI(title=PRODUCT, description=SKELETON)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    auth_router,
    plants_router,
    outfalls_router,
    samples_router,
    exceed_router,
    release_router,
    seal_router,
    permits_router,
    lineage_router,
    reconcile_router,
    locks_router,
    audit_router,
    lab_router,
    sludge_router,
):
    app.include_router(r)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    from db import DB_PATH, connect

    with connect() as conn:
        plants = conn.execute("SELECT COUNT(*) c FROM plants").fetchone()["c"]
        outfalls = conn.execute("SELECT COUNT(*) c FROM outfalls").fetchone()["c"]
        samples = conn.execute("SELECT COUNT(*) c FROM sample_batches").fetchone()["c"]
        tables = conn.execute(
            "SELECT COUNT(*) c FROM sqlite_master WHERE type='table'"
        ).fetchone()["c"]
    return {
        "ok": True,
        "product": PRODUCT,
        "skeleton": SKELETON,
        "plants": plants,
        "outfalls": outfalls,
        "samples": samples,
        "tables": tables,
        "db": str(DB_PATH),
        "meta": PRODUCT_META,
    }


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
''',
    )


def _service_modules() -> dict[str, str]:
    return {
        "plants_svc.py": '''"""处理厂主数据。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from models import PlantIn

router = APIRouter(tags=["plants"])


@router.get("/api/plants")
def list_plants(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute("SELECT * FROM plants ORDER BY id").fetchall()
        items = []
        for r in rows:
            d = dict(r)
            out_n = conn.execute(
                "SELECT COUNT(*) c FROM outfalls WHERE plant_id=?", (r["id"],)
            ).fetchone()["c"]
            d["outfall_count"] = out_n
            items.append(d)
        return {"items": items}


@router.get("/api/plants/{plant_id}")
def get_plant(plant_id: int, authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        row = conn.execute("SELECT * FROM plants WHERE id=?", (plant_id,)).fetchone()
        if not row:
            raise HTTPException(404, "处理厂不存在")
        outfalls = conn.execute(
            "SELECT * FROM outfalls WHERE plant_id=? ORDER BY id", (plant_id,)
        ).fetchall()
        permits = conn.execute(
            "SELECT * FROM discharge_permits WHERE plant_id=? ORDER BY id", (plant_id,)
        ).fetchall()
        return {
            "plant": dict(row),
            "outfalls": [dict(o) for o in outfalls],
            "permits": [dict(p) for p in permits],
        }


@router.post("/api/plants")
def create_plant(body: PlantIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    with connect() as conn:
        if conn.execute(
            "SELECT id FROM plants WHERE plant_code=?", (body.plant_code,)
        ).fetchone():
            raise HTTPException(400, "处理厂编码已存在")
        cur = conn.execute(
            """INSERT INTO plants(plant_code,name,basin,design_cap_m3d,status,created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                body.plant_code,
                body.name,
                body.basin,
                body.design_cap_m3d,
                body.status,
                now_iso(),
            ),
        )
        pid = cur.lastrowid
        write_audit(conn, user, "plant_create", body.plant_code, body.model_dump())
        conn.commit()
        return {"id": pid, **body.model_dump()}


@router.post("/api/plants/{plant_id}/status")
def set_plant_status(plant_id: int, status: str, authorization: AuthHeader = None):
    user = require_writer(authorization)
    if status not in ("运行", "检修", "停用"):
        raise HTTPException(400, "非法状态")
    with connect() as conn:
        row = conn.execute("SELECT * FROM plants WHERE id=?", (plant_id,)).fetchone()
        if not row:
            raise HTTPException(404, "处理厂不存在")
        conn.execute("UPDATE plants SET status=? WHERE id=?", (status, plant_id))
        write_audit(
            conn, user, "plant_status", row["plant_code"], {"status": status}
        )
        conn.commit()
        return {"id": plant_id, "status": status}
''',
        "outfalls_svc.py": '''"""排放口限值与开放态。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from models import OutfallIn

router = APIRouter(tags=["outfalls"])


@router.get("/api/outfalls")
def list_outfalls(authorization: AuthHeader = None, plant_id: int | None = None):
    require_user(authorization)
    with connect() as conn:
        if plant_id:
            rows = conn.execute(
                """SELECT o.*, p.plant_code, p.name plant_name FROM outfalls o
                   JOIN plants p ON p.id=o.plant_id WHERE o.plant_id=? ORDER BY o.id""",
                (plant_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT o.*, p.plant_code, p.name plant_name FROM outfalls o
                   JOIN plants p ON p.id=o.plant_id ORDER BY o.id"""
            ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.get("/api/outfalls/{outfall_id}")
def get_outfall(outfall_id: int, authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        row = conn.execute(
            """SELECT o.*, p.plant_code, p.design_cap_m3d FROM outfalls o
               JOIN plants p ON p.id=o.plant_id WHERE o.id=?""",
            (outfall_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "排放口不存在")
        recent = conn.execute(
            """SELECT sample_code, status, flow_m3h, created_at FROM sample_batches
               WHERE outfall_id=? ORDER BY id DESC LIMIT 10""",
            (outfall_id,),
        ).fetchall()
        return {"outfall": dict(row), "recent_samples": [dict(s) for s in recent]}


@router.post("/api/outfalls")
def create_outfall(body: OutfallIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    with connect() as conn:
        plant = conn.execute(
            "SELECT * FROM plants WHERE id=?", (body.plant_id,)
        ).fetchone()
        if not plant:
            raise HTTPException(404, "处理厂不存在")
        if conn.execute(
            "SELECT id FROM outfalls WHERE outfall_code=?", (body.outfall_code,)
        ).fetchone():
            raise HTTPException(400, "排放口编码已存在")
        cur = conn.execute(
            """INSERT INTO outfalls(outfall_code,plant_id,river_reach,cod_limit,nh3n_limit,
               tp_limit,status,created_at) VALUES (?,?,?,?,?,?,?,?)""",
            (
                body.outfall_code,
                body.plant_id,
                body.river_reach,
                body.cod_limit,
                body.nh3n_limit,
                body.tp_limit,
                body.status,
                now_iso(),
            ),
        )
        oid = cur.lastrowid
        write_audit(conn, user, "outfall_create", body.outfall_code, body.model_dump())
        conn.commit()
        return {"id": oid, **body.model_dump()}


@router.post("/api/outfalls/{outfall_id}/status")
def set_outfall_status(outfall_id: int, status: str, authorization: AuthHeader = None):
    user = require_writer(authorization)
    if status not in ("开放", "停用", "检修"):
        raise HTTPException(400, "非法状态")
    with connect() as conn:
        row = conn.execute("SELECT * FROM outfalls WHERE id=?", (outfall_id,)).fetchone()
        if not row:
            raise HTTPException(404, "排放口不存在")
        conn.execute("UPDATE outfalls SET status=? WHERE id=?", (status, outfall_id))
        write_audit(
            conn, user, "outfall_status", row["outfall_code"], {"status": status}
        )
        conn.commit()
        return {"id": outfall_id, "status": status}
''',
        "samples_svc.py": '''"""采样批次入库与超标裁定。"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from locks import release, require_lock
from models import SampleIn
from validators import (
    adjudicate_exceed,
    metric_summary,
    validate_flow_cap,
    validate_metrics_nonneg,
    validate_outfall_open,
    validate_plant_running,
)

router = APIRouter(tags=["samples"])


def _next_sample_code(conn, outfall_id: int) -> str:
    outfall = conn.execute(
        "SELECT outfall_code FROM outfalls WHERE id=?", (outfall_id,)
    ).fetchone()
    prefix = outfall["outfall_code"] if outfall else f"OF-{outfall_id}"
    n = conn.execute(
        "SELECT COUNT(*) c FROM sample_batches WHERE outfall_id=?", (outfall_id,)
    ).fetchone()["c"]
    return f"SM-{prefix}-{n + 1:03d}"


@router.get("/api/samples")
def list_samples(authorization: AuthHeader = None, status: str | None = None):
    require_user(authorization)
    with connect() as conn:
        q = """SELECT s.*, o.outfall_code, p.plant_code FROM sample_batches s
               JOIN outfalls o ON o.id=s.outfall_id
               JOIN plants p ON p.id=o.plant_id"""
        if status:
            rows = conn.execute(
                q + " WHERE s.status=? ORDER BY s.id DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(q + " ORDER BY s.id DESC").fetchall()
        items = []
        for r in rows:
            d = dict(r)
            d["metrics"] = json.loads(d["metrics"] or "{}")
            items.append(d)
        return {"items": items}


@router.get("/api/samples/{sample_id}")
def get_sample(sample_id: int, authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        row = conn.execute(
            """SELECT s.*, o.outfall_code, o.cod_limit, o.nh3n_limit, o.tp_limit,
                      p.name plant_name
               FROM sample_batches s
               JOIN outfalls o ON o.id=s.outfall_id
               JOIN plants p ON p.id=o.plant_id
               WHERE s.id=?""",
            (sample_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "采样批次不存在")
        data = dict(row)
        data["metrics"] = json.loads(data["metrics"] or "{}")
        holds = conn.execute(
            "SELECT * FROM exceed_holds WHERE sample_id=? ORDER BY id DESC",
            (sample_id,),
        ).fetchall()
        seals = conn.execute(
            "SELECT * FROM discharge_seals WHERE sample_id=? ORDER BY id DESC",
            (sample_id,),
        ).fetchall()
        releases = conn.execute(
            "SELECT * FROM discharge_releases WHERE sample_id=? ORDER BY id DESC",
            (sample_id,),
        ).fetchall()
        return {
            "sample": data,
            "exceed_holds": [dict(h) for h in holds],
            "discharge_seals": [dict(s) for s in seals],
            "discharge_releases": [dict(r) for r in releases],
        }


@router.post("/api/samples")
def create_sample(body: SampleIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    lock_key = f"outfall:{body.outfall_id}"
    with connect() as conn:
        require_lock(conn, lock_key, user)
        try:
            outfall = conn.execute(
                """SELECT o.*, p.status plant_status, p.design_cap_m3d
                   FROM outfalls o JOIN plants p ON p.id=o.plant_id WHERE o.id=?""",
                (body.outfall_id,),
            ).fetchone()
            if not outfall:
                raise HTTPException(404, "排放口不存在")
            validate_outfall_open(outfall["status"])
            validate_plant_running(outfall["plant_status"])
            metrics = body.metrics.model_dump()
            validate_metrics_nonneg(metrics)
            validate_flow_cap(body.flow_m3h, float(outfall["design_cap_m3d"]))
            permit = conn.execute(
                "SELECT * FROM discharge_permits WHERE permit_code=?",
                (body.permit_ref,),
            ).fetchone()
            if not permit:
                raise HTTPException(400, "排放许可不存在")
            if permit["status"] != "有效":
                raise HTTPException(400, "排放许可未生效")
            exceeded, metric, measured, limit = adjudicate_exceed(
                metrics,
                {
                    "cod": outfall["cod_limit"],
                    "nh3n": outfall["nh3n_limit"],
                    "tp": outfall["tp_limit"],
                },
            )
            code = body.sample_code or _next_sample_code(conn, body.outfall_id)
            if conn.execute(
                "SELECT id FROM sample_batches WHERE sample_code=?", (code,)
            ).fetchone():
                raise HTTPException(400, "采样编号已存在")
            status = "旁路挂起" if exceeded else "已裁定"
            adjudicated = None if exceeded else now_iso()
            cur = conn.execute(
                """INSERT INTO sample_batches(sample_code,outfall_id,permit_ref,metrics,
                   flow_m3h,generation,status,adjudicated_at,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    code,
                    body.outfall_id,
                    body.permit_ref,
                    json.dumps(metrics, ensure_ascii=False),
                    body.flow_m3h,
                    1,
                    status,
                    adjudicated,
                    now_iso(),
                ),
            )
            sid = cur.lastrowid
            hold = None
            if exceeded:
                hold_key = f"EX-{code}-{metric}"
                conn.execute(
                    """INSERT INTO exceed_holds(sample_id,hold_key,exceed_metric,measured,
                       limit_value,status,opened_at,note)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        sid,
                        hold_key,
                        metric,
                        measured,
                        limit,
                        "开放",
                        now_iso(),
                        "入库自动挂起",
                    ),
                )
                hold = hold_key
            write_audit(
                conn,
                user,
                "sample_create",
                code,
                {
                    "status": status,
                    "metrics": metrics,
                    "summary": metric_summary(metrics),
                    "exceed": exceeded,
                },
            )
            conn.commit()
            return {
                "id": sid,
                "sample_code": code,
                "status": status,
                "exceed": exceeded,
                "hold_key": hold,
            }
        finally:
            release(conn, lock_key, user)
            conn.commit()
''',
        "exceed_svc.py": '''"""超标旁路挂起开闭。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from locks import release, require_lock
from models import ExceedCloseIn, ExceedOpenIn

router = APIRouter(tags=["exceed"])


@router.get("/api/exceeds")
def list_exceeds(authorization: AuthHeader = None, status: str | None = None):
    require_user(authorization)
    with connect() as conn:
        q = """SELECT h.*, s.sample_code, o.outfall_code FROM exceed_holds h
               JOIN sample_batches s ON s.id=h.sample_id
               JOIN outfalls o ON o.id=s.outfall_id"""
        if status:
            rows = conn.execute(
                q + " WHERE h.status=? ORDER BY h.id DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(q + " ORDER BY h.id DESC").fetchall()
        return {"items": [dict(r) for r in rows]}


@router.post("/api/exceeds/open")
def open_exceed(body: ExceedOpenIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    lock_key = f"sample:{body.sample_id}"
    with connect() as conn:
        require_lock(conn, lock_key, user)
        try:
            sample = conn.execute(
                """SELECT s.*, o.cod_limit, o.nh3n_limit, o.tp_limit
                   FROM sample_batches s JOIN outfalls o ON o.id=s.outfall_id
                   WHERE s.id=?""",
                (body.sample_id,),
            ).fetchone()
            if not sample:
                raise HTTPException(404, "采样批次不存在")
            if sample["status"] == "作废":
                raise HTTPException(400, "已作废不可挂起")
            open_row = conn.execute(
                "SELECT id FROM exceed_holds WHERE sample_id=? AND status='开放'",
                (body.sample_id,),
            ).fetchone()
            if open_row:
                raise HTTPException(400, "已有开放挂起")
            import json

            metrics = json.loads(sample["metrics"] or "{}")
            from validators import adjudicate_exceed

            exceeded, metric, measured, limit = adjudicate_exceed(
                metrics,
                {
                    "cod": sample["cod_limit"],
                    "nh3n": sample["nh3n_limit"],
                    "tp": sample["tp_limit"],
                },
            )
            if not exceeded:
                raise HTTPException(400, "当前指标未超标，无需挂起")
            hold_key = f"EX-{sample['sample_code']}-{metric}-M"
            conn.execute(
                """INSERT INTO exceed_holds(sample_id,hold_key,exceed_metric,measured,
                   limit_value,status,opened_at,note) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    body.sample_id,
                    hold_key,
                    metric,
                    measured,
                    limit,
                    "开放",
                    now_iso(),
                    body.note,
                ),
            )
            conn.execute(
                "UPDATE sample_batches SET status=? WHERE id=?",
                ("旁路挂起", body.sample_id),
            )
            write_audit(
                conn,
                user,
                "exceed_open",
                sample["sample_code"],
                {"hold_key": hold_key, "metric": metric},
            )
            conn.commit()
            return {"hold_key": hold_key, "metric": metric}
        finally:
            release(conn, lock_key, user)
            conn.commit()


@router.post("/api/exceeds/close")
def close_exceed(body: ExceedCloseIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    with connect() as conn:
        hold = conn.execute(
            "SELECT * FROM exceed_holds WHERE id=?", (body.hold_id,)
        ).fetchone()
        if not hold:
            raise HTTPException(404, "挂起不存在")
        if hold["status"] != "开放":
            raise HTTPException(400, "挂起已关闭")
        lock_key = f"sample:{hold['sample_id']}"
        require_lock(conn, lock_key, user)
        try:
            conn.execute(
                """UPDATE exceed_holds SET status='已关闭', closed_at=?, note=?
                   WHERE id=?""",
                (now_iso(), body.note or hold["note"], body.hold_id),
            )
            conn.execute(
                """UPDATE sample_batches SET status='已裁定', adjudicated_at=?
                   WHERE id=?""",
                (now_iso(), hold["sample_id"]),
            )
            sample = conn.execute(
                "SELECT sample_code FROM sample_batches WHERE id=?",
                (hold["sample_id"],),
            ).fetchone()
            write_audit(
                conn,
                user,
                "exceed_close",
                sample["sample_code"] if sample else str(hold["sample_id"]),
                {"hold_id": body.hold_id, "note": body.note},
            )
            conn.commit()
            return {"ok": True, "ticket_adjudicated": True, "sample_adjudicated": True}
        finally:
            release(conn, lock_key, user)
            conn.commit()
''',
        "release_svc.py": '''"""准排放裁定放行。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from locks import release, require_lock
from models import ReleaseIn
from validators import validate_sample_releasable

router = APIRouter(tags=["release"])


@router.get("/api/releases")
def list_releases(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT r.*, s.sample_code, o.outfall_code FROM discharge_releases r
               JOIN sample_batches s ON s.id=r.sample_id
               JOIN outfalls o ON o.id=r.outfall_id
               ORDER BY r.id DESC"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.post("/api/releases")
def create_release(body: ReleaseIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    lock_key = f"sample:{body.sample_id}"
    with connect() as conn:
        require_lock(conn, lock_key, user)
        try:
            sample = conn.execute(
                "SELECT * FROM sample_batches WHERE id=?", (body.sample_id,)
            ).fetchone()
            if not sample:
                raise HTTPException(404, "采样批次不存在")
            validate_sample_releasable(sample["status"])
            open_hold = conn.execute(
                "SELECT id FROM exceed_holds WHERE sample_id=? AND status='开放'",
                (body.sample_id,),
            ).fetchone()
            if open_hold:
                raise HTTPException(400, "仍有开放超标挂起，禁止准排")
            existing = conn.execute(
                "SELECT id FROM discharge_releases WHERE sample_id=? AND status='已准排'",
                (body.sample_id,),
            ).fetchone()
            if existing:
                raise HTTPException(400, "已准排，勿重复")
            ref = f"RL-{sample['sample_code']}"
            conn.execute(
                """INSERT INTO discharge_releases(sample_id,outfall_id,release_ref,status,officer,released_at)
                   VALUES (?,?,?,?,?,?)""",
                (
                    body.sample_id,
                    sample["outfall_id"],
                    ref,
                    "已准排",
                    body.officer,
                    now_iso(),
                ),
            )
            conn.execute(
                "UPDATE sample_batches SET status=? WHERE id=?",
                ("已准排", body.sample_id),
            )
            write_audit(
                conn,
                user,
                "release",
                sample["sample_code"],
                {"release_ref": ref, "officer": body.officer},
            )
            conn.commit()
            return {"release_ref": ref, "status": "已准排"}
        finally:
            release(conn, lock_key, user)
            conn.commit()
''',
        "seal_svc.py": '''"""排放封批升代快照。"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from locks import release, require_lock
from models import SealIn
from validators import metric_summary, validate_sample_sealable

router = APIRouter(tags=["seal"])


@router.get("/api/seals")
def list_seals(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT d.*, s.sample_code FROM discharge_seals d
               JOIN sample_batches s ON s.id=d.sample_id
               ORDER BY d.id DESC"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.post("/api/seals")
def create_seal(body: SealIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    lock_key = f"sample:{body.sample_id}"
    with connect() as conn:
        require_lock(conn, lock_key, user)
        try:
            sample = conn.execute(
                "SELECT * FROM sample_batches WHERE id=?", (body.sample_id,)
            ).fetchone()
            if not sample:
                raise HTTPException(404, "采样批次不存在")
            validate_sample_sealable(sample["status"])
            open_hold = conn.execute(
                "SELECT id FROM exceed_holds WHERE sample_id=? AND status='开放'",
                (body.sample_id,),
            ).fetchone()
            if open_hold:
                raise HTTPException(400, "开放挂起未闭，禁止封批")
            metrics = json.loads(sample["metrics"] or "{}")
            gen = int(sample["generation"]) + 1
            snap = body.snapshot or metric_summary(metrics)
            seal_ref = f"SL-{sample['sample_code']}-G{gen}"
            conn.execute(
                """INSERT INTO discharge_seals(sample_id,sample_generation,snapshot,seal_ref,status,sealed_at)
                   VALUES (?,?,?,?,?,?)""",
                (body.sample_id, gen, snap, seal_ref, "已封批", now_iso()),
            )
            conn.execute(
                """UPDATE sample_batches SET generation=?, status=? WHERE id=?""",
                (gen, "已封批", body.sample_id),
            )
            write_audit(
                conn,
                user,
                "seal",
                sample["sample_code"],
                {"seal_ref": seal_ref, "generation": gen, "snapshot": snap},
            )
            conn.commit()
            return {"seal_ref": seal_ref, "generation": gen, "snapshot": snap}
        finally:
            release(conn, lock_key, user)
            conn.commit()
''',
        "permits_svc.py": '''"""排放许可册。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from models import PermitIn

router = APIRouter(tags=["permits"])


@router.get("/api/permits")
def list_permits(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT d.*, p.plant_code, p.name plant_name FROM discharge_permits d
               JOIN plants p ON p.id=d.plant_id ORDER BY d.id"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.get("/api/permits/{permit_code}")
def get_permit(permit_code: str, authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        row = conn.execute(
            """SELECT d.*, p.plant_code FROM discharge_permits d
               JOIN plants p ON p.id=d.plant_id WHERE d.permit_code=?""",
            (permit_code,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "许可不存在")
        samples = conn.execute(
            """SELECT sample_code, status, flow_m3h, metrics FROM sample_batches
               WHERE permit_ref=? ORDER BY id DESC""",
            (permit_code,),
        ).fetchall()
        import json

        items = []
        for s in samples:
            d = dict(s)
            d["metrics"] = json.loads(d["metrics"] or "{}")
            items.append(d)
        return {"permit": dict(row), "samples": items}


@router.post("/api/permits")
def create_permit(body: PermitIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    with connect() as conn:
        plant = conn.execute(
            "SELECT id FROM plants WHERE id=?", (body.plant_id,)
        ).fetchone()
        if not plant:
            raise HTTPException(404, "处理厂不存在")
        if conn.execute(
            "SELECT id FROM discharge_permits WHERE permit_code=?", (body.permit_code,)
        ).fetchone():
            raise HTTPException(400, "许可编码已存在")
        cur = conn.execute(
            """INSERT INTO discharge_permits(permit_code,plant_id,quota_m3d,cod_cap,nh3n_cap,
               tp_cap,period_label,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                body.permit_code,
                body.plant_id,
                body.quota_m3d,
                body.cod_cap,
                body.nh3n_cap,
                body.tp_cap,
                body.period_label,
                "有效",
                now_iso(),
            ),
        )
        write_audit(conn, user, "permit_create", body.permit_code, body.model_dump())
        conn.commit()
        return {"id": cur.lastrowid, **body.model_dump(), "status": "有效"}
''',
        "metric_lineage_svc.py": '''"""指标血缘边。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from models import LineageIn

router = APIRouter(tags=["lineage"])


@router.get("/api/lineage")
def list_lineage(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT e.*, f.sample_code from_code, t.sample_code to_code
               FROM metric_lineage e
               JOIN sample_batches f ON f.id=e.from_sample_id
               LEFT JOIN sample_batches t ON t.id=e.to_sample_id
               ORDER BY e.id DESC"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.post("/api/lineage")
def create_edge(body: LineageIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    with connect() as conn:
        fr = conn.execute(
            "SELECT * FROM sample_batches WHERE id=?", (body.from_sample_id,)
        ).fetchone()
        if not fr:
            raise HTTPException(404, "源采样不存在")
        if body.to_sample_id:
            to = conn.execute(
                "SELECT id FROM sample_batches WHERE id=?", (body.to_sample_id,)
            ).fetchone()
            if not to:
                raise HTTPException(404, "目标采样不存在")
        cur = conn.execute(
            """INSERT INTO metric_lineage(from_sample_id,to_sample_id,edge_type,detail,created_at)
               VALUES (?,?,?,?,?)""",
            (
                body.from_sample_id,
                body.to_sample_id,
                body.edge_type,
                body.detail,
                now_iso(),
            ),
        )
        write_audit(
            conn,
            user,
            "lineage_edge",
            fr["sample_code"],
            body.model_dump(),
        )
        conn.commit()
        return {"id": cur.lastrowid, **body.model_dump()}
''',
        "reconcile_svc.py": '''"""排放许可与采样对账证明。"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user
from validators import validate_permit_match

router = APIRouter(tags=["reconcile"])


@router.get("/api/reconcile")
def reconcile_all(authorization: AuthHeader = None):
    require_user(authorization)
    from db import connect

    with connect() as conn:
        rows = conn.execute(
            "SELECT permit_code FROM discharge_permits ORDER BY permit_code"
        ).fetchall()
        return {"items": [_reconcile_permit(conn, r["permit_code"]) for r in rows]}


@router.get("/api/reconcile/{permit_code}")
def reconcile_one(permit_code: str, authorization: AuthHeader = None):
    require_user(authorization)
    from db import connect

    with connect() as conn:
        if not conn.execute(
            "SELECT id FROM discharge_permits WHERE permit_code=?", (permit_code,)
        ).fetchone():
            raise HTTPException(404, "许可不存在")
        return _reconcile_permit(conn, permit_code)


def _reconcile_permit(conn, permit_code: str) -> dict:
    permit = conn.execute(
        "SELECT * FROM discharge_permits WHERE permit_code=?", (permit_code,)
    ).fetchone()
    samples = conn.execute(
        """SELECT sample_code, flow_m3h, metrics, status, generation FROM sample_batches
           WHERE permit_ref=? AND status NOT IN ('作废')""",
        (permit_code,),
    ).fetchall()
    if not samples:
        return {
            "permit_code": permit_code,
            "balanced": False,
            "reason": "无采样批次",
            "samples": [],
        }
    caps = {
        "cod": permit["cod_cap"],
        "nh3n": permit["nh3n_cap"],
        "tp": permit["tp_cap"],
    }
    details = []
    all_ok = True
    for s in samples:
        metrics = json.loads(s["metrics"] or "{}")
        ok = validate_permit_match(
            caps, metrics, float(s["flow_m3h"]), float(permit["quota_m3d"])
        )
        if not ok:
            all_ok = False
        details.append(
            {
                "sample_code": s["sample_code"],
                "status": s["status"],
                "generation": s["generation"],
                "metrics": metrics,
                "flow_m3h": s["flow_m3h"],
                "matched": ok,
            }
        )
    seal_rows = conn.execute(
        """SELECT d.seal_ref, d.sample_generation, s.sample_code
           FROM discharge_seals d JOIN sample_batches s ON s.id=d.sample_id
           WHERE s.permit_ref=?""",
        (permit_code,),
    ).fetchall()
    return {
        "permit_code": permit_code,
        "quota_m3d": permit["quota_m3d"],
        "caps": caps,
        "balanced": all_ok,
        "proof_ready": all_ok and len(seal_rows) >= 1,
        "seal_count": len(seal_rows),
        "samples": details,
        "seals": [dict(x) for x in seal_rows],
    }


@router.get("/api/proof/sample/{sample_code}")
def proof_sample(sample_code: str, authorization: AuthHeader = None):
    require_user(authorization)
    from db import connect

    with connect() as conn:
        sample = conn.execute(
            "SELECT * FROM sample_batches WHERE sample_code=?", (sample_code,)
        ).fetchone()
        if not sample:
            raise HTTPException(404, "采样不存在")
        holds = conn.execute(
            "SELECT * FROM exceed_holds WHERE sample_id=?", (sample["id"],)
        ).fetchall()
        releases = conn.execute(
            "SELECT * FROM discharge_releases WHERE sample_id=?", (sample["id"],)
        ).fetchall()
        seals = conn.execute(
            "SELECT * FROM discharge_seals WHERE sample_id=?", (sample["id"],)
        ).fetchall()
        open_holds = [h for h in holds if h["status"] == "开放"]
        closed = [h for h in holds if h["status"] == "已关闭"]
        return {
            "sample_code": sample_code,
            "status": sample["status"],
            "generation": sample["generation"],
            "released": any(r["status"] == "已准排" for r in releases),
            "sealed": any(s["status"] == "已封批" for s in seals),
            "exceed_closed": len(open_holds) == 0 and (len(closed) > 0 or sample["status"] != "旁路挂起"),
            "holds": [dict(h) for h in holds],
            "releases": [dict(r) for r in releases],
            "seals": [dict(s) for s in seals],
        }
''',
        "audit_svc.py": '''"""审计轨迹只读。"""
from __future__ import annotations

from fastapi import APIRouter

from auth import AuthHeader, require_user
from db import connect

router = APIRouter(tags=["audit"])


@router.get("/api/audit")
def list_audit(authorization: AuthHeader = None, limit: int = 100):
    require_user(authorization)
    limit = max(1, min(limit, 500))
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_trail ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return {"items": [dict(r) for r in rows]}
''',
        "lab_courier_stub_svc.py": '''"""空桩：外送化验快递槽（题面可点到接口，默认 dry_run）。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from models import LabCourierIn

router = APIRouter(tags=["lab_courier_stub"])


@router.get("/api/stubs/lab-courier")
def list_jobs(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM lab_courier_jobs ORDER BY id DESC"
        ).fetchall()
        return {"items": [dict(r) for r in rows], "stub": True, "ready": False}


@router.post("/api/stubs/lab-courier")
def enqueue(body: LabCourierIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    if body.mode not in ("dry_run", "enqueue"):
        raise HTTPException(400, "仅支持 dry_run / enqueue")
    with connect() as conn:
        status = "演练" if body.mode == "dry_run" else "排队"
        cur = conn.execute(
            """INSERT INTO lab_courier_jobs(sample_code,courier_slot,mode,status,detail,created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                body.sample_code,
                body.courier_slot,
                body.mode,
                status,
                body.detail or "空桩未接通外送",
                now_iso(),
            ),
        )
        write_audit(
            conn,
            user,
            "lab_courier_stub",
            body.sample_code,
            body.model_dump(),
        )
        conn.commit()
        return {"id": cur.lastrowid, "status": status, "stub": True}
''',
        "sludge_plan_stub_svc.py": '''"""空桩：污泥消化仓排程（题面可点到接口，默认 dry_run）。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from models import SludgePlanIn

router = APIRouter(tags=["sludge_plan_stub"])


@router.get("/api/stubs/sludge-plan")
def list_jobs(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sludge_plan_jobs ORDER BY id DESC"
        ).fetchall()
        return {"items": [dict(r) for r in rows], "stub": True, "ready": False}


@router.post("/api/stubs/sludge-plan")
def enqueue(body: SludgePlanIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    if body.mode not in ("dry_run", "enqueue"):
        raise HTTPException(400, "仅支持 dry_run / enqueue")
    with connect() as conn:
        status = "演练" if body.mode == "dry_run" else "排队"
        cur = conn.execute(
            """INSERT INTO sludge_plan_jobs(plant_id,digester_bay,mode,status,detail,created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                body.plant_id,
                body.digester_bay,
                body.mode,
                status,
                body.detail or "空桩未接通污泥排程",
                now_iso(),
            ),
        )
        write_audit(
            conn,
            user,
            "sludge_plan_stub",
            body.digester_bay,
            body.model_dump(),
        )
        conn.commit()
        return {"id": cur.lastrowid, "status": status, "stub": True}
''',
    }


def write_fixtures() -> None:
    plants = [
        {
            "plant_code": "PL-EAST-01",
            "name": "东城水质净化中心",
            "basin": "东城河流域",
            "design_cap_m3d": 80000,
            "status": "运行",
            "created_at": "2026-11-01T08:00:00",
        },
        {
            "plant_code": "PL-WEST-02",
            "name": "西湾再生水厂",
            "basin": "西湾水系",
            "design_cap_m3d": 45000,
            "status": "运行",
            "created_at": "2026-11-01T08:05:00",
        },
        {
            "plant_code": "PL-NORTH-03",
            "name": "北岸深度处理站",
            "basin": "北岸干渠",
            "design_cap_m3d": 60000,
            "status": "运行",
            "created_at": "2026-11-01T08:10:00",
        },
        {
            "plant_code": "PL-SOUTH-04",
            "name": "南港膜处理厂",
            "basin": "南港感潮段",
            "design_cap_m3d": 35000,
            "status": "检修",
            "created_at": "2026-11-01T08:15:00",
        },
    ]
    outfalls = [
        {
            "outfall_code": "OF-E1-A",
            "plant_code": "PL-EAST-01",
            "river_reach": "东城河下游",
            "cod_limit": 50,
            "nh3n_limit": 5,
            "tp_limit": 0.5,
            "status": "开放",
            "created_at": "2026-11-01T09:00:00",
        },
        {
            "outfall_code": "OF-E1-B",
            "plant_code": "PL-EAST-01",
            "river_reach": "东城河旁路渠",
            "cod_limit": 40,
            "nh3n_limit": 4,
            "tp_limit": 0.4,
            "status": "开放",
            "created_at": "2026-11-01T09:05:00",
        },
        {
            "outfall_code": "OF-W2-A",
            "plant_code": "PL-WEST-02",
            "river_reach": "西湾主渠",
            "cod_limit": 50,
            "nh3n_limit": 5,
            "tp_limit": 0.5,
            "status": "开放",
            "created_at": "2026-11-01T09:10:00",
        },
        {
            "outfall_code": "OF-N3-A",
            "plant_code": "PL-NORTH-03",
            "river_reach": "北岸入江口",
            "cod_limit": 30,
            "nh3n_limit": 3,
            "tp_limit": 0.3,
            "status": "开放",
            "created_at": "2026-11-01T09:15:00",
        },
        {
            "outfall_code": "OF-S4-A",
            "plant_code": "PL-SOUTH-04",
            "river_reach": "南港感潮口",
            "cod_limit": 50,
            "nh3n_limit": 5,
            "tp_limit": 0.5,
            "status": "停用",
            "created_at": "2026-11-01T09:20:00",
        },
    ]
    permits = [
        {
            "permit_code": "DP-2026-E01",
            "plant_code": "PL-EAST-01",
            "quota_m3d": 75000,
            "cod_cap": 50,
            "nh3n_cap": 5,
            "tp_cap": 0.5,
            "period_label": "2026Q4",
            "status": "有效",
            "created_at": "2026-11-01T10:00:00",
        },
        {
            "permit_code": "DP-2026-W02",
            "plant_code": "PL-WEST-02",
            "quota_m3d": 40000,
            "cod_cap": 50,
            "nh3n_cap": 5,
            "tp_cap": 0.5,
            "period_label": "2026Q4",
            "status": "有效",
            "created_at": "2026-11-01T10:05:00",
        },
        {
            "permit_code": "DP-2026-N03",
            "plant_code": "PL-NORTH-03",
            "quota_m3d": 55000,
            "cod_cap": 30,
            "nh3n_cap": 3,
            "tp_cap": 0.3,
            "period_label": "2026Q4",
            "status": "有效",
            "created_at": "2026-11-01T10:10:00",
        },
    ]
    samples = [
        {
            "sample_code": "SM-OF-E1-A-001",
            "outfall_code": "OF-E1-A",
            "permit_ref": "DP-2026-E01",
            "metrics": {"cod": 42.0, "nh3n": 3.2, "tp": 0.28},
            "flow_m3h": 2800,
            "generation": 2,
            "status": "已封批",
            "adjudicated_at": "2026-11-10T11:00:00",
            "created_at": "2026-11-10T10:30:00",
        },
        {
            "sample_code": "SM-OF-E1-A-002",
            "outfall_code": "OF-E1-A",
            "permit_ref": "DP-2026-E01",
            "metrics": {"cod": 58.0, "nh3n": 4.1, "tp": 0.33},
            "flow_m3h": 2900,
            "generation": 1,
            "status": "旁路挂起",
            "adjudicated_at": None,
            "created_at": "2026-11-18T09:00:00",
        },
        {
            "sample_code": "SM-OF-W2-A-001",
            "outfall_code": "OF-W2-A",
            "permit_ref": "DP-2026-W02",
            "metrics": {"cod": 36.0, "nh3n": 2.8, "tp": 0.22},
            "flow_m3h": 1500,
            "generation": 1,
            "status": "已准排",
            "adjudicated_at": "2026-11-15T14:00:00",
            "created_at": "2026-11-15T13:20:00",
        },
        {
            "sample_code": "SM-OF-N3-A-001",
            "outfall_code": "OF-N3-A",
            "permit_ref": "DP-2026-N03",
            "metrics": {"cod": 24.0, "nh3n": 2.1, "tp": 0.18},
            "flow_m3h": 2000,
            "generation": 1,
            "status": "已裁定",
            "adjudicated_at": "2026-11-20T08:40:00",
            "created_at": "2026-11-20T08:10:00",
        },
        {
            "sample_code": "SM-OF-E1-B-001",
            "outfall_code": "OF-E1-B",
            "permit_ref": "DP-2026-E01",
            "metrics": {"cod": 31.0, "nh3n": 2.4, "tp": 0.19},
            "flow_m3h": 1200,
            "generation": 1,
            "status": "已裁定",
            "adjudicated_at": "2026-11-19T16:00:00",
            "created_at": "2026-11-19T15:30:00",
        },
    ]
    exceeds = [
        {
            "sample_code": "SM-OF-E1-A-002",
            "hold_key": "EX-SM-OF-E1-A-002-COD",
            "exceed_metric": "COD",
            "measured": 58.0,
            "limit_value": 50.0,
            "status": "开放",
            "opened_at": "2026-11-18T09:00:00",
            "note": "入库自动挂起",
        }
    ]
    releases = [
        {
            "sample_code": "SM-OF-W2-A-001",
            "release_ref": "RL-SM-OF-W2-A-001",
            "status": "已准排",
            "officer": "西湾值班",
            "released_at": "2026-11-15T14:20:00",
        }
    ]
    seals = [
        {
            "sample_code": "SM-OF-E1-A-001",
            "sample_generation": 2,
            "snapshot": "COD=42.0 NH3-N=3.20 TP=0.280",
            "seal_ref": "SL-SM-OF-E1-A-001-G2",
            "status": "已封批",
            "sealed_at": "2026-11-10T12:00:00",
        }
    ]
    lineage = [
        {
            "from_sample": "SM-OF-E1-A-001",
            "to_sample": "SM-OF-E1-A-002",
            "edge_type": "复测续批",
            "detail": "东城主口二次采样",
            "created_at": "2026-11-18T09:05:00",
        },
        {
            "from_sample": "SM-OF-W2-A-001",
            "to_sample": None,
            "edge_type": "准排锚点",
            "detail": "西湾主渠准排留痕",
            "created_at": "2026-11-15T14:25:00",
        },
    ]
    for name, data in (
        ("plants.json", plants),
        ("outfalls.json", outfalls),
        ("permits.json", permits),
        ("samples.json", samples),
        ("exceeds.json", exceeds),
        ("releases.json", releases),
        ("seals.json", seals),
        ("lineage.json", lineage),
    ):
        w(f"fixtures/{name}", json.dumps(data, ensure_ascii=False, indent=2))


def write_frontend() -> None:
    # Copy vue from pierload if present
    vue_src = ROOT.parents[0] / "13-pierload" / "frontend" / "vue.global.prod.js"
    vue_dst = ROOT / "frontend" / "vue.global.prod.js"
    if vue_src.exists() and not vue_dst.exists():
        vue_dst.write_bytes(vue_src.read_bytes())

    w(
        "frontend/index.html",
        """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>污水排放批</title>
<link rel="stylesheet" href="/static/css/app.css"/>
<script src="/static/vue.global.prod.js"></script>
</head>
<body>
<div id="app"></div>
<noscript><p class="noscript">需要启用 JavaScript</p></noscript>
<script type="module" src="/static/js/app.js"></script>
</body>
</html>
""",
    )
    w("frontend/css/app.css", FRONTEND_CSS)
    w("frontend/js/api.js", FRONTEND_API)
    for name, body in FRONTEND_VIEWS.items():
        w(f"frontend/js/views/{name}", body)
    w("frontend/js/app.js", FRONTEND_APP)


FRONTEND_CSS = """
:root {
  --ink: #1a2b34;
  --muted: #5c7380;
  --paper: #f3f6f4;
  --panel: #ffffff;
  --line: #c9d6cf;
  --accent: #c47a2c;
  --teal: #2f6f6a;
  --danger: #a33b2d;
  --ok: #2d6a45;
  --warn: #9a6b1f;
  --hero: linear-gradient(135deg, #e8f0ec 0%, #d5e4df 45%, #cfe0e6 100%);
  --font-display: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif;
  --font-body: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: var(--font-body);
  color: var(--ink);
  background: var(--paper);
  min-height: 100vh;
}
.noscript { padding: 2rem; }
.login-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: var(--hero);
  padding: 2rem;
}
.login-card {
  width: min(420px, 100%);
  background: var(--panel);
  border: 1px solid var(--line);
  padding: 2rem 2.1rem 1.6rem;
}
.brand-mark {
  font-family: var(--font-display);
  font-size: 1.85rem;
  letter-spacing: 0.04em;
  color: var(--teal);
  margin: 0 0 0.35rem;
}
.brand-sub { color: var(--muted); margin: 0 0 1.4rem; font-size: 0.92rem; }
label { display: block; font-size: 0.82rem; color: var(--muted); margin: 0.7rem 0 0.25rem; }
input, select, textarea, button {
  font: inherit;
  width: 100%;
  padding: 0.55rem 0.65rem;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
}
button {
  cursor: pointer;
  background: var(--teal);
  color: #fff;
  border-color: var(--teal);
  margin-top: 1rem;
}
button.secondary { background: #fff; color: var(--teal); }
button.warn { background: var(--accent); border-color: var(--accent); }
.err { color: var(--danger); font-size: 0.88rem; margin-top: 0.6rem; }
.ok { color: var(--ok); font-size: 0.88rem; margin-top: 0.6rem; }
.app-shell { display: grid; grid-template-rows: auto auto 1fr; min-height: 100vh; }
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.85rem 1.4rem;
  background: #1f3d3a;
  color: #e8f2ef;
}
.topbar h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 600;
}
.topbar .meta { font-size: 0.85rem; opacity: 0.85; }
.topbar button { width: auto; margin: 0; padding: 0.35rem 0.8rem; background: transparent; border-color: #7aa39a; }
.ribbon {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
  padding: 0.65rem 1.2rem;
  background: #e7eeea;
  border-bottom: 1px solid var(--line);
}
.ribbon button {
  width: auto;
  margin: 0;
  background: transparent;
  color: var(--ink);
  border-color: transparent;
  padding: 0.4rem 0.75rem;
}
.ribbon button.active {
  background: #fff;
  border-color: var(--line);
  color: var(--teal);
  box-shadow: 0 1px 0 rgba(0,0,0,0.04);
}
.main { padding: 1.1rem 1.4rem 2rem; }
.hero-strip {
  background: var(--hero);
  border: 1px solid var(--line);
  padding: 1.1rem 1.25rem;
  margin-bottom: 1rem;
}
.hero-strip h2 {
  margin: 0 0 0.35rem;
  font-family: var(--font-display);
  font-size: 1.35rem;
  color: var(--teal);
}
.hero-strip p { margin: 0; color: var(--muted); }
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.6rem;
  margin: 1rem 0;
}
.stat {
  background: var(--panel);
  border: 1px solid var(--line);
  padding: 0.75rem 0.85rem;
}
.stat .n { font-size: 1.4rem; font-weight: 600; color: var(--teal); }
.stat .l { font-size: 0.78rem; color: var(--muted); margin-top: 0.15rem; }
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  padding: 0.9rem 1rem;
  margin-bottom: 0.9rem;
}
.panel h3 {
  margin: 0 0 0.7rem;
  font-size: 1rem;
  font-family: var(--font-display);
}
.grid-2 { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 0.9rem; }
@media (max-width: 960px) { .grid-2 { grid-template-columns: 1fr; } }
table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
th, td { text-align: left; padding: 0.45rem 0.4rem; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 500; }
.pass { color: var(--ok); }
.fail { color: var(--danger); }
.warn { color: var(--warn); }
.muted { color: var(--muted); }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.55rem; }
.form-row.one { grid-template-columns: 1fr; }
.actions { display: flex; gap: 0.45rem; flex-wrap: wrap; margin-top: 0.7rem; }
.actions button { width: auto; margin: 0; }
.banner { padding: 0.55rem 0.7rem; margin-bottom: 0.7rem; border: 1px solid var(--line); background: #fff8ef; color: var(--warn); }
.banner.err { background: #f8ecea; color: var(--danger); }
.banner.ok { background: #eaf4ee; color: var(--ok); }
.kv { display: grid; grid-template-columns: 110px 1fr; gap: 0.25rem 0.5rem; font-size: 0.88rem; }
.kv span:nth-child(odd) { color: var(--muted); }
"""

FRONTEND_API = '''
export function createApi(getToken, onUnauthorized) {
  async function request(path, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    const token = getToken();
    if (token) headers.Authorization = "Bearer " + token;
    const res = await fetch(path, Object.assign({}, options, { headers }));
    if (res.status === 401) {
      onUnauthorized();
      throw new Error("未登录或令牌失效");
    }
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
    if (!res.ok) {
      const detail = data && (data.detail || data.message);
      throw new Error(typeof detail === "string" ? detail : ("请求失败 " + res.status));
    }
    return data;
  }
  return {
    login: (username, password) => request("/api/login", { method: "POST", body: JSON.stringify({ username, password }) }),
    me: () => request("/api/me"),
    dashboard: () => request("/api/dashboard"),
    plants: () => request("/api/plants"),
    plant: (id) => request("/api/plants/" + id),
    createPlant: (body) => request("/api/plants", { method: "POST", body: JSON.stringify(body) }),
    outfalls: () => request("/api/outfalls"),
    outfall: (id) => request("/api/outfalls/" + id),
    createOutfall: (body) => request("/api/outfalls", { method: "POST", body: JSON.stringify(body) }),
    setOutfallStatus: (id, status) => request("/api/outfalls/" + id + "/status?status=" + encodeURIComponent(status), { method: "POST" }),
    samples: (status) => request("/api/samples" + (status ? ("?status=" + encodeURIComponent(status)) : "")),
    sample: (id) => request("/api/samples/" + id),
    createSample: (body) => request("/api/samples", { method: "POST", body: JSON.stringify(body) }),
    exceeds: (status) => request("/api/exceeds" + (status ? ("?status=" + encodeURIComponent(status)) : "")),
    closeExceed: (body) => request("/api/exceeds/close", { method: "POST", body: JSON.stringify(body) }),
    openExceed: (body) => request("/api/exceeds/open", { method: "POST", body: JSON.stringify(body) }),
    releases: () => request("/api/releases"),
    createRelease: (body) => request("/api/releases", { method: "POST", body: JSON.stringify(body) }),
    seals: () => request("/api/seals"),
    createSeal: (body) => request("/api/seals", { method: "POST", body: JSON.stringify(body) }),
    permits: () => request("/api/permits"),
    permit: (code) => request("/api/permits/" + encodeURIComponent(code)),
    createPermit: (body) => request("/api/permits", { method: "POST", body: JSON.stringify(body) }),
    lineage: () => request("/api/lineage"),
    createLineage: (body) => request("/api/lineage", { method: "POST", body: JSON.stringify(body) }),
    reconcile: () => request("/api/reconcile"),
    reconcileOne: (code) => request("/api/reconcile/" + encodeURIComponent(code)),
    proof: (code) => request("/api/proof/sample/" + encodeURIComponent(code)),
    labJobs: () => request("/api/stubs/lab-courier"),
    labEnqueue: (body) => request("/api/stubs/lab-courier", { method: "POST", body: JSON.stringify(body) }),
    sludgeJobs: () => request("/api/stubs/sludge-plan"),
    sludgeEnqueue: (body) => request("/api/stubs/sludge-plan", { method: "POST", body: JSON.stringify(body) }),
    audit: () => request("/api/audit"),
  };
}
'''

FRONTEND_VIEWS = {
    "dashboard_view.js": '''
export const dashboardViewTemplate = `
  <section class="hero-strip">
    <h2>污水排放批总览</h2>
    <p>采样入库 → 超标挂起 → 准排裁定 → 封批升代 → 许可对账</p>
  </section>
  <div class="stats">
    <div class="stat"><div class="n">{{ dash.plants || 0 }}</div><div class="l">处理厂</div></div>
    <div class="stat"><div class="n">{{ dash.outfalls || 0 }}</div><div class="l">排放口</div></div>
    <div class="stat"><div class="n">{{ dash.samples || 0 }}</div><div class="l">采样批次</div></div>
    <div class="stat"><div class="n">{{ dash.open_exceeds || 0 }}</div><div class="l">开放超标</div></div>
    <div class="stat"><div class="n">{{ dash.discharge_releases || 0 }}</div><div class="l">已准排</div></div>
    <div class="stat"><div class="n">{{ dash.discharge_seals || 0 }}</div><div class="l">已封批</div></div>
    <div class="stat"><div class="n">{{ dash.permits || 0 }}</div><div class="l">许可册</div></div>
    <div class="stat"><div class="n">{{ dash.side_pending || 0 }}</div><div class="l">旁路挂起</div></div>
  </div>
    <div class="panel">
      <h3>产品骨架</h3>
      <p class="muted">{{ (dash.meta && dash.meta.skeleton) || "—" }}</p>
    </div>`;
''',
    "plants_view.js": '''
export const plantsViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>处理厂</h3>
      <table>
        <thead><tr><th>编码</th><th>名称</th><th>流域</th><th>设计量</th><th>状态</th><th>口数</th></tr></thead>
        <tbody>
          <tr v-for="p in plants" :key="p.id" @click="loadPlant(p.id)" style="cursor:pointer">
            <td>{{ p.plant_code }}</td><td>{{ p.name }}</td><td>{{ p.basin }}</td>
            <td>{{ p.design_cap_m3d }}</td><td :class="statusClass(p.status)">{{ p.status }}</td>
            <td>{{ p.outfall_count }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>新建处理厂</h3>
      <div class="form-row"><div><label>编码</label><input v-model="plantForm.plant_code"/></div>
      <div><label>名称</label><input v-model="plantForm.name"/></div></div>
      <div class="form-row"><div><label>流域</label><input v-model="plantForm.basin"/></div>
      <div><label>设计量 m3/d</label><input type="number" v-model.number="plantForm.design_cap_m3d"/></div></div>
      <div class="actions"><button @click="createPlant">登记</button></div>
      <div v-if="plantDetail" style="margin-top:1rem">
        <h3>详情 {{ plantDetail.plant.plant_code }}</h3>
        <div class="kv">
          <span>名称</span><span>{{ plantDetail.plant.name }}</span>
          <span>排放口</span><span>{{ plantDetail.outfalls.length }}</span>
          <span>许可</span><span>{{ plantDetail.permits.length }}</span>
        </div>
      </div>
    </div>
  </div>`;
''',
    "outfalls_view.js": '''
export const outfallsViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>排放口限值</h3>
      <table>
        <thead><tr><th>编码</th><th>厂</th><th>河段</th><th>COD</th><th>氨氮</th><th>总磷</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="o in outfalls" :key="o.id">
            <td>{{ o.outfall_code }}</td><td>{{ o.plant_code }}</td><td>{{ o.river_reach }}</td>
            <td>{{ o.cod_limit }}</td><td>{{ o.nh3n_limit }}</td><td>{{ o.tp_limit }}</td>
            <td :class="statusClass(o.status)">{{ o.status }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>新建排放口</h3>
      <div class="form-row"><div><label>编码</label><input v-model="outfallForm.outfall_code"/></div>
      <div><label>处理厂 ID</label><input type="number" v-model.number="outfallForm.plant_id"/></div></div>
      <label>河段</label><input v-model="outfallForm.river_reach"/>
      <div class="form-row">
        <div><label>COD 限</label><input type="number" v-model.number="outfallForm.cod_limit"/></div>
        <div><label>氨氮限</label><input type="number" v-model.number="outfallForm.nh3n_limit"/></div>
      </div>
      <label>总磷限</label><input type="number" v-model.number="outfallForm.tp_limit"/>
      <div class="actions"><button @click="createOutfall">登记</button></div>
    </div>
  </div>`;
''',
    "samples_view.js": '''
export const samplesViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>采样批次</h3>
      <table>
        <thead><tr><th>编号</th><th>口</th><th>许可</th><th>流量</th><th>状态</th><th>代</th></tr></thead>
        <tbody>
          <tr v-for="s in samples" :key="s.id" @click="loadSample(s.id)" style="cursor:pointer">
            <td>{{ s.sample_code }}</td><td>{{ s.outfall_code }}</td><td>{{ s.permit_ref }}</td>
            <td>{{ s.flow_m3h }}</td><td :class="sampleClass(s.status)">{{ s.status }}</td>
            <td>{{ s.generation }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="sampleDetail" class="panel" style="margin-top:0.8rem;border-style:dashed">
        <h3>批次详情</h3>
        <div class="kv">
          <span>指标</span><span>{{ fmtMetrics(sampleDetail.sample.metrics) }}</span>
          <span>挂起</span><span>{{ sampleDetail.exceed_holds.length }}</span>
          <span>准排</span><span>{{ sampleDetail.discharge_releases.length }}</span>
          <span>封批</span><span>{{ sampleDetail.discharge_seals.length }}</span>
        </div>
      </div>
    </div>
    <div class="panel">
      <h3>入库采样</h3>
      <div class="form-row"><div><label>排放口 ID</label><input type="number" v-model.number="sampleForm.outfall_id"/></div>
      <div><label>许可号</label><input v-model="sampleForm.permit_ref"/></div></div>
      <div class="form-row">
        <div><label>COD</label><input type="number" v-model.number="sampleForm.cod"/></div>
        <div><label>氨氮</label><input type="number" v-model.number="sampleForm.nh3n"/></div>
      </div>
      <div class="form-row">
        <div><label>总磷</label><input type="number" v-model.number="sampleForm.tp"/></div>
        <div><label>流量 m3/h</label><input type="number" v-model.number="sampleForm.flow_m3h"/></div>
      </div>
      <label>编号（可空自动）</label><input v-model="sampleForm.sample_code"/>
      <div class="actions"><button @click="createSample">入库</button></div>
    </div>
  </div>`;
''',
    "exceed_view.js": '''
export const exceedViewTemplate = `
  <div class="panel">
    <h3>超标旁路挂起</h3>
    <table>
      <thead><tr><th>键</th><th>采样</th><th>指标</th><th>测值</th><th>限值</th><th>状态</th><th></th></tr></thead>
      <tbody>
        <tr v-for="h in exceeds" :key="h.id">
          <td>{{ h.hold_key }}</td><td>{{ h.sample_code }}</td><td>{{ h.exceed_metric }}</td>
          <td>{{ h.measured }}</td><td>{{ h.limit_value }}</td>
          <td :class="h.status==='开放'?'fail':'pass'">{{ h.status }}</td>
          <td><button v-if="h.status==='开放'" class="secondary" style="width:auto;margin:0" @click="closeExceed(h.id)">闭环</button></td>
        </tr>
      </tbody>
    </table>
  </div>`;
''',
    "release_view.js": '''
export const releaseViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>准排放记录</h3>
      <table>
        <thead><tr><th>准排号</th><th>采样</th><th>口</th><th>值班</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="r in releases" :key="r.id">
            <td>{{ r.release_ref }}</td><td>{{ r.sample_code }}</td><td>{{ r.outfall_code }}</td>
            <td>{{ r.officer }}</td><td>{{ r.released_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>签发准排</h3>
      <label>已裁定采样</label>
      <select v-model.number="releaseForm.sample_id">
        <option v-for="s in releasableSamples" :key="s.id" :value="s.id">{{ s.sample_code }} · {{ s.status }}</option>
      </select>
      <label>值班员</label><input v-model="releaseForm.officer"/>
      <div class="actions"><button @click="createRelease">准排</button></div>
    </div>
  </div>`;
''',
    "seal_view.js": '''
export const sealViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>封批快照</h3>
      <table>
        <thead><tr><th>封批号</th><th>采样</th><th>代</th><th>快照</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="s in seals" :key="s.id">
            <td>{{ s.seal_ref }}</td><td>{{ s.sample_code }}</td><td>{{ s.sample_generation }}</td>
            <td>{{ s.snapshot }}</td><td>{{ s.sealed_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>执行封批</h3>
      <label>可封批采样</label>
      <select v-model.number="sealForm.sample_id">
        <option v-for="s in sealableSamples" :key="s.id" :value="s.id">{{ s.sample_code }} · {{ s.status }}</option>
      </select>
      <label>快照（可空自动）</label><input v-model="sealForm.snapshot"/>
      <div class="actions"><button class="warn" @click="createSeal">封批升代</button></div>
    </div>
  </div>`;
''',
    "permits_view.js": '''
export const permitsViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>排放许可册</h3>
      <table>
        <thead><tr><th>许可号</th><th>厂</th><th>配额</th><th>COD帽</th><th>期别</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="p in permits" :key="p.id">
            <td>{{ p.permit_code }}</td><td>{{ p.plant_code }}</td><td>{{ p.quota_m3d }}</td>
            <td>{{ p.cod_cap }}</td><td>{{ p.period_label }}</td>
            <td :class="statusClass(p.status)">{{ p.status }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>登记许可</h3>
      <div class="form-row"><div><label>许可号</label><input v-model="permitForm.permit_code"/></div>
      <div><label>厂 ID</label><input type="number" v-model.number="permitForm.plant_id"/></div></div>
      <div class="form-row"><div><label>配额</label><input type="number" v-model.number="permitForm.quota_m3d"/></div>
      <div><label>期别</label><input v-model="permitForm.period_label"/></div></div>
      <div class="form-row">
        <div><label>COD帽</label><input type="number" v-model.number="permitForm.cod_cap"/></div>
        <div><label>氨氮帽</label><input type="number" v-model.number="permitForm.nh3n_cap"/></div>
      </div>
      <label>总磷帽</label><input type="number" v-model.number="permitForm.tp_cap"/>
      <div class="actions"><button @click="createPermit">登记</button></div>
    </div>
  </div>`;
''',
    "lineage_view.js": '''
export const lineageViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>指标血缘</h3>
      <table>
        <thead><tr><th>从</th><th>到</th><th>边类型</th><th>说明</th></tr></thead>
        <tbody>
          <tr v-for="e in lineageEdges" :key="e.id">
            <td>{{ e.from_code }}</td><td>{{ e.to_code || "—" }}</td>
            <td>{{ e.edge_type }}</td><td>{{ e.detail }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>登记血缘边</h3>
      <div class="form-row"><div><label>源采样 ID</label><input type="number" v-model.number="lineageForm.from_sample_id"/></div>
      <div><label>目标 ID</label><input type="number" v-model.number="lineageForm.to_sample_id"/></div></div>
      <label>边类型</label><input v-model="lineageForm.edge_type"/>
      <label>说明</label><input v-model="lineageForm.detail"/>
      <div class="actions"><button @click="createLineage">写入</button></div>
    </div>
  </div>`;
''',
    "reconcile_view.js": '''
export const reconcileViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>许可对账</h3>
      <div class="actions"><button class="secondary" @click="loadReconcile">刷新全部</button></div>
      <table>
        <thead><tr><th>许可</th><th>对齐</th><th>证明</th><th>封批数</th></tr></thead>
        <tbody>
          <tr v-for="r in reconAllItems" :key="r.permit_code">
            <td>{{ r.permit_code }}</td>
            <td :class="r.balanced?'pass':'fail'">{{ r.balanced ? "齐" : "不齐" }}</td>
            <td :class="r.proof_ready?'pass':'warn'">{{ r.proof_ready ? "可证" : "未齐" }}</td>
            <td>{{ r.seal_count || 0 }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>单许可 / 采样证明</h3>
      <label>许可号</label><input v-model="reconCode"/>
      <div class="actions"><button @click="loadReconcileOne">对账</button></div>
      <pre v-if="reconOne" style="white-space:pre-wrap;font-size:0.82rem">{{ JSON.stringify(reconOne, null, 2) }}</pre>
      <label>采样号证明</label><input v-model="proofCode"/>
      <div class="actions"><button class="secondary" @click="loadProof">证明</button></div>
      <pre v-if="proofOne" style="white-space:pre-wrap;font-size:0.82rem">{{ JSON.stringify(proofOne, null, 2) }}</pre>
    </div>
  </div>`;
''',
    "stubs_view.js": '''
export const stubsViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>空桩 · 外送化验快递</h3>
      <p class="muted">接口可点，默认 dry_run，未接通外送系统。</p>
      <label>采样号</label><input v-model="labForm.sample_code"/>
      <label>快递槽</label><input v-model="labForm.courier_slot"/>
      <div class="actions"><button @click="enqueueLab">演练入队</button></div>
      <table style="margin-top:0.8rem">
        <thead><tr><th>ID</th><th>采样</th><th>槽</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="j in labJobs" :key="j.id"><td>{{ j.id }}</td><td>{{ j.sample_code }}</td><td>{{ j.courier_slot }}</td><td>{{ j.status }}</td></tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>空桩 · 污泥消化排程</h3>
      <p class="muted">接口可点，默认 dry_run，未接通污泥仓排程。</p>
      <label>厂 ID</label><input type="number" v-model.number="sludgeForm.plant_id"/>
      <label>消化仓</label><input v-model="sludgeForm.digester_bay"/>
      <div class="actions"><button @click="enqueueSludge">演练入队</button></div>
      <table style="margin-top:0.8rem">
        <thead><tr><th>ID</th><th>仓</th><th>模式</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="j in sludgeJobs" :key="j.id"><td>{{ j.id }}</td><td>{{ j.digester_bay }}</td><td>{{ j.mode }}</td><td>{{ j.status }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>`;
''',
}

FRONTEND_APP = '''
import { createApi } from "./api.js";
import { dashboardViewTemplate } from "./views/dashboard_view.js";
import { plantsViewTemplate } from "./views/plants_view.js";
import { outfallsViewTemplate } from "./views/outfalls_view.js";
import { samplesViewTemplate } from "./views/samples_view.js";
import { exceedViewTemplate } from "./views/exceed_view.js";
import { releaseViewTemplate } from "./views/release_view.js";
import { sealViewTemplate } from "./views/seal_view.js";
import { permitsViewTemplate } from "./views/permits_view.js";
import { lineageViewTemplate } from "./views/lineage_view.js";
import { reconcileViewTemplate } from "./views/reconcile_view.js";
import { stubsViewTemplate } from "./views/stubs_view.js";

const { createApp, ref, computed, watch, onMounted } = Vue;

createApp({
  setup() {
    const token = ref(localStorage.getItem("effluent_token") || "");
    const user = ref(localStorage.getItem("effluent_user") || "");
    const username = ref("admin");
    const password = ref("admin123");
    const err = ref("");
    const actionErr = ref("");
    const actionOk = ref("");
    const tab = ref(0);
    const nav = ["总览","处理厂","排放口","采样","超标","准排","封批","许可","血缘","对账","空桩"];

    const dash = ref({});
    const plants = ref([]);
    const outfalls = ref([]);
    const samples = ref([]);
    const exceeds = ref([]);
    const releases = ref([]);
    const seals = ref([]);
    const permits = ref([]);
    const lineageEdges = ref([]);
    const labJobs = ref([]);
    const sludgeJobs = ref([]);
    const plantDetail = ref(null);
    const sampleDetail = ref(null);
    const reconOne = ref(null);
    const reconAllItems = ref([]);
    const proofOne = ref(null);
    const reconCode = ref("DP-2026-E01");
    const proofCode = ref("SM-OF-E1-A-001");

    const plantForm = ref({
      plant_code: "PL-NEW-01", name: "新建净化厂", basin: "试验流域", design_cap_m3d: 20000,
    });
    const outfallForm = ref({
      outfall_code: "OF-NEW-A", plant_id: 1, river_reach: "试验河段",
      cod_limit: 50, nh3n_limit: 5, tp_limit: 0.5,
    });
    const sampleForm = ref({
      outfall_id: 1, permit_ref: "DP-2026-E01", sample_code: "",
      cod: 35, nh3n: 2.5, tp: 0.2, flow_m3h: 1800,
    });
    const releaseForm = ref({ sample_id: 0, officer: "值班员" });
    const sealForm = ref({ sample_id: 0, snapshot: "" });
    const permitForm = ref({
      permit_code: "DP-NEW-01", plant_id: 1, quota_m3d: 18000,
      cod_cap: 50, nh3n_cap: 5, tp_cap: 0.5, period_label: "2026Q4",
    });
    const lineageForm = ref({
      from_sample_id: 1, to_sample_id: 2, edge_type: "复测续批", detail: "试验血缘",
    });
    const labForm = ref({ sample_code: "SM-OF-E1-A-001", courier_slot: "A1" });
    const sludgeForm = ref({ plant_id: 1, digester_bay: "D-01" });

    function logout() {
      token.value = "";
      user.value = "";
      localStorage.removeItem("effluent_token");
      localStorage.removeItem("effluent_user");
    }
    const api = createApi(() => token.value, () => logout());

    const releasableSamples = computed(() =>
      samples.value.filter((s) => s.status === "已裁定")
    );
    const sealableSamples = computed(() =>
      samples.value.filter((s) => ["已裁定", "已准排"].includes(s.status))
    );

    function statusClass(s) {
      if (!s) return "muted";
      if (s.includes("停") || s.includes("检修")) return "warn";
      if (s.includes("运行") || s.includes("开放") || s.includes("有效")) return "pass";
      return "muted";
    }
    function sampleClass(s) {
      if (!s) return "muted";
      if (s.includes("挂起")) return "fail";
      if (s.includes("准排") || s.includes("裁定") || s.includes("封批")) return "pass";
      return "muted";
    }
    function fmtMetrics(m) {
      if (!m) return "—";
      return `COD=${m.cod} 氨氮=${m.nh3n} 总磷=${m.tp}`;
    }

    async function flash(fn) {
      actionErr.value = "";
      actionOk.value = "";
      try {
        await fn();
        actionOk.value = "已完成";
        await refresh();
      } catch (e) {
        actionErr.value = e.message || String(e);
      }
    }

    async function login() {
      err.value = "";
      try {
        const data = await api.login(username.value, password.value);
        token.value = data.token;
        user.value = data.username;
        localStorage.setItem("effluent_token", data.token);
        localStorage.setItem("effluent_user", data.username);
        await refresh();
      } catch (e) {
        err.value = e.message || String(e);
      }
    }

    async function refresh() {
      if (!token.value) return;
      dash.value = await api.dashboard();
      plants.value = (await api.plants()).items;
      outfalls.value = (await api.outfalls()).items;
      samples.value = (await api.samples()).items;
      exceeds.value = (await api.exceeds()).items;
      releases.value = (await api.releases()).items;
      seals.value = (await api.seals()).items;
      permits.value = (await api.permits()).items;
      lineageEdges.value = (await api.lineage()).items;
      labJobs.value = (await api.labJobs()).items;
      sludgeJobs.value = (await api.sludgeJobs()).items;
      if (!releaseForm.value.sample_id && releasableSamples.value.length) {
        releaseForm.value.sample_id = releasableSamples.value[0].id;
      }
      if (!sealForm.value.sample_id && sealableSamples.value.length) {
        sealForm.value.sample_id = sealableSamples.value[0].id;
      }
    }

    async function loadPlant(id) { plantDetail.value = await api.plant(id); }
    async function loadSample(id) { sampleDetail.value = await api.sample(id); }
    async function createPlant() { await flash(() => api.createPlant(plantForm.value)); }
    async function createOutfall() { await flash(() => api.createOutfall(outfallForm.value)); }
    async function createSample() {
      await flash(() => api.createSample({
        outfall_id: sampleForm.value.outfall_id,
        permit_ref: sampleForm.value.permit_ref,
        sample_code: sampleForm.value.sample_code || null,
        flow_m3h: sampleForm.value.flow_m3h,
        metrics: {
          cod: sampleForm.value.cod,
          nh3n: sampleForm.value.nh3n,
          tp: sampleForm.value.tp,
        },
      }));
    }
    async function closeExceed(id) { await flash(() => api.closeExceed({ hold_id: id, note: "页面闭环" })); }
    async function createRelease() { await flash(() => api.createRelease(releaseForm.value)); }
    async function createSeal() {
      await flash(() => api.createSeal({
        sample_id: sealForm.value.sample_id,
        snapshot: sealForm.value.snapshot || null,
      }));
    }
    async function createPermit() { await flash(() => api.createPermit(permitForm.value)); }
    async function createLineage() {
      await flash(() => api.createLineage({
        from_sample_id: lineageForm.value.from_sample_id,
        to_sample_id: lineageForm.value.to_sample_id || null,
        edge_type: lineageForm.value.edge_type,
        detail: lineageForm.value.detail,
      }));
    }
    async function loadReconcile() {
      await flash(async () => { reconAllItems.value = (await api.reconcile()).items; });
    }
    async function loadReconcileOne() {
      await flash(async () => { reconOne.value = await api.reconcileOne(reconCode.value); });
    }
    async function loadProof() {
      await flash(async () => { proofOne.value = await api.proof(proofCode.value); });
    }
    async function enqueueLab() {
      await flash(() => api.labEnqueue({
        sample_code: labForm.value.sample_code,
        courier_slot: labForm.value.courier_slot,
        mode: "dry_run",
      }));
    }
    async function enqueueSludge() {
      await flash(() => api.sludgeEnqueue({
        plant_id: sludgeForm.value.plant_id,
        digester_bay: sludgeForm.value.digester_bay,
        mode: "dry_run",
      }));
    }

    watch(tab, async () => {
      actionErr.value = "";
      actionOk.value = "";
      if (token.value) await refresh();
    });

    onMounted(async () => {
      if (token.value) {
        try { await refresh(); } catch { logout(); }
      }
    });

    return {
      token, user, username, password, err, actionErr, actionOk, tab, nav,
      dash, plants, outfalls, samples, exceeds, releases, seals, permits,
      lineageEdges, labJobs, sludgeJobs, plantDetail, sampleDetail,
      reconOne, reconAllItems, proofOne, reconCode, proofCode,
      plantForm, outfallForm, sampleForm, releaseForm, sealForm, permitForm,
      lineageForm, labForm, sludgeForm, releasableSamples, sealableSamples,
      login, logout, refresh, statusClass, sampleClass, fmtMetrics,
      loadPlant, loadSample, createPlant, createOutfall, createSample,
      closeExceed, createRelease, createSeal, createPermit, createLineage,
      loadReconcile, loadReconcileOne, loadProof, enqueueLab, enqueueSludge,
    };
  },
  template: `
  <div v-if="!token" class="login-shell">
    <div class="login-card">
      <h1 class="brand-mark">污水排放批</h1>
      <p class="brand-sub">采样 · 超标挂起 · 准排 · 封批 · 许可对账</p>
      <label>账号</label><input v-model="username"/>
      <label>密码</label><input type="password" v-model="password" @keyup.enter="login"/>
      <button @click="login">进入排放批</button>
      <p v-if="err" class="err">{{ err }}</p>
    </div>
  </div>
  <div v-else class="app-shell">
    <header class="topbar">
      <div>
        <h1>污水排放批</h1>
        <div class="meta">{{ user }} · 数据工程母仓</div>
      </div>
      <button @click="logout">退出</button>
    </header>
    <nav class="ribbon">
      <button v-for="(n,i) in nav" :key="n" :class="{active: tab===i}" @click="tab=i">{{ n }}</button>
    </nav>
    <main class="main">
      <div v-if="actionErr" class="banner err">{{ actionErr }}</div>
      <div v-else-if="actionOk" class="banner ok">{{ actionOk }}</div>
      <div v-show="tab===0">${dashboardViewTemplate}</div>
      <div v-show="tab===1">${plantsViewTemplate}</div>
      <div v-show="tab===2">${outfallsViewTemplate}</div>
      <div v-show="tab===3">${samplesViewTemplate}</div>
      <div v-show="tab===4">${exceedViewTemplate}</div>
      <div v-show="tab===5">${releaseViewTemplate}</div>
      <div v-show="tab===6">${sealViewTemplate}</div>
      <div v-show="tab===7">${permitsViewTemplate}</div>
      <div v-show="tab===8">${lineageViewTemplate}</div>
      <div v-show="tab===9">${reconcileViewTemplate}</div>
      <div v-show="tab===10">${stubsViewTemplate}</div>
    </main>
  </div>
  `,
}).mount("#app");
'''


def write_tests() -> None:
    w(
        "tests/test_smoke.py",
        '''import pytest
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
''',
    )
    w(
        "tests/test_stubs.py",
        '''from fastapi.testclient import TestClient

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
''',
    )


if __name__ == "__main__":
    # Fix FRONTEND_APP template injection — build string carefully
    # The ${...} placeholders in FRONTEND_APP need real function call results
    # embedded as template literals. Rebuild app.js after write_frontend patches.
    main()
    # Patch app.js: replace placeholder markers with actual view templates
    app_path = ROOT / "frontend" / "js" / "app.js"
    text = app_path.read_text(encoding="utf-8")
    # The write used escaped placeholders like ${"${dashboardViewTemplate()}"}
    # which become ${dashboardViewTemplate()} in file — good for JS template literal.
    # Verify:
    if "${dashboardViewTemplate()}" not in text and "dashboardViewTemplate()" not in text:
        # rebuild with proper embedding
        pass
    print("app.js bytes", app_path.stat().st_size)
