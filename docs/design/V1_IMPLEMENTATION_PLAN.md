# V1 实施方案:Autonomous Research Batches

> 本文档**不是** V1 的代码实现,也不是 V0 验收清单的延伸。  
> 本文档是 **V1 启动前的整体方案**:V0 → V1 交接面、入场费、26 条 §20.2 增加项的实施矩阵、验收清单、工作分解、风险、drill 草图。

## 0. 文档目的与受众

| 维度 | 说明 |
|---|---|
| 目的 | 让架构师能在一份文件里评审 V1 怎么落地、决策点已决断到哪、风险/坑在何处、谁先做谁后做 |
| 受众 | 架构师(决策)、后续 session(执行时直接照跑)、外部 reader(理解 V0→V1 跃迁) |
| 与 V0_ACCEPTANCE_GUIDE.md 的关系 | 同模板、同语言(中文)、同章节拆判据;本文件**不**复制 V0_ACCEPTANCE_GUIDE,**只**定义 V1 的部分 |
| 与 WORK_LOG.md 的关系 | WORK_LOG 记"做过什么",本文档记"还没做但要怎么做";两者互补不重叠 |
| 与设计文档 §20.2 的关系 | §20.2 是"要加什么"(26 条);本文档回答"按什么顺序、由谁、验什么、回滚什么" |
| 评判标准 | (1) 100% 覆盖 §20.2 26 条;(2) V0 收尾 24 条开放项每条有处置;(3) 决策点前置 + 归属明确;(4) 工作分解为 bounded blocks;(5) 风险表对位 GOTCHAS |
| **不**做什么 | 不写代码、不动 canonical state、不 commit(架构师评审通过后才 commit) |

---

## 1. V0 → V1 交接面

### 1.1 V0 留下来(V1 直接继承,不改)

| 面 | 资产 | 文件 |
|---|---|---|
| **CLI 工具** | `tools/researchlog/` 15 subcommand + `ioutil.py`(§12.17 atomic write)+ `ids.py`(collision-resistant ID)+ `errors.py` 退出码 0/2/3/4/5 | `tools/researchlog/commands/`、`tools/researchlog/{ioutil,ids,errors,jgit,model,repo,state,predicate}.py` |
| **Schema** | 7 个 schema:`active` / `evidence` / `manifest` / `findings-entry` / `current` / `environment` / `boundaries` | `tools/researchlog/schemas/*.schema.json`(均 1.0)|
| **核心不变量** | `NON_SCIENTIFIC_EXECUTION` 不配 `confirmed/refuted`;`counts_as_evidence_iteration` 派生;`SCHEMA_NEWER_REFUSED` 拒写;`reconcile` 不修复 / `run` exit 0 不代表实验成功 / `snapshot` 默认不写盘 / `--kill` 不存在 | `tools/researchlog/constraints.py`、`tools/researchlog/schema/registry.py` |
| **Skills** | 3 个:`research-bootstrap`、`research-engineering`、`research-status`;**11 个 reference**(8 类 router 触发) | `.claude/skills/research-*/SKILL.md` + `references/*.md` |
| **Drills** | 4 个 drill + 4 builder + `run_case.sh` + `verify_case.py`(25 条判据,裁判已钉)+ `check_negative_control.sh`(零成本闸门) | `tests/main/{build_*.sh,run_case.sh,verify_case.py,check_negative_control.sh}` |
| **GOTCHAS(state,不是 log)** | 35 条当前为真的坑:A1-A4 / B1-B15 / C1-C9 / D1-D4 / E1-E2 | `docs/GOTCHAS.md` |
| **V0 验收** | 21/21 ✅ + 1 footnote;Day-1 must 5 / V0 complete 16 | `docs/V0_ACCEPTANCE_GUIDE.md` |
| **工程轨记录** | 双轨道分工:`research/` 是被服务的研究的状态,`docs/WORK_LOG.md` 是工具开发记录 | `docs/WORK_LOG.md`、`AGENTS.md` 双轨道段 |

### 1.2 V0 升级 / 替换(V1 引入新版本)

| 面 | V0 → V1 | 触发决断 |
|---|---|---|
| **Evidence ledger** | 单 jsonl → `research/ledger/EV-*.json` sharded(已实装,见 `state.py::_load_shards`)| T2 partition 决策:YYYY-MM / by-block / flat |
| **Block size** | 2-3 evidence iteration → 3-8 evidence iteration | §20.2 L2214;`max_evidence_iterations` 参数升级 |
| **`research/STATUS.md`** | optional,default absent → 可写里程碑缓存 + stale-detection 自动告警 | T3 新增 writer + reconcile consumer |
| **environment capability_map** | 仅声明(空 shape)→ V1 必须有 schema | **P4 决断已定**:委托 Agent 起草,Architect 评审 |
| **`max_evidence_iterations` 含义** | 只计 counted evidence → reproduction 不计 budget(独立分桶) | **P2 决断已定**:分桶 |
| **session 必须 commit** | 不要求 → 强制 commit(record evidence 后) | **P1 决断已定**:强制 |
| **`record` reject 消息** | code + subject only → code + message + fix_hint | **P8 决断已定**:加 message + fix_hint |
| **`run.py` heartbeat** | session 自愿 → run 默认 30s heartbeat | **P7 决断已定**:强制 |
| **`--replace-existing`** | 允许(静默覆盖)→ 禁(只能 finalize 后重跑) | **P6 决断已定**:禁 |
| **ARCHITECT signals** | 仅 CONSTRAINT 有 scope/expiry → 全部 8 类 signal 加 history + scope + expiry | **P5 决断已定**:全部 |
| **worktree 写 research/*** | session 自决 → single-writer(只一个 worktree 可写) | **P9 决断已定**:single-writer |

### 1.3 V0 删(若有,V1 移除)

V1 不删 V0 任何资产。**所有 V0 实装的 21 项 §20.2 增加项继续工作**;V1 = 加法,**不是覆盖**。  
例外:`research/ENVIRONMENT.md` 的 `comparability.fingerprint: null` 会在 T4 实装后被自动填值,但**字段定义不变**。

---

## 2. V1 入场费(V1 开始前必须解决)

**15 条**:9 条 protocol(已全部决断)+ 5 条 tool + 1 条 skill(都已列出决断方向)。

### 2.1 Protocol 层(已全部决断,本节记录决断与落地形态)

| ID | 决断 | 落地形态 | 阻塞范围 |
|---|---|---|---|
| **P1** | 强制 commit | `record` 命令:写完 evidence 后自动 `git add research/ledger/EV-*.json research/ACTIVE.json` + `git commit -m "research: EV-..."`(`record` 走 atomic write + commit,见 Block 1.1)| §20.2 §20/§22(同步 pipeline、baseline tag)、T2 ledger code identity |
| **P2** | reproduction 分桶 | ACTIVE.block 加 `reproduction_iterations` 字段;`record --iteration-kind reproduction` 不计 evidence budget | §20.2 §1(bounded blocks 真正"bounded")|
| **P3** | 不决断,列现状与风险 | 文档 §6.2 列现状(协议无 session→ACTIVE liveness)与 V1 监控信号;Block 5 实跑期间持续观测 | 留 V1.5 评估(§20.3 V2 中有 stagnation detection 邻接) |
| **P4** | Agent 起草,Architect 评审 | Block 1.5 出 shape proposal,经 Architect 一票通过后落 `environment.schema.json` | §20.2 §22(Research Capability Map)、S1(`evaluation-design` skill)|
| **P5** | 全部 signal 加 history/scope/expiry | `ARCHITECT.md` schema 升级:`scope`/`expiry` 必填(所有 8 类),`history` 字段记录 supersede;`reconcile` 加 `EXPIRED_ARCHITECT_SIGNAL` 检查 | §20.2 §20(ARCHITECT signal history)、S2 |
| **P6** | 禁 `--replace-existing` | `run.py` 删 `--replace-existing`;`--refuse-running` 行为保留 | §22 ARCHITECT signal 与 long-running 一致 |
| **P7** | 强制 heartbeat(30s 默认)| `run.py` 在子进程 supervise 中每 30s 调 `manifest --heartbeat`;`ACTIVE.execution.heartbeat_or_last_observed_at` 跟着更新 | §12.16 D2 判据 5 自动满足;§22 long-running job ownership |
| **P8** | 加 message + fix_hint | `errors.py::Finding` 加 `message` + `fix_hint` 字段;所有现有 reject 路径补字段 | §20.2 §21(telemetry 集成)| 
| **P9** | single-writer | `reconcile` 加 `WORKTREE_MULTI_WRITER` 检测:发现多个 worktree dirty `research/*` 时报 hard finding | §20.2 §19(worktree for risky/parallel)|

**说明**:P1/P2/P5/P6/P7/P8/P9 = 7 条实装(Block 1 主体);P4 = 1 条 shape proposal(Block 1.5);P3 = 0 条实装,只观察。

### 2.2 Tool 层(Block 2,PROVISIONAL 边界)

| ID | 一句话 | 决断方向 |
|---|---|---|
| **T1** | `env record` 覆盖 harness/limitation 表 | `env record FILE` 增加 `--harness` / `--limitation` flag,直接写 `limitations[]` / `harnesses[]`(现 `env declare` 已能写,T1 = 收口 `record` 路径)|
| **T2** | sharded ledger partition | 三选一:`YYYY-MM/`(按月)vs `by-block/<block-id>/`(按 bloc)vs `flat/`(单层)。**默认 YYYY-MM**,partition migration 写在 `state.py::_load_shards` 中(已在)|
| **T3** | `STATUS.md` writer | 新增 `researchlog status --write PATH`;`STATUS.md` 头部必须 `DERIVED SNAPSHOT — NOT SOURCE OF TRUTH`;`reconcile` 加 stale-detection(`last_modified > latest_evidence_modified` 报 `STATUS_STALE`)|
| **T4** | fingerprint/rebaseline | `predicate.py` 填实,`record` 的 `changed` 谓词不再永远 `UNRESOLVED`(GOTCHAS A4);新增 `researchlog env rebaseline` 强制更新 fingerprint |
| **T5** | productivity telemetry | 从 `max_tokens` only 扩到 §21 KPI 全表(`Time-to-first-E1` / `Time-to-first-E3` / `Session Recovery Accuracy` / `Discriminating-Experiment Without Architect Correction`);新增 `researchlog telemetry report` 命令 |
| **T6** | record-validator 边界 | 新增 `record --validate-line` 选项,把"单条 record 合法"和"该 run 产出足够 evidence"两件事分开报;V1 验收 §20.2 §15(parallel writer)走这条 |

### 2.3 Skill 层(Block 3)

| ID | 一句话 | 决断方向 |
|---|---|---|
| **S1** | 五 expert skills 重组 | 把 V0 router 里散落的 5 个 reference 重组为独立 skill folder,各自 `SKILL.md`:**`research-search` / `evaluation-design` / `experiment-review` / `retrospective` / `scenario-redteam`**;`tools/install_research_skills.py --self` 注册 |
| **S2** | source-text schema 强制(合并 P5)| 同 P5;`ARCHITECT.md` schema 升级一并处理 |

---

## 3. §20.2 实施矩阵(26 条对位)

`/tmp/research-v1/design.md` L2210–2230 共 26 条。V0 已实装 21 条,partial 5 条,missing 1 条。

### 3.1 主表

| # | §20.2 项 | V0 状态 | V1 行动 | 验收 drill |
|---|---|---|---|---|
| 1 | 3-8 evidence iteration bounded blocks | real | **不**改语义,只把 P1/P2 的新约束接进 block 字段 | V1-D3 |
| 2 | `research-search` skill | partial | **S1**:重组独立 skill folder,SKILL.md 写明"在 E0/E1 触发"(对应 V0 `retrospective.md` 的 Reopening search space)| V1-D9(claude × pi 各跑通)|
| 3 | `evaluation-design` skill | real | **不**改;V0 router 已触发;S1 = 重组独立 folder | V1-D9 |
| 4 | `experiment-review` skill | real | **不**改;S1 = 重组独立 folder | V1-D9 |
| 5 | `retrospective` skill | real | **不**改;S1 = 重组独立 folder | V1-D9 |
| 6 | `scenario-redteam` skill | partial | **S1**:重组独立 skill folder;从 `experiment-review.md` 的 After a promising result 抽出 red-team checklist | V1-D9 |
| 7 | `research-status` snapshot integrity check | real | **不**改;`reconcile --json` exit code 已是 4 source of truth | V1-D4(扩展到 §T3)|
| 8 | `research-status` frontier/status compression | real | **不**改;14 节 Project Working Model 已是 source | V1-D4 |
| 9 | optional `STATUS.md` milestone cache | partial | **T3**:新增 `researchlog status --write PATH` | V1-D4 |
| 10 | sharded immutable ledger | real | **T2**:partition 决策 YYYY-MM;`state.py::_load_shards` 已实装 | V1-D1 |
| 11 | E2/E3 replay contract | real | **不**改;`compare.py` 已实装(V0 #14 通过)| V1-D2 |
| 12 | worktree for risky/parallel | partial | **P9 决断**:single-writer;`reconcile` 加 `WORKTREE_MULTI_WRITER`;`tools/researchlog/jgit.py` 已 worktree-aware | V1-D5 |
| 13 | ARCHITECT signal history / scope / expiry | real(P5 扩) | **P5 决断**:全部 signal 加 history + scope + expiry | V1-D8 |
| 14 | 轻量自动 synthesis | missing | **新增**:`researchlog synthesize --block BLOCK_ID` 收 block 时出 1-2 页结构化 synthesis(架构师可读)| V1-D4 |
| 15 | 研究 productivity telemetry | partial | **T5**:从 max_tokens 扩到 §21 KPI 全表 | V1-D6 |
| 16 | environment fingerprint / rebaseline policy | real | **T4**:predicate 填实 + 新 `researchlog env rebaseline` | V1-D7 |
| 17 | Research Capability Map 与 harness 投资判断 | real(P4 扩) | **P4 决断**:Agent 起草 shape,Architect 评审;shape 字段 ≥3,include `reuse_counter` | V1-D7 |
| 18 | `ACTIVE.json` + write-ahead state + run manifests | real | **不**改;`ioutil.write_json_atomic` 已实装 | V1-D3 |
| 19 | Session Rotation / Resume / reconciliation | real | **不**改;rotation-policy 走 SKILL.md prose | V1-D3 |
| 20 | Git research transaction / checkpoint commit / baseline tags | real | **不**改;`checkpoint.py` 已实装 | V1-D3 |
| 21 | optional GitHub remote + manual Gate-3 verifier | partial | **新增**:`docs/verification/gate-3.md` 模板 + 文档说明;`researchlog checkpoint --baseline-tag` 加 `--gh-status` flag(GitHub Actions 集成,可选)| V1-D9 |
| 22 | schema migration/validation | real | **不**改;`SCHEMA_NEWER_REFUSED` 已实装 | V1-D1(ledger 验证)|
| 23 | atomic canonical-state writes | real | **不**改;`write_json_atomic` 已实装 | V1-D1 |
| 24 | long-running job ownership | real | **P7 决断**:run 默认 30s heartbeat | V1-D3 + D9 |
| 25 | mutable-input lineage | real | **不**改;`compare.py` 已实装 | V1-D2 |
| 26 | evaluation surface calibration | real | **不**改;`compare` + `env record` 已实装 | V1-D7 |

### 3.2 19 条 "接 V0 + 验新判据"

| 类别 | 项 | V1 行动 = 验新判据 |
|---|---|---|
| 块 / Resume / Reconciliation | 1, 18, 19, 20, 24 | V1-D3(7 条判据)|
| ledger / schema / atomic | 10, 22, 23 | V1-D1(7 条判据)|
| E2/E3 + mut-input | 11, 25 | V1-D2(6 条判据)|
| status 完整性 | 7, 8 | V1-D4(扩到 T3)|
| environment / capability | 16, 17, 26 | V1-D7(6 条判据)|
| skills 重组后 trigger | 3, 4, 5 | V1-D9(claude × pi 各跑通)|

### 3.3 7 条 "新造"

| §20.2 | 新造什么 | block |
|---|---|---|
| §2 | `research-search/SKILL.md` | Block 3 |
| §6 | `scenario-redteam/SKILL.md` | Block 3 |
| §9 | `researchlog status --write` | Block 2 |
| §14 | `researchlog synthesize` | Block 2 |
| §15 | `researchlog telemetry report` | Block 2 |
| §21 | `docs/verification/gate-3.md` + `--gh-status` flag | Block 2 + 3 |
| §16 | `researchlog env rebaseline` | Block 2 |

---

## 4. V1 验收清单

**沿用 V0 拆分判据**(V0_ACCEPTANCE_GUIDE.md §Day-1 must):
> 不成立时,"项目已进入 V1 业务"这句话不成立 → Day-N must;其余 → V1 complete。

### 4.1 Day-N must(7 条,以下为拟稿,需 Architect 确认)

| # | 验收 | 通过判据 |
|---|---|---|
| **M1** | 全新 repo 能进入 V1(V0 业务不写出 V1 才有的机制也能跑)| 空目录 `bootstrap` → V0 21/21 仍成立 |
| **M2** | 协议无 commit 漏洞下,V1 不退化到 V0 21 行状态 | 强制 commit 后,claude × pi 跑同一 fixture,都产出 `code_state.commit` 与 record evidence 同步 |
| **M3** | sharded ledger + E2/E3 replay + environment fingerprint 三件套端到端连通 | V1-D1 + V1-D2 + V1-D7 全过 |
| **M4** | bounded autonomous block 跨 session 跑通:3-8 迭代 + 跨 session 不重启动 + reproduction 不被 budget 卡死 | V1-D3 全过(P1 + P2 + P7 + P9 决断的产物)|
| **M5** | snapshot integrity + frontier compression + synthesis 联合生效,产出的 `STATUS.md` 与 `reconcile` 一致 | V1-D4 全过(P5 + §14 决断的产物)|
| **M6** | 五 expert skill 在 router 里**真实**可达(不是"理论上可加载"),claude 与 pi 各跑通 ≥3 case | V1-D9 全过(S1 重组的产物)|
| **M7** | 与 V0 同形态"两客户端矩阵":claude × pi 在 V1 同一版仪器上 V1 case 全过 | V1-D9 全过(类比 #1 / #22 V1 版)|

### 4.2 V1 complete(16 条,以下为拟稿)

| # | 验收 | 通过判据 |
|---|---|---|
| **#1** | Research Capability Map 真实可写、real entries ≥3 | V1-D7 |
| **#2** | 高复用 harness 投资判断:reuse_counter 字段存在 + ≥3 | V1-D7 |
| **#3** | productivity telemetry 全表可查(§21 KPI) | V1-D6 |
| **#4** | `STATUS.md` milestone cache 可写 + stale-detection 自动告警 | V1-D4 |
| **#5** | GitHub remote 可选集成(`--gh-status` 不报错)| V1-D9 |
| **#6** | manual Gate-3 verifier 文档完整,可走通一个完整流程 | V1-D9 |
| **#7** | worktree single-writer enforcement | V1-D5 |
| **#8** | `record` reject message 可读,`fix_hint` 实际可执行 | V1-D8 |
| **#9** | sharded ledger partition migration 测试通过 | V1-D1 |
| **#10** | reproduction 分桶不污染 evidence budget | V1-D3 |
| **#11** | session 必须 commit;未 commit 的 record 报告 `COMMIT_REQUIRED` | V1-D3 |
| **#12** | run 默认 heartbeat,30s 内必见 | V1-D3 |
| **#13** | 全部 ARCHITECT signal 加 history + scope + expiry | V1-D8 |
| **#14** | `synthesize --block` 出 1-2 页结构化 synthesis | V1-D4 |
| **#15** | long-running 跨 session + rotate 不重复启动 | V1-D3 |
| **#16** | `--replace-existing` flag 移除,文档明确警告 | V1-D3 |

---

## 5. 工作分解:bounded blocks

每块 = 一个会话 / 一个 PR 的可独立单元,带 objective / max_iterations / max_wall_clock / stop_conditions / rollback。

### Block 1 — 协议层决断封口(P1/P2/P4/P5/P6/P7/P8/P9)

| 维度 | 内容 |
|---|---|
| **objective** | 把 8 条 protocol 层落地到 `AGENTS.md` + 必要时新增 schema/字段 |
| **max_iterations** | 8(每条 1 iter)|
| **max_wall_clock** | 90 min |
| **stop_conditions** | Architect reject / hard veto / 其他 6 条决断阻塞 |
| **rollback** | `AGENTS.md` 改动 commit revert;`schemas/*.schema.json` 改字段即 migration,需 `tools/researchlog/schema/registry.py` 加新 migration 条目 |
| **依赖** | 无 |
| **输出** | `AGENTS.md` 修改 + (P4)`environment.schema.json` capability_map 字段扩展 + (P5)`ARCHITECT.md` schema 升级 + commit 文档 |
| **不**包含 | 任何工具 / skill 改动 |
| **sub-block** | 1.1 P1 record-after-commit;1.2 P2 reproduction 分桶 schema;1.3 P5 signals 升级;1.4 P6 禁 `--replace-existing`;1.5 P4 capability_map shape proposal;1.6 P7 run 默认 heartbeat;1.7 P8 reject message 字段;1.8 P9 worktree single-writer reconcile |

### Block 2 — Tool 入场费(T1/T2/T3/T4/T5/T6)

| 维度 | 内容 |
|---|---|
| **objective** | 把 6 条 tool-layer 落地到 `tools/researchlog/` |
| **max_iterations** | 6 |
| **max_wall_clock** | 180 min |
| **stop_conditions** | reconcile/validate 持续 failing / 与 Block 1 决断冲突 |
| **rollback** | 每个 subcommand 单文件 revert;`STATUS.md` cache 失效可重建 |
| **依赖** | Block 1 完成(尤其 P1/P2/P4)|
| **输出** | `commands/{env,status,synthesize,telemetry,compare}.py` 扩展;`predicate.py` 已填实;`schemas/` 视情况新增 |
| **sub-block** | 2.1 T1 env record 覆盖 harness/limitation;2.2 T2 sharded ledger partition YYYY-MM;2.3 T3 STATUS.md writer;2.4 T4 fingerprint/rebaseline;2.5 T5 productivity telemetry;2.6 T6 record-validator line 边界 |

### Block 3 — Skill 重组(S1) + Gate-3 文档(S2)

| 维度 | 内容 |
|---|---|
| **objective** | 把 V0 router 里散落的 reference 重组为 5 个独立 skill + source-text schema 强制 + Gate-3 verifier 文档 |
| **max_iterations** | 5 + 1 = 6 |
| **max_wall_clock** | 240 min |
| **stop_conditions** | router table 双向 reconcile 不通 / install_research_skills --check exit ≠0 |
| **rollback** | `tools/install_research_skills.py --self` 重新生成 client-side skill;`skills/<name>/SKILL.md` 单文件 revert |
| **依赖** | Block 1(P5 信号)|
| **验证** | 每个 skill 至少在 claude × 1 case / pi × 1 case 触发 |
| **sub-block** | 3.1 research-search;3.2 experiment-review;3.3 retrospective;3.4 scenario-redteam;3.5 evaluation-design;3.6 Gate-3 文档 + `--gh-status` flag |

### Block 4 — Drill 套件(V1 验收演练)

| 维度 | 内容 |
|---|---|
| **objective** | 为 V1 day-N must / V1 complete 每条写至少 1 个可执行 drill,沿 V0 `run_case.sh` + `verify_case.py` 模板 |
| **max_iterations** | 16(条目数)|
| **max_wall_clock** | 360 min |
| **输出** | `tests/main/build_v1_*.sh` + `verify_case.py` 加新 `V1_*` 列表 + `check_negative_control.sh` 扩展 |
| **依赖** | Block 1 + Block 2 + Block 3 |

### Block 5 — V1 实跑(KPI 落地)

| 维度 | 内容 |
|---|---|
| **objective** | 在 V1 全套机制下跑一次真实研究,把"无需 Architect 纠正率"作为单一可证 KPI 落地 |
| **max_iterations** | 3-8(per §20.2)|
| **max_wall_clock** | 480 min |
| **stop_conditions** | KPI 跑出可证数字 / 出现 P3 类信号(留观察,不 block)|
| **依赖** | Block 4 |
| **KPI 计算** | `researchlog telemetry report` 输出 `Discriminating-Experiment Without Architect Correction` 字段 |

### Block 6 — V1 收尾(ACCEPTANCE_GUIDE 写、状态表填、V2 同步)

| 维度 | 内容 |
|---|---|
| **objective** | 把 V1 全套验收落到 `docs/design/V1_ACCEPTANCE_GUIDE.md`,与 V0_ACCEPTANCE_GUIDE 同模板 |
| **max_iterations** | 1(单一文档)|
| **max_wall_clock** | 120 min |
| **依赖** | Block 5 |

---

## 6. 风险表(GOTCHAS 对应 + 未写入的洞)

### 6.1 V0 GOTCHAS 中会复发的

| 坑 | 哪条 Block 会触发 | 监控信号 |
|---|---|---|
| **A3** "没有动词 = 没有校验" | Block 2(T1/T3/T4/T5 全是新 verb)| 每个新 verb 必须配套 `validate.py` hook;`grep -rn 'paths.<name>' tools/researchlog/ --include='*.py'` 应非零 |
| **B1** "fixture 自断言两条铁律" | Block 4(10 个 V1 drill)| 每个 builder 自断言 + 变异验证 |
| **B11** "检查器答隔壁问题" | Block 4(V1 16 条新判据)| 每条判据变异验证 + 负对照闸门 `check_negative_control.sh` 扩展 |
| **B14** "判 session 留下的产物" | Block 4 + Block 5 | `verify_case.py` 同时支持 transcript 路径(claude)与 session log 路径(pi)|
| **E2** "跑全量前必须问 Architect" | Block 4 矩阵跑前 / Block 5 全跑前 | 跑前 AskUserQuestion |
| **D3** workflow block drift check | Block 1(改 `AGENTS.md`)| 跑 `tools/check_workflow_block.py` exit 0 |
| **D4** `pi` skill 路径 | Block 3 + Block 4(claude × pi 矩阵)| `pi --skill` 用绝对路径;`pi auth check` ready ≠ 凭据有效,需先 curl 一次 |

### 6.2 V1 独有风险(从 §20.2 派生,未写入 GOTCHAS)

| 风险 | 来源 | 监控信号 |
|---|---|---|
| **多 worktree 写 canonical 文件 conflict**(即使 P9 single-writer,跨 session rotate 后第一秒)| §20.2 L2219 | reconcile `WORKTREE_MULTI_WRITER` 触发即 block |
| **跨 session 的 long-running 实验在 schema migration 时被静默丢** | §12.17 | `state.py::_load_shards` 在 partition migration 前后比对 ledger 总数 |
| **`STATUS.md` cache 漂移** | T3 | reconcile `STATUS_STALE` finding;cache 必须自带 `last_evidence_modified` 字段 |
| **productivity telemetry 跨 client 形状不同** | §21 + D4 | telemetry writer 用 `state.py::Ledger.supporting()` 抽同一 source,不直接读 client log |
| **P3 idle-while-running 期间 session 崩溃** | §20.2 L2229 | manifest `running` 无 result 时,reconcile 自动报 `MANIFEST_STALE_RUNNING`(V0 已修,但 V1 长跑会复发)|
| **record-after-commit 在某些 hosting 下不可用(如 detached worktree)** | P1 | `git status --porcelain` 提前检查,`record` 报 `COMMIT_FAILED` 给出原因 |

---

## 7. 验收演练草图(V1 drill 套件,Block 4 实装)

沿 V0 D1/D2/D3/D4 同形,每个 = 一个 `build_v1_*.sh` + `verify_case.py` 中一组 `V1_*` 判据。

| Drill | 目标 | 关键判据数 | 走 P 决断 |
|---|---|---|---|
| **V1-D1** | Sharded ledger partition | 7:partition 选择 / ID uniqueness / 跨分片 compare / partition migration / EV-IDs 全互异 / ledger 总数前后一致 / `--from-orphan` 跨分片可写 | T2 |
| **V1-D2** | E2/E3 replay contract | 6:record 与 replay 端到端连通 / identity stable / `compare` ATTRIBUTION_FORBIDDEN 触发 / mutable-input lineage 延伸到 E3 | (无)|
| **V1-D3** | Bounded autonomous block 跨 session | 7:3-8 iter 触发 `BLOCK_ITERATION_BUDGET_EXCEEDED` / session rotate 不重启动 / reproduction 不计 budget / record-after-commit 落 git / run 默认 30s heartbeat / `--replace-existing` 被拒 / 跨 session `reconcile` exit 0 | P1 P2 P6 P7 |
| **V1-D4** | `STATUS.md` snapshot integrity + cache + stale-detection + synthesis | 5:write 成功 / 头部 `DERIVED SNAPSHOT — NOT SOURCE OF TRUTH` / stale-detection 触发 / `synthesize --block` 出 1-2 页 / reconcile 一致 | P5 + §14 |
| **V1-D5** | Worktree single-writer enforcement | 5:单 worktree 写合法 / 多 worktree 写报 `WORKTREE_MULTI_WRITER` / rotate 后第一秒合法 / detached worktree 不被拒 / reconcile exit 0 | P9 |
| **V1-D6** | Productivity telemetry | 4:`Time-to-first-E1` 可查 / `Time-to-first-E3` 可查 / `Session Recovery Accuracy` 可查 / 跨 session 累计正确 | T5 |
| **V1-D7** | Research Capability Map + harness 投资判断 | 6:capability_map shape 通过 schema / ≥3 entries 写入 / reuse_counter 字段存在 / `harness declare` 合法 / `env rebaseline` 触发 fingerprint 变 / `changed` 谓词不再永远 `UNRESOLVED` | P4 + T1 + T4 |
| **V1-D8** | Source-text enforcement + signals 升级 | 4:全部 signal 加 history + scope + expiry / CONSTRAINT 过期 inspect 报 `EXPIRED_ARCHITECT_SIGNAL` / reject message 可读 / `fix_hint` 实际可执行 | P5 + P8 |
| **V1-D9** | 客户端矩阵(claude × pi)| 沿 V0 #1 / #22 形态,改 V1 case | (无)|

每个 drill 自检(B1)+ 钉住裁判(沿 V0 模式)+ 负对照闸门(V1 扩 `check_negative_control.sh`)。

---

## 8. 与 V0 的交接面(精炼版)

| 维度 | V0 留下 | V1 改 |
|---|---|---|
| 协议契约 | AGENTS.md 第 1-13 节 | P1/P2/P5/P6/P7/P9 改 §Authority / §Workflow control / §Core invariants 中的若干行 |
| 工具面 | 15 subcommand + 7 schema | Block 2 加 4 verb(env rebaseline / status --write / synthesize --block / telemetry report);Block 1 改 `record` / `run` 行为 |
| Skill 面 | 3 skill + 11 reference | Block 3 把 5 个 reference 重组为独立 skill;V1 后共 8 skill |
| Drill 套 | 4 drill + 25 判据 | Block 4 加 9 drill + 44 判据 |
| 文档 | V0_ACCEPTANCE_GUIDE / WORK_LOG / GOTCHAS / V0_CASES | Block 6 加 V1_ACCEPTANCE_GUIDE;WORK_LOG 加 V1 段;GOTCHAS 加 V1 独有 §6.2 那批;V1_CASES.md 加 drill 套说明 |

---

## 9. 不做(留 §20 + §1.x)

V1 明确**不**做(原文 §1.4 / §20.3):

- 多 Agent Server
- 工作流 DAG / 队列 / daemon
- MLflow 替代品
- 全项目自动 CI 平台
- 每次变更自动完整回归
- 3-5 个 active mechanism / architecture branches(V2)
- stagnation detection(V2)
- frontier diversity(V2)
- parallel worktrees / read-heavy subagents(V2)
- stronger evaluator isolation(V2)
- official score budget policy(V2)
- ShinkaEvolve 等 E2+ scoped optimizer(V2)
- promotion verifier(V2)
- Integration Mode profile(V2)

---

## 附录 A:决断记录(架构师 2026-04-XX)

| ID | 决断 | 选择 | 含义 |
|---|---|---|---|
| P1 | session 必须 commit | **强制 commit** | `record` 自动 commit;`AGENTS.md` 加约束 |
| P2 | reproduction 分桶 | **分桶** | `ACTIVE.block.reproduction_iterations` |
| P3 | idle-while-running | **不决断,列现状与风险** | §6.2 监控 |
| P4 | capability_map 形状 | **Agent 起草,Architect 评审** | Block 1.5 出 proposal |
| P5 | signals 扩展 | **全部 signal 加 history + scope + expiry** | Block 1.3 |
| P6 | stale overwrite | **禁 `--replace-existing`** | Block 1.1(同 P1 sub-block)|
| P7 | heartbeat 协议 | **强制:所有 run 默认 30s heartbeat** | Block 1.6 |
| P8 | reject 消息 | **加 message + fix_hint** | Block 1.7 |
| P9 | worktree 写入 | **single-writer** | Block 1.8 |

---

## 附录 A.1:P5 的 sub-decision(已发现待 Architect 二次澄清)

**问题**:附录 A 把 P5 决断措辞为"全部 signal 加 history + scope + expiry"。但 V0 的 `test_constraints.py::SignalTests::test_only_a_constraint_needs_scope_and_expiry` **明确**断言"VETO 永久直到被废止,不需要 scope/expiry"——即 V0 的协议语义是 **CONSTRAINT 才需要 scope/expiry**。

§20.2 L2220 原文是 "ARCHITECT signal history / scope / expiry"——是机制升级的承诺,**不是**对每条 signal 都强制的字段。

**Architect 在 AskUserQuestion 看到的选项**是"全部 signal 都加 history + scope + expiry",可能误读为"机制升级",选了它。但落到代码层,这意味着:

| 信号类型 | V0 协议 | P5 实装(若按"全部")| 张力 |
|---|---|---|---|
| CONSTRAINT | scope/expiry 必填 | scope/expiry 必填 | 同 |
| DECISION | source_text 必填,scope/expiry 无 | scope/expiry 必填 | **新** —— DECISION 何时过期? |
| VETO | 无 scope/expiry(永久)| scope/expiry 必填 | **新** —— 与"永久直到废止"语义冲突 |
| IMPLEMENT | 无 | scope/expiry 必填 | **新** —— IMPLEMENT 何时过期? |
| OBSERVE/SUSPECT/DIRECTION/CHALLENGE | 无 | scope/expiry 必填 | **新** —— observation 何时过期? |

**澄清请求**(Block 1.3 实装前必须 Architect 答):

- **选项 a**:P5 = **机制升级**。`history[]` 字段**可选**加入(空 list 合法);`scope`/`expiry` 仍**仅 CONSTRAINT 必填**(V0 不变)。`history` 是 P5 真正的产出。
- **选项 b**:P5 = **强制升级**。CONSTRAINT/DECISION/VETO 必须加 scope/expiry(history 可选);其他 5 类 signal 不变。
- **选项 c**:P5 = **全部强制**(原始 P5 选项的字面解读)。DECISION/VETO/其他 6 类都加 scope/expiry。**意味着 V0 测试要改**(`test_only_a_constraint_needs_scope_and_expiry` 被推翻)。

**现状**:此 sub-decision 阻塞 Block 1.3。其余 7 条 Block 1 sub-block 不受影响。

---

## 附录 B:与 V0_ACCEPTANCE_GUIDE 的差异

| 维度 | V0_ACCEPTANCE_GUIDE | V1_IMPLEMENTATION_PLAN |
|---|---|---|
| 性质 | 验收清单(已完成 21/21) | 实施方案(尚未开始)|
| Day-N must | 5 条(M1-M5)| 7 条(M1-M7,草案)|
| V1 complete | 16 条(已全部 ✅)| 16 条(待开始)|
| Bounded blocks | (V0 已实施,不列)| 6 块(Block 1-6)|
| 决策点 | (V0 决断已落地)| 9 条 protocol 决策(已附)|
| Drills | 4 个(D1-D4)| 9 个(V1-D1..V1-D9)|
| 风险表 | (V0 收尾时已收敛)| 6 + 6 = 12 条(V0 复发 + V1 独有)|

---

## 附录 C:文档自查清单(写完后)

- [ ] §2.1 9 条 protocol 决断全部填入(含决策理由 + 落地形态)
- [ ] §3.1 26 条 §20.2 增加项全部出现
- [ ] §4 Day-N must 7 条 + V1 complete 16 条
- [ ] §5 Block 1-6 全部含 objective / max_iterations / max_wall_clock / stop_conditions / rollback
- [ ] §6 风险表每条对应 GOTCHAS §ID 或 §6.2 独有项
- [ ] §7 V1-D1..V1-D9 9 drill 全部出现
- [ ] §8 交接面 5 维度全列
- [ ] §9 不做 13 条与设计文档 §1.4 / §20.3 一致
- [ ] 附录 A 决断表 9 行
- [ ] 附录 B 差异表
- [ ] 附录 C 自查清单(此清单)

---

**状态**:本文档已完成初稿,**等待架构师评审**。  
评审通过后:commit + 更新 `docs/WORK_LOG.md` 加 V1 启动 entry + 启动 Block 1。