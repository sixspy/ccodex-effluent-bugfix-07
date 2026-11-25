"""处理厂主数据。"""
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
