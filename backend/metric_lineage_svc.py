"""指标血缘边。"""
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
