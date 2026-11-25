"""空桩：外送化验快递槽（题面可点到接口，默认 dry_run）。"""
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
