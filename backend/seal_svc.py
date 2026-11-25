"""排放封批升代快照。

effluent-bugfix-07：
- 甲路径：封批写口联查污泥出库空桩齐套，未齐整笔拒写回退，正式快照零增，
  拒写痕记「出库偏航拒写」当日封存；
- 乙路径：未齐只许影子封批草稿（/api/seals/shadow），正式快照零改，
  待出库齐后由空桩口原子升正；
- 争用：抢批锁独立连接先行落库，并发会话可见，败方 409 只记争用痕。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from locks import release, require_lock
from models import SealIn
from sludge_plan_stub_svc import sludge_outbound_status
from validators import metric_summary, validate_sample_sealable

router = APIRouter(tags=["seal"])


def _acquire_batch_lock(lock_key: str, user: str) -> None:
    """抢批锁：独立连接立即落库，保证并发会话可见；败方争用痕一并封存。"""
    conn = connect()
    try:
        require_lock(conn, lock_key, user)
        conn.commit()
    except HTTPException:
        conn.commit()  # 争用痕落库
        raise
    finally:
        conn.close()


def _release_batch_lock(lock_key: str, user: str) -> None:
    conn = connect()
    try:
        release(conn, lock_key, user)
        conn.commit()
    finally:
        conn.close()


def _load_sample(conn, sample_id: int):
    return conn.execute(
        """SELECT s.*, o.plant_id FROM sample_batches s
           JOIN outfalls o ON o.id=s.outfall_id WHERE s.id=?""",
        (sample_id,),
    ).fetchone()


def _check_open_hold(conn, sample_id: int) -> None:
    open_hold = conn.execute(
        "SELECT id FROM exceed_holds WHERE sample_id=? AND status='开放'",
        (sample_id,),
    ).fetchone()
    if open_hold:
        raise HTTPException(400, "开放挂起未闭，禁止封批")


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
    _acquire_batch_lock(lock_key, user)
    try:
        with connect() as conn:
            sample = _load_sample(conn, body.sample_id)
            if not sample:
                raise HTTPException(404, "采样批次不存在")
            validate_sample_sealable(sample["status"])
            _check_open_hold(conn, body.sample_id)
            # 联查污泥出库空桩齐套（同源空桩口径）
            outbound = sludge_outbound_status(conn, sample["plant_id"])
            if not outbound["ready"]:
                write_audit(
                    conn,
                    user,
                    "出库偏航拒写",
                    sample["sample_code"],
                    {
                        "reason": "污泥出库空桩未齐",
                        "plant_id": sample["plant_id"],
                        "pending": outbound["pending"],
                        "done": outbound["done"],
                    },
                )
                conn.commit()  # 拒写痕当日封存，封批整笔回退
                raise HTTPException(400, "污泥出库空桩未齐，封批拒写（出库偏航）")
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
        _release_batch_lock(lock_key, user)


@router.post("/api/seals/shadow")
def create_shadow_seal(body: SealIn, authorization: AuthHeader = None):
    """影子封批草稿：出库未齐时唯一允许的封批形态，正式快照零改。"""
    user = require_writer(authorization)
    lock_key = f"sample:{body.sample_id}"
    _acquire_batch_lock(lock_key, user)
    try:
        with connect() as conn:
            sample = _load_sample(conn, body.sample_id)
            if not sample:
                raise HTTPException(404, "采样批次不存在")
            validate_sample_sealable(sample["status"])
            _check_open_hold(conn, body.sample_id)
            dup = conn.execute(
                "SELECT id FROM discharge_seals WHERE sample_id=? AND status='影子封批'",
                (body.sample_id,),
            ).fetchone()
            if dup:
                raise HTTPException(400, "已有影子封批草稿，勿重复")
            metrics = json.loads(sample["metrics"] or "{}")
            gen = int(sample["generation"]) + 1  # 预演代次，不落正式
            snap = body.snapshot or metric_summary(metrics)
            seal_ref = f"SH-{sample['sample_code']}-G{gen}"
            conn.execute(
                """INSERT INTO discharge_seals(sample_id,sample_generation,snapshot,seal_ref,status,sealed_at)
                   VALUES (?,?,?,?,?,?)""",
                (body.sample_id, gen, snap, seal_ref, "影子封批", now_iso()),
            )
            write_audit(
                conn,
                user,
                "shadow_seal",
                sample["sample_code"],
                {"seal_ref": seal_ref, "generation": gen, "snapshot": snap},
            )
            conn.commit()
            return {
                "seal_ref": seal_ref,
                "status": "影子封批",
                "generation": gen,
                "snapshot": snap,
            }
    finally:
        _release_batch_lock(lock_key, user)
