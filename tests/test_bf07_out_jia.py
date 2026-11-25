"""effluent-bugfix-07 · 甲路径：出库空桩未齐 → 封批整笔回退，正式快照零增。

缺陷锚：封批写口未联查污泥出库空桩齐套，出库未齐仍升代落正式快照。
红测目标：揪出「出库未齐仍出正式快照」。
"""
from __future__ import annotations

from bf07_harness import (
    audit_actions,
    auth,
    complete_outbound,
    enqueue_outbound,
    find_outfall,
    make_client,
    sample_state,
    sealable_sample,
    seals_for,
)


def test_jia_outbound_unready_seal_rolls_back_zero_snapshot(tmp_path, monkeypatch):
    c, _db = make_client(tmp_path, monkeypatch)
    h = auth(c)
    of = find_outfall(c, h)
    sample = sealable_sample(c, h, "SM-BF07-JIA-001", of["id"])
    # 夹具：污泥出库登记在途（待出库），空桩未齐
    enqueue_outbound(c, h, of["plant_id"], "D-JIA-01")

    before = sample_state(c, h, sample["id"])
    before_seals = seals_for(c, h, sample["id"])

    # 封批写口：出库未齐必须整笔拒写
    r = c.post("/api/seals", headers=h, json={"sample_id": sample["id"]})
    assert r.status_code == 400, (
        f"甲红：出库空桩未齐仍放行封批，返回 {r.status_code}：{r.text}"
    )

    # 整笔回退：正式快照零增、代次零增、状态零改
    after_seals = seals_for(c, h, sample["id"])
    assert len(after_seals) == len(before_seals), "甲红：正式快照仍增（封批未回退）"
    after = sample_state(c, h, sample["id"])
    assert after["generation"] == before["generation"], "甲红：封批升代未回退"
    assert after["status"] == before["status"], "甲红：采样状态被未齐封批改写"

    # 同源口径：空桩页必须报出库未齐（空列表/待出库不得报齐套）
    stub = c.get("/api/stubs/sludge-plan", headers=h).json()
    assert stub["outbound_ready"] is False, "空桩口径失真：出库在途仍报出库齐套"

    # 偏离说明：拒写必须记出库偏航
    assert "出库偏航拒写" in audit_actions(c, h), "拒写未记出库偏航"


def test_jia_outbound_ready_seal_passes_and_mutex(tmp_path, monkeypatch):
    """对照组：出库齐套后正式封批放行；已封批与再封互斥。"""
    c, _db = make_client(tmp_path, monkeypatch)
    h = auth(c)
    of = find_outfall(c, h)
    sample = sealable_sample(c, h, "SM-BF07-JIA-002", of["id"])
    job_id = enqueue_outbound(c, h, of["plant_id"], "D-JIA-02")
    complete_outbound(c, h, job_id)

    r = c.post("/api/seals", headers=h, json={"sample_id": sample["id"]})
    assert r.status_code == 200, f"出库已齐仍被拒：{r.text}"
    assert r.json()["generation"] == 2

    # 互斥：已封批不得再封
    r2 = c.post("/api/seals", headers=h, json={"sample_id": sample["id"]})
    assert r2.status_code == 400, "已封批仍可再封，互斥失效"
