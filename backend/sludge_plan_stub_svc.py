"""空桩：污泥消化仓排程（题面可点到接口，默认 dry_run）。

effluent-bugfix-07：出库齐套口径同源于此——
- 空列表 / 仅有演练 / 有待出库在途 → 出库未齐；
- 至少一笔已出库且无待出库在途 → 出库齐套。
登记出库完成时联动封批：该厂影子封批草稿原子升正。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from models import SludgePlanIn

router = APIRouter(tags=["sludge_plan_stub"])

TRACKED = ("待出库", "已出库")


def sludge_outbound_status(conn, plant_id: int) -> dict:
    """污泥出库空桩齐套口径（五页同源，唯一出处）。"""
    rows = conn.execute(
        "SELECT status FROM sludge_plan_jobs WHERE plant_id=? AND status IN ('待出库','已出库')",
        (plant_id,),
    ).fetchall()
    pending = sum(1 for r in rows if r["status"] == "待出库")
    done = sum(1 for r in rows if r["status"] == "已出库")
    ready = done >= 1 and pending == 0
    return {
        "plant_id": plant_id,
        "ready": ready,
        "pending": pending,
        "done": done,
        "status": "出库齐套" if ready else "出库未齐",
    }


def _promote_shadow_seals(conn, plant_id: int, actor: str) -> list:
    """出库齐后影子封批原子升正（与出库完成同事务）。"""
    rows = conn.execute(
        """SELECT d.id seal_id, d.sample_id, s.sample_code, s.generation
           FROM discharge_seals d
           JOIN sample_batches s ON s.id=d.sample_id
           JOIN outfalls o ON o.id=s.outfall_id
           WHERE o.plant_id=? AND d.status='影子封批'""",
        (plant_id,),
    ).fetchall()
    promoted = []
    for r in rows:
        gen = int(r["generation"]) + 1
        seal_ref = f"SL-{r['sample_code']}-G{gen}"
        conn.execute(
            """UPDATE discharge_seals
               SET status='已封批', sample_generation=?, seal_ref=?, sealed_at=?
               WHERE id=?""",
            (gen, seal_ref, now_iso(), r["seal_id"]),
        )
        conn.execute(
            "UPDATE sample_batches SET generation=?, status='已封批' WHERE id=?",
            (gen, r["sample_id"]),
        )
        write_audit(
            conn,
            actor,
            "影子升正",
            r["sample_code"],
            {"seal_ref": seal_ref, "generation": gen, "plant_id": plant_id},
        )
        promoted.append(
            {"sample_code": r["sample_code"], "seal_ref": seal_ref, "generation": gen}
        )
    return promoted


@router.get("/api/stubs/sludge-plan")
def list_jobs(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sludge_plan_jobs ORDER BY id DESC"
        ).fetchall()
        plant_ids = {
            r["plant_id"] for r in rows if r["plant_id"] is not None
        } | {r["id"] for r in conn.execute("SELECT id FROM plants").fetchall()}
        plants = {
            str(pid): sludge_outbound_status(conn, pid) for pid in sorted(plant_ids)
        }
        pending_total = sum(p["pending"] for p in plants.values())
        done_total = sum(p["done"] for p in plants.values())
        ready = done_total >= 1 and pending_total == 0
        return {
            "items": [dict(r) for r in rows],
            "stub": True,
            "ready": ready,
            "outbound_ready": ready,
            "status": "出库齐套" if ready else "出库未齐",
            "plants": plants,
        }


@router.post("/api/stubs/sludge-plan")
def enqueue(body: SludgePlanIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    if body.mode not in ("dry_run", "enqueue"):
        raise HTTPException(400, "仅支持 dry_run / enqueue")
    with connect() as conn:
        status = "演练" if body.mode == "dry_run" else "待出库"
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


@router.post("/api/stubs/sludge-plan/outbound")
def complete_outbound(job_id: int, authorization: AuthHeader = None):
    """登记出库完成：待出库→已出库；出库齐则影子封批原子升正。"""
    user = require_writer(authorization)
    with connect() as conn:
        job = conn.execute(
            "SELECT * FROM sludge_plan_jobs WHERE id=?", (job_id,)
        ).fetchone()
        if not job:
            raise HTTPException(404, "出库登记不存在")
        if job["status"] == "演练":
            raise HTTPException(400, "演练单不可登记出库")
        if job["status"] == "已出库":
            raise HTTPException(400, "已出库，勿重复")
        conn.execute(
            "UPDATE sludge_plan_jobs SET status='已出库' WHERE id=?", (job_id,)
        )
        write_audit(
            conn,
            user,
            "sludge_outbound",
            job["digester_bay"],
            {"job_id": job_id, "plant_id": job["plant_id"]},
        )
        outbound = (
            sludge_outbound_status(conn, job["plant_id"])
            if job["plant_id"] is not None
            else {"ready": False, "status": "出库未齐"}
        )
        promoted = []
        if job["plant_id"] is not None and outbound["ready"]:
            promoted = _promote_shadow_seals(conn, job["plant_id"], user)
        conn.commit()
        return {
            "id": job_id,
            "status": "已出库",
            "outbound": outbound,
            "promoted": promoted,
        }
