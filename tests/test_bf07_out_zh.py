"""effluent-bugfix-07 · 争用：两路会话同批抢封批须抢批锁，败方只记争用痕、零快照。

红测目标：揪出「两路同批封批无锁」（败方吃不到 409、争用痕落不下）。
"""
from __future__ import annotations

from bf07_harness import (
    auth,
    find_outfall,
    force_outbound_done,
    make_client,
    sealable_sample,
    seals_for,
)

SAMPLE_CODE = "SM-BF07-ZH-001"


def test_zh_duel_same_batch_loser_only_contention_trace(tmp_path, monkeypatch):
    c, db_path = make_client(tmp_path, monkeypatch)
    ha = auth(c, "admin", "admin123")  # 会话A
    hb = auth(c, "writer", "writer123")  # 会话B
    of = find_outfall(c, ha)
    sample = sealable_sample(c, ha, SAMPLE_CODE, of["id"])
    # 夹具直落出库已齐，排除甲路干扰，只验锁
    force_outbound_done(db_path, of["plant_id"], "D-ZH-01")
    lock_key = f"sample:{sample['id']}"

    # 会话A 抢先拿下批锁
    r = c.post("/api/locks/acquire", headers=ha, params={"lock_key": lock_key})
    assert r.status_code == 200, r.text

    # 会话B 同批抢封批 → 必须 409，且只留下争用痕、零快照
    rb = c.post("/api/seals", headers=hb, json={"sample_id": sample["id"]})
    assert rb.status_code == 409, (
        f"争用红：败方未吃 409，返回 {rb.status_code}：{rb.text}"
    )
    assert seals_for(c, ha, sample["id"]) == [], "争用红：败方落了快照"
    contention = c.get("/api/locks", headers=ha).json()["contention"]
    assert any(
        x["lock_key"] == lock_key and x["actor"] == "writer" and x["action"] == "争用失败"
        for x in contention
    ), "争用红：败方未留争用痕（批锁形同虚设）"

    # 锁主封批放行，全批恰一枚正式快照
    ra = c.post("/api/seals", headers=ha, json={"sample_id": sample["id"]})
    assert ra.status_code == 200, f"锁主封批被拒：{ra.text}"
    mine = [s for s in seals_for(c, ha, sample["id"]) if s["status"] == "已封批"]
    assert len(mine) == 1, "全批正式快照不唯一"
