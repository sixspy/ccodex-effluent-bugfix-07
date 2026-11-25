"""排放口限值与开放态。"""
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
