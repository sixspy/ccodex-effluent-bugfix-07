"""超标旁路挂起开闭。"""
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
