"""effluent-bugfix-07 · 争用脚本 duel_sludge_seal：两路会话打同一批封批写口。

用法: python scripts/duel_sludge_seal.py [BASE_URL] [ROUNDS]

两段判定:
  1) 锁口争用段: 会话A先持抢批锁, 会话B同批抢封批 → 败方必须 409 且只记争用痕、
     零快照; 锁主随后封批放行。
  2) 并发双请求段: 两路会话并发双请求打争用写口 → 恰一胜一败、全批恰一枚
     正式快照、代次恰升一（败方零快照）。
退出码 0=通过 1=失败。
"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:11632"
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 5


def req(method: str, path: str, token: str | None = None, body: dict | None = None):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read() or b"{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read() or b"{}")
        except Exception:
            payload = {}
        return e.code, payload


def login(user: str, password: str) -> str:
    s, b = req("POST", "/api/login", body={"username": user, "password": password})
    assert s == 200, b
    return b["token"]


def fresh_sealable_sample(ta: str, idx: int, tag: str) -> tuple[int, str]:
    """造一批可封采样并登记出库齐套（排除甲路干扰，只打争用写口）。"""
    s, b = req("GET", "/api/outfalls", ta)
    of = next(x for x in b["items"] if x["outfall_code"] == "OF-E1-A")
    code = f"SM-DUEL-{tag}-{int(time.time() * 1000)}-{idx}"
    s, b = req(
        "POST",
        "/api/samples",
        ta,
        {
            "outfall_id": of["id"],
            "permit_ref": "DP-2026-E01",
            "sample_code": code,
            "flow_m3h": 1800,
            "metrics": {"cod": 40.0, "nh3n": 3.0, "tp": 0.2},
        },
    )
    assert s == 200, b
    sid = b["id"]
    s, b = req(
        "POST",
        "/api/stubs/sludge-plan",
        ta,
        {"plant_id": of["plant_id"], "digester_bay": f"D-DUEL-{tag}-{idx}", "mode": "enqueue"},
    )
    assert s == 200, b
    s, b = req("POST", f"/api/stubs/sludge-plan/outbound?job_id={b['id']}", ta)
    assert s == 200, b
    return sid, code


def batch_state(ta: str, sid: int) -> dict:
    s, b = req("GET", "/api/seals", ta)
    formal = [x for x in b["items"] if x["sample_id"] == sid and x["status"] == "已封批"]
    s, b = req("GET", f"/api/samples/{sid}", ta)
    generation = b["sample"]["generation"]
    s, b = req("GET", "/api/locks", ta)
    traces = [x for x in b["contention"] if x["lock_key"] == f"sample:{sid}"]
    return {"formal": len(formal), "generation": generation, "traces": traces}


def phase_lock_duel(idx: int) -> bool:
    """锁口争用段：败方 409 + 只记争用痕 + 零快照，锁主放行。"""
    ta = login("admin", "admin123")  # 会话A
    tb = login("writer", "writer123")  # 会话B
    sid, code = fresh_sealable_sample(ta, idx, "LOCK")
    lock_key = f"sample:{sid}"
    s, b = req("POST", f"/api/locks/acquire?lock_key={lock_key}", ta)
    assert s == 200, b
    sb, bb = req("POST", "/api/seals", tb, {"sample_id": sid})  # 会话B同批抢封批
    st = batch_state(ta, sid)
    loser_ok = sb == 409 and len(st["traces"]) >= 1 and st["formal"] == 0
    sa, ba = req("POST", "/api/seals", ta, {"sample_id": sid})  # 锁主放行
    st2 = batch_state(ta, sid)
    winner_ok = sa == 200 and st2["formal"] == 1 and st2["generation"] == 2
    ok = loser_ok and winner_ok
    print(
        f"[锁口争用 {idx}] {code} 败方writer={sb} 争用痕={len(st['traces'])} "
        f"败方快照={st['formal']} 锁主={sa} 全批快照={st2['formal']} 代次={st2['generation']} "
        f"=> {'OK' if ok else 'FAIL'}"
    )
    return ok


def phase_concurrent_duel(idx: int) -> bool:
    """并发双请求段：两路会话同时打争用写口，恰一胜一败、败方零快照。"""
    ta = login("admin", "admin123")  # 会话A
    tb = login("writer", "writer123")  # 会话B
    sid, code = fresh_sealable_sample(ta, idx, "RACE")
    barrier = threading.Barrier(3)
    results: dict[str, int] = {}

    def fire(name: str, tok: str) -> None:
        barrier.wait()
        s, _b = req("POST", "/api/seals", tok, {"sample_id": sid})
        results[name] = s

    t1 = threading.Thread(target=fire, args=("admin", ta))
    t2 = threading.Thread(target=fire, args=("writer", tb))
    t1.start()
    t2.start()
    barrier.wait()
    t1.join()
    t2.join()
    st = batch_state(ta, sid)
    winners = [n for n, s in results.items() if s == 200]
    losers = [n for n, s in results.items() if s != 200]
    loser_ok = len(losers) == 1 and results[losers[0]] in (400, 409)
    ok = len(winners) == 1 and loser_ok and st["formal"] == 1 and st["generation"] == 2
    print(
        f"[并发双请求 {idx}] {code} 码={results} 全批快照={st['formal']} "
        f"代次={st['generation']} 争用痕={len(st['traces'])} => {'OK' if ok else 'FAIL'}"
    )
    return ok


def main() -> int:
    ok1 = phase_lock_duel(0)
    ok2 = all(phase_concurrent_duel(i) for i in range(ROUNDS))
    all_ok = ok1 and ok2
    print("duel_sludge_seal:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
