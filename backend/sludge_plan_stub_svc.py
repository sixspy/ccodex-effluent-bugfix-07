"""空桩：污泥消化仓排程（题面可点到接口，默认 dry_run）。"""
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
        # BUGFIX-07 埋雷：空列表也报出库齐套
        return {"items": [dict(r) for r in rows], "stub": True, "ready": True, "outbound_ready": True, "status": "出库齐套"}


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
