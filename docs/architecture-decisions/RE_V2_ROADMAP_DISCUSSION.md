# RE V2 Roadmap — 完整架构决策讨论锚点

**日期**：2026-09-20
**状态**：讨论中（未决议）—— 本轮已读 V1.5 设计 PDF §4/§5/§17/§21 + Iteris 实际代码（UI server / commands/ui.py / agents/{explore,execute}.py / supervision/engine.py / profiles/evolve.py）+ RE 协议本体工具代码（repo.py / commands/19 个 verb / 6 个 schema）
**Architect handoff 输入**：
1. Iteris 调度 + Dashboard 是真需要（dashboard 用于长跑时 Architect 看见 AI 在干什么）
2. 实战题目已 ready（`~/sandbox/competitions-2026/Embodied-Safety-Application-Challenge`，20+ 天 docs 完整）
3. AI 基本理解前两轮有偏差，已重置
4. **RE 协议服务于实验项目**，**RE 状态机目录用 `.research/`**，**实验项目目录独立于 RE 协议本体**

---

## 0. 触发与背景

四条外部材料 + Architect 4 条输入：

| 源 | 内容 | 状态 |
|---|---|---|
| `docs/v1/DANUS_VS_RE_COMPARISON.md` | Danus vs RE 第一轮对照 | 已 commit（2026-09-19） |
| `docs/v1/SESSION_2026-09-19_REVIEW.md` | 该 session 收尾 + 下次 deep fix 同步 acceptance | 已 commit（2026-09-19） |
| `docs/research/iteris-research-engineering-analysis.md` | 三项目对照 + 3 改进建议 | 已 commit（`40e5cbe`） |
| V1.5 设计 PDF | §4 Architect-in-the-loop + §5 Architect Signals + §17 具身安全示例 + §21 评价 | 已重读 |
| Iteris 实际代码 | UI server + ui command + explore/execute agent + supervision engine | 已 follow |

**AI 重读后的核心修正**：

| 我前几轮理解 | 修正 |
|---|---|
| "RE 是薄控制层" | **错**：RE 角色模型是 AI 长时段连续自主推进 + Architect session 内 Signal-based steering impulse。Dashboard 是核心不是 detached 优化。 |
| "Recover/状态保留是 RE 主要价值" | **Architect 原话**："都是次一级的优化功能"。RE 主要价值在 AI session 内几小时跨阶段不被打断 + Architect 看见能纠偏。 |
| "Iteris 是无人值守 workbench" | **错**：Iteris 也遵循 Architect-in-the-loop（数学家中途判断/干预）。 |
| "对照组难因为 Architect 不用 AI" | **Architect**：从**实战项目启动点开始跑 RE**，对照 20 天实际数据 |
| "Dashboard = synthesize 类 snapshot" | **错**：长跑 banner 滚动不便，要 UI / 旁路 file 兜底 |
| "RE 状态机放本仓库" | **Architect**：RE 协议服务于实验项目；RE workspace 与 RE 协议本体分离；状态机用 `.research/`，放在 RE workspace cwd 而非实验项目目录内 |

---

## 1. 三目录模型（Architect 这轮的明确口径）

```
~/sandbox/agentic-2026/                                  # 与 research-engineering 同级的根
├── research-engineering/                               # RE 协议本体（本仓库，无 research 目录）
│   ├── skills/                                            # Skill canonical source
│   ├── tools/researchlog/                                 # 19 个 verb + 6 个 schema + templates/
│   ├── templates/research/                                # .research 骨架
│   ├── docs/                                              # V0/V1/V2/acceptance + design
│   ├── .claude/, .agents/                                 # Install 的 skill 副本
│   └── tests/                                             # V0/V1 acceptance 304 case + V0 drill fixtures
├── <study-id>/                                        # RE workspace（每个 study 一个 cwd）
│   ├── .research/                                     # RE 状态机（点目录 + ACTIVE.json / ledger/ / runs/ / sessions.jsonl）
│   │   ├── ACTIVE.json
│   │   ├── CURRENT.md / ARCHITECT.md / BOUNDARIES.md / ENVIRONMENT.md / FINDINGS.md
│   │   ├── ledger/<YYYY-MM>/<EV-...>.json
│   │   ├── runs/<EXP-...>/manifest.json
│   │   ├── sessions.jsonl
│   │   └── references.json                            # external_refs（指向兄弟项目路径）
│   ├── docs/                                          # 项目启动材料（从兄弟项目 TASK.md 引用的材料，fetch-only）
│   ├── src/, tests/, ...                              # AI 在该 study 下跑出的实验产物
│   ├── data/, output/, runs/...                       # 项目特有 artifact 路径
│   └── .gitignore                                     # 含 .research/ledger/.gitignore 这种 per-study 配置

~/sandbox/competitions-2026/<project>/                # 兄弟实验项目（被研究对象）
├── docs/intent/INDEX.md / docs/status/ / docs/specs/ / docs/plans/
├── docs/research/PRACTICAL-RL-...md                  # 项目 own 文档（非 V0/V1 状态机）
├── src/, tests/, ...                                  # 工程代码
└── Makefile / AGENTS.md / pyproject.toml
```

**关键边界**（Architect 拍板）：

| 项目 | cwd | 状态机 | 来源 |
|---|---|---|---|
| RE 协议本体 | `research-engineering/` | 无（属于纯协议） | — |
| RE workspace（study） | `~/sandbox/agentic-2026/<study-id>/` | `.research/` | RE 协议 `init` 创建 |
| 兄弟实验项目 | `~/sandbox/competitions-2026/Embodied-Safety-Application-Challenge/` | `docs/intent/INDEX.md`（项目 own） | ESA 自己 init |

**`<study-id>` 与 RE 协议本体同级**（都在 `~/sandbox/agentic-2026/` 下）：
- 例：`~/sandbox/agentic-2026/esa-study/` ← 该 study 的 RE workspace
- 例：`~/sandbox/agentic-2026/asterion-study/` ← 其它 study 各自 cwd
- 这条与 `re-projects/` 子目录的区别：RE 协议和 study workspace 在 **同一父目录下**平铺，方便 `ls` 一眼看清楚：哪些是协议、哪些是研究项目

**`.research/` 不在 ESA 项目目录内**（即使 ESA 项目目录是 cwd 的 parent），理由：

1. ESA 主仓库 `docs/research/` 已经被 ESA own 用了（放 `PRACTICAL-RL-TRAINING-METHODOLOGY.md` 等论文级文档）
2. ESA 主 git 仓库由 ESA 自己治理（governance scripts + AGENTS.md），RE 协议状态机不应该污染 ESA
3. RE workspace 自己的 git 仓库（如果 init 了 git）与 ESA 主 git 完全分离
4. RE workspace 自己 ignore 自己的 `.research/`（`.gitignore` 由 `researchlog init` 创建）

**`references.json` schema proposal**（放到 `.research/references.json`，登记兄弟项目路径）：

```json
{
  "schema_version": "1.0",
  "external_refs": [
    {
      "id": "esa-2026",
      "type": "experimental_project",
      "path": "~/sandbox/competitions-2026/Embodied-Safety-Application-Challenge",
      "purpose": "primary read-only evidence source; current study treats ESA as Day 0–N baseline",
      "git": {
        "branch": "main",
        "base_commit": "abc1234...",
        "checkpoint_commit": null
      },
      "doc_anchors": [
        "docs/intent/INDEX.md",
        "docs/status/CURRENT-STATE.md",
        "docs/specs/",
        "docs/plans/"
      ],
      "read_only": true,
      "invalidated_if": [
        "esa.git.commit != <pinned sha>"
      ]
    }
  ]
}
```

`references.json` 通过 `researchlog init --reference <path>` 注册；`reconcile` 校验 ref 路径可读 + sha pinning；`EV` 的 `artifacts[].path` 可以含 `references://esa-2026/...` URI 形式（reconcile 解析真实 path）。

---

## 2. 当前 RE 状态盘点

### 2.1 已完成（V0/V1 闭环）

| 维度 | 完成 | 测试 |
|---|---|---|
| 协议层 skill 路由 | `skills/research-engineering/` 主 + 5 expert | V0 M2 ✅ |
| `researchlog` tool | 19 verb，stateless bookkeeping | V1-D1..D8 45 PASS + 4 ENV_BLOCKED |
| 跨 session state | `ACTIVE.json` + `sessions.jsonl` + `cumulative_evidence_iterations` | V1-D6 ✅ |
| `ARCHITECT.md` signal 语法 | 8 类 signal + scope/expiry/source_text + reconcile 强制校验 | V1-D8 ✅ |
| Capability Map + harness investment | `CAP-v1d9-routing-001` 等 | V1-D7 ✅ |
| Acceptance 管道骨架 | `Makefile` + `tools/run_acceptance.py` + `tools/acceptance/` + `docs/RE_ACCEPTANCE_CASES.md` | commit `a26203f` |
| V1 drill 8/9 closed（剩 V1-D9 全 ENV_BLOCKED） | 304 测试全绿 | commit `523de95` (`added_since` fix) + V1-D6 #4 |

### 2.2 当前缺口（按 Architect 这轮 + V1.5 §21 重排）

| # | 缺口 | 性质 | Architect 拍板指向 |
|---|---|---|---|
| **G1** | **RE workspace 模式（`.research/` + RE workspace cwd）** | 协议层 | 本轮 Architect 已明示 |
| **G2** | **Architect session 内 observability（dashboard UI / banner / 旁路 file）** | 核心价值 | 抄 Iteris UI（具体方案见 §3） |
| **G3** | **Extern project 引用协议（`references.json` + EV artifact URI）** | 中等 | 本轮 Architect 已明示（"RE 是从实验项目启动点开始工作"） |
| **G4** | **study workspace RE 组件装载关系**（已拍板 C：全局装，全 110+ skill 同形态） | 协议层 | Architect 已拍板（"为什么不安装成全局skills呢"）+ 已实施待实装 |
| A | 独立 Evidence verifier | 中等 | 暂缓（可选 2a） |
| D | `researchlog obligations --json` | 中等 | 暂缓 |
| B | wall-clock 心跳 | 中等 | 暂缓 |
| C | V0 → V1 协议同步收尾 | hygiene | 已 `added_since` fix，仍可能有同型隐患 |

---

## 3. Iteris UI 实际形态 + RE 改造路径（具体事实）

### 3.1 Iteris UI 实际代码

| 层 | 文件 | 实装 |
|---|---|---|
| Python CLI contract | `~/sandbox/agentic-2026/Danus/iteris/src/iteris/commands/ui.py` (463 行) | 6 verb: `streams` / `snapshot` / `facts` / `fact` / `activity` / `normalize` |
| Python sub-commands | `commands/ui_report.py` + `commands/ui_evolve.py` | 子命令注册 |
| Node server | `~/sandbox/agentic-2026/Danus/iteris/src/iteris/ui/server/` | Fastify + WebSocket；thin bridge 调 `iteris tool ui ... --json` |
| Client SPA | `~/sandbox/agentic-2026/Danus/iteris/src/iteris/ui/client/` | React/Vite，5 个 view: Overview / Facts / Evolve / Reports / Logs |
| Loopback only | `server/src/index.ts` line 60-65 | 仅 localhost 访问，无 auth |

**关键设计**：
- UI server **不解析 project state**，只做 Python CLI → REST → SPA 的反射
- 单 `--json` CLI 是 contract，TS 层不重复 parsing 逻辑
- WebSocket 推 JSONL streams（`normalize` 模式）
- 5 个 view 都对应 `commands/ui*.py` 的某个 verb

### 3.1.b G4：study workspace RE 组件装载关系（Architect 这轮抽到）

**问题**：RE 协议改进了，**实验项目 cwd 下装的 skill 副本**（`.claude/skills/` `.agents/skills/`）要不要同步？ — **Architect 拍板**：装成**全局**（`~/.claude/skills/` + `~/.codex/skills/`），不装到 study cwd。

**实装现状**：

| 层 | 实装 | 状态 |
|---|---|---|
| 协议本体（`skills/`）→ 本仓库 cwd 副本（`.claude/skills/`、`.agents/skills/`） | `install_research_skills.py --self` + `--check` | **已闭环**：commit `9e48d0a` + workflow_block drift check |
| 协议本体 → 全局 clients（`~/.claude/skills/` + `~/.codex/skills/`） | `install_research_skills.py` 待加 `--global` flag | **未实装**，本轮要做 |
| 协议本体 → study workspace cwd 副本 | 不实装（已被全局装替代） | 见下 |

**ESA 主仓库**：

- ESA 主仓库**不装 RE skill**（没 `.claude/skills/` `.agents/skills/` 等），ESA own 的 `AGENTS.md` 与 RE 协议正交
- ESA 主仓库不会被 RE 协议改动污染（**这是关键好处**：与 ESA 项目完全分离）

**Architect 拍板：装成全局 skills（路径 C）**：

> "那岂不是每个实验项目都要同步skills，为什么不安装成全局skills呢？"

**为什么 C 是正解**：

1. **drift 风险 = 0** —— 一份副本,不需要 N 处 sync
2. **与现有 113 个 skill 在 `~/.claude/skills/` 的生态一致** —— 看到了 `~/.claude/skills/{agents-sdk, anthropic-diagram, cloudflare, ...}` 全部平铺,RE 同样平铺
3. **study cwd 不装**.claude/skills/,skill 从全局自动来 —— ESA single study, working tree 是 `esa-study/`,AI session 在 `esa-study/` 启动时 client 从 `~/.claude/skills/` 自动找 skill
4. **多 study 工作环境契合**:一个 Architect 跑 N 个 study,装一次全局 → 全 study session 下次启动自动最新
5. **与 Iteris/Vendor plugin 形态一致**:vendor plugin 也用全局装,不按项目

**与既有三种路对比**：

| 路 | 副本数 | drift 风险 | client 支持 | 推荐度 |
|---|---|---|---|---|
| A 每 study 装副本 (`--target <study>`) | 2N | N>1 时高 | 全支持 | ~~不推荐~~ |
| B 协议动态挂载 (`claude --add-dir`) | 0 | 0 | 部分 | 不推荐 (minimax 端点拧巴) |
| C 全局装 (`~/.claude/skills/` + `~/.codex/skills/`) | 2(client 全局共享) | 0（单副本） | 全支持 | **推荐** |

**C 路具体动作**：

```bash
# 协议本体改完 skill 后（commit + acceptance 跑通）
make install-global
# → 把 skills/ 拷到 ~/.claude/skills/ + ~/.codex/skills/,平铺命名（research-engineering/, evaluation-design/ 等）

make install-global-check
# → 对比 skills/ 与全局副本,drift 报 exit 1
```

**Makefile target**：

```makefile
install-global:
	python3 tools/install_research_skills.py --global

install-global-check:
	python3 tools/install_research_skills.py --global --check
```

**study cwd 实际行为**：

- `~/sandbox/agentic-2026/esa-study/` cwd 下**不**装 `.claude/skills/`(study cwd 没有 skill 副本)
- `claude`/`codex` 启动时,client 从 `~/.claude/skills/` 自动发现 `research-engineering/` skill
- study cwd 的 `AGENTS.md` 写明"用 RE 协议"具体指引(等价当前本仓库的 AGENTS.md 角色)
- 协议本体改 skill → `make install-global` → 任意 study session 下次启动自动用最新,**无需每个 study 重复 sync**

**实装成本**：

| Step | 内容 | LOC |
|---|---|---|
| 1 | `install_research_skills.py` 加 `--global` flag | ~30 |
| 2 | `--check` 在 `--global` 下也工作 | ~15 |
| 3 | `Makefile` 加 `install-global` + `install-global-check` target | ~10 |
| 4 | tests: install target check 覆盖 `--global` | ~30 + 5 tests |
| 5 | 文档:study workspace 模式下,`**不再需要**` `--target <study>`,改用 `--global` | doc |

总 ~ 90 LOC + 5 tests + 1 doc 段

### 3.1.c 与 ESA 主仓库的边界（澄清）

**ESA 主仓库** vs **esa-study/ cwd** vs **本协议仓库** 三处：

| | 本协议仓库 (`research-engineering/`) | esa-study/ (RE workspace) | ESA 主仓库 (研究对象) |
|---|---|---|---|
| 装 RE skill | 是(via `--self`,本仓库内 acceptance 用) | **否**(从全局来) | 否 |
| 有 `.research/` | 不(纯协议) | 是(via `researchlog init`) | 否 |
| 装全局 skills | 是(协议本体负责 distribute) | 是(from `~/.claude/skills/`) | 否 |
| 角色 | 协议本体 | RE workspace(cwd) | 主研究对象(read-only via references) |
| Architect 干预 | 改协议本体 + commit | 通过 Signal 投到 RE session | ESA 自己治理(不受 RE 协议影响) |

**关键不变量**：ESA 主仓库永远不被 RE 协议改动污染。

### 3.2 Iteris explore / execute subagent 实质

| Agent | 文件 | 职责 |
|---|---|---|
| `explore` agent | `agents/explore.py`（~200 行） | 读 PROJECT.md / STATUS.md / TASK_POOL.json / FRONTIER_INDEX.json，产 candidate routes + fact candidates + verification requests |
| `execute` agent | `agents/execute.py`（~280 行） | 跑**单个 TASK_POOL item**，mode ∈ {foundation, experiment, code}，并行与主 agent 共存 |

**两者**隔离上下文 + 任务边界；explore 不进主 loop thinking 通道，execute 不接整个项目。

**RE subagent 覆盖分析**：
- **能 cover ~ 70-80%**：
  - Claude Code `Agent` 工具 / Codex 多 agent 都给独立上下文
  - SKILL.md 路由器 + AI 自己裁夺 ≈ "explore 模式"
  - RE 单 AI 在 block 内主动 spawn subagent，可与 Iteris execute 等价

- **不该 cover 的 30%**：
  - TASK_POOL.json 任务池调度
  - 自动调度空闲 agent（evolve profile）
  - **演化 master**（`supervision/profiles/evolve.py` 1474 行）

**结论**：RE 跳过 task pool + orchestrate，但保留 explore/execute 形态（通过 subagent 调用 + AI 自己裁夺）。

### 3.3 RE 实装 `researchlog ui ... --json` 的具体动作

| Step | 内容 | 估行 |
|---|---|---|
| 1 | `tools/researchlog/commands/ui.py` 新 verb，6 个子命令与 Iteris `commands/ui.py` 同型 | 200-250 |
| 2 | `commands/__init__.py` 注册 `ui` | 1 |
| 3 | Iteris UI 客户端迁移至 `tools/ui/client/` + 适配 `iteris tool ui ...` → `researchlog ui ...`，EV-* 字段映射 | 300-500 |
| 4 | Iteris UI server 迁移至 `tools/ui/server/`，单调用改为 `execFile('researchlog', ...)` | 100-150 |
| 5 | `Makefile` 加 `make ui` 启动 server | 5 |
| 6 | tests + JSON schema | 5 测试 |

**总成本**：600-900 LOC（其中 ~40% 是 Iteris 已 collect 完）。本轮：**先实装 Step 1 + 5 + 6（纯 Python，零外部依赖）**，Step 3/4 留到 Step 1 数据契约稳定后。

### 3.4 RE workspace (`.research/`) 实装路径

| Step | 内容 | 估行 |
|---|---|---|
| 1 | `tools/researchlog/repo.py`：`RESEARCH_DIR` 默认改 `".research"`，`discover()` 同时认 `.research/ACTIVE.json` 和 `research/ACTIVE.json`（兼容老名） | 5 |
| 2 | `commands/init.py`：默认建 `.research/`，加 `--legacy` flag 用老名 `research/` | 10 |
| 3 | `commands/checkpoint.py:56`：`RESEARCH_PREFIX = "research/"` 改用 `repo.RESEARCH_DIR` | 5 |
| 4 | 本仓库 `.gitignore` lines 11-24：加 `.research/...` 对应规则，旧 `research/...` 保留（兼容） | 10 |
| 5 | `tests/main/build_*.sh`：用 `${RE_RESEARCH_DIR:-.research}` 兼容 | 5 |
| 6 | `templates/research/` 拷到 `templates/.research/` | copy |
| 7 | `commands/references.py` 新 verb（`researchlog references add/list/sync`），写 `.research/references.json` | 80-120 |
| 8 | `commands/reconcile.py`：加 `references.json` 校验（path 存在 + git sha pinning 与 EV artifact 路径解析） | 30-50 |
| 9 | `skills/research-engineering/SKILL.md`："Resume comes first" 段加 RE workspace 模式说明 + how to register reference | 50 lines text |
| 10 | 新增 `tools/researchlog/commands/external.py` verb：在 manifest / EV 上加 `external_ref` URI 解析 | 50-80 |
| 11 | tests + JSON schema for `references.json` | 5 测试 + 1 schema |
| 12 | 本仓库 `research/`（自研究产物）的处置：保留为 audit trail，commit 一段 doc 说明"本仓库的 `research/` 是 RE 自身开发轨迹，与 `.research/` 是两个用途" | doc |

**总成本**：~250 LOC + 1 schema + ~10 tests

---

## 4. 对照实验形状（再次精确化）

### 4.1 对照组 vs Treatment 组

**Architect 拍板：treatment 起点仅限 ESA `docs/TASK.md` + 该文档中提到的具体文件与数据**。不复用 ESA 整个 `intent/` `specs/` `plans/` 工作包索引（那是 ESA own 状态机的产物，不是"项目启动材料"）。

| 组 | 数据 / 路径 |
|---|---|
| **对照组**（baseline） | ESA 主仓库 20+ 天数据（已有能力 + 工程代码 + 文档遗产） |
| **Treatment 组起点材料** | 仅 ESA `docs/TASK.md` + 它直接提到的 docs（`Safety-Embodiment-Docker-Usage-Instructions.md` 等）+ 它提到的 data（`data/question_to_player/`）|

### 4.1.a Treatment 起点 fetch 路径（具体步骤）

RE workspace（`~/sandbox/agentic-2026/esa-study/`）初始化时：

1. `researchlog init --reference ~/sandbox/competitions-2026/Embodied-Safety-Application-Challenge`
2. **不**复制任何 ESA 文件到 `<study>/docs/`。`.research/references.json` 只登记：`{id: "esa-root", path: "..../Embodied-Safety-Application-Challenge", purpose: "primary read-only evidence source"}`
3. AI 要读 ESA `docs/TASK.md`：通过 `references://esa-root/docs/TASK.md` URI 或直接在 cwd 用相对 path
4. 读 TASK.md 后再按它提到的 docs/data 局部拉：fetch 模式按需，不预先复制全部

**`.research/references.json` 的关键字段（与 §1 schema 一致但补充 purpose 类型）**：

```
purpose 取值:
  - primary_read_only_target   # 主研究对象，几乎所有 EV 引用其 docs/data
  - secondary_evidence_source   # 备份 source，cross-check 用
  - local_baseline              # 自身对照组数据（如本仓库的 `research/` 自研究轨迹）
```

### 4.2 评判维度（Architect 4 维）

按 V1.5 §21 表外扩展（Architect 给的 KPI）：

1. **实际完成度**：treatment 复算已通过哪些 gate（SPEC-P0-003 G1 / SPEC-P1-001 P1 / SPEC-P2-001 P2 / G2-001 / DATA / SPEC-DELIVERY-001 等），对照原 ESA 已通过的 gate
2. **Architect 干预次数**：treatment 运行期内 chat 中 Architect 投放 Signal/decision/clarify 的次数
3. **RE 持续自主推进时长**：treatment 单 AI session 内自主推进的最大时长（wall-clock）
4. **RE 无故闲置次数**：treatment 内 AI 在 EV record 后无新动作的 idle 间隔数（应低）

### 4.3 启动顺序

- 必须先实装 G2（`researchlog ui ...`）+ G1（`.research/`）+ G3（references）才能启 treatment
- 因为 dashboard 是治疗组 Architect 实时可见性的前提；没有 references，无法登记 ESA 主仓库做 read-only baseline

---

## 5. AI 自己的判断（修正版）

按 Architect 4 条输入 + Iteris 实装 + RE 协议现状整合：

| # | 决策点 | 我倾向 | 理由 |
|---|---|---|---|
| 1 | `.research/` 命名 | **采纳** | Architect 已明示；251 处 `RESEARCH_DIR` 引用改常量 + discover() 兼容老名 |
| 2 | RE workspace cwd | **采纳**（独立 cwd，不污染 ESA） | ESA `docs/research/` 已被 ESA 自己用；RE workspace 自己 git own |
| 3 | Dashboard 实装 | **Step 1 先**（纯 Python verb） | 数据契约稳定后才能抄 Iteris UI client；先稳契约再上 UI |
| 4 | UI 客户端复用 | **直接拷**（Architect 已指示） | Iteris 已 collect 完 build + run；reuse 80%+ |
| 5 | Subagent 覆盖 Iteris 调度 | **cover 70-80%，不抄 task pool + evolve** | subagent 能给独立上下文；架构师调度不该在 RE 出现 |
| 6 | `references.json` 实装 | **本轮同 `.research/` 一起做**（Step 7-8） | 是 treatment 启动的硬前提 |
| 7 | 实装顺序 | **1）`.research/` 改名 2）`references.json` 3）`--global` 安装 + Makefile target 4）`researchlog ui` Step 1 5）对照 treatment** | 1+2 是协议层；3 是分发；4 是 UI；5 是实验 |

**总路线**：先协议层（`.research/` + references + RE workspace 模式说明），再 UI（Step 1 verb），最后启动 treatment。

---

## 6. 给 Architect 的具体下一步选项

按 ROI / 不破现有顺序：

### 选项 X：仅协议层改造（G1 + G3 落地）

- Step 1-6（`.research/`）+ Step 7-8 + 10-11（references verb + reconcile 校验）
- + Step 9 SKILL.md 一段说明
- **总成本 ~ 250 LOC + 1 schema + ~10 tests + 1 SKILL.md edit**
- 不动 UI、不动 dashboard
- 落地后可以启对照实验 treatment（虽然 dashboard 尚未上，但 protocol 已 ok）

### 选项 X + UI Step 1：协议层 + dashboard verb

- 选项 X + `researchlog ui ... --json` 6 verb（~ 200-250 LOC + 5 tests）
- 总 ~ 500 LOC + ~ 15 tests
- 仍不抄 Iteris UI client（等数据契约 1-2 轮稳定后再说）

### 选项 X + 完整 UI 抄写

- X + Step 1 + Iteris UI client/server 全拷
- 总 ~ 1200 LOC + ~ 25 tests
- 但现在是协议还跑不动对照实验前也用不上 dashboard，**投资回报不高**

### Architect 该拍板：

- 选项 X / X+UI-Step1 / X+完整 UI？
- 已拍板：treatment 起点 = ESA `docs/TASK.md` + TASK.md 提到的 docs/data（fetch-on-demand）
- 已拍板：RE workspace 与 RE 协议本体同级（`~/sandbox/agentic-2026/esa-study/`）

---

## 7. 引用

- V1.5 设计 PDF：`docs/research-engineering-complete-design-v1.5.pdf`
- `docs/v1/DANUS_VS_RE_COMPARISON.md` / `docs/v1/SESSION_2026-09-19_REVIEW.md`
- `docs/research/iteris-research-engineering-analysis.md`（commit `40e5cbe`）
- `skills/research-engineering/SKILL.md`
- `tools/researchlog/repo.py` / `tools/researchlog/commands/__init__.py` / `tools/researchlog/commands/{init,checkpoint}.py` / `tools/researchlog/commands/__init__.py`
- `tools/researchlog/schemas/{evidence,manifest}.schema.json`
- `tests/main/build_*.sh`（gitignore 内）
- `~/sandbox/competitions-2026/Embodied-Safety-Application-Challenge/docs/TASK.md` + 它直接提到的 docs/data（`docs/intent/INDEX.md` v0.58 + `docs/status/RESUME-NEXT-SESSION.md` 等按 TASK 引用 fetch-on-demand）
- `~/sandbox/agentic-2026/Danus/iteris/src/iteris/commands/ui.py`
- `~/sandbox/agentic-2026/Danus/iteris/src/iteris/agents/{explore,execute}.py`
- `~/sandbox/agentic-2026/Danus/iteris/src/iteris/supervision/{engine,sensors,contracts}.py`
- `~/sandbox/agentic-2026/Danus/iteris/src/iteris/ui/{server,client}/`

---

## 8. Architect handoff（2026-09-20）

### 8.1 调度 + Dashboard 是真需要

- Iteris UI 形态：Fastify + WebSocket + React SPA + 6 个 `tool ui ... --json` verb
- RE 改造：实装 `researchlog ui ... --json` Step 1（pure Python），完成数据契约后抄 client/server
- 不抄 Iteris 的 orchestration（task pool + evolve profile）

### 8.2 实战题目已 ready

- ESA（`~/sandbox/competitions-2026/Embodied-Safety-Application-Challenge`）20+ 天数据
- 作为对照 baseline；**treatment 起点仅限 `docs/TASK.md` + 它直接提到的 docs/data**（不复用 ESA 整个 intent/specs/plans 工作包索引）
- 必须先实装 G1（`.research/` + RE workspace）+ G3（references），再启 treatment
- dashboard 是 treatment 运行中 Architect 实时可见性，前置需求

### 8.3 RE 协议服务于实验项目

- RE 协议本体（`research-engineering/`）纯 tool/skill/docs，无 `research/`
- RE workspace（`~/sandbox/re-projects/<study-id>/`）独立 cwd，RE 状态机在 `.research/`
- ESA 主仓库作为兄弟实验项目，通过 `.research/references.json` 登记 read-only
- 路径隔离：RE workspace 与 ESA 主 git 仓库不共享 .gitignore / 不污染 ESA 工作树

### 8.4 评估指标对照已确定

- 完成度 / Architect 干预次数 / 持续自主时长 / 无故闲置次数（Architect 给）
- 只能在 treatment 启动后实测，**前 3 项必依赖 G2（dashboard）或 G2 替代（log 解析）**

---

## 9. 待办

- [ ] ~~G4 装载策略当前推荐 A~~ → **已拍板 C (全局装，路径 `~/.claude/skills/` + `~/.codex/skills/`)**
- [ ] Architect 在 §6 选 X / X+UI-Step1 / X+完整 UI
- [ ] ESA `intent/INDEX.md v0.58` 是否就为 treatment 起点（已拍板 = ESA `docs/TASK.md` + 它直接提到的 docs/data）
- [ ] RE workspace 路径（已拍板 = `~/sandbox/agentic-2026/<study-id>/`，与协议本体同级）
- [ ] 选完路径后 AI 写实施 spec 分两份：
  - `RE_RENAME_RESEARCH_DIR_AND_REFERENCES_SPEC.md`（协议层）
  - `RE_RESEARCHLOG_UI_JSON_SPEC.md`（UI verb）
- [ ] Architect 二次批准后动 code；动 code 前 commit 本讨论锚点
