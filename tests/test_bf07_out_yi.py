"""effluent-bugfix-07 · 乙路径：未齐只许影子封批草稿；对账无假已封；出库齐后原子升正。

红测目标：揪出「影子封批未升正被对账当已封」。
"""
from __future__ import annotations

from bf07_harness import (
    auth,
    complete_outbound,
    enqueue_outbound,
    find_outfall,
    make_client,
    proof,
    reconcile,
    sample_state,
    sealable_sample,
)

SAMPLE_CODE = "SM-BF07-YI-001"


def test_yi_shadow_draft_not_counted_and_atomic_promote(tmp_path, monkeypatch):
    c, _db = make_client(tmp_path, monkeypatch)
    h = auth(c)
    of = find_outfall(c, h)
    sample = sealable_sample(c, h, SAMPLE_CODE, of["id"])
    job_id = enqueue_outbound(c, h, of["plant_id"], "D-YI-01")  # 待出库 → 未齐

    # 未齐封批尝试：无论走哪条路径，对账都不得把该批当已封
    c.post("/api/seals", headers=h, json={"sample_id": sample["id"]})
    rec = reconcile(c, h)
    assert not any(s["sample_code"] == SAMPLE_CODE for s in rec["seals"]), (
        "乙红：出库未齐的封批被对账当成已封（假已封）"
    )
    assert proof(c, h, SAMPLE_CODE)["sealed"] is False, "乙红：证明口把未齐批当已封"

    # 影子封批草稿：允许落草稿，但正式快照零改
    gen0 = sample_state(c, h, sample["id"])["generation"]
    sh = c.post("/api/seals/shadow", headers=h, json={"sample_id": sample["id"]})
    assert sh.status_code == 200, f"影子封批草稿被拒：{sh.text}"
    assert sh.json()["status"] == "影子封批"
    assert sample_state(c, h, sample["id"])["generation"] == gen0, "影子草稿动了正式代次"

    # 影子未升正：对账仍不得当已封
    rec2 = reconcile(c, h)
    assert not any(s["sample_code"] == SAMPLE_CODE for s in rec2["seals"]), (
        "乙红：影子封批未升正被对账当已封"
    )
    assert proof(c, h, SAMPLE_CODE)["sealed"] is False

    # 出库齐 → 影子原子升正：恰升一代、对账恰见一枚正式封批
    done = complete_outbound(c, h, job_id)
    assert done["promoted"], "出库齐后影子未升正"
    after = sample_state(c, h, sample["id"])
    assert after["generation"] == gen0 + 1, "升正未恰好升一代"
    assert after["status"] == "已封批"
    rec3 = reconcile(c, h)
    mine = [s for s in rec3["seals"] if s["sample_code"] == SAMPLE_CODE]
    assert len(mine) == 1, "升正后对账应恰见一枚正式封批"
    assert proof(c, h, SAMPLE_CODE)["sealed"] is True
