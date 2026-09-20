# ESA study 初始化操作指南

**目的**：让 Architect 或下一 session 能在 `~/sandbox/agentic-2026/esa-study/` 完成 RE 工作区初始化，登记 ESA 主仓库作 read-only 主研究对象。
**前置**：本仓库 commit `9ee2951`(Step 2 全局 skill)已落地，`make install-global` 已把 8 个 RE skill 装到 `~/.claude/skills/`、`~/.agents/skills/`、`~/.codex/skills/`。

---

## Step 4.1 建 study 目录 + init

```bash
cd ~/sandbox/agentic-2026   # 与 research-engineering/ 同级
mkdir esa-study
cd esa-study
git init -b main            # study 自己的 git repo(可选;如果想 git 历史可省)

# init 建 .research/(本版 researchlog 默认 .research,而非 research/)
PYTHONPATH=~/sandbox/agentic-2026/research-engineering/tools \
  python3 -m researchlog init --submission-budget 5

# init 应在 .research/ 下建：ACTIVE.json / CURRENT.md / ARCHITECT.md /
# BOUNDARIES.md / ENVIRONMENT.md / FINDINGS.md
ls .research/
```

如果 init 失败(本仓库尚未 commit Step 1 改动)+ cwd 里**没** ESA 主仓库路径前缀,先回到 research-engineering/ pull 一下:`git pull` 拿 Step 1 协议层改动。或者 init 时 cwd 是 research-engineering/ 里跑 init(失败因本仓库已存在 `research/`),可能与 ESA 无关,具体看错误信息。

## Step 4.2 登记 ESA 主仓库 + data 路径

`researchlog` 还没有 `references` verb —— 这是 Step 4 的临时手工方式(等 Step 4 verb 实装后用 verb):

```bash
cd ~/sandbox/agentic-2026/esa-study
# 创建 references.json 初始结构
cat > .research/references.json << 'EOF'
{
  "schema_version": "1.0",
  "external_refs": [
    {
      "id": "esa-project",
      "type": "experimental_project",
      "path": "/Users/sujiangwen/sandbox/competitions-2026/Embodied-Safety-Application-Challenge",
      "purpose": "primary_read_only_target",
      "git": {
        "branch": "main"
      },
      "doc_anchors": [
        "docs/TASK.md",
        "docs/Safety-Embodiment-Docker-Usage-Instructions.md",
        "data/question_to_player/assets/ASSET_INDEX.json"
      ],
      "read_only": true,
      "invalidated_if": []
    },
    {
      "id": "esa-data",
      "type": "experimental_project_data",
      "path": "/Users/sujiangwen/sandbox/competitions-2026/Embodied-Safety-Application-Challenge/data",
      "purpose": "primary_read_only_target",
      "size_gb": 16,
      "read_only": true,
      "doc_anchors": [
        "question_to_player/assets/ASSET_INDEX.json",
        "question_to_player/CONTENT_SHA256SUMS",
        "question_to_player/UNIFIED_RELEASE.json"
      ],
      "invalidated_if": [
        "esa-data.ASSET_INDEX.json.sha256 mismatch"
      ]
    }
  ]
}
EOF
git add .research/references.json
git commit -m "chore(esa-study): register ESA primary read-only target"
```

**注意**：本仓库目前**没有** `researchlog references add` verb,手写 `references.json` 是 Step 4 临时姿态。后续 session 应实装 verb 把本节改写。

## Step 4.3 写 study AGENTS.md(给 AI session 的本地声明)

```bash
cd ~/sandbox/agentic-2026/esa-study
cat > AGENTS.md << 'EOF'
# AGENTS — esa-study

本工作区是 RE 协议服务的实验项目 cwd,与 RE 协议本体
(~/sandbox/agentic-2026/research-engineering/)同位于 ~/sandbox/agentic-2026/。

## cwd 结构

  - .research/    RE 状态机(本工作区自己的;与 research-engineering/research/ 不可混淆)
    - references.json   登记主研究对象(ESA 项目 + data)
    - ACTIVE.json       active block; record 一次落这里
    - ledger/YYYY-MM/   Evidence records(append-only)
    - runs/EXP-*/      Run manifests
  - src/, tests/   AI session 在本工作区生成的研究产物(本仓库 own)
  - data/ / output/   本工作区自己的 output(不入 git)

## 主研究对象(read-only)

- ESA 项目主仓库: ~/sandbox/competitions-2026/Embodied-Safety-Application-Challenge/
- 16GB data: 在该主仓库 data/question_to_player/assets/ 下(不可复制,只读引用)
- 起点: 该主仓库 docs/TASK.md + 它直接提到的 docs/data(按需 fetch)
- 不动: ESA 主仓库 git 不被本工作区影响。所有改动落本工作区 src/ + src/。

## RE 协议 skill 来源

Skill 通过全局装(已 `make install-global` 完成):

  - ~/.claude/skills/research-engineering/  ← 本 cwd 下启动 claude 会自动读
  - ~/.agents/skills/research-engineering/  ← codex 同理
  - ~/.codex/skills/research-engineering/    ← 同理

不要 `install --self` 或 `install --target .` 在本工作区装 skill —— skill 已在 global。

## 协调

研究改 RE 协议本体: 在 ~/sandbox/agentic-2026/research-engineering/ cwd 跑 session
(本仓库)。改完跑 `make acceptance-full` + `make install-global`,本工作区下次启动
自动用最新。
EOF
git add AGENTS.md
git commit -m "docs(esa-study): AGENTS.md — RE workspace 与主研究对象边界"
```

## Step 4.4 测 RE workspace 启动

```bash
cd ~/sandbox/agentic-2026/esa-study
claude --model fable --bare -p "/research-engineering"
# 或：
codex -c 'skills.config=[{name="research-engineering",enabled=true}]' --prompt "/research-engineering"

# 验证：
# 1) skill 能调出 research-engineering
# 2) .research/ACTIVE.json 能被读到
# 3) references.json 路径(ESA 主仓库)有效
```

## Step 4.5 .gitignore + 防 L1 路径污染

```bash
cd ~/sandbox/agentic-2026/esa-study
cat > .gitignore << 'EOF'
# RE state tracked (machine-readable audit trail)
!.research/ledger/
!.research/runs/
.research/.derived/

# ESA 主仓库引用是路径不是 git submodule,不入 git
# 不复制 ESA data,绝不 commit
data/

# Research output, 不入 git
output/
*.pyc
__pycache__/
EOF
```

注:`!.research/ledger/` 等前导 `!` 是显式 add, 使 .research 实际 default ignored 但子路径 included。`status --porcelain` 在 .research/ 下 EV 文件会被 git 列。

---

## Step 4 之后的对照实验

启动 ESA study 在 cwd:cd 到 `~/sandbox/agentic-2026/esa-study`,开新 Claude Code / Codex session,prompt:

> "读 .research/ + ESA 主仓库 docs/TASK.md + ASSET_INDEX.json;按 RE 协议走第一个 evidence-producing iteration。"

会话照 P1 loop 跑:notebook 里有 active block + EV record + reconcile + 跨 session state 维护。Architect 端只投递 Architect Signal / DECISION,V0/V1 acceptance 的 4 个评判维度(完成度 / Architect 干预次数 / 持续自主推进时长 / 无故闲置次数)开始计时。

---

## 实施后续待办(下一 session)

- 实装 `researchlog references add/list/sync` verb(本 session 未实装,hand-write 临时)
- 写 EV `artifacts[]` 大文件 policy doc(inline / sha256 + path / size 阈值)
- 补 `make sync-tools` target 把 skill sync 集成进 acceptance-full(可选)
- ESA study 跑对照实验 3-5 session 后,采集 evidence 数据,落 V2 acceptance report
