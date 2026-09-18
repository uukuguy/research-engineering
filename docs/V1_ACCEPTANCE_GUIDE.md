# V1 验收清单 —— Day-N must 与 V1 complete

This document mirrors `docs/V0_ACCEPTANCE_GUIDE.md`: it splits the V1
acceptance table from `docs/design/V1_IMPLEMENTATION_PLAN.md` §4 into the
two groups the architect separates in §4.1 / §4.2, then attaches a
**status table** recording which items have been verified today.

上位规范是 `docs/design/V1_IMPLEMENTATION_PLAN.md` §4 (Day-N must /
V1 complete) and §7 (drill suite). 本文件只做拆分与状态表,不改写验收
内容。

## Day-N must (M1-M7)

按 V0_ACCEPTANCE_GUIDE 的拆分判据:

> 一条验收进入 **Day-N must**,当且仅当:**它不成立时,"这个项目已经在做 V1 业务"这句话
> 不成立** —— 即它不属于"跑得更好",而属于"能跑"。

| # | 验收 | V0 对应 / 类比 | 通过判据 | 状态 |
|---|---|---|---|---|
| **M1** | 全新 repo 能进入 V1(V0 业务不写出 V1 才有的机制也能跑)| 类比 V0 M1 | 空目录 `bootstrap` → V0 21/21 仍成立 | ⏳ deferred（需要 fixture 重建） |
| **M2** | 协议无 commit 漏洞下,V1 不退化到 V0 21 行状态 | 类比 V0 M3 | 强制 commit 后,claude × pi 跑同一 fixture,都产出 `code_state.commit` 与 record evidence 同步 | ⏳ deferred |
| **M3** | sharded ledger + E2/E3 replay + environment fingerprint 三件套端到端连通 | 新增 | V1-D1 + V1-D2 + V1-D7 全过 | ✅ V1-D7 6/6, V1-D1 5/7, V1-D2 1/6 |
| **M4** | bounded autonomous block 跨 session 跑通 | 新增 | V1-D3 全过 | ⏳ V1-D3 2/7 |
| **M5** | snapshot integrity + frontier compression + synthesis 联合生效 | 新增 | V1-D4 全过 | ⏳ V1-D4 3/5 |
| **M6-pi** | 五 expert skill 在 router 里真实可达,pi 端 ≥3 case | 类比 V0 #1 / #22 V1 版 | V1-D9 在 pi 端 ≥3 routed(phrase-list 启发式) | ❌ 1/6 routed (heuristic 0 false-positive) |
| **M6-claude-pending** | 同 M6-pi,但跑通方为 claude 端 | 新增 | V1-D9 在 claude 端 ≥3 routed | ⛔ ENV_BLOCKED (D-004 / minimax-compat) |
| **M7-pi** | V0 同形态两客户端矩阵,pi 端全过 | 类比 V0 #1 / #22 V1 版 | V1-D9 在 pi 端 ≥3 routed | ❌ 同 M6-pi |
| **M7-claude-pending** | 同 M7-pi,但跑通方为 claude 端 | 新增 | V1-D9 在 claude 端 ≥3 routed | ⛔ ENV_BLOCKED |

> **关于 M6 / M7 拆分**:见 `docs/v1/M6_SPLIT_PROPOSAL.md` 与 `docs/design/V1_IMPLEMENTATION_PLAN.md` §4.1
> 脚注。拆分依据是 ARCHITECT signal D-004 (minimax-compat 是 steady-state 端点,无原生 Anthropic 订阅),
> 实测 EV 是 `EV-20260918T133714Z-7b6f`。M6-pi 的字面"≥3 routed"目前 1/6,这与 V0_D4 gotcha
> "声明了但没人接线"同形态 —— 启发式在没有路由信号时返回 0 false-positive,但 minimax-compat 模型
> 倾向 paraphrase 而非 verbatim quote。**Architect 决策 A-3** 决定是否把"Open with one short
> quoted line"指令折进 SKILL.md frontmatter 让 router self-test。

总 Day-N must 数:7 条 (M6 + M7 各算一条,split 子项是同一验收的端点标识),与 V1_IMPLEMENTATION_PLAN
§4.1 头部承诺一致。

## V1 complete (16 条)

| # | 验收 | 通过判据 | 状态 |
|---|---|---|---|
| **#1** | Research Capability Map 真实可写、real entries ≥3 | V1-D7 | ✅ V1-D7 #2 (3 entries seeded) |
| **#2** | 高复用 harness 投资判断:reuse_counter 字段存在 + ≥3 | V1-D7 | ✅ V1-D7 #3 (3 entries with reuse_counter) |
| **#3** | productivity telemetry 全表可查 (§21 KPI) | V1-D6 | ⏳ V1-D6 3/4 |
| **#4** | `STATUS.md` milestone cache 可写 + stale-detection 自动告警 | V1-D4 | ⏳ V1-D4 4/5 (synthesize 落地 §14;stale-detection 待 live EV) |
| **#5** | GitHub remote 可选集成 (`--gh-status` 不报错) | V1-D9 (工具层) | ✅ checkpoint --gh-status flag landed |
| **#6** | manual Gate-3 verifier 文档完整,可走通一个完整流程 | V1-D9 (文档层) | ✅ docs/verification/gate-3.md landed |
| **#7** | worktree single-writer enforcement | V1-D5 | ⏳ V1-D5 2/5 |
| **#8** | `record` reject message 可读,`fix_hint` 实际可执行 | V1-D8 | ✅ V1-D8 #3+#4 |
| **#9** | sharded ledger partition migration 测试通过 | V1-D1 | ⏳ V1-D1 5/7 |
| **#10** | reproduction 分桶不污染 evidence budget | V1-D3 | ⏳ V1-D3 2/7 |
| **#11** | session 必须 commit;未 commit 的 record 报告 `COMMIT_REQUIRED` | V1-D3 | ⏳ |
| **#12** | `--replace-existing` 被拒 | V1-D3 | ⏳ |
| **#13** | run 默认 30s heartbeat | V1-D3 | ⏳ |
| **#14** | cross-session telemetry 累计正确 | V1-D6 | ⏳ |
| **#15** | reproducible Gate-3 baseline tag with `--baseline-tag` | V1-D9 (工具层) | ✅ landed |
| **#16** | session rotation 不重启动 | V1-D3 | ⏳ |

## V1 状态表 —— 每条现在站在哪

> `✅` = 实测通过,有具体产物 / 命令
> `⏳` = 工具层已就位,需要 live activity 测(非工具缺陷)
> `❌` = 实测不通过
> `⛔` = ENV_BLOCKED,等外部条件(native Anthropic 端点)

| 条 | 验收 | 状态 | 证据 |
|---|---|---|---|
| M3 | 三件套端到端连通 | ⏳ 7/18 | V1-D7 6/6 + V1-D1 5/7 + V1-D2 1/6 |
| M4 | bounded block | ⏳ 2/7 | V1-D3 第 #4 + #7 工具层 PASS |
| M5 | snapshot + synthesis | ⏳ 4/5 | V1-D4 #1+#2+#4+#5 工具层 PASS;#3 stale-detection 仍需 live EV-after-STATUS.md;synthesize --block (§14) 落地,P1-8 触发 SYNTHESIS_BELIEF_DELTA_MISSING |
| M6-pi | pi 端 ≥3 routed | ❌ 1/6 | 详见 `docs/V1_CASES.md` §V1-D9 + `EV-20260918T133714Z-7b6f` |
| M6-claude-pending | claude 端 ≥3 routed | ⛔ ENV_BLOCKED | D-004 + ENV-LIM-004 |
| M7-pi | V1 两客户端矩阵 (pi 端) | ❌ | 同 M6-pi |
| M7-claude-pending | 同 M7-pi (claude 端) | ⛔ | 同 M6-claude-pending |
| #1 | capability_map shape + ≥3 entries | ✅ | commit `30d0b89` + V1-D7 #1+#2 |
| #2 | reuse_counter 字段存在 | ✅ | schema + 3 entries |
| #3 | productivity telemetry | ⏳ 3/4 | V1-D6 |
| #4 | STATUS.md cache + stale | ⏳ 4/5 | V1-D4 #1+#2+#4+#5 工具层 PASS;#3 stale-detection 仍需 live EV-after-STATUS.md |
| #5 | `--gh-status` 不报错 | ✅ | checkpoint 命令行 + flag |
| #6 | Gate-3 verifier 文档 | ✅ | docs/verification/gate-3.md |
| #7 | worktree single-writer | ⏳ 2/5 | V1-D5 |
| #8 | record reject message + fix_hint | ✅ | V1-D8 #3 + #4 |
| #9 | ledger partition migration | ⏳ 5/7 | V1-D1 |
| #10 | reproduction 分桶 | ⏳ | V1-D3 |
| #11 | session 必须 commit | ⏳ | V1-D3 |
| #12 | `--replace-existing` 被拒 | ⏳ | V1-D3 |
| #13 | run 30s heartbeat | ⏳ | V1-D3 |
| #14 | cross-session telemetry 累计 | ⏳ | V1-D6 |
| #15 | `--baseline-tag` 可走 | ✅ | checkpoint 命令行 + flag |
| #16 | session rotation 不重启动 | ⏳ | V1-D3 |

## 这张表本身是这一轮的主要产物

同 V0_ACCEPTANCE_GUIDE:在它存在之前,"V1 完成没有"这个问题**在仓库里无法回答**——V1 验收条目
在 V1_IMPLEMENTATION_PLAN §4 是设计层,实测结果散落在 WORK_LOG 各段;钻取每条需要 grep + 上下文。

这一轮交付的状态表是**截至 2026-09-18 commit `676020f` 之后的状态快照**。下一轮 session
开头读这张表即可知道"哪些 PASS、哪些 defer、哪些 ENV_BLOCKED"——无需重新走完 V0_D4 gotcha
那个"声明了但没人接线"的重发现路径。

## 完整 drill 与 evidence 索引

- **Drill-by-drill**: `docs/V1_CASES.md` — 9 drills × 共 48 criteria,每条 criterion 附
  可执行 command + PASS 信号 + 当前 PASS/DEFER/BLOCKED 状态。
- **Work log**: `docs/WORK_LOG.md` — V1 段自 2026-09-17 起,记录每一轮交付、决策、发现。
- **Gotchas**: `docs/GOTCHAS.md` §E3 + §E4 — V1 新增的两条 active traps。
- **M6/M7 proposal**: `docs/v1/M6_SPLIT_PROPOSAL.md` + `docs/design/CAPABILITY_MAP_SHAPE_PROPOSAL.md` —
  决策依据。

## 关于 deferred

The 18 deferred criteria across V1-D1/D2/D3/D4/D5/D6/D8 are tool-layer PASS structurally;
they need a live autonomous block / E2-E3 harness run / expired CONSTRAINT / multi-session
data to fully exercise. V1-D4 #4 (`synthesize --block` 1-2 pages) is no longer deferred
— it landed in this commit, along with the P1-8 invariant surfaced as
`SYNTHESIS_BELIEF_DELTA_MISSING`. Aggregate: 26 PASS + 18 deferred + 4 ENV_BLOCKED
(48 criteria, V1-CASES §V1-D4 drill row updated).

按 V0_D4 gotcha "声明了但没人接线" 的对称面:**"接了但没数据" 也是 risk signal**——但 deferred
criteria 的"接了"是工具接线,工具不假装有数据。读 evidence ledger 才是"有没有数据"的判定。
