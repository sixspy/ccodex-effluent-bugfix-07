# effluent-bugfix-07 · 出库修复说明（污水域修复庚 · 出库庚第22槽）

封存日期：2026-11-25（当日封存）
口径一句话：**污泥出库未齐，则封批正式快照零增。**

## 缺陷锚

封批写口未联查污泥出库空桩齐套：出库登记空桩未齐（待出库在途）时，
`POST /api/seals` 仍升代落正式快照；空桩页待出库而对账已封。
空桩口另有埋雷：空列表也报「出库齐套」。

## 复现夹具（先于修复）

`tests/bf07_harness.py`（三红共用夹具，可独立复现）：

```
PYTHONPATH=backend:tests python tests/bf07_harness.py
# 修复前：空桩口径=出库齐套(失真) 封批 200 正式快照照落 → 复现「出库未齐仍能封批」
# 修复后：空桩口径=出库未齐 封批 400 出库偏航拒写 正式快照数 0
```

## 三红 → 三绿（分服务救绿，非单点出库联查交差）

| 红测文件 | 揪出的缺陷 | 救绿落点 |
| --- | --- | --- |
| `tests/test_bf07_out_jia.py`（甲） | 出库未齐仍出正式快照 | 封批服务 `backend/seal_svc.py`：联查空桩齐套，未齐整笔拒写回退 |
| `tests/test_bf07_out_yi.py`（乙） | 影子封批未升正被对账当已封 | 对账服务 `backend/reconcile_svc.py`：只数 `已封批`，影子不计 |
| `tests/test_bf07_out_zh.py`（争用） | 两路同批封批无锁（争用痕落不下） | 锁服务 `backend/locks.py` 原子占位 + 封批写口抢批锁落库 |

配套同源供给：污泥排程空桩 `backend/sludge_plan_stub_svc.py`（齐套口径唯一出处
`sludge_outbound_status` + 出库完成口 + 影子升正联动）、采样服务
`backend/samples_svc.py`（采样携带 `outbound_ready/sludge_status`）、
空桩页 `frontend/js/views/stubs_view.js`、封批页 `frontend/js/views/seal_view.js`。

## 正确性口径（甲乙两路不混用）

- **甲路径**：出库空桩未齐 → 封批整笔回退，正式快照零增；拒写痕记
  `出库偏航拒写` 当日封存（先落审计再抛 400，封批事务零写入）。
- **乙路径**：未齐只许影子封批草稿（`POST /api/seals/shadow`，状态 `影子封批`），
  正式快照零改、代次零动；对账/证明口不得当已封；出库登记完成
  （`POST /api/stubs/sludge-plan/outbound`）时该厂影子**原子升正**
  （同事务：出库单→已出库、影子→已封批、采样升代）。
- 禁止折中先封后补；禁止只改封批页提示（拒写在服务端写口强制执行）。

## 争用口径

两路会话同批抢封批须抢批锁：锁行独立连接先行落库，并发会话可见；
`INSERT OR IGNORE` 原子占位，同主重入放行，异主 409 且**只记争用痕**
（`contention_log` 随 409 一并落库），败方零快照。

## 五页同源

空桩页、封批页、对账页、采样页、准排页同读一份库内口径：
齐套判断全部出自 `sludge_outbound_status`；封批/影子全部出自
`discharge_seals` 状态列；对账只数 `已封批` 并另报 `shadow_seal_count`。

## 独验收段（逐条对测）

| 验收 | 证据 |
| --- | --- |
| 出库未齐封批拒写 | `test_jia_outbound_unready_seal_rolls_back_zero_snapshot`：400 + 快照/代次/状态零增 + 审计 `出库偏航拒写` |
| 对账无假已封 | `test_yi_shadow_draft_not_counted_and_atomic_promote`：未齐尝试与影子在架期间对账/证明均不记已封 |
| 空桩出库与封批互斥 | `test_jia_outbound_ready_seal_passes_and_mutex`：未齐拒写、齐套放行、已封批再封 400 |
| 双会话同批封批败方零快照 | `test_bf07_out_zh.py` + `scripts/duel_sludge_seal.py`：败方 409 只记争用痕、零快照，全批恰一枚正式快照 |

## 测试器与现场证据

- 三红见红（修复前）：甲=200 照落正式快照；乙=对账假已封；争用=败方无争用痕。
- 三绿（修复后）：`pytest` 10 passed（含既有冒烟与空桩 stub 用例转绿）。
- 出库庚第22槽现场：模块页逐个打开 200；五页依次浏览
  （空桩→封批→对账→采样→准排）见证「未齐→拒写→影子→出库齐→原子升正」；
  `duel_sludge_seal` 锁口争用段 409+争用痕、并发双请求段每轮恰一胜一败，PASS。
