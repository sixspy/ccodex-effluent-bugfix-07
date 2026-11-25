"""污水排放批 — FastAPI 入口。"""
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
