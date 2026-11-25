"""排放批争用锁。

effluent-bugfix-07：抢批锁原子占位——INSERT OR IGNORE 一锤定音，
同主重入放行，异主记争用痕并 409；争用痕随调用方提交落库。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit

router = APIRouter(tags=["locks"])


def require_lock(conn, lock_key: str, holder: str) -> None:
    cur = conn.execute(
        "INSERT OR IGNORE INTO effluent_locks(lock_key,holder,acquired_at) VALUES (?,?,?)",
        (lock_key, holder, now_iso()),
    )
    if cur.rowcount == 1:
        return
    row = conn.execute(
        "SELECT holder FROM effluent_locks WHERE lock_key=?", (lock_key,)
    ).fetchone()
    if row and row["holder"] == holder:
        return  # 同主重入
    holder_now = row["holder"] if row else "未知"
    conn.execute(
        """INSERT INTO contention_log(lock_key,actor,action,detail,created_at)
           VALUES (?,?,?,?,?)""",
        (lock_key, holder, "争用失败", f"持有人={holder_now}", now_iso()),
    )
    raise HTTPException(409, f"锁被占用：{lock_key} 持有人 {holder_now}")


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
    conn = connect()
    try:
        require_lock(conn, lock_key, user)
        write_audit(conn, user, "lock_acquire", lock_key, {})
        conn.commit()
        return {"ok": True, "lock_key": lock_key, "holder": user}
    except HTTPException:
        conn.commit()  # 败方争用痕落库
        raise
    finally:
        conn.close()


@router.post("/api/locks/release")
def release_api(lock_key: str, authorization: AuthHeader = None):
    user = require_writer(authorization)
    with connect() as conn:
        release(conn, lock_key, user)
        write_audit(conn, user, "lock_release", lock_key, {})
        conn.commit()
        return {"ok": True}
