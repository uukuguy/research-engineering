# Work Log

本仓库的**开发记录**。新会话从这里接续：读最新一条即可知道"做到哪、下一步做什么、动手前要注意什么"。

---

## 2026-09-18 — Block 2 第二批：T2 ledger partition YYYY-MM

承接上一轮（T3 STATUS.md milestone cache）。本轮做 T2——`research/ledger/YYYY-MM/EV-*.json`
分区。**V1 方案 §2.2 T2 写"partition migration 已在 `state.py::_load_shards`"——这是方案
作者的理解错位**：V0 `_load_shards` 用 `glob("*.json")`（flat），不是 partition。**T2 的真正
实装**是改 record 写路径到 `evidence_in_partition` + 改 _load_shards 到 `rglob` + 老 flat 文件
继续读。一次提交，两轮变异验证。

### 这一轮交了什么

**`tools/researchlog/repo.py`**

* 新 method `ResearchPaths.evidence_in_partition(evidence_id)` → `ledger/YYYY-MM/EV-*.json`
* 新 helper `_evidence_month(evidence_id)` 解析 id 里的 `YYYYMMDDTHHMMSSZ` 戳，返 `YYYY-MM`；
  malformed id（手写 fixture）回落到字面量 `unpartitioned`，永不与真月份混淆
* 新 regex `_EVIDENCE_MONTH_RE` 锚定 `^[A-Z]+-(\d{4})(\d{2})\d{2}T\d{2}\d{2}\d{2}Z-`

**`tools/researchlog/commands/record.py`**

`ids.claim_new("evidence", paths.evidence_in_partition)` 一行改 —— id 在 mint 时已经定下
时间戳，partition 完全是 id 推导，无新字段。

**`tools/researchlog/state.py`**

`_load_shards` 改 `rglob("*.json")` —— partition + flat 同时读。不递归的话单个新写就
与 reconcile / validate 失联。

**`tools/researchlog/commands/compare.py` + `validate.py` + `reconcile.py`**

三个 reader 都加 partition-first + flat-fallback 链：
* `compare._load` partition → flat → `EVIDENCE_NOT_FOUND`
* `validate` 检查"memory 有 record 但 file absent" 时同样 partition-first
* `_ledger_latest_mtime` 用 `rglob`，否则 partition 写完 reconcile 的 `STATUS_STALE` 不触发

**`tests/test_commands.py::LedgerPartitionTests`**（新）

* `test_record_writes_the_shard_under_a_month_subdirectory` —— 写路径 contract：
  partition 存在 + flat **不**被创建
* `test_reconcile_walks_partitioned_and_flat_shards` —— 读路径 contract：
  `evidence_records == 2`，partition + flat 都数上（**这一条是变异**的核心 catcher）
* `test_unpartitioned_fallback_for_hand_written_ids` —— 手写 fixture 走 `unpartitioned`

**`tests/test_integration.py`**

predicate 端到端测试直接读 ledger 文件，按 id 推 partition。

### 变异验证

1. **`_load_shards` 退回 `glob`**：partition 写入的 evidence 漏读 → `evidence_records == 1`
   不等于 2，红。
2. **`_evidence_month` 永远返 `"unpartitioned"`**：partition 字符串不再是 `YYYY-MM`，
   测试 `assertNotEqual(partition, "unpartitioned")` 红。

### 现在能核验的状态

```
HEAD 4a0db1d · 工作树干净
Block 1 协议层 8/8 ✅
Block 2：T2 ✅ · T3 ✅ · T1 / T4 / T5 / T6 ⏳
170 个 unittest 全绿（167 + 3 新）
python3 tools/researchlog reconcile --json → exit 0 clean
python3 tools/researchlog validate       → exit 0
```

### 动手前要知道（这一轮新增）

24. **T2 partition 决策不是 0 成本**。V1 方案说"已在 _load_shards"是错的——V0 是 flat。
    真实装需要改 record 写路径 + state loader + compare / validate / reconcile 的 reader
    都要走 partition-first。**`compare` 和 `validate` 也会因为 flat 路径找不到新 evidence 而
    报 NOT_FOUND / SHARD_MISSING**，必须一起改。
25. **partition 字符串从 evidence_id 推导**，不存 wall clock。测试用 `_evidence_month`
    而不是 `_now()` 算 partition，避免 wall clock 跨月时 fixture 漂移。
26. **`unpartitioned` 是 fallback 不是 placeholder**。手写 fixture（V0 时代遗留、第三方
    import）走这条路径；reconcile 必须能 load 它，否则 schema migration 期间 evidence
    "静默丢"（V1 §6.2 风险）。

### 下一步

Block 2 剩：
* **T5 productivity telemetry** —— 把 max_tokens only 扩到 §21 KPI 全表
* **T6 record --validate-line** —— record 边界，单条 record 合法 vs run evidence 足够分开
* 等架构师回 P4 → T1
* 等架构师触发 P5 → Block 3 / 4 / 5

---

## 2026-09-18 — Block 2 第一批：T3 STATUS.md milestone cache + stale-detection

承接上一轮（P4 capability_map shape proposal）。架构师回"V1 还有一大堆工作没完成"，在
Block 4/3/5/6 都被 P4/P5 阻塞的前提下，今夜走 Block 2 里**不依赖 P4/P5** 的子项。T3 是首选
—— STATUS.md writer + reconcile stale-detection，边界清晰，验收 #4 + V1-D4 全 cover。

### 这一轮交了什么

**`tools/researchlog/commands/status.py`**（新增）

新 verb `status --write PATH`。默认写 `STATUS.md` 到 repo 根。Body 复用 `snapshot._build`
的同款（git / environment / active / reconcile 摘要），头部加两行 markdown comment：

* `<!-- DERIVED SNAPSHOT — NOT SOURCE OF TRUTH -->` —— 契约，让未来 reader 别当 source of truth
* `<!-- last_evidence_modified: <epoch> -->` —— anchor，`reconcile` 解析它来判 staleness

`--write` opt-in；不传 `--write` 时跟 snapshot 一样只读不写。
`STATUS_NOT_IGNORED` warning 镜像 `SNAPSHOT_NOT_IGNORED` —— STATUS.md 在 root 会 dirty tree，
提醒加 `.gitignore` 但不拒写。
`STATUS_PATH_OUTSIDE_ROOT` 拒 root 之外的 `..` 越界。

**`tools/researchlog/commands/__init__.py`**

注册 `status` 到 `from researchlog.commands import (...)` 和 `MODULES` 元组。

**`tools/researchlog/commands/reconcile.py`**

* 模块顶部加 `_LAST_MODIFIED_RE` regex 和 `_STATUS_HEADER` 常量（不走 import `status`，避免
  `status → snapshot → reconcile` 的循环）。
* 新 detector `_stale_status` 挂到 `detectors` 元组尾部。
* `_ledger_latest_mtime` 直接扫 `research/ledger/*.json` 而不是用 `state.Ledger`，让空 ledger
  也能稳定跑 detector。
* 三种 failure mode 报 `STATUS_STALE`（warning）：unreadable、缺 `DERIVED SNAPSHOT` 头、缺
  `last_evidence_modified:` anchor、ledger mtime > cached mtime。

**`tools/researchlog/tests/test_commands.py`**

* `StatusCommandTests`（新）：no-write 不动盘、write 落地 + 头部存在、root 之外路径拒、
  `STATUS_NOT_IGNORED` 提醒。
* `ReconcileStaleStatusTests`（新）：无 STATUS.md → 静默、缺头 → 红、缺 anchor → 红、
  empty ledger 上 fresh cache → 静默、ledger 推进 → 红。
* 涉及 warning 的断言用 `assertIn(code, (0, 3))` 兼容 V0 的"warning 让 reconcile exit 3"
  语义。

### 变异验证

把 `_stale_status` 整体替换为 `return []` —— 三个 positive-path stale-detection 测试
都红，`'STATUS_STALE' not found in []` 准确报告 detector 没工作。回滚后 9 个新测试全过。

### 现在能核验的状态

```
HEAD 24aa8da · 工作树干净
Block 1 协议层 8/8 ✅
Block 2：T3 ✅ · T1 / T2 / T4 / T5 / T6 ⏳
167 个 unittest 全绿（158 + 9 新）
python3 tools/researchlog reconcile --json → exit 0 clean（本仓库无 STATUS.md）
python3 tools/researchlog validate       → exit 0
```

### 动手前要知道（这一轮新增）

22. **status.py → snapshot → reconcile 形成 import 环**。reconcile 自己复制 regex（不
    import status）打破。代价：regex 改一次两个地方要同步。下一次想引入"共享 strings module"
    时再抽象。
23. **V0 reconcile 把 warning 当 exit 3**。新 detector 是 warning 级，新测试用
    `assertIn(code, (0, 3))` 而不是 `assertEqual(code, 0)`。这是 V0 invariant 的延伸。

### 下一步

* **Block 2 / T2**(sharded ledger partition YYYY-MM)—— 独立可启，零依赖
* **Block 2 / T5**(productivity telemetry 扩到 §21 KPI 全表)—— 独立可启，零依赖
* **Block 2 / T6**(record --validate-line)—— record 已有路径，加边界
* 等架构师回 P4 → T1（capability_map 写路径）
* 等架构师触发 P5 → Block 3 / Block 4 / Block 5

---

## 2026-09-18 — Block 1 第六批：P4 capability_map shape proposal

承接上一轮（P2 reproduction 分桶）。本轮只产出一份设计提案文档，**不动 schema**，等
架构师评审。Block 1.5 是 P4 的全部范围。

### 这一轮交了什么

**`docs/design/CAPABILITY_MAP_SHAPE_PROPOSAL.md`**（新增，168 行）

提案 9 字段 shape：

* 必填：`id`、`capability`、`status`、`reuse_counter`
* 可选：`supports_evidence`、`first_used_at`、`last_used_at`、`last_used_by_evidence_id`、`notes`

`reuse_counter` 是 V1 §2.1 P4 唯一点名必含的字段，V1-D7 测试 + V1 complete #2 都钉它。
`status` 沿 harness / limitation 二分用 `AVAILABLE | LIMITED | UNSUPPORTED`，理由见提案 §6。

### 提案里刻意列了"考虑过但丢弃的字段"

让架构师能直接**反驳**而不必从头读：

* cross-ref 到 limitations / harnesses —— Block 2 / T1 才有的字段，硬外键得等 harness id 稳定
* category —— 已经被 `available.{compute,simulator,data,external_services}` + `harnesses[]` +
  `limitations[]` 三层表达
* 自由 `description` 长文本 —— 鼓励没人读的散文
* `cost_estimate` —— "成本"是多维（wall clock / token / GPU / 钱 / 机会），pinning 一种会锁死 schema

每个都有理由，架构师不同意可以直接在文档上划。

### 提案结尾三个具体决策点

1. **字段集**：9 字段是不是够。`reuse_counter + id` 是不可谈判的，其余可议。
2. **状态词汇**：`AVAILABLE | LIMITED | UNSUPPORTED` 三分，还是更细分
   （`AVAILABLE | DEGRADED | LIMITED | UNSUPPORTED` 等）。
3. **optional vs required**：现在的"required-only-where-data-is-always-known"
   取向 vs 更宽的"required 多 null"。

### 为什么提案**不动 schema**

V1 §2.1 P4 原文："Block 1.5 出 shape proposal，经 Architect 一票通过后落
`environment.schema.json`" —— 出提案是 P4 的全部范围。schema 紧固在评审通过后单独立 commit。
**forward-compatible 紧固**：当前 `capability_map` 是 `type: array`（无 items 约束），
空数组在 `items: <object>` 下仍合法 —— V0 任何 instance 不破坏。

### V1-D7 6 断言对照

| 断言 | 提案关 |
|---|---|
| `capability_map shape 通过 schema` | ✅ items 改 typed object |
| `≥3 entries 写入` | 由 T1（Block 2）写路径负责，本提案不写 |
| `reuse_counter 字段存在` | ✅ required field |
| `harness declare 合法` | 不在本提案；harnesses[] 已合法 |
| `env rebaseline 触发 fingerprint 变` | 不在本提案；Block 2 / T4 |
| `changed` 谓词不再永远 `UNRESOLVED` | 不在本提案；Block 2 / T4 |

**提案直接关 2 条**,其余 4 条 unblock。

### 现在能核验的状态

```
HEAD d0b3ea0 · 工作树干净
Block 1 进度：1.1 P1 ✅ · 1.2 P2 ✅ · 1.3 P5 sub-decision ✅ · 1.4 P6 ✅ · 1.5 P4 提案 ✅ · 1.6 P7 ✅ · 1.7 P8 ✅ · 1.8 P9 ✅
158 个 unittest 全绿
python3 tools/researchlog reconcile --json → exit 0 clean
python3 tools/researchlog validate       → exit 0
```

**Block 1 协议层 8 个 sub-block 现在只剩 P5（架构师触发）。** 所有不依赖 P5 的都落完了。

### 下一步

等架构师回提案 (d0b3ea0)。如果架构师要扩范围：
* 加 c/树/agent-sdk 调研 → 单独立项，本会话不主动开
* 启动 Block 2（Tool 入场费）→ 等架构师触发，因为 T1 / T4 依赖 P4 schema

---

## 2026-09-18 — Block 1 第五批：P2 reproduction 分桶

承接上一轮（P7 run heartbeat）。本轮做 P2——`record` 自带 `iteration_kind`，`reproduction`
不进 evidence budget，仍落 ledger。一次提交，两轮变异验证。

### 这一轮交了什么

**`templates/research/ACTIVE.json` + `schemas/active.schema.json`**

加 `block.reproduction_iterations: integer ≥ 0`，required。template 默认 0。

**`schemas/evidence.schema.json`**

加 `iteration_kind: enum["evidence","reproduction",null]`。老 evidence 该字段为 null，schema
允许。

**`constraints.py`**

* `derive_counts_as_evidence_iteration` 头部加 `iteration_kind == "reproduction"` 时返 False
  —— 是 evidence 桶的唯一闸门。
* 新增 `count_reproduction_iterations`：对称计数，走 iteration_kind 字段。

**`commands/record.py`**

`--iteration-kind evidence|reproduction` flag，默认 `evidence`。`_apply_links` 后写入 document。

**`commands/active.py`**

* `belief_delta` 路径同时写 `completed_evidence_iterations` 和 `reproduction_iterations`。
* `block.id` 重置时同时清零两个。

**`commands/init.py`**

`_stamp_active` backfill `block.reproduction_iterations = 0`。**这是真实 schema migration**：
本仓库自己的 `research/ACTIVE.json` 是 V0 时代遗物，没这字段，新 schema required 的话
reconcile 会 REDCOVERY_REQUIRED。init 时 backfill 一下，老 instance 也能跑。

**`research/ACTIVE.json`** 本仓库自己的 ACTIVE，被 backfill + base_commit 推进 + updated_at
更新，一并提交进 P2 commit。

**`tests/test_integration.py`**

* `test_reproduction_does_not_consume_the_evidence_budget`：三条 record（两 evidence + 一
  reproduction）同一 block，close 后断言 evidence=2、reproduction=1。
* `test_reproduction_skips_even_with_no_belief_delta_dropped`：一条 scientific fields 本该
  count 的 reproduction（`belief_delta=refined`），断言 override 赢，evidence=0、
  reproduction=1。

### 变异验证

1. **drop `iteration_kind == "reproduction"` 分支** —— 两个新测试都红，`3 != 2` 和
   `0 != 1` 准确报告错桶。
2. **stub `count_reproduction_iterations` 为 `return 0`** —— 两个新测试在 reproduction
   计数断言上红。

### 现在能核验的状态

```
HEAD 3f11cf7 · 工作树干净
Block 1 进度：1.1 P1 ✅ · 1.2 P2 ✅ · 1.3 P5 sub-decision ✅ · 1.4 P6 ✅ · 1.6 P7 ✅ · 1.7 P8 ✅ · 1.8 P9 ✅
            1.5 P4 capability_map shape
158 个 unittest 全绿
python3 tools/researchlog reconcile --json → exit 0 clean
python3 tools/researchlog validate       → exit 0
```

### 动手前要知道（这一轮新增）

20. **schema migration 的真实成本**：加 required 字段会让所有老 ACTIVE/ledger 报
    `RECOVERY_REQUIRED`。**backfill 是必要的**，不是 nice-to-have。本仓库自己的
    `research/ACTIVE.json` 就被 backfill 了。
21. **`block.reproduction_iterations` 在 record 阶段不动**。`record` 只写 ledger；分桶
    计数是 close-block 时一次性重派生。这是 V0 invariant 的延伸（"counter nobody maintains
    is a counter that lies"）。

### 下一步

剩一条：

1. **Block 1.5 P4 capability_map shape proposal**（写文档等架构师评审；不动 schema）

P5（Block 1.3）等架构师触发——V0 测试不动。

---

## 2026-09-17 — Block 1 第四批：P7 run heartbeat

承接上一轮（P1 record-after-commit）。本轮做 P7 —— `run` 的子进程 supervise 在子进程仍在
跑期间定期 bump manifest 的 `heartbeat_or_last_observed_at` 字段，默认 30s；`--heartbeat-interval 0`
显式 opt-out。一次提交，一轮变异验证，五轮稳定性验证。

### 这一轮交了什么

**`tools/researchlog/commands/manifest.py`**

抽出 `bump_heartbeat(record)` helper：单独更新 heartbeat 字段，不动其他。`_apply(--heartbeat)`
路径改调它，`manifest --heartbeat` 的现有行为不变。

**`tools/researchlog/commands/run.py`**

* `--heartbeat-interval` flag，默认 30.0；0 关闭。
* `_start_heartbeat(record, manifest_path, interval, stop)`：daemon thread，每 `interval` 秒
  bump 一次。sleep loop 拆 0.2s slice 检查 `stop()` —— Ctrl+C / session stop 在 1s 内能拆
  loop，不是卡到下一个完整 interval。
* `interval <= 0` → 返回 None，不起 thread（opt-out 路径 0 成本）。
* 心跳写盘失败被吞（best-effort）：下一次 bump 或 closeout 总会 publish 状态。

**`tools/researchlog/tests/test_commands.py::RunCommandTests`**

* `test_heartbeat_is_bumped_while_the_child_runs`（新）：起一个真 subprocess 跑
  `sleep 1.8` + `--heartbeat-interval 0.2`，从测试线程 polling 两次 manifest：~0.55s 一次、
  ~1.55s 一次，断言 `second > first`（ISO 8601 字典序 == 时间序）。
* `test_heartbeat_interval_zero_disables_bumps`（新）：`--heartbeat-interval 0` 关闭 daemon，
  closeout 心跳仍正常落盘。

### 为什么 polling 故意跨秒 floor

`_now()` 用 `timespec="seconds"` —— 0.2s / 0.4s / 0.6s / 0.8s 心跳都被 floor 到同一秒。两次
polling 如果都跨同一秒 floor，`assertLess(first, second)` 会假阴性（即使 daemon 在跑）。

解法：让两个 polling 时刻**故意落在不同秒**（0.55s + 1.0s）。`time.sleep(0.55)` + json 解析
+ `time.sleep(1.0)` + json 解析 ≈ wall-clock 1.55s，肯定跨秒。bump 在 0.2/0.4/0.6/0.8/1.0/1.2/1.4s，
0.55s 时读到 0.4 bump (T+0.0)，1.55s 时读到 1.4 bump (T+1.0)——**字典序必然 second > first**。

### 变异与稳定性

* **变异**：把 `_start_heartbeat` 内部函数掏空（只留 early-return None），两个 sample 落
  在同一秒 floor，`assertLess` 红，且把 `first=... second=...` 都打出来。
* **稳定性**：5 轮全套测试连续 OK，5 轮单测连续 OK。Timing race 在初版（polling 0.4+0.6）
  上偶发（5 轮中 1 轮 fail），扩到 0.55+1.0 后稳定。

### 现在能核验的状态

```
HEAD fd20bf6 · 工作树干净
Block 1 进度：1.1 P1 ✅ · 1.3 P5 sub-decision ✅ · 1.4 P6 ✅ · 1.6 P7 ✅ · 1.7 P8 ✅ · 1.8 P9 ✅
            1.2 P2 reproduction 分桶 · 1.5 P4 capability_map shape
58 个 unittest 全绿（含 2 个新 P7 heartbeat 测试）
python3 tools/researchlog reconcile --json → exit 0 clean
python3 tools/researchlog validate       → exit 0
```

### 动手前要知道

18. **`_now()` 用 `timespec="seconds"`** —— 所有跨秒断言要注意 floor。sub-second 测试要么
    跨 floor 边界，要么用 `process.returncode` 而非时间戳判定。
19. **daemon thread 是 best-effort**：写盘失败被吞，但 closeout 路径一定会写。所以**心跳
    不存在不代表进程没在跑**——读不到心跳时 `job --experiment-id` 是更可靠的判定。

### 下一步

剩两条协议层 sub-block：

1. **Block 1.2 P2 reproduction 分桶**（schema + record 命令分流计数）
2. **Block 1.5 P4 capability_map shape proposal**（写文档等架构师评审；不动 schema）

P5（Block 1.3）等架构师触发——V0 测试不动。

---

## 2026-09-17 — Block 1 第三批：P1 record-after-commit

承接上一轮（P6 + P8）。本轮只做 P1，是 Block 1 最大的一块——`record` 命令从此
自带 `git add + git commit`，失败必报 `COMMIT_FAILED`。一次提交，三轮变异验证。

### 这一轮交了什么

**`tools/researchlog/jgit.py`**

加两个低层 helper：

* `add_paths(root, paths)` —— `git add -- <repo-relative paths>`。**空列表是编程错误**而非
  无操作（空 `git add` 会 stage 所有已追踪变更，不是 caller 想要的）。
* `commit_with_message_file(root, message_file)` —— `git commit -F <file>`。**禁止 `-m`**
  因为 E1：反引号/$/! 会被 shell 静默吞掉，消息变残缺且不报错。

**`tools/researchlog/commands/record.py::run`**

写完 evidence → 调 `_commit_evidence` → 失败抛 `COMMIT_FAILED` (StateInvalid, exit 2)。
三个失败路径独立区分 `subject` + `message`：

| 失败点 | `subject` | `message` |
|---|---|---|
| `jgit.is_repository` 失败 | `git commit` | `<root> is not a git repository` |
| `git add` 失败 | `git add` | `<git add stderr>` |
| `git commit` 失败 | `git commit` | `<git commit stderr>` |

区分 subject 的意义：上层 reconciler 能按 subject 知道是哪一步崩，而不是只看
`code=COMMIT_FAILED` 然后瞎猜。

**`tools/researchlog/tests/test_commands.py`**

P1 把 record 强行绑到 git，但 `CommandTestCase.setUp` 之前不在 git 仓库跑——所以
带三个改动：

1. **`CommandTestCase.setUp` 改**：加 `git init` + `git config user.email/name` + 写
   `.gitignore`（含 `research/.derived/`）+ baseline commit。**`test_write_lands_in_derived`
   的 SNAPSHOT_NOT_IGNORED 失败因此自动消失**——这是 setUp 早期遗漏的"测试基础设施
   旧 bug"，P1 顺手补了。
2. **`test_record_appends_an_evidence_record_and_reports_the_closure` 重写**：原来跑
   `env record` 验 ENVIRONMENT.md history；现在跑 bare `record` 验 commit subject 和
   `git ls-files --error-unmatch` 的 evidence tracked 状态。V0 env-record 路径断言
   留给 `test_the_closure_of_a_change_is_reported`。
3. **新基类 `NonGitCommandTestCase`**：不带 git init 的 setUp，给 is_repository 防线
   测试用。

**新测试类**：

* `RecordCommitTests`（继承 `GitCommandTestCase`）：钉 commit subject 是
  `research: record <evidence_id>`，evidence 文件被 git tracked。
* `RecordRejectsInNonGitRepo`（继承 `NonGitCommandTestCase`）：钉 `subject=git commit`
  + message 含 `"is not a git repository"` 字面量。

### 变异验证（三轮，全部红-回滚）

1. **删除 `_commit_evidence` 调用** —— `git ls-files --error-unmatch` 在 evidence
   路径上 non-zero，整条测试红。
2. **`-F <file>` 换成 `-m <message>`** —— 测试仍过（`_RECORD_COMMIT_SUBJECT` 不含
   特殊字符）。E1 不是测试可强制的，是 code review 守的。
3. **删除 `is_repository` 防线** —— `RecordRejectsInNonGitRepo` 的 `subject` 断言
   从 `git commit` 变成 `git add`（兜底报错），整条红。**这正是 GOTCHAS B11 #1
   "标签 vs 代码对得上"的镜像**——测试同时钉 subject 和 message 字面量，变异让
   两个一起露馅。

### 现在能核验的状态

```
HEAD e6506e1 · 工作树干净
Block 1 进度：1.1 P1 ✅ · 1.3 P5 sub-decision ✅ · 1.4 P6 ✅ · 1.7 P8 ✅ · 1.8 P9 ✅
            1.2 P2 reproduction 分桶 · 1.5 P4 capability_map shape · 1.6 P7 run heartbeat
56 个 unittest 全绿（含 2 个新 P1 commit/reject 测试）
python3 tools/researchlog reconcile --json → exit 0 clean
python3 tools/researchlog validate       → exit 0
```

### 动手前要知道（这一轮新增 + 之前的）

15. **CommandTestCase.setUp 现在 git init**，所有继承它的测试都在 git 仓库跑。新加测试
    如果要测"非 git 仓库"路径，必须继承 `NonGitCommandTestCase`（V0 的 `GitCommandTestCase`
    也仍然可继承——它现在 init 重复了，无害）。
16. **E1 是纪律不是断言**。`-F <file>` 替换 `-m` 时测试仍过——subject 不含反引号。代码 review
    必须看 commit message 走文件这一约束。
17. **P1 字面只覆盖 bare `record`**。`env record` 改 ENVIRONMENT.md 但不 commit（与 P1
    方案 §2.1 描述一致："git add research/ledger/EV-*.json research/ACTIVE.json"）。
    `env record` 的 commit duty 是 T1 Block 2 的事。

### 下一步

按之前列的队列：

1. **Block 1.6 P7 run heartbeat**（run.py 子进程 supervise 30s 默认；ACTIVE 加
   `heartbeat_or_last_observed_at`；与 P1 不同——run 是另一条命令族，不影响 record）
2. **Block 1.2 P2 reproduction 分桶**（schema + record 命令分流计数）
3. **Block 1.5 P4 capability_map shape proposal**（写文档等评审；不动 schema）
4. **Block 1.3 P5**（等架构师说）

---

## 2026-09-17 — Block 1 第二批：P6 收 `--replace-existing` + P8 补 record 的 fix_hint

承接上一轮（Block 1 首批：P5 sub-decision 落地 + P9 detector 跑通）。架构师选 P5 = 机制升级
（history[] 可选加；scope/expiry 仍仅 CONSTRAINT 必填；V0 测试不动），并指定本轮范围 = P6 + P8。
两个 sub-block 各一提交，两次变异验证。

### 这一轮交了什么

**Block 1.4 P6 — 禁 stale overwrite（`7c62d51`）**

`tools/researchlog/commands/run.py`：

* 删除 `--replace-existing` flag（V1 不允许任何 override）。
* `_refuse_running` 改成"in-flight 永远拒"——`{pending, running}` 两个状态都拒。V0 只看
  `running`，但 `_write_manifest` 之前如果进程崩，会留下一个 `pending` 的半成品。新条件比
  V0 紧，关掉了一个隐藏 overwrite 窗口。
* 文档字符串同步：现在"start even if a manifest says running"这段已无意义。

`tools/researchlog/tests/test_commands.py::RunCommandTests`：

* 原 `test_refuses_to_restart_an_experiment_whose_manifest_says_running` 不动，仍钉 running 拒绝。
* `test_replace_existing_is_an_explicit_opt_in` 替换为
  `test_replace_existing_flag_is_removed_and_in_flight_is_always_refused`：argparse 拒
  `--replace-existing` 时 `SystemExit(code=2)`；去掉 flag 后 in-flight 仍被拒。
* 新增 `test_a_finalised_run_can_be_rerun_under_the_same_experiment_id`：completed 不被
  视为 ownership，可以同 `--experiment-id` 重跑——这是 P6 的反半边。
* 新增 `test_a_pending_manifest_is_also_refused`：钉 V0→V1 收紧的差异。

变异验证：缩 in-flight set 到 `{running}` 让 only `pending` 测试红；`_refuse_running` 掏空
让三个 in-flight 测试**全部**红而 `finalised` 测试仍绿。两条都证明测试在钉它声称的事。

**Block 1.7 P8 — record 的 fix_hint 全数补齐（`a58568d`）**

`Finding` dataclass 早就有 `fix_hint` 字段，但 `record` 的五个拒绝站点没用它。补了：

* `EXPERIMENT_FLAG_CONFLICT`：丢 `--no-experiment` 或丢 `--experiment-id`。
* `ARTIFACT_ROLE_WITHOUT_ARTIFACT`：要么 `--artifact PATH` 一起给，要么删 `--artifact-role`。
* `EVIDENCE_FILE_UNREADABLE`：先检查 path/权限/存在，或传 `-` 走 stdin。
* `EVIDENCE_SOURCE_MALFORMED`：`python -m json.tool < source` 先验，再重跑。
* `EVIDENCE_SOURCE_NOT_OBJECT`：顶层包成 `{...}`，数组和标量不算合法。

测试 `RecordRejectTests`（新 class）每条端到端跑，`_assert_every_finding_has_fix_hint` 扫 envelope
上所有 finding，断言 `fix_hint.strip()` 非空。变异：把 `EXPERIMENT_FLAG_CONFLICT.fix_hint`
清空，对应测试**红**——而且报错信息把代码名和空字符串都打印出来，不是 silent green。

### 现在能核验的状态

```
HEAD a58568d · 2 个新 commit 落地
Block 1 进度：1.3 P5 sub-decision ✅ · 1.4 P6 ✅ · 1.7 P8 ✅ · 1.8 P9 ✅
            1.1 P1 record-after-commit · 1.2 P2 reproduction 分桶 · 1.5 P4 capability_map shape
            · 1.6 P7 run heartbeat
54 个 unittest 全绿（含 4 个新 P8 reject 测试）
python3 tools/researchlog reconcile --json → exit 0
python3 tools/researchlog validate       → exit 0
```

### 动手前要知道（这一轮新增 + 上轮提到）

13. **`PreconditionMissing` → exit 5，不是 exit 2。** 写测试时猜错一次。`StateInvalid=2` /
    `RefusedByPolicy=4` / `PreconditionMissing=5` / `EXIT_FINDINGS_PRESENT=3` / `EXIT_OK=0`。
    这条不是 V0 漏掉的（既有 `test_heartbeat_without_a_manifest_is_a_precondition_failure` 已钉过），
    是 P8 新测试要断 P8 的外缘时撞到的。
14. **P8 验收在 record 上**（V1 方案 §4 #8 + V1-D8 都点名 record），其他命令的 reject 路径
    是另一个 sub-block 的事。这一轮我只动 record.py。

### 下一步

按架构师选的 P5 = 机制升级，今晚 Block 1 的剩余：

1. **Block 1.1 P1 record-after-commit**（最大块：record 写完 evidence 后自动 `git add
   research/ledger/ research/ACTIVE.json && git commit -F msg_file`；新增错误码 `COMMIT_REQUIRED`
   / `COMMIT_FAILED`；detached worktree 路径需要预检——V1 方案 §6.2 列过这个风险点）
2. **Block 1.6 P7 run heartbeat**（run.py 子进程 supervise 30s 默认；ACTIVE 加 `heartbeat_or_last_observed_at`）
3. **Block 1.2 P2 reproduction 分桶**（ACTIVE schema + evidence schema 加 `reproduction_iterations`
   + `iteration_kind`；record 命令分流计数）
4. **Block 1.5 P4 capability_map shape proposal**（写提案文档，等架构师评审；不直接动 schema）

P5 (Block 1.3) 等架构师触发——V0 测试不动，schema 升级只是 `history[]` 可选加。等架构师说。

---

## 2026-09-17 — Block 1 首批：P5 二次澄清 + P9 实装

承接上一轮（V1 整体方案落盘）。本轮启动 Block 1，但只做了一处澄清 + 一条 sub-block。理由写在 §本轮做了什么。

### 决策澄清：P5 的 sub-decision（2044d00）

V1_IMPLEMENTATION_PLAN.md 附录 A 把 P5 措辞为"全部 signal 加 history + scope + expiry"。但 V0 的 `test_constraints.py::SignalTests::test_only_a_constraint_needs_scope_and_expiry` 明确断言 **VETO 不需要 scope/expiry**（因为 VETO 是"永久直到废止"）。

建筑师在 AskUserQuestion 看到的选项可能误读为"机制升级"而不是"强制升级"。**不擅自落地**，把这条张力作为附录 A.1 摆出来，三个候选：

- a）机制升级：仅 CONSTRAINT 必填 scope/expiry（V0 不变）
- b）强制升级：CONSTRAINT/DECISION/VETO 必填
- c）字面解读：全部 8 类都强制（推翻 V0 测试）

**阻塞 Block 1.3**。其余 7 条 Block 1 sub-block 不受影响。

### 实装：P9 single-writer detector（195b646）

修改：`tools/researchlog/commands/reconcile.py` 加 `_worktree_multi_writer` 与 `_list_worktrees`；`tools/researchlog/tests/test_integration.py` 加 4 个新测试。

**为什么挑 P9 而非其他**：

- 影响面最小（detector-only，不改 `record` / `run` 行为）
- 不改 schema
- 不改 `AGENTS.md`
- 不动 `research/ACTIVE.json`
- 测试可构造两个 worktree 临时目录，效果可测

**核验**：

```bash
uv run --python 3.12 python -m unittest discover -t tools -s tools/researchlog/tests
# Ran 243 tests in 10.509s — OK  # 239 旧 + 4 新，全过

python3 tools/researchlog reconcile --json
# exit_code: 0
# clean: True                    # V0 状态仍干净

python3 tools/researchlog validate
# exit_code: 0                   # validate exit_code 0
```

### 未触动

- `research/` 轨道（idle）
- 其余 7 条 Block 1 sub-block：P1 + P6（record 自动 commit + 禁 `--replace-existing`）、P2（reproduction 分桶）、P3（不决断）、P5（阻塞）、P7（run 默认 30s heartbeat）、P8（补 fix_hint 126 处）
- `tools/researchlog` 其余 14 个 subcommand
- `skills/`、`tests/main/`

### 下一步

1. **Architect 二次澄清 P5**（附录 A.1 的 a / b / c 三选一）
2. **启动下一个 Block 1 sub-block** —— 建议选 **P7 run 默认 heartbeat**（影响面比 P1/P2/P6 小、比 P8 工作量轻、且 V0 `manifest --heartbeat` 已实装可直接复用）
3. **避开 P1 + P6 + P2 + P8 集中在主会话改**——每条独立 session

### 动手前必须知道

按 V0 GOTCHAS：本次 P9 涉及的是 `jgit.git()` 与 `subprocess.run`，无新增坑；4 个测试用 `GitRepoCase` 模板，符合现有 V0 惯例；detector 三参数签名保持与 V0 一致（即便 Pyright 标 `_args` / `_ledger` "unused"，这是 V0 风格，不修）。

---

> **未启动 V1 实现**。本轮只交付一份方案文档供架构师评审。

### 产物（单一文件）

`docs/design/V1_IMPLEMENTATION_PLAN.md` —— V1 实施方案：Autonomous Research Batches。

- 沿用 `V0_ACCEPTANCE_GUIDE.md` 同模板（Day-N must vs V1 complete）
- 覆盖设计文档 §20.2 全部 26 条"增加项"
- 9 条 protocol 层决策已收集并落地为决断（P1-P9 见附录 A）
- 工作分解为 6 个 bounded blocks，每块独立可推进 / 可中断 / 可回滚
- 9 个 V1 drill 草图（V1-D1..V1-D9）
- 风险表对位 V0 GOTCHAS（35 条中**会复发**的 7 条）+ V1 独有 6 条

### 决策概览（详见文档附录 A）

| ID | 决断 | 选择 |
|---|---|---|
| P1 | session 必须 commit | 强制 commit |
| P2 | reproduction 分桶 | 分桶 |
| P3 | idle-while-running | 不决断，列现状与风险 |
| P4 | capability_map 形状 | Agent 起草，Architect 评审 |
| P5 | signals 扩展 | 全部 signal 加 history + scope + expiry |
| P6 | stale overwrite | 禁 `--replace-existing` |
| P7 | heartbeat 协议 | 强制：所有 run 默认 30s heartbeat |
| P8 | reject 消息 | 加 message + fix_hint |
| P9 | worktree 写入 | single-writer |

### 核验

```bash
git status --short
# ?? docs/design/                                 # 仅新建目录，无 canonical state 改动
python3 tools/researchlog reconcile --json | jq .exit_code
# 0                                              # research/ 轨道干净
```

### 下一步（架构师评审后）

1. **架构师评审 V1_IMPLEMENTATION_PLAN.md**——尤其是 §2（protocol 决断）、§4（验收清单草案）、§5（6 块分解）
2. **评审通过后 commit**——本文档与 WORK_LOG 同 commit（`docs:` prefix）
3. **启动 Block 1**——按 §5 顺序，先把 8 条 protocol 决断落到 `AGENTS.md` + schema 字段
4. **Block 1.5（P4 capability_map shape）**——这是 Block 1 内第一个产出，会被 Block 2 / Block 3 / Block 4 依赖

### 未触动

- `research/` 轨道（idle，未变）
- `tools/`（未改）
- `skills/`（未改）
- `tests/`（未改）
- V0_ACCEPTANCE_GUIDE / V0_CASES（未改）

---

条目**带日期且只追加** —— 一条过期的条目看起来就是旧的，不会伪装成现状。这正是它不需要被重新
生成或校验的原因（而"当前状态快照"需要）。

> 两条轨道别混：`research/*` 是**这个工具所服务的研究**的状态（由 `researchlog` 持续维护）；
> 本文件是**开发这个工具**的记录。本仓库的 `research/ACTIVE.json` 保持 `idle` 是正常状态，
> 不是待填的空缺。

---

## 2026-09-17 — 交接（V0 收尾）

> 新会话从这里接续。**下面每一条都可以当场核验**，不是回忆。

### 可核验的现状

```bash
git rev-parse --short HEAD          # 8c3de91
git status --porcelain              # 空
git ls-remote <ssh-url> main        # 8c3de91 —— 与本地相同
```

```bash
python3 tools/researchlog validate >/dev/null;                       echo $?   # 0
python3 tools/researchlog reconcile >/dev/null;                      echo $?   # 0
python3 tools/check_workflow_block.py >/dev/null;                    echo $?   # 0
python3 tools/install_research_skills.py --self --check >/dev/null;  echo $?   # 0
bash tests/main/check_negative_control.sh;                           echo $?   # 0
```

**别用 `for c in "tools/researchlog validate" …; do python3 $c; done`** —— zsh 不做词分割，那会
得到 `exit=2`，看起来像工具坏了，其实是 python 去找一个含空格的文件名（`GOTCHAS.md` C9 第二半）。
这一轮我踩了两次。

| | 值 |
|---|---|
| **V0 状态表** | **21 行 = 21 ✅ + 0 ⏸ + 0 ⏳ + 0 ❌**（`#1` 架构师改判为"另一个客户端也能进入 Research Mode"，第二客户端记 **pi**；codex 明确暂缓） |
| **`research/` 轨道** | `ACTIVE.status: idle`、`ledger/` 0 条、`runs/` 0 个 —— **正常状态，不是空缺** |
| **案例集** | 4 个 builder + `run_case.sh` + `verify_case.py` + `check_negative_control.sh` |
| **裁判** | 已**钉住**：`run_case.sh` 在 build 时把 `verify_case.py` 复制进运行私有的 workdir，判时用那份（源树中途被改不影响判读） |

### 这一轮做了什么（九个 commit，全部已推）

1. **负对照当场抓到检查器说谎**：`d2` 把 fixture 种下的文本当成 session 的行为来判（两个方向都
   错），`r2` 的消息声称它没测的事。修完补上零成本闸门 `check_negative_control.sh`（四案例，6 秒）
2. **真实运行抓到 fixture 三处不自洽**（种下的改动自己会崩、两臂只差一个打印前缀、
   `expected_outputs` 在构造上无法满足）→ 修 + 四条自断言（各带变异验证）+ 补上 §12.16 判据 2
   此前**没有任何一行在判**的 `r7`
3. **pi 上三个案例全过**（`recovery` / `evaluator-conflict` / `bootstrap`，各 7/7）—— 而**每一个的
   第一份判读都是检查器答错了隔壁问题**：`r2` 与提及判据读错产物、`d6` 判"有没有新 run 目录"、
   `b5` 要 ≥3 而判据原文是 2–3
4. **fixture 没有 `.gitignore`** → 提交了字节缓存 → 两次 run 的"代码身份"一直在哈希 `.pyc` 的抖动；
   清掉噪声后暴露真不一致（种植在 run **之后**，而 manifest 声称用了那个 flag）→ 种植移到 run 之前
5. **`#22` 演练通过** → V0 状态表全绿

### 下一步（有顺序）

1. **V1 候选**（两个，未开工）：协议**无提交要求** —— `code_state.commit` 因此可能指向 fixture
   自己的 commit，让 `#18` 的双向映射没有东西可映射；`max_evidence_iterations` **绑不住复现工作**
2. **一条未抹平的账**：`#22` 的素材由**旧** builder 生成、带 73 个 tracked `.pyc`，所以它结束时
   `reconcile` 不干净（`ENV-LIM-002`）。builder 已修；判定材料写在 `V0_ACCEPTANCE_GUIDE.md` 的
   `#22` 行里，素材本身在 `/tmp`（会随重启消失）
3. **claude 侧三个案例不在同一版 fixture 上**：`recovery` 的 6/6 是**修 fixture 之前**跑的；
   `evaluator-conflict` 在 claude 上**从未真实跑过**（pi 侧有 7/7）。若要"同一版仪器、两个客户端"
   的完整矩阵，还需 2 个 claude session —— 但 `#1` 的证据按架构师口径**已经够了**，这属于加固

### 动手前必须知道

**全部在 `GOTCHAS.md`**（那是当前为真的清单，与这份日志分工不同）。这一轮新增/改动最相关的：

- **B15** fixture 提交字节缓存 → "代码身份"哈希算在缓存上；**`.gitignore` 对已跟踪文件无效**
- **B14** 判一个 session 要判**它留下的那个产物**：pi 的 stdout 是摘要（4 KB），session log 才是
  记录（254 KB）
- **B13** 种植式 fixture 的 `.replace()` 链**静默失败**
- **B12** 验证检查器时别拿**实现里的字符串**去构造验证用例
- **B11** 现有**四个**可操作的检查（新增两条：**它会不会惩罚本该奖励的行为？**、**键集合为空时
  它还能失败吗？**）

**一条给下一个会话的**：这一轮我的**验证程序自己错了五次**（`ps` 模式写窄、变异锚点写错、变异
脚本把多个 case 铺进同一目录互相覆盖、两次变异"因别的原因变红"却被当成通过、以及上面 C9 那次）。
第六轮写过"**凡是要据以下结论的数字，先确认你读的确实是那个东西的数字**" —— 它仍然作数，而且
我仍然会犯。

---

## 2026-09-17（第十轮）— fixture 把字节缓存提交进了历史；`#22` 演练通过，V0 状态表全绿

### fixture 的 `.gitignore` —— 一个"身份哈希算的是什么"的问题

四个 builder 都**没有 `.gitignore`**，于是 `git add -A` 把 `__pycache__` 提交了（一个 bootstrap
fixture 里 73 个 `.pyc`）。后果有两层，第二层才是要紧的：

1. 任何一次工具运行都让工作树变脏，脏在 session 从未碰过的文件上 —— **没人埋的异常**（B8），
   也正是 B11 里 `tool_digest` 那条的原始形态；
2. **两次 run 的"代码身份"一直在哈希 `.pyc` 的字节抖动**。`code_state` 刻意排除 `research/`
   （否则每条证据身份都唯一、`compare` 永久 `ATTRIBUTION_FORBIDDEN`），所以排除之后剩下的
   "脏"就只剩工具自己重写的字节缓存 —— `dirty: true` 看起来像"运行用的是改过的代码"，
   实际什么都没说明。

加上 `.gitignore` 后脏消失，身份变成诚实的 `dirty: false` —— 而**诚实暴露了第二处不一致**：
那次在飞的运行，命令里带的 `--closed-loop` **只存在于后来种下的未提交改动里**，而 manifest
记录的是"代码干净"，两者描述的不是同一棵树。

修法：**把种植移到两次 run 之前**，并让状态提交**排除**那处改动（`git reset -- probes/…`）。于是
两次 run 的身份就是那棵种过的树，`stdout.log` 里的数字就是那棵树会打印的。两条自断言守着她，
**变异验证各自触发正确的那条**：把种植移回 run 之后 → "Plant the unfinished work before the
runs"；多脏一个文件 → "the drill describes exactly one change"。

（我的**前两次变异尝试都错了**：一次种进了不存在的文件（Python traceback），一次先触发了上游断言。
**因别的原因红，只说明 builder 脆，不说明那条断言在工作** —— 所以是重写而不是接受。）

### `#22` 演练：通过，而且比预期更有信息量

素材：pi 那次 `bootstrap` 的真实产出。claude 跑 `/research-status` 出报告 → 交给 **pi**。

**报告自己就是一次自检**：它开出一份 STATUS INTEGRITY WARNING，点了四条 `reconcile` **不覆盖**
的不一致（分支名无人比较、`dirty_expected=true` 关掉了唯一的 Git 检测器、73 个 tracked `.pyc`、
`environment_id` 三处不一致）—— 第 3 条正是**我几分钟前那次 prep 的半截修法**（只加 ignore、
没 `git rm --cached`；builder 侧我的修法是对的）。

**pi 的两半都成立**：

- **Resume 在前**：动作次序是 读 skill + `ACTIVE.json` + `git status` → 读 `CURRENT/ARCHITECT/
  BOUNDARIES` + `reconcile` → **之后**才动状态。**报告是上下文，不是状态的替代品。**
- **认知正确且更好**：它复述 RB-001 已结题、`FND-…c5da` 是 durable belief，然后**去工具源码里
  核对**报告的每条断言，把核不动的落成 `ENV-LIM-002/003`（环境限制，不是科学否定），**再顺着
  finding 自己写下的 limitation 做真研究**：threshold sweep 找到 `RETRY_THRESHOLD ∈ [30,40]ms`
  的**相变**（T≥40ms 时 p99=19.91ms，与 retry-off 臂三位小数一致），并把"70ms hold-time"从
  **触发器**修正为**放大器**。产出侧 `validate` exit 0。

**一处如实记录**：结束时 `reconcile` 仍报"工作树脏" —— 根因是那份素材由**旧** builder 生成、
带着 73 个 tracked `.pyc`。pi 选择文档化而非 `git rm --cached`。判据不要求终点干净，故不影响
判定，但它确实留在那里。

### V0 状态表：**21/21 全 ✅**

架构师把 `#1` 改判为"另一个客户端也能进入 Research Mode"（第二个客户端记 pi；codex 明确暂缓），
`#22` 由本次演练补齐。**0 ⏸、0 ⏳、0 ❌。**

### 下一步（V1 候选，未开工）

协议**无提交要求**（`code_state.commit` 因此可能指向 fixture 自己的 commit，让 #18 的双向映射
没有东西可映射）；`max_evidence_iterations` **绑不住复现工作**。

---

## 2026-09-17（第九轮）— 三个案例在 pi 上全过，而每一个都先修掉一处"答隔壁问题"的检查

架构师口径：**claude code / pi 能跑通即可**，codex 暂缓。三个案例在 pi 上跑完，最终**全部 7/7**，
但**每一个的第一份判读都是 FAIL，而每一个的 FAIL 都是检查器的错**：

| 案例 | 第一份判读 | 修掉什么 | 最终 |
|---|---|---|---|
| `recovery` | FAILED r2 / r3 / r6 | `r2` 只看工作树（看不见**已提交**的证据）；提及判据读的是 pi 的 **4 KB 摘要**而非 **254 KB** session log | **7/7** |
| `evaluator-conflict` | FAILED d6 | `d6` 标签写"**针对它拒绝的那条计划**起 run"，代码问"有没有新 run 目录" | **7/7** |
| `bootstrap` | FAILED b5 | `b5` 要 ≥3 条记录，判据原文是 **2–3** | **7/7** |

**四处缺陷同一族，而三处的方向是"判一个做对了的 session 失败"** —— 与上一轮 `d2` 的方向相反，
所以更值得记：检查比标签更严时**不会**被日常运行发现，因为报告是红的、看起来像"协议没做到"。

### pi 实际做到了什么（每个案例的定性判读都站得住）

- **`recovery`**：`job` → `never_started`；读出 `--closed-loop` 是**占位实现**（"只改 scale，不改
  2-vs-3 分离结构"）；判定**补跑 case-03..05 零信息**；重跑并以 `EVIDENCE_INVALID` 记录；关块；
  提交；把 (a) 环境投资 / (c) 换方向升级给架构师、(b) 合成状态机留给自己。
- **`evaluator-conflict`**：扫遍 window 0.40→0.10，**证明 proxy_score 是参数的单调函数而非振荡的
  测量**（记成 `informative_failure` / `belief_delta: overturned`），再查 intervention_trace 的字段
  判断"能否仅凭它造出 dwell-aware proxy"（答：不能，每个 intervention 只有三个字段）。
- **`bootstrap`**：分解 top-1% 延迟（`queue_wait=10790ms` vs `service_time=14ms` vs `backoff_wait=70ms`），
  **补跑缺失的对照臂**（retry-off、同 seed：p99 19.91ms、无级联），再确认那 150 个重试请求是
  **连续 id、单一级联**（`max_id_gap=0`）并定位到触发请求。**并且用了 git worktree**
  （`.worktrees/rb-001-queue-vs-retry/`）—— 本项目明文保留可用的那个技能，被真的用上了。

### 一个具体化了的 harness 隐患

`b5` 的缺陷是**在 `bootstrap` × pi 还在飞的时候发现的**，而我**刻意没改文件** —— 裁判读的是运行时
磁盘上的那份代码，改了它等于**中途换裁判**。修法等判定结束、把旧判读如实记下、再离线复判。

于是"**裁判没被钉住**"这条不再是理论隐患，它有一个具体的差点发生的实例：早改 5 分钟，那份判读
就会在无人留痕的情况下改变。**下一件该做的事**：`run_case.sh` 在 build 时把 `verify_case.py`
复制进运行私有的 workdir，判时用那份（与 `g0` 对"被测方可改工具"的处置同形）。

### 下一步

1. 上面那条**钉住裁判**。
2. **claude 在修好的 fixture 上重跑三个案例** —— 目前 claude 的 `recovery` 6/6 是在修 fixture
   **之前**跑的，两个客户端的证据不在同一版仪器上；`#1`/`#22` 要的正是"同一版仪器、两个客户端"。
3. 然后是 `#22` 本身（status 报告交给 pi → 快速建立正确认知 → 执行前仍走 Resume）。

---

## 2026-09-17（第八轮）— 第二个客户端：pi 跑通了，而第一份判读是 harness 的错

架构师明确了验收口径：**"claude code / pi 能跑通即可"，codex 暂缓** —— 所以 `#1`/`#22` 的活路径
就是第二个客户端，案例集正是验它的仪器。

### `recovery` × pi：真实判读 **7/7 PASS**

第一份判读是 **FAILED / r2,r3,r6**，而**三条全是 harness 的错** —— 同一棵树、同一次运行，只有
判据的输入错了：

| 判据 | 第一份 | 真实 | 根因 |
|---|---|---|---|
| `r2` | FAIL ——"改成 completed 却没留证据" | **PASS** | 它用只看**工作树**的 `new_files`，而 pi **提交了**记录、树是干净的 → **指控它犯了这个案例的核心失败**。`changed_since` 的 docstring 早就写明了这个形状，而 r2 一直没换掉那个 helper：**坑被写下来了，缺陷留下来了** |
| `r3`/`r6` | FAIL ——"从未提及" | **PASS** | 判的是 pi 的 **4 KB 最终摘要**，而完整 session log 是 **254 KB**（`MANIFEST_STALE_RUNNING` ×3、HEAD subject ×9） |

修法与验证：`added_since`（跟 baseline 的树比目录，提交与否都看得见）替换 `new_files` 并**删除**
后者（`d2` 也在用它，那边漏判的方向是**放过**真做错的）；`run_case.sh` 改判 pi 的 session log 并
**打印用了哪个文件**。**验证用离线复判归档的那次运行**，五条变异：已提交记录 PASS、未跟踪记录
PASS、无记录仍 FAIL，决定性的一对是同一棵树同一次运行 —— 判摘要 2 条 FAIL、判 session log 0 条。

### pi 实际做了什么（摘要原文的判读，值得记）

查 `job` → `never_started`；读出 `--closed-loop` 是**占位实现**（"只改 scale，不改 2-vs-3 分离
结构"）；据此判定**补跑 case-03..05 零信息** —— 正是项目要的"最便宜可执行证据"经济学；重跑并以
`EVIDENCE_INVALID` 记录（`EV-…-ac1c`：E1、`inconclusive`、observation 写明 probe 结构上偏向 H-041
无法证伪）；关块 `belief_delta: refined`；提交 `13bada2`；把 (a) 环境投资 / (c) 换方向升级为架构师
决策、(b) 合成状态机归自己 FREE-tier 自主推进。摘要按语言约定用中文写。

**一处留给架构师判读**：pi 用 `researchlog run --replace-existing` 重跑并**覆盖**了陈旧 manifest，
于是"它曾经是 stale"这个事实只留在 transcript 里。按指南字面（确认存活→发现已死→finalize 成
interrupted→再决定重跑）它算通过，`r2` 也走"finalize 且有新证据"那条分支；但若认为**覆盖 stale
记录本身**就是它该报告的东西，这条要另算。

> **补（查过工具后，这个问题更尖锐）**：`--replace-existing` 不是随手可用的开关 —— 默认路径是
> `run.py::_refuse_running` **拒绝**在 `running` manifest 上重跑，理由消息明写"inspect it with
> `researchlog job …`; **if the process is gone, finalise that run first**"，并说明这个 flag
> "only to deliberately start a second run"。**工具把正确路径写在拒绝消息里了**，pi 选了 override。
> 它确实先 `job` 确认了（r3 提及成立），所以不是"未确认就重跑"；但它跳过了 finalise 那一步，
> 那次 stale 的**记录**因此消失。**判据 7 明文允许"确认后重跑"，所以这不是 session 的失败，而是
> 判据覆盖度的问题** —— 是否要求先 finalise 再重跑，是个案例设计问题。

### 我自己的验证程序这一轮错了三次

`ps` 模式写窄（据此差点宣布"pi 没在跑"，改用进程树才看到）；变异锚点写错两处；变异脚本把多个
case 准备进**同一个目录**，于是第一个 case 判完覆盖了其余的 —— 那份报告评的是它从没拿到过的树。
**第六轮写过"凡是要据以下结论的数字，先确认你读的确实是那个东西的数字"，这一轮仍然作数。**

### 下一步

`evaluator-conflict` × pi（**在飞**；这个案例从未在任何客户端上真实跑过，而它的核心判据 `d2`
正是本轮修的），随后 `bootstrap` × pi。三个案例都过，`#1`/`#22` 就有第二个客户端的完整数据点。

---

## 2026-09-17（第七轮续）— 把 D1 fixture 的三处不自洽修掉，并补上判据 2 的那一行

上一轮真实 `recovery` 运行报出的三处缺陷（R-1/R-2/R-0，详下一条），全部已修，**每条都带变异验证**：

| | 修法 |
|---|---|
| **R-1** 种下的"未完成工作"自己会崩，且它要加的 flag 早在 HEAD 里 | probe 模板**去掉**那个 flag（HEAD 变成"还没有它"）；种下的改动**可运行地**加上它 |
| **R-2** 两臂只差一个打印前缀 | flag 现在**改变计算**（`CLOSURE_GAIN` 占位系数），两臂数值不同 |
| **R-0** `expected_outputs` 构造上无法满足 | 去掉该声明（probe 的 docstring 明说永不写文件） |

**根因也修了**：builder 的种植从三个**静默**的 `.replace()` 链改成断言式 `sub()` —— pattern
不匹配就退出并说明。这正是 R-1 的来历：三个里两个匹配不到，而 `str.replace` 对不匹配不报错。

**新增四条 fixture 自断言**，每条都**变异验证过**（把该缺陷重放一遍 → builder exit 1 并点名）：

1. **committed probe 里不得有 `--closed-loop`** —— 否则判据 2 的意图推不出来。
   注意一条**不能**用的写法：不解析参数的脚本会**忽略**未知参数并正常退出，所以"HEAD 拒绝这个 flag"
   **无法从退出码观测**，只能断言源码。
2. 工作树的**两臂都必须能跑**（EXP-0142 的 stdout 就是那棵工作树跑出来的）；
3. **两臂输出必须有实质差异**（否则"对照"是空壳）；
4. **EXP-0142 的 stdout 必须等于 closed-loop 臂打印的前两行** —— 把 artifact 钉回代码。

**判据补全**：新增 `r7 opened the uncommitted probe change`。§12.16 判据 2 此前**没有任何一行在
判它**，而且 fixture 也支撑不了它。现在它判**缺席那一半** —— `CLOSURE_GAIN` 只存在于那处未提交
改动里，从状态、台账、manifest 都拿不到 —— "是否真懂"仍留给读者，与另外五条提及判据同一约定。
**所以 M4 的 7/7 现在与其余各行同一口径，而不再是 6/7。**

变异：r7 缺席 → FAIL（stub）；在场 → PASS。

**注意**：fixture 已改，所以第七轮那次 `recovery` 6/6 **只对旧 fixture 成立**。

### 下一步

**pi**。架构师已明确验收要求为"**claude code / pi 能跑通即可**"，codex 暂缓 —— 所以 `#1`/`#22`
的活路径就是第二个客户端，而案例集正是验它的仪器。三个案例（`recovery` / `evaluator-conflict` /
`bootstrap`）尚未在 pi 上跑过。

---

## 2026-09-17（第七轮）— 负对照当场抓到检查器说谎，而真实运行抓到 fixture 不自洽

### 起点：交接单第一步（两个从未对真实运行跑过的案例）

先走**免费的那条路** —— `stub` 负对照同样能把 builder + runner + checker 整条管路跑通，
零模型成本。`recovery` 与 `evaluator-conflict` 一跑就各暴露一处**"检查的东西与标签声称的相邻"**
（至今占比最大的缺陷类）：

- **`d2`（conflict 的核心判据）两个方向都判错**。它读 `next_action`，把"还留着 seed 文本"当成
  采纳。那是 **fixture 的文本**，于是：自然语言明确拒绝的 session 判 **FAIL 且被指控**"把 proxy
  当成了目标"（该检查从未观测过这个行为）；而真正采纳了计划的 session，因为句子里恰好有
  "did not adopt" 被判 **UNJUDGED 逃脱**。上一轮那次"修复"的验证 transcript 是**照着实现里的
  子串写的** —— 验的是实现的措辞，不是判据的含义。
- **`r2`** 的消息声称"reported"，而它只看得见"not repaired"（报告那一半是 `r3`）。

修法：`d2` 只判**产物能判的那一半** —— 新增证据记录对**那个假说**报了**进展**
（`research_outcome`，不是 `belief_delta`：后者任何信念变化都写，包括**正确的向下修正**，拿它当
信号会冤枉案例本该奖励的 session）。通过栏是一句话，子串不是决定，所以状态没被移开时报
`UNJUDGED`，不假装读得懂。六条变异全测：采纳→FAIL、移开→PASS，四条守卫（无关假说/向下修正/
不确定结论/自然拒绝）**都不 FAIL**。

**规则写在文档里不够。** 负对照此前是"记得手工跑一次"。现在是一条命令、
`tests/main/check_negative_control.sh`（四案例，6 秒，零模型成本），只断言不变量
（每案例必须红、`g0` 必须绿），不钉具体行（钉了会在判据正当修改时腐烂）。变异验证：把
`mentions` 改成恒 PASS → 两个案例变绿、闸门 exit 1。

提交：`fe841dc`（d2/r2 + 闸门）、`c826fb0`（d2 收窄到 outcome）。推送已核（远端 = 本地）。

### `recovery` × 真实 `claude`：6/6 PASS，而且读得下去

第一次对这案例跑真实 session。`g0` + `r1`–`r6` 全过，其中 **`r2` 走的是"finalize 且同一次动作里
留了证据"那条**（不是"什么都没动"那条）。`ACTIVE` 被改写、三条新证据记录、`EXP-0142` 定为
`interrupted`。定性读（判据的"在场不等于理解"那一半）也强：它先查 job（`never_started`）、
读 heartbeat 停滞 150 分钟、判定中断而不是重跑，并**自己发现漏关了 `execution.status`**。

### 但它同时报出三处 **fixture 真缺陷** —— 三条我都独立实测复核过，全部成立

| | 缺陷 | 我的复核 |
|---|---|---|
| **R-1** | 种下的那处"未完成工作"**本身是坏的**：它给 probe 加的第二行是 `ArgumentParser().add_argument(...).parse_args()` —— 返回的是 Action，再调 `.parse_args()` 就是 **AttributeError**。而 HEAD 的 probe **本来就完整支持 `--closed-loop`** | 两臂都实测：工作树版本崩，HEAD 版本正常打印 5 行 |
| **R-2** | `--closed-loop` **只改打印前缀**（`arm = "closed-loop " if closed_loop else ""`），两臂输出**除前缀外逐字节相同** —— 这个 fixture 的中心对照（offline vs closed-loop）是空的 | 实测 diff：除前缀无差异 |
| **R-0** | manifest 声明 `expected_outputs: ["probes/residual.json"]`，而该 probe 的 docstring 明说**永不写输出文件** —— 这次运行**在构造上无法满足自己的完成条件** | manifest 全文核对 |

**为什么会发生 R-1**：builder 那次种植是三个 `.replace()` 链，而**其中两个的 pattern 在当前 probe
模板里根本不存在** —— `.replace()` 静默失败、不报错。于是作者以为自己种下了 A，实际种下了 B。
这是 B11 那一族的 builder 版本，而**它是静默的**。

**为什么它重要**：D1 判据 2 要判"**理解 dirty diff 的意图**（死掉的 session 正在加
`--closed-loop`）"，而那个意图**推不出来** —— flag 早就在 HEAD 里了，那处 diff 读起来只是**损坏**，
不是**在办的事**。而 `r1`–`r6` 里**没有一条判据对应它**，所以自动判据看不见这一层。

**R-2/R-0 的代价是注意力**：session 顺着链走到了最上游，得到"这个 harness 不做任何计算、五个
residual 都是源码常量"（**对的**，而且正是"先验证 surrogate"那条不变量），随后把
`next_action` 改写成"先确定能不能拿到 trace 数据"。对**研究**这是好行为；对**演练**这是
B8 那一类 —— **没人埋的异常**，让判据分不清"它处理了埋下的谜题"还是"它发现了作者的 bug"。

### 下一步（有顺序）

1. **修 fixture 并补上"本来能抓到它"的断言**（这是上一轮立下的做法）。三条断言，都很便宜：
   - 种下的 dirty diff 必须**只有一处**，且**工作树版本必须能跑**（EXP-0142 的 stdout 就是它跑出来的
     —— 一条断言同时杀掉 R-1 的两个面）；
   - **两臂输出必须有实质差异**（杀掉 R-2）；
   - manifest 的 `expected_outputs` 必须与 probe 实际写什么**一致**（杀掉 R-0）。
   然后 builder 的 `.replace()` 链要改成**断言式**（pattern 不匹配就失败），否则同一处会再静默一次。
2. **`evaluator-conflict` × 真实运行** —— 交接单第一步的另一半，仍未跑。
3. **补一条判据**：D1 判据 2（dirty diff 的意图）目前**没有任何行**在判。
4. `pi` 上跑其余三个案例；V1 候选（协议无提交要求、`max_evidence_iterations` 绑不住复现工作）。

### 动手前必须知道

新增两条进 `GOTCHAS.md`：**B12**（验证检查器时别拿实现里的字符串构造验证用例）、
**B13**（builder 的 `.replace()` 链静默失败 —— 种植式 fixture 必须断言"我种下的就是我以为的那处"）。

---

## 2026-09-17 — 交接

> 新会话从这里接续。**下面每一条都可以当场核验，不是回忆** —— 命令与期望输出都给了。详尽的
> 叙述在下面那条（第六轮）里，这里只放**立刻要用的东西**。

### 可核验的现状

```bash
git rev-parse --short HEAD          # c85cef5
git status --porcelain              # 空
git ls-remote <ssh-url> main        # c85cef50 —— 与本地相同
```

```bash
python3 tools/researchlog validate >/dev/null 2>&1;                  echo $?   # 0
python3 tools/researchlog reconcile >/dev/null 2>&1;                 echo $?   # 0
python3 tools/check_workflow_block.py >/dev/null 2>&1;               echo $?   # 0（80 工作流 / 116 名字 / 8 warning）
python3 tools/install_research_skills.py --self --check >/dev/null 2>&1; echo $?  # 0
```

**注意这两行的写法**：不接管道、不静音 —— `cmd | head -1; echo $?` 读的是 `head` 的退出码。
见 `GOTCHAS.md` C9。

| | 值 |
|---|---|
| **V0 状态表** | 21 行 = **19 ✅ + 2 ⏸**（#1/#22，架构师暂缓）+ 0 ❌ |
| **`research/` 轨道** | `ACTIVE.status: idle`、`ledger/` 0 条、`runs/` 0 个 —— **正常状态，不是空缺** |
| **案例集** | 4 个 builder + `run_case.sh` + `verify_case.py`，见 `docs/V0_CASES.md` |
| **工具动词** | 15 个（含本轮新增的 `boundaries`） |

### 两条轨道别混

`research/` 是**这个工具所服务的研究**的状态（`researchlog` 维护）；`docs/WORK_LOG.md` 是**开发这个
工具**的记录。本仓库的 `ACTIVE.json` 保持 `idle` 是**正常状态**。

### 本轮（第六轮）做了什么

1. **案例集跑起来了**，架构师亲手跑了两遍：`bootstrap claude` **7/7 PASS**、`rotation pi`
   **4 PASS / 2 UNJUDGED / 0 FAIL**（#1/#22 的第一份端到端证据）。
2. **案例发现了我 fixture 里的真 bug** —— docstring 声称的 `total_latency` 分解对 217/2000 行不成立
   （重试循环每轮加一次 service 抽样，而 `service_time` 只记第一次）。已修，并加了**本来能抓到它
   的断言**。
3. **`BOUNDARIES.md` 补上了动词**（第 4 例"声明了但没人接线"，且在**那句声称问题已修好的话里**）。
4. **判据 5 的形状问题**修了：新增 `c6`（run 先完成时判"有没有把 loop 走完"）。
5. **实验回答了它自己**：M3 不依赖那个缺陷 —— 修好之后 7/7，而且研究质量**强于基线**。

### 下一步（有顺序）

1. **跑 `recovery` 与 `evaluator-conflict`** —— 它们的检查器已写、已变异验证，但**从未对真实运行
   跑过**。这是案例集最后一块没被真实运行碰过的地方。
   ```bash
   tests/main/run_case.sh recovery claude
   tests/main/run_case.sh evaluator-conflict claude
   ```
2. **`pi` 的完整案例**：`rotation pi` 已跑（4 PASS / 2 UNJUDGED / 0 FAIL），但**其余三个案例没在
   pi 上跑过**。#1/#22 需要的是"另一个客户端能进入 Research Mode"，现在各有一个数据点。
3. **V1 候选**（详见第六轮 entry）：协议**无提交要求**（`code_state.commit` 因此可能指向 fixture
   自己的 commit，让 #18 的双向映射没有东西可映射）；`max_evidence_iterations` **绑不住复现工作**。

### 动手前必须知道

**全部在 `GOTCHAS.md`，读它**（那是当前为真的清单，与这份日志分工不同：日志说"当时发生了什么"）。
本轮新加的四条最相关：

- **B10** "还没发生"不是"不可能发生" —— 快照不是判决
- **B11** 写检查器时最大的缺陷类：**检查的东西与标签声称的相邻**（本轮 11 例）
- **C8** 判别人正在跑的任务用 PID + artifact 双信号；**别用代理信号代替直接测量**
- **C9** 别静音你读判决的检查；别让管道替你决定退出码是谁的

**一条给下一个会话的**：本轮我自己的**验证程序**犯了 6 次同类错误（比代码里那 11 处更难自查）。
**凡是要据以下结论的数字，先确认你读的确实是那个东西的数字。**

---

## 2026-09-17（第六轮）— 案例集跑起来了，而它发现的第一个缺陷是我的

### 会话概览

架构师把目标定成"**可用于长时间自主研究 AI 编程**"，V0 是路标；并把案例集**亲自跑了两遍**
（`bootstrap claude` 与 `rotation pi`）。两个案例都跑完并留下判定。**本轮最有价值的东西不是任何
一个判定，而是 `bootstrap` 那次发现了我 fixture 里的一个真 bug —— 而我在它发现之前，先给出了
两个错的诊断。**

### 判定

| 案例 | 结果 |
|---|---|
| `bootstrap claude` | **7/7 PASS**（旧 fixture，含那个分解 bug） |
| `rotation pi` | **4 PASS / 2 UNJUDGED / 0 FAIL** —— #1/#22 的第一份端到端证据 |

`rotation pi` 那次 pi 走完了整个 loop：等到 run 结束、读结果、记 `EV-…6dd6`、以 `belief_delta: none`
关掉 `RB-021`、带完整 provenance footer 提交。**它甚至通过 router 加载了 `session-continuity.md`**
—— 修好 router 之前 Claude 三次都没读到那份文件。

### 案例发现的 fixture 缺陷（我的）

`bootstrap` 的 session **独立重算了**恒等式 `total_latency = queue_wait + service_time +
backoff_wait`，在 2000 行里查出 **217 行违反**，记为一次 `counts: true` 的迭代（`refuted` /
`refined`）。**它是对的**：重试循环每轮 `total += wait + rng.expovariate(...)` 加了一次新的
service 抽样，而 `service_time` 只记第一次 —— 每个重试过的请求**差 1.6–35 ms**。

而 docstring 明写"Total latency decomposes into…"。**fixture 既没有那个性质，又声称有** ——
本仓库最忌的形状。已修（`6267fe9`）：`service_time` 累加全部 attempts；docstring 改成
"成立到列所记录的六位小数"；builder 加断言，**变异验证在 `0.034606s` 触发 —— 正是 session 报的数**。

### 我自己被证伪的三个诊断（都记进 GOTCHAS）

1. **"旧 fixture 把消融替它做好了，所以 M3 不可能发生"** —— 证伪：它在那个 fixture 上产出了
   `counts: true` 的迭代，而且**用过**那条对照臂。撤掉对照臂的改动已**回退**。教训：**"还没发生"
   不是"不可能发生"的证据**（记入 B10）。
2. **"交接没有接线"** —— 证伪：`ACTIVE.next_action` 留下的是"seeds 0..199 多种子复现两个臂，
   记录每个 seed 是否 cascade、第一个重试的 request_id、以及两臂的 p99/max"，**正是
   `research-bootstrap` 的成功条件**。交接是工作的。
3. **"两个运行都已结束"** —— 见 C8：我用一次被自己 `head` 截断的 `ps` 判了一个**还在飞**的运行，
   而 artifact 信号（transcript 正在长）就在同一条消息里。

### 检查器的六处修正

| 缺陷 | 后果 |
|---|---|
| `tool_digest` 含 `__pycache__` | 运行工具就会生成它 → 守卫对**每个正常 session** 报"你改了裁判" |
| `c5` 判"文件变了没" | 收尾写 = 意图写 → **假 PASS**（pi 的写发生在 run 完成之后 3.5 分钟） |
| `b5` 标签"2-3"而检查只要 ≥1 | 标签与判的东西不一致 → 按指南改成"≥3 条记录且有 ≥1 条 counted" |
| `--json` 后面跟人读的句子 | 输出无法被程序解析 |
| `git diff` 看不见未跟踪文件 | 新建的证据记录**完全不报** |
| `--porcelain` 里删除也算变化 | **删掉** ledger 会读成**追加**了证据 |

### 协议缺口：没有任何地方要求 session 提交

实测：`bootstrap` 那次的 `research/` **整个是未跟踪的**（`?? research/`），只有 builder 一个 commit。
查协议：`AGENTS.md` 没有、`research-bootstrap` 没有、`research-engineering` 只在 router 里有一行
"**about to commit** 时去看 git reference" —— 那是"当它要提交时"，不是"它必须提交"。

**后果是实的**：`record` 把 `code_state.commit` 写成当前工作区 commit；session 不提交，那条记录就
指向 **fixture 的 commit**，#18 的 Git↔Evidence 双向映射**没有东西可映射**。旁证：pi 那次提交了
（`3090983`），claude 这次没有 —— **两个客户端行为不一致，而协议对两者都没要求**。

**这是协议层的洞，归 V1**，不是案例能修的。

### 后半段：`BOUNDARIES.md` 是我们声称已经修好、而实际漏掉的那一个

架构师自己起了第二次 `bootstrap`（修掉分解决 bug 之后的 fixture）。它 8.5 分钟就产出了第一条
记录、问的正是案例的方向 —— **但随后卡住了，而卡住的原因是一个不存在的动词。**

它最近 8 个动作全在找一条路：**grep 工具源码里的 `boundaries`（两次）、grep skill 文本、读
`commands/init.py`、跑 `validate`**。查证结果：

| 环节 | 状态 |
|---|---|
| `research-bootstrap/SKILL.md:38` | **"Identify HARD boundaries"** —— 协议明确要求 |
| `research-engineering/SKILL.md:242` | `BOUNDARIES.md → research:boundaries` |
| 写入路径 | **不存在**（14 个动词里没有 `boundaries`；只有 `init` 写空骨架） |
| schema | **`boundaries.schema.json` 不存在** |
| `AGENTS.md:220` | **"Every canonical file has a verb"** —— 假的 |

**而那句假话的旁边，正是在解释"这曾经不成立，已为 `CURRENT.md` 与 `ENVIRONMENT.md` 的表修好"
—— 当年修那两处时漏掉了它。** 不能手改（同一份契约禁止），不能命令改，于是无路可走。

**已修（`93104dd`）**：新增 `researchlog boundaries`（读 / `--set` / `--add TIER=FILE`）、
`boundaries.schema.json`、注册、`validate` 覆盖（含**提交预算用尽报 error** —— 文件自己的散文
就是这么规定的）。`--add` 用**文件**而非命令行数组，因为**两次运行实际都这么干**：写 `/tmp`
临时 JSON 再喂给 `env declare`。**entry 的 `id` 之外刻意不约束形状** —— 与 `capability_map`
同一个判断，那属于设计决定。

**顺带抓到两处**：`--set nonsense=1` 原本**静默接受**（打错字段名就写进 canonical 状态）→
`additionalProperties: false`；守卫测试先失败、且它是对的（它把 schema 数量写死，docstring 写明
"应当逼人停下来想新 schema 是否完整"）→ 按它的意图更新。

**`AGENTS.md` 那句话改准了**，并点名唯一的**刻意例外**：`ARCHITECT.md` 的 signal 手写，因为
signal 是架构师说过的话，`source_text` 就是重点。

### 判据 5 的形状问题：修的是判据（`c9784be`）

见下面"判据 5 的形状问题"一节被替换的部分。新增 **`c6`**：run 完成之后，session 该做的是
**把 loop 走完**（为它留下一条证据记录 + 把 `execution.status` 移开 `running`）。每条判据在另一种
形状下报 `UNJUDGED`，所以这一对无论场景落在哪边都覆盖到了。

### 检查器的缺陷总数：**9 处，全部同一形状**

前 6 处在上面那张表里；后半段又 3 处：`c1`（只认字面命令，而判据也收"读 manifest"）、`d2`
（只读 `next_action`，嘴上拒绝的过不了）、以及写 `c6` 时差点犯的 `changed_since`（**porcelain
查不到已提交的记录** —— pi 提交了它的证据，工作树干净，**一个走完 loop 的运行会被读成"没记录
任何证据"**）。

已记成 `GOTCHAS.md` **B11**，附两个本来就能抓到每一例的检查：**把 label 和它下面那几行并排读
一遍**；**失败消息描述的检查，代码真的做了吗**（`c1` 的消息写着 "or reads the manifest"，
代码只查了前半句）。

### 开放项

1. ~~修完分解 bug 之后，M3 还会不会发生？~~ **已回答：会，而且与那个 bug 无关。** 见下。

### 实验的答案：M3 不依赖那个缺陷（第三次运行，`7/7 PASS`）

架构师在修好的 fixture 上跑了第三次 `bootstrap`。**`g0` + `b1..b6` 全过**，`ledger=23`、
`counted=2`。所以"把已知 bug 留着制造迭代"那个诱惑是不必要的 —— **fixture 不说谎之后，它照样
撑得住研究。**

**而这次的产出强于基线。** 基线发现的是我 fixture 的数据缺陷；这次做的是一条完整的因果链：

- **假说 H-2**：retry 的要害是谓词量的是总时长（queue_wait + service）。**它造了 queue_wait 免疫
  的变体，并把重试率匹配到基线**（控制混淆）→ **崩塌照旧 → 自己的假说被自己推翻**
  （`EV-…d353`，E2，`refuted`，`belief_delta: overturned`）。
- **收窄到"重试反馈回路本身"**（`EV-…5508`，E2，`confirmed`，`refined`）：只有从不重试的变体稳定；
  连完全去掉退避（`--backoff-base 0`）仍崩（p99 965.5 ms vs 健康 19.9 ms）。
- **它指出我问的是个假二分**："The architect's question was queue wait or retry. **It is neither** …
  the service has **two operating points**"，第二个在 ρ 1.2–10.6 且**是吸收态**。
- **它验证了自己的仪器**：给 `sim/queue.py` 加了四个保持基线的开关，**每加一个就重跑一次 G1 门**，
  确认默认路径与 `data/requests.csv` **逐字节相同** —— 即不变量 #4 的"先验证 surrogate 再据它下
  结论"。commit 带完整 provenance（Hypothesis / Evidence / Findings / Outcome / Level / Block）。
- **它提交了**（基线没提交）。我先前记的"协议无提交要求"那个洞，**行为上被自行闭合了**，但
  **要求仍然不存在** —— 归 V1 的判断不变。

**一条对我自己的判决**：基线那条 M2 证据是"它**完全没有碰** `sim/` 与 `data/`"，我差点把它当成
M2 的判据。**那样写，这次运行会被误判失败** —— 而它改动 `sim/queue.py` 的方式（加仪器 + 证明
默认路径不变）**恰恰是 M2 想看到的**。"没碰 sim/" 是那种美德的一种形式，不是它的定义。
**这是第 10 个"检查与它声称的东西相邻"的实例，只不过这次我是在写下去之前停住的。**

### 我自己的验证程序也犯了同一个错（第 11 例）

判它的时候我用 `--tool-hash-of .` 现算期望值 —— 而 **`.` 是 SOURCE_ROOT，它在这轮被我改了**
（加 `boundaries`）。于是 `g0` 报 FAIL，我差点当成"session 改了判它的工具"。**git 说得很清楚：
没改。** 我判错的原因和这一轮反复出现的完全一样：**在错误的时刻取了一个值，然后把它当成关于
另一件事的事实。**

顺带揪出**指南里一条恒真的命令**：手工流程写的是 `--tool-hash-of <fixture>` 再传回
`--tool-hash` —— **自己跟自己比，永远通过**。修法不是提醒顺序（手工流程没有机制强制顺序），而是
新增 `--at <baseline>` **从建 fixture 那一刻的 commit 读工具**，于是**什么时候算都一样**。

### 两个只记录、未修的设计观察

- **`max_evidence_iterations` 绑不住复现工作。** 它记了 23 条而 `counts: true` 只有 2 条，预算只数
  counted 的（2/4）。**一个把工作诚实标成"非迭代"的 session 可以永不触发预算** —— 真正约束它的
  是 wall-clock 与 token 预算，而**那两个工具都不强制**。
- **`ACTIVE.status = idle` 而它在干活**（16:06 标 idle，之后又干了 8 分钟），而 `reconcile` 与
  `validate` 都是 exit 0。**工具原理上抓不到"session 在不在干活"这一半**，所以这条我认一半。
2. **协议缺提交要求**（见上），归 V1。
3. `capability_map` 仍无形状（架构师的设计决定）。
4. `recovery` / `evaluator-conflict` 的检查器已写但**从未对真实运行跑过**。
5. 判据 5 的**形状问题**（run 在 session 活着时完成，判据前提不成立）—— 要的是新判据，不是放松。

### 下一步

1. **单独**跑一次 `bootstrap`（新 fixture，一次一个案例），看 M3 在缺陷修掉之后还立不立得住
2. 跑 `recovery` / `evaluator-conflict`，让这两个检查器第一次见真实运行

### 动手前必须知道（本轮新增，已同步 `GOTCHAS.md`）

17. **"还没发生"不是"不可能发生"**（B10）—— 从 `runs/` 空推出"M3 不可能"是错的；快照不是判决
18. **判一个别人正在跑的任务用 PID + artifact**（C8）—— 一次被过滤/截断的 `ps` 连信号都不算；
    **别用代理信号代替直接测量**（事件时间戳 ≠ 文件 mtime）
19. **fixture 要断言它自己声称的性质**（本轮的分解决 bug：断言写在 builder 里，变异验证能触发）

---

## 2026-09-17（第五轮）— V0 收尾：判据 5 的三次运行，与案例集

### 会话概览

架构师定了目标与优先级：**可用于长时间自主研究 AI 编程**；V0 是路标不是终点，条件合适就推进
V1/V2；**不要求每一步精准工程级符合**。据此我**撤回**了一版提议（给 V0 状态表加"证据形式"列去
对齐 3 行）—— 那是账目，不是能力。同轮委托：**一批核心验证案例**，跑在临时项目目录里，由 coding
agent 完成，有执行指南，可自动验收也可手工执行。

主线是 **A（重跑 D2，判判据 5）**，跑了三次。

### 判据 5 的三次运行：FAIL / FAIL / PASS

| 次 | 条件 | 结果 | 关键证据 |
|---|---|---|---|
| 1 | 旧协议文本 | ✗ | `ACTIVE.json` mtime 未动 |
| 2 | 同上，但 transcript 移到 fixture 外 | ✗ | mtime == builder 那次 commit 的时刻；`git diff HEAD` 为空 |
| 3 | **router 修好后** | **✓** | `ACTIVE.json` 相对 baseline 变了；写的是**意图**（"Decision: attach/observe"，"Wait for EXP-0200 to exit, then read probes/sweep.json"） |

**第 2 次是第 3 次有意义的原因**：它排除了"是我的台账污染导致的"。两次同结果 → 单变量成立。

### 根因：不是那句话，是路由

第 2 次做了链路追踪：session 读了 AGENTS.md 列的**恰好那 6 个** canonical 文件 + manifest +
probe，**对任何 reference 的 Read 调用为 0** —— 而 skill **确实加载了**（init 事件里它在 100 个
skill 中）。所以 `session-continuity.md` 从未进入它的工作路径。

`SKILL.md` 的 router 表里**两行匹配同一状态**，先匹配的那行只说了"先 reconcile"、**不指向任何
reference**；指向 `session-continuity.md` 的那行在后面。session 走完 reconcile 就停了。

改那一行（`e9044b8`）→ 第 3 次 5/5。

**上一轮那句"它拒绝预写，因为那是 post-hoc 合理化"是错的解读** —— 那是从行为倒推的理由，不是
它说的。它只是没读到那句话。**措辞一直是对的。**

### 交付：案例集（`c8e4d00`、`ea389f3`）

```
tests/main/run_case.sh               建 fixture → 驱动 agent → 判据（claude / pi）
tests/main/verify_case.py            从产物判，三态：PASS / FAIL / UNJUDGED
tests/main/build_bootstrap_case.sh   M1/M2/M3/M5 的 fixture（新的）
docs/V0_CASES.md                     执行指南：判据表 + 自动跑法 + 手工跑法
```

- **两种跑法共用同一套判据** —— 只能用一种方式跑的案例，没法拿自己的 harness 对照。
- **`UNJUDGED` 是第三种裁决** —— 产物判不了就明说，**绝不静默算通过**。
- rotation 与 bootstrap 有产物检查器；**recovery / evaluator-conflict 还没有**，
  `verify_case.py` 对它们 exit 2 并指回判据表（已在指南里列为已知未完成项）。

**判据 5 的检查器判的是"发生过一次写"，不是"字段里写着什么"** —— builder 自己在 fixture 里种了
"Wait for the sweep to finish"，所以读内容的检查**恒真**。`--baseline` 因此是必需的。

### `pi`：三点实测，没有一条是等价替换

1. 原生读 `AGENTS.md` / `CLAUDE.md`（但**必须 source 项目 `.env`** 才有凭据）。
2. **`--skill` 要绝对路径** —— 传相对路径时**静默加载 0 个**项目技能、转去加载用户级的 18 个。
   **没有报错的失败。**
3. **`--no-skills` 是 pi 这边的 workflow block** —— 不加它，加载的是用户级 `brainstorming` /
   `writing-plans` / `test-driven-development` / `project-state`，正是 AGENTS.md 声明机械禁用的
   那批。**pi 没有项目级等价机制。**

另外：**`pi auth check` 报 `ready` 只表示"配了"，不表示"有效"** —— 三个 provider 全 ready、全 401。

### 顺带：`.env` 泄漏风险

架构师把 `MINIMAX_*` 放进项目本地 `.env`，而 `.gitignore` 没覆盖它，`git status` 里是 `?? .env`，
提交流程用 `git add -A`。已修（`7ff13bb`）。

### 开放项

1. **`recovery` / `evaluator-conflict` 的产物检查器未写** —— 判据在指南里有，检查器没有。
2. **`pi` 的完整案例没跑过** —— 技能加载那一环已验证，端到端没有。#1 / #22 因此仍未验。
3. **`bootstrap` 的 fixture 从未被真实 session 跑过** —— builder 自断言通过，端到端没有。
4. `capability_map` 仍无形状（设计决定）。
5. 指南里"复现 session A 的 fixture"那份配方**不可复现** —— 它自称造"空项目"却不含研究对象，
   而 M2/#2 的证据都指向有可跑的 `sim/`。`build_bootstrap_case.sh` 按证据建，不按配方建。

### 下一步

1. 跑一次 `run_case.sh bootstrap claude`（第一次真实运行，会暴露 fixture 与判据的问题）
2. 跑一次 `run_case.sh rotation pi`（端到端验 pi，同时给 #1/#22 证据）
3. 补 recovery / evaluator-conflict 的检查器

### 动手前必须知道（本轮新增，已同步进 `GOTCHAS.md`）

13. **判据要判"发生过什么"，不要判"字段里写着什么"**（B6）—— fixture 种好的答案会让检查恒真
14. **自断言的 glob 要排除 vendored 目录**（B7）—— `rglob("test_*.py")` 会算上工具自带的测试
15. **台账污染会让判据无法归因**（B8）—— transcript 写进 fixture 是"没人埋的异常"
16. **`pi` 的调用形状**（D4）与 **凭据文件要先 `git check-ignore`**（C7）

---

## 2026-09-17（第四轮）— gotcha 从日志里搬出来，研发轨道补上入口

### 会话概览

架构师问的是结构问题："`research-engineering` skill 负责项目下的研究课题，那**本项目的研发**如何
管理？" 答案是两条轨道两套制度，而且**不对称是刻意的** —— 但审计下来发现研发轨道有三个薄弱点，
这一轮修了前两个。

### 两条轨道为什么不对称（结论，值得记住）

| | 研究轨道 | 研发轨道 |
|---|---|---|
| 载体 | `research/` 八件 canonical + `ledger/` + `runs/` | `docs/WORK_LOG.md` + `docs/V0_ACCEPTANCE_GUIDE.md` |
| 断言的是 | **现在为真** | **当时发生了什么** |
| 机制 | schema + 每文件一个动词 + `validate` + `reconcile` | 只追加、带日期；新会话读**最新一条** |

研发轨道不需要 `researchlog` 那一套，理由 `WORK_LOG` 开头自己给过：**过期的条目看起来就是旧的，
不会伪装成现状**（而"当前状态快照"需要被重新生成与校验）。这是**事件日志 vs 状态快照**之分。

### 三个薄弱点，以及修了什么

1. **gotcha 注册表住在事件日志里** —— 12 条编号跨 4 条 entry，而 gotcha 是**当前为真**的东西，
   过期时不像日期那样自己显形。新建 **`docs/GOTCHAS.md`**（`c045a6a`）：一页、可编辑、声明
   "这是状态不是日志"，**修好的直接删掉而不是追加"已修"**。B5 与 A2 两条原先只以散文形式散在
   正文里，一并落成条目。
2. **一半的操作知识只在 Claude 专有的记忆里** —— agent memory 有 5 条 WORK_LOG 没有的，其中
   **`.gitignore` 必须锚定**、**`environ` 快照是 `changed` 谓词的前提** 是**工具行为事实**，
   本该是两个客户端都读得到的项目 canonical。已迁入 `docs/GOTCHAS.md`，记忆改成**指向它**，
   不再维护第二份。
3. **研发轨道唯一的"状态型"产物（V0 状态表）是手维护的，且 `README` 的 Status 只有一行 `V0`** ——
   外部读者进不来。README 的 Status 现在写明 V0 的含义（21 行中 19 条有实测证据、2 条架构师暂缓、
   0 条失败）并点名三个文件。

**外加一条不在清单里但必须做的**：`AGENTS.md` 指向 `docs/GOTCHAS.md`。它是**唯一**每会话都加载的
文件 —— 一个从那里没有链接的注册表会被整个错过，那样第 1 条就白做了。

### 核实（不是回忆）

```
c045a6a · 工作树干净 · 真实远端 main == 本地 HEAD（git ls-remote 核实）
python3 tools/check_workflow_block.py  → exit 0（80 交付工作流 / 116 名字）
python3 tools/researchlog validate     → exit 0
python3 tools/researchlog reconcile    → exit 0 clean
```

顺带再确认一次：`origin/main` 这个 **remote-tracking ref 仍然是陈旧的**（停在 `e3ee9f1`），因为
推送走的是显式 SSH URL。**要判断本地与远端是否同步，用 `git ls-remote`，不要用 `git status -sb`。**
已写进 GOTCHAS.md C2。

### 开放项

- **`capability_map` 仍无形状** —— 设计决定，按架构师规则不由 Claude 定。
- **#1 / #22 暂缓**（客户端矩阵项）；若日后要做，不必等 codex。
- 漂移检查仍有 8 条 warning（低价值，可长期挂着）。
- **`project-state` 与全局 CLAUDE.md §18 的冲突已解**：`AGENTS.md` 明文 supersede 了"跑
  `/project-state update`"那条全局建议。本轮再次确认没有活的冲突。

### 下一步

没有待做的收尾。剩下的都是架构师决定项（`capability_map`）或已明确暂缓项（#1 / #22）。

---

## 2026-09-14 — 评审收官、V0 验收操作化、三个演练

### 会话概览

关闭 V1.5 评审的**全部 19 项**（P0-1..5 / M-1 / P1-1..12 / D-1）；把设计文档 §20.1 的 22 条验收
拆成 **Day-1 must（5）/ V0 complete（16）** 并操作化到可执行；§26.4 的六个故障注入在 CLI 层
实测；三个 session 级演练（D1 恢复 / D2 rotation / D3 evaluator conflict）脚本化、跑过、结果入档。
**17 个 commit**，工作树干净。

这一轮最有价值的产出不是那些修复，而是**那条缺陷模式**：绝大多数缺陷是"声明了但没人接线"
（`git_recover` 参数没人传、`max_evidence_iterations` 没有消费者、`completed_evidence_iterations`
没有写入者、示例 signal 是合规的真块），而测试之所以放过它们，是因为**测试注入了被测字段本身**。

### 技术变更

**`tools/researchlog/`**

- `constraints.py` —— Architect Signal 的字段契约（八类、`source_text` 对
  CONSTRAINT/DECISION/VETO 强制、`scope`/`expiry` 对 CONSTRAINT 强制）；块成员改由 `block_id`
  认定；`BLOCK_ITERATION_BUDGET_EXCEEDED`（用**派生** count 在块**运行期间**报）；
  `count_evidence_iterations`、`identified_hypotheses`
- `commands/validate.py` —— 假说注册表改用 `ACTIVE.hypothesis_ids`（原先把 EV id 空间当注册表，
  100% 误报）；四种 kind 都做 schema 校验（原先从不校验 manifest）；报告非当前 schema 版本
- `commands/reconcile.py` —— 把 ACTIVE 的加载结果加入报告（原先对不可读的 ACTIVE 报
  `clean: true`）；signal 完整性；抽出 `_signal_blocks`
- `commands/record.py` —— 从 ACTIVE 落印 `block_id`
- `commands/active.py` —— 关块时派生并写入 count；开新块重置块摘要
- `state.py` —— 接上 Git 恢复回退（`git_recover` 此前从未被传入）；`Ledger.findings_block`
- `jgit.py` —— code identity 排除 `research/`（原先每写一条证据就改变一次身份，导致
  `compare` 的 `COMPARABLE` 不可达）
- `schema/registry.py`、`schema/__init__.py` —— 新增 `version_findings`
- `schemas/evidence.schema.json` —— 新增 `block_id`

**skills** —— `SKILL.md`（块归属语义、预算在运行期生效）；`references/architect-signals.md`
（signal 契约、echo-back、**选项框的文案不是架构师的原话**）；`references/session-continuity.md`
（块归属、schema 兼容表）；`references/evaluation-design.md`（E2/E3 的隔离：frozen replay +
hash + dev/holdout 只读）；`research-status/SKILL.md`（末尾英文 key 的 YAML snapshot basis、
不一致时给出下一步）

**状态与模板** —— `templates/research/ARCHITECT.md` 与 `research/ARCHITECT.md`：示例不再放在
`research:signal` 围栏里（**围栏就是形状与状态的全部差别**，骨架现在自带 0 条 live signal）

**演练工具** —— `tests/main/build_recovery_drill.sh`、`build_rotation_drill.sh`、
`build_evaluator_conflict.sh`。三者都会**自断言自己要测的状态确实存在**，失败时报
"改 fixture，不要改判据"

**文档** —— `docs/V0_ACCEPTANCE_GUIDE.md`（新增）：拆分判据、两张表、三个演练的判据与结果、
§26.4 实测表、每个缺陷的修法

### 测试结果

- `researchlog` 的四个模块（`test_constraints` / `test_integration` / `test_commands` /
  `test_schema`）**152 项全绿**
- `validate` exit 0 / `reconcile` exit 0 clean（在仓库根跑）
- `install_research_skills.py --self --check` —— 两个 client 无漂移
- **每个修复都做了变异验证**（把修复改回去，测试确实失败），结果写在各自 commit message 里
- 三个演练的自校验：D1 → `reconcile` 恰好只报 `MANIFEST_STALE_RUNNING` 且 `validate` 干净；
  D2 → `job` 报 alive + 双清；D3 → proxy 在 window 0.40 报 0.51、0.25 报 0.81，两条记录
  `diff_sha256` 相同，`compare` 判 **COMPARABLE**

### 开放项

- **⚠️ 本轮未推送。** 本会话无网络（`git fetch` 报 `Error in the HTTP2 framing layer`），且这个
  工作副本没有 upstream、没有 remote-tracking ref、reflog 里 0 条 push —— **远端状态未知**。
  17 个 commit 只在本地。有网络时：`git push -u origin main`
- **D2 / D3 的结论对应修 fixture 之前**的版本，需在新 fixture 上重跑；D2 还会顺带验证
  **收紧后的判据 5**（要求把"在等什么"写进 `ACTIVE`）
- D1 的判据 1 与判据 5、以及所有"说出……"类判据，**只能从 transcript 判**；目前只核实了产物能
  证明的那一半
- V0 complete 里需要**第二个客户端**（#1、#22）、**长时自治块**（#12 的完整形态）、
  **并发写入**（#15）的项尚未做过。#11 与 #14 已由 §26.4 探测覆盖
- `research/ACTIVE.json` 的 `git.base_commit` 仍是 bootstrap 的 `403383d`（没有块开过，从未更新；
  `reconcile` 不检查它，无功能影响 —— 但别据此以为状态落后）
- `docs/V0_ACCEPTANCE_GUIDE.md` 的位置：它是**题材范围**的参考材料（V0 验收），按全局约定 §4
  属于"核心文档"（`docs/design/`）。留在 `docs/` 根还是挪过去，待定

### 下一步

1. `git push -u origin main`
2. 在**修好的** fixture 上重跑 D2 与 D3 —— 命令与判据表见 `docs/V0_ACCEPTANCE_GUIDE.md`
   的 D2 / D3 两节。收尾：`kill $(jq -r .execution.pid_or_job_id research/runs/EXP-0200/manifest.json)`
3. 若架构师保留了 transcript，回填需要 transcript 的判据；没有就标"未判定"，不要猜
4. V0 complete 的剩余项（第二个客户端 / 长时自治块 / 并发写入）

### 动手前必须知道

1. **`researchlog` 按 cwd 向上找 `research/`，不看脚本路径。** 检查一个副本（例如演练 repo 里的
   `tools/researchlog`）时必须先 `cd` 进去，否则它会去检查你**当前所在**的仓库 —— 而且很可能报
   clean，于是你得到一个关于错误对象的"通过"。踩过，误读了一次演练结果。
2. **跑全量测试前必须先问架构师**，哪怕改动落在共享底座上。先跑覆盖改动模块的定向测试并报告。
3. **造演练 fixture 的两条铁律**：每条主张都要有 artifact 支撑；每个异常都必须是刻意埋的
   （工作区文件在捕获身份**之前**就位、探测桩只打印不写工作区、可调参数走**声明的 input** 而不是
   工作区文件）。并且让 fixture **自断言**这两条 —— 否则会悄悄腐烂。

---

## 2026-09-14（第二轮）— 推送、无头重跑 D2/D3、不变量 #4 接线

### 会话概览

先把上一轮**未推送**的 17 个 commit 推上 `origin/main`（远端此前确实空，`ls-remote` 无任何分支）。
然后在**修好的** fixture 上重跑 D2 与 D3 —— 这次由 Claude 用无头方式驱动，因此 transcript
第一次可读，判据里"说出……"那一半第一次可判。

**D3 5/5。D2 4/5** —— 不过的那条恰是上一轮被收紧过的**判据 5**，而且失败方式很有信息量（见下）。
D2 的 session 另外交出了本轮最有价值的产出：**它拒绝把 `41/60` 当结果**（拒绝理由是硬编码字面量，
判 `EVIDENCE_INVALID` + 如实计为零进展），并独立报了 fixture 的两处 state 层缺陷。

### 技术变更（5 个 commit，均已推送）

- **`101dc46`** —— 三个 drill builder 之前只复制 `AGENTS.md`，**没复制 `.claude/settings.json`**，
  而 AGENTS.md 写着那个 workflow 屏蔽是 mechanical、"the deny list ... is the load-bearing part"。
  builder 现在带上该文件并自断言。**第一版断言是死的**（写的是"fixture 与源仓库一致"，而 fixture
  就是源的字节副本 —— 恒真、永不失败），变异验证抓到后才改成对内容的断言。
- **`1de3c9f`** —— **不变量 #4 接线**。`_check_surrogate` 从不比较 `required_causal_features` 与
  `missing_or_distorted_features`，所以"必需因果特征全缺 + `VALID_SURROGATE` + `promising`"能一路
  通过。新增 `SURROGATE_VERDICT_CONTRADICTS_MISSING_FEATURES`。**是 D3 的 session 自己发现并上报的。**
- **`3325935` / `b11e08c`** —— 参考文档补上"这条规则由谁执行"，并把 docstring 从下绝对断言
  （"绝不会冤枉"）改成只陈述机制。
- **`32d1b33`** —— recovery fixture 的契约把**宽主张**当成了 `target_causal_claim`，同时把它要求的
  `actuator dynamics` 列为 missing 却宣告 `VALID_SURROGATE`。查设计文档 §6.5.3 才敢动。

### 演练判据

**D3 —— 5/5。** 详见 `docs/V0_ACCEPTANCE_GUIDE.md`（含每条判据的可核实证据）。两条超出判据的
表现：它**反向发现 E4 证据是单臂的**（没有收窄前的对照臂，所以那条 `refuted` 其实不足以区分
reduced/preserved/caused），并把要那一臂作为**架构师范围内的请求**提出；它**没有回改历史记录**，
而是写新证据。

**D2 —— 4/5。** 判据 1–4 过（无第二次 launch、没替它收尾、没杀进程、状态干净）。
**判据 5 未满足**：等待期间 `ACTIVE` 一字未动。但它**不是疏忽，是拒绝预写** —— 理由是"观测没到就
先写，正是 post-hoc 合理化要防的那件事"。这个理由对**结论**成立，而判据要的是**意图**；意图不是
post-hoc 合理化，恰恰相反，**未写下的意图事后无法与编造区分**。判据的修法是协议设计问题（接受
manifest heartbeat 作为 attach 证据，或在 `session-continuity.md` 里写明"等待期写意图、不写结论"），
**不是 session 的错**。

### 这一轮暴露的 fixture 缺陷（都还没修）

1. **缺 workflow 块**（A）—— 已修。
2. **D3 的污染记录现在造不出来了** —— 已改成"先写诚实契约、事后补丁"，并自断言补丁生效。
3. **D1 的契约写错了 target claim** —— 已修。
4. **D2 的 canonical state 是三个互不相关的示例拼的**（D 节）：`research_question` 是本轮新造、
   `H-037/H-039` 来自 `experiment-review.md` / `diagnosis.md`、`case-31/37/42` 来自
   `evaluation-design.md`，而五份 canonical 文件全是空骨架。后果是 session **无路可走** ——
   它无法从 state 设计实验，而"Do not invent missing prior state"又不许它补。**未修。**
5. **fixture 里 `AGENTS.md` 指向不存在的路径**（E 节）：`docs/WORK_LOG.md`（AGENTS.md 写的是
   "**Start here**"）、`skills/`、`tools/install_research_skills.py` 全不存在。根因与 A 同族 ——
   `CLAUDE.md` 是本仓库的适配说明，整份复制进 fixture 等于让它声称一个没有的布局。**未修。**

### 工具缺口（两轮独立发现，据此确认）

**`researchlog env record` 写不了 `ENVIRONMENT.md` 的三张表。** D3 与 D2 **独立**报出同一处：
没有 `limitations` / `capability_map` / `available` 的写入路径，`tools/researchlog/schemas/` 下
根本没有 `environment.schema.json`。两者都没有绕过、没有手改 canonical JSON，而是把缺口报上来。

### 开放项

- **V0 远未完成。** 有实测证据的约 6 条（M4 / #10 / #11 / #13 / #14 / #12 的一半）；明确没做过的是
  #1、#22（需第二个客户端）、#12 完整形态（需长时自治块）、#15（需并发写入）、#16 端到端复验、
  #18、#19（需移除适配器）、#20、#21。**且指南里那张 V0 complete 表是"为什么不算 Day-1"，不是
  状态表** —— `#2/#5/#8/#20/#21` 与 `M1/M2/M3` 在指南里找不到"是否验过"的记录：可能验过没落档，
  也可能没验。要答"V0 还差什么"，得先把这张表补成真状态表。
- 上面 fixture 缺陷 4 与 5 **未修**。
- `record` 拒绝写入时报 `error <CODE> <id>`，**不带 message 与 remedy**（`_default_human` 只打印
  severity/code/subject，带 message 的那条只在 `quiet` 模式下走）。这是既有全局行为，但让新的拒绝
  路径不可行动。是否改渲染层（简明 vs 可行动）待定。
- RTK 混杂（C 节）：三轮演练共有，作用于**每一个** Claude Code session，含架构师交互式跑的。
  想拿干净证据得摘 hook —— 侵入性改动，先问架构师。

### 下一步

1. 修 fixture 缺陷 4（canonical state 内部一致）与 5（补齐或被指向的路径）—— 两者都是"没人埋的
   异常"，且 4 会让 session 无路可走
2. 判据 5 的修法：在 `session-continuity.md` 写明"等待期写**意图**、不写结论"（比改判据更对，
   因为它保留了判据的目的）
3. `env record` 的写入路径 + `environment.schema.json`
4. 把 V0 complete 那张表补成真状态表

### 动手前必须知道

4. **Bash 输出被 RTK 改写：`git status` 干净时只剩一个 `ok`。** `rtk hook claude` 是**用户全局**
   `~/.claude/settings.json` 里的 `PreToolUse` hook，把 `git status` 之类改写成 `rtk git status`。
   干净仓库的 `git status --porcelain` **不产出真实输出**。对演练尤其重要：这是**没人埋的异常**。
   应对写在 `~/.claude/RTK.md`（`rtk proxy <cmd>` 走原始输出）。**别去查 git** —— D2 用
   `GIT_TRACE` + plumbing 交叉验证才把它澄清。
5. **fixture 里的 commit 用 `drill:` 前缀、session 用 `fix:`** —— 这是两者**唯一稳定**的区分。
   作者字段分不出来，因为 builder 把 `git config user.email` 写进了 fixture。上一轮指南里有一处
   把 fixture 的 commit 当成了 session 的产物，就是这么来的。

---

## 2026-09-14（第三轮）— 修掉上一轮发现的六条缺陷

### 会话概览

架构师指示"先把你发现的缺陷修复"。**六条全部修完**，每条都带变异验证，239 项定向测试全绿
（8 个模块逐个跑，不是一次全套）。其中三条是**工具缺口**，性质相同：canonical 状态里声明了、
协议要求维护、而没有任何动词能读写它。

### 修了什么

| | 缺陷 | 修法 | commit |
|---|---|---|---|
| **H** | `record` 拒绝时只报 `error CODE id`，**不带 message 与 remedy** | `_default_human` 补上两者；带 message 的那条原先只在 `quiet` 模式下走 | `01b05b5` |
| **3** | 判据 5 不可判（等待期不写痕迹） | `session-continuity.md` 写明"等待期写**意图**、不写结论"，并说清两者之别 | `a07397b` |
| **F** | **`research:current` 完全未接线** —— 无命令读、无命令写、无 schema、从不校验 | 新 `researchlog current`（读 / `--set`）+ `current.schema.json` + `validate` 第五种 kind | `5730351` |
| **D** | fixture 的 state 由三个互不相关的示例拼成；rotation 缺 `expected_evidence` | 假说换成 fixture 自有的 H-041/H-042 并在 CURRENT 里写明各自主张；case 换掉；补 `expected_evidence`；三个 builder 都加自断言 | `2f3a1cc` |
| **E** | fixture 复制上游 `CLAUDE.md`，声称一个它没有的布局 | fixture 写**自己的** adapter，声明它是"使用这个工具的项目"；加自断言 | `e721196` |
| **G** | `env record` 写不了 `limitations`/`harnesses`/`available`；无 `environment.schema.json` | 新 `env declare TABLE FILE` + `environment.schema.json` + `validate` 第六种 kind | `69db11c` |

### F 是最深的一条，也是 D 的前提

审计方式：逐个 canonical 文件问"谁写它、谁读它"。结果是 `paths.current` **在代码里零引用** ——
`loader.py` 认识这个名字、`repo.py` 建了这个路径对象、没有任何命令碰它。

这同时让项目的两句话失真：`CURRENT.md` 写着 "Edit it through `researchlog`, never by hand"，
AGENTS.md 写着 "**Never hand-edit that JSON — use the tool**"。没有动词时，手改是唯一选项。
而且**命令够不到的状态，检查也够不到** —— 所以它对 `validate` 完全隐形，而其余每个 canonical
文件都在被检查。

**顺序是有依赖的**：D 要用工具把 fixture 的 CURRENT 写成一贯的，所以 F 必须先做，否则修 D 只能
手改 JSON，正好违反那条禁令。

### 一处必须留给出题人的口径

`capability_map` **刻意没给形状**。它在骨架里是一个空数组，任何地方都没有一条 entry 示例 ——
所以在这里发明一个形状，等于把一个猜测当成已决定的事去强制。它是这次审计里**第三个**"声明了
但没有消费者"的 canonical 字段（前两个是 `research:current` 和上面那三张表）。给它定义属于
设计决定，不属于修复。

### 同一轮里想通的几件事

- **`Finding` 的第 5 个字段是 `fix_hint`**，不是 `remedy`。我先前打印 `f.get('remedy')` 得到
  `None`，是因为那个 key 根本不存在 —— 我查询写错了，不是工具没给。
- **`_check_surrogate` 的 message 里 `verdict is EVIDENCE_INVALID, not {verdict!r}`** 在 verdict
  为 `None` 时会打印 `not None`；完整性检查同一条记录里也会报，所以只是措辞略糙，不是缺陷。
- **验证副本时要确认副本是新的。** 我一度用 `/tmp/eval-conflict` 里那份**约束修复之前**建的
  `tools/researchlog` 副本去验证"拒绝信息"，结果它照常写入 —— 差点得出"修没生效"的错误结论。
  这与"按 cwd 找仓库"那条是同一个陷阱的另一面：**副本既是代码的副本，也是代码版本的副本。**

### 开放项

- `AGENTS.md` 的命令清单还缺一行 `current`（以及 `env declare`）。**没有动这个文件**：它带着
  架构师本轮的 DeepSeek 后端规则改动，提交它会把别人的在途工作一起包进来。
- `AGENTS.md` 的 "Resuming work on the tool itself" 一节措辞仍只是**隐含**地把路径限定在上游仓库；
  fixture 现在自己声明了、不再依赖这一点，但这句话本身仍可更明确。同上，属架构师的在途文件。
- **V0 状态表仍未补**（上一轮列的下一步第 1 项）。所以"V0 完成几条"目前仍答不了。
- 判据 5 已改协议文本，但**尚未在新文本下重跑 D2** —— 所以"这样写是否就能判"仍未实测。

### 下一步

1. 在新 `session-continuity.md` 下重跑 D2，验证判据 5 真的可判了（这是 3 的验收）
2. 补 V0 状态表
3. 给 `capability_map` 定形状（设计决定）
4. `AGENTS.md` 的两处（命令清单 + tool-dev 一节的措辞）—— 待架构师的在途改动落地

### 动手前必须知道（追加）

6. **"没有动词的状态，也没有校验。"** 这次三条工具缺口是同一个形状。看到一个 canonical 文件/
   块时，问两句：谁写它？谁读它？两个都答不出来的，就是下一个缺口。审计方法：
   `grep -rn "paths\.<name>" tools/researchlog/ --include="*.py"`，零引用即未接线。
7. **改共享底座后，三个 drill builder 全部重跑一遍** —— 它们是这套状态最真实的使用者，
   比单元测试更早暴露接线缺口（这一轮 D1 fixture 就是被不变量 #4 的接线打坏的）。
8. **`origin` 走 HTTPS 会连不上，改用 SSH。** 症状是 `Failed to connect to github.com port 443
   after 75003 ms`，而它**看起来像断网、其实不是** —— 同一时刻 `ping github.com` 通（110ms）、
   `https://api.github.com` 返回 200，只有 `github.com` 解析到的那台 IP（`20.205.243.166`）连不上。
   `origin` 是 HTTPS URL，所以 `git push` 会卡 75 秒再失败。
   可用的推送命令（`~/.ssh/id_rsa` 属于 `idleuncle`，**对 uukuguy 的仓库没有权限**，
   必须显式指定属主那把 key）：

   ```bash
   GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa_uukuguy -o IdentitiesOnly=yes" \
     git push git@github.com:uukuguy/research-engineering.git main
   ```
   本轮就是这样把 7 个 commit 推上去的。**根治办法是把 `origin` 换成 SSH URL**（`gh` 的配置
   本来就是 ssh 协议），但那属于改架构师的仓库配置，留给他定。

---

## 2026-09-17 — 按设计要求跑完 V0 验收

### 会话概览

架构师定目标："按设计要求完成 V0，research-engineering 是 skills 开发，不是上线系统的功能发布，
不要过重的工程测试"。做法因此不是补测试，而是**每条验收跑一次、留一份可查产物**。

先立 **V0 状态表**（指南新增一节）—— 在此之前"V0 完成没有"这个问题在仓库里**无法回答**：两张旧表
回答的是"为什么这样分组"，不是"哪条验过了"。把分组理由当状态表读，会把没验过的条目当成已完成。
这张表本身就是本轮的主要产物。

### 结果：20/22 有实测证据，2 条环境阻塞

| 组 | 结果 |
|---|---|
| Day-1 must | M2 / M3 / M4 / M5 ✅；M1 见下 |
| V0 complete | #2 #5 #8 #10 #11 #12 #13 #14 #15 #16 #18 #19 #20 #21 ✅ |
| 阻塞 | **#1 / #22 = `ENV_BLOCKED`**（不是失败） |

### 一次 session 覆盖六条（session A）

在**全新空项目**（无 `research/`）上给一个高层方向，不给算法："尾延迟来自 queue 还是 retry？"
一次运行拿下 M2 / M3 / M5 / #2 / #5 / #8：

- **M2**：它**完全没有碰** fixture 的 `sim/` 与 `data/`，改动全在两支自建 probe（281 + 171 行）
  与研究状态；无 plan 文档、无新增测试套件
- **M3**：块 `RB-001` 内 3 条证据，2 条 `counts_as_evidence_iteration: true`
- **M5**：`ENV-LIM-001..006` 以 `ENV_UNSUPPORTED` 入 `ENVIRONMENT.md`，各带 `verified_by` ——
  **6 条里没有一条被写成 `refuted`**。这条此前**不可能通过**：三张表在 `env declare` 出现之前
  没有写入路径
- **#8**：自建 `HARNESS-001`，带 `supports_evidence` 与 `preserves` / `missing` 边界

它的科学结论也值得记：**用消融实验推翻了按毫秒归因的答案** —— `backoff_wait` 是内生变量，
只有 `queue_wait` 已超阈值才会被赋值，所以"方差份额"不等于"因果贡献"；正确的归因是反事实。
它还**证明了 fixture 里那句 "Stable by construction" 是错的**（util 0.8、retry 打开时队列真的跑飞，
p99 730ms vs 关掉 6.4ms），并自查修正了自己两处错误（分解采样点取错、provenance 误判）。

### CLI 层一次跑掉四条

- **#12**：预算 2、记满 3 条 → 块**运行期间**报 `BLOCK_ITERATION_BUDGET_EXCEEDED`（用派生 count）
- **#15**：12 个并发 `record` → 12 条记录、12 个互异 ID、文件名与 ID 全等
- **#16**：`code_state.commit` 是**工作区** commit，不等于加入该记录的 commit
- **#18**：`Evidence:` trailer 给出 commit→EV，`code_state.commit` 给出 EV→commit；构造违规后
  `SELF_REFERENTIAL_COMMIT` 准确报出（这条检查是真的接线的）

### #19 跑了两次，第二次才是准确条件

第一次 `--bare`：无 hooks / plugins / MCP / LSP，工具只剩 `Bash/Edit/Read` —— loop 跑完了，
4 条证据分类全对。**但它把 skill 发现也关掉了**，而那不在 #19 列的（hooks/subagents/MCP/GitHub）
之内，所以那次契约只来自 AGENTS.md。

第二次改用 `--settings '{"hooks":{}}' --strict-mcp-config --mcp-config '{"mcpServers":{}}'`：
保留 skill、只摘 hooks 与 MCP。判据是**可观测**的 —— `mcp_servers: []`，且 RTK hook 留下的
裸 `ok` 出现 **0** 次；skill 确实加载了（读了 `git-research-infrastructure.md`）。loop 跑完，
`validate` 0、`reconcile` clean。

### #1 / #22 的三条路径都试过

| 路径 | 结果 |
|---|---|
| codex 默认后端 | `chatgpt.com` / `api.openai.com` **超时** |
| `aicoding.2233.ai` | 可达，但凭据 `OPENAI_API_KEY_0011AI` **不在 agent 环境里** |
| `openrouter.ai` | 可达，`OPENROUTER_API_KEY` **已设置**，但返回 `401 Unauthorized: User not found` |

`codex exec` 本身可用（`codex-cli 0.153.4`）。所以这是**环境不可行，不是能力缺口**（不变量 3）——
不变量存在的意义正是把这两者分开，所以这里记 `ENV_BLOCKED` 而不是"未通过"。

### 两处我自己犯的错，都留了痕

1. **fixture 打包错误**：M1 第一次跑时我 `mkdir -p templates` 之后又 `cp -R src/templates templates`，
   于是变成 `templates/templates/research`，session 拿到 `TEMPLATES_ABSENT` 并**替我把 fixture 修好了**
   （它自己的 commit `fix: repair vendored template path...`）。这是"没人埋的异常"，所以 M1 重跑。
   drill builder 没有这个问题 —— 它们不预先建 `templates/`。
2. **commit message 里的反引号**：`git commit -m "…\`code_state\`…"` 会把反引号当命令替换执行，
   词从消息里**静默消失**（提交成功、消息残缺、不报错）。丢过 `code_state` 与
   `SELF_REFERENTIAL_COMMIT` 两个词。已记入 gotcha 记忆：**永远写文件再 `-F`**。

### 开放项

- **M1**：bootstrap 本身已验证（canonical 八件齐备、plan 文档 0），但那次 session 建完状态后
  继续做了一轮远超范围的研究（在查本机 `perf_counter` 的精度），留下 3 个 `ORPHAN_RUN`，
  于是 `reconcile` 不干净。**判据本身无歧义，是测量点的问题** —— M1 测的是 bootstrap，
  测量该取在 bootstrap 完成那一刻。
- **#1 / #22**：需要你解。最省的是你在自己的交互 shell 里跑一次 codex（凭据在那里），
  或把可用的 provider 凭据放进 agent 环境。素材已就绪：#20 产出的中文报告可直接投喂。
- `capability_map` 仍无形状（设计决定）。
- `AGENTS.md` 的命令清单仍缺 `current` 与 `env declare` 两行 —— 该文件带着你的在途改动，我没动。

### 下一步

1. 解 M1 的测量点（bounded bootstrap 或接受"canonical 干净、run 是进行中"的区分）
2. 解 #1/#22 的环境阻塞
3. 补 `AGENTS.md` 的两行

---

## 2026-09-17（第二轮）— 把 Claude Code 这条路做好

### 会话概览

架构师定调：**codex 放一放，把 Claude Code 做好**。于是这一轮不碰第二个客户端，
专查 Claude Code 这条路上**声明与实现不一致**的地方 —— 结果找到一处大的。

### 主线：workflow block 只覆盖了一家，而机器上长出了 70 个

`AGENTS.md` 第 33 行写着"the generic software-delivery workflow skills are **disabled for this
project mechanically**"，紧接着写明"brainstorming / a written plan / TDD / a review checklist
的**缺失就是重点**"。而 deny 列表只列了 superpowers 一家。

**实测**：在带项目 settings 的仓库里调用 `gsd-plan-phase` —— **整份 skill 正文加载了，没有任何拒绝**。
这台机器上有 **65 个 `gsd-*`**，合起来提供的正是写好的 plan、测试生成、review checklist 和
phase 脚手架。

修法（`7bc632d`、`70ab9f5`）：`skillOverrides` 补 70 条（65 个 gsd + `discuss` / `review-plan` /
`code-review-changes` / `test` / `frontend-test`）；`permissions.deny` 补 plugin 级的
`dev-phase-manager`(9) 与 `planning-with-files`。现在覆盖 **80 个交付工作流、116 个名字**。

**两个陷阱，都会产出"看起来对、其实什么都不做"的屏蔽** —— 都是这轮踩出来的：

1. **`permissions.deny` 不支持通配。** `Skill(gsd-*)` 匹配不到任何东西 —— 在只 deny 这个模式的
   settings 下调用 `gsd-plan-phase`，它照样加载。AGENTS.md 里把 `Skill(superpowers:*)` 当作家族
   简写来写，读起来像一个可用的通配符，**不是**。
2. **denied 名字里的 plugin 是版本目录上面那一层，不是 marketplace 目录。** `omc` marketplace 下的
   plugin 叫 `oh-my-claudecode`，所以 `Skill(omc:autopilot)` 匹配不到任何东西。**这一条是漂移检查器
   的 warning 列表发现的** —— 正是它被写出来的用途。

第三个发现：**缓存里的 plugin ≠ 可用的 plugin**。检查器一开始把 plugin cache 当成可用集合，于是对着
`oh-my-claudecode`（`enabledPlugins` 里是 **disabled**）报了 12 条不需要的屏蔽 —— 而**真正的缺口会被
它挡在后面看不见**。现在先读 `enabledPlugins`。

### 防漂移：`tools/check_workflow_block.py`

一份清单不会注意到机器长大了，所以加了漂移检查（`7bc632d`）。它读**这台机器自己的** skill 清单
（personal + 已启用 plugin），未覆盖的交付工作流一律 exit 1 点名；并且**反过来**检查：
`AGENTS.md` 明文保留可用的 `systematic-debugging` / `using-git-worktrees` 若被误关，同样 exit 1。

变异验证两个方向都做了：摘掉一个 plugin skill → exit 1 点名它；摘掉一个 personal skill → exit 1
点名它；对照组 exit 0。

这不是测试套件，是**配置漂移检查** —— 与 `install_research_skills.py --check` 同一个形状。

### 两件顺手查清、结论是"不用动"的

- **权限摩擦不存在。** 我全程用 `--dangerously-skip-permissions` 跑，所以从没暴露交互式的问题；
  实测不加该参数跑 `researchlog validate` —— 直接通过。`permissions.defaultMode: "auto"` 加
  `skipAutoPermissionPrompt` 已经免去逐条批准。**所以没有加 allow 列表** —— 那会是给一个不存在的
  问题发明修法。
- **skill frontmatter 干净。** 三个 skill 只有 `name` + `description`，没有 Claude 特有字段写错，
  副本与 canonical 一致。

### 文档

- **`CLAUDE.md`**（Claude Code 适配文档，Claude 特有的机制正该住这里）新增 "The workflow block"
  一节：两个机制不可互换、两个陷阱、以及漂移检查的跑法。
- **`docs/V0_ACCEPTANCE_GUIDE.md`**：#1 / #22 改记为 **⏸ 架构师决定先放一放**，并写明
  **V0 在 Claude Code 这条路径上是完整的**（其余 19 条全部实测通过）。

### 一处顺带纠正的账面

`#22` 的判据是"交给**另一客户端**"，不是"交给 codex"。这台机器上另有
`opencode` / `cursor-agent` / `gemini` / `aider` / `crush` 五个 agent CLI —— 所以这条**并不缺验证
路径**，只是架构师选择先不做。日后要验不必受 codex 限制。

### 下一步

1. `AGENTS.md` 的两处（命令清单缺 `current` / `env declare`；`Skill(superpowers:*)` 的措辞容易
   被读成通配符）—— 该文件带着架构师的在途改动，等他提交后我来补
2. 若日后要做第二个客户端：#22 用上面任一 CLI 即可

---

## 2026-09-17（第三轮）— 收尾补完与交接

### 这一轮只做了一件事

补完上一轮列在"下一步"里的 `AGENTS.md` 两处（`03a92c4`）：命令清单加 `current` 与
`env declare`；deny 列表那句 `Skill(superpowers:*)` 改成"一个 skill 一个精确名字"，并指向漂移
检查 —— 因为它是**读起来像通配符、实际匹配不到任何东西**的写法，而 70 个交付工作流就是这么漏掉的。

**该文件同时带着架构师自己的 DeepSeek 后端规则**（3 行，本会话加的），一并提交了，commit message
里写明那段不是 Claude 写的。工作树因此**完全干净**。

### 现在的状态（可核验，不是回忆）

```
HEAD 03a92c4 · 工作树干净 · 本地 = 远端
V0 状态表：21 行 = 19 ✅ + 2 ⏸（#1/#22 架构师决定暂缓）+ 0 ❌
python3 tools/check_workflow_block.py    → 覆盖 80 个交付工作流 / 116 个名字
python3 tools/researchlog validate       → exit 0
python3 tools/researchlog reconcile      → exit 0 clean
python3 tools/install_research_skills.py --self --check → 两个 client 无漂移
tests/main/build_*.sh                    → 3 个 drill builder，各自自断言
tools/                                   → check_workflow_block.py · install_research_skills.py · researchlog/
```

**V0 在 Claude Code 这条路径上是完整的。** 唯一未验的两条是客户端矩阵项，架构师明确说先放一放。

### 这个会话（09-14 起）一共交出了什么

- **19 项 V0 验收拿到实测证据**（每条一次运行 + 一份可查产物，不为任何一条搭测试框架）
- **七条缺陷修掉**，全部带变异验证：`research:current` 未接线、`env record` 三张表无写入路径、
  `record` 拒绝时不带 message/fix hint、不变量 #4 从未执行、三个 fixture 缺陷、workflow block 只覆盖
  一家
- **V0 状态表**（指南新增一节）—— 在它之前"V0 完成没有"在仓库里**无法回答**
- 三个 drill fixture 现在都**自断言**自己的状态（注册表≠定义、adapter 是自己的、补丁确实生效）

### 开放项

1. **`capability_map` 没有形状** —— `ENVIRONMENT.md` 里它是个空数组，任何地方都没有一条 entry 示例。
   它是审计里**第三个**"声明了没有消费者"的字段（前两个是 `research:current` 和三张表）。
   **给它定形状是设计决定，按架构师规则不由 Claude 定。**
2. **#1 / #22 暂缓** —— 判据是"另一客户端"，不限于 codex。这台机器上另有
   `opencode` / `cursor-agent` / `gemini` / `aider` / `crush` 五个 agent CLI；#22 的素材也早已就绪
   （`research-status` 的中文报告含 resume 所需的全部状态指针）。
3. 漂移检查有 **8 条 warning**（知识类 skill 的描述里含 "plan"/"test" 等词）。它们是"提示去看"，
   不是失败；要消掉就得逐个判断并加进白名单，目前认为不值得。

### 动手前必须知道（本会话新增的四条，与前几轮的一起看）

9. **`permissions.deny` 与 `skillOverrides` 都不支持通配。** 前者管 plugin 命名空间、后者管
   personal 级 skill，都要**一个 skill 一个精确名字**。`Skill(gsd-*)` 匹配不到任何东西 —— 实测过。
   而且 denied 名字里的 **plugin 是版本目录上面那层，不是 marketplace 目录**（`omc` marketplace 下
   的 plugin 叫 `oh-my-claudecode`）。
10. **缓存里的 plugin ≠ 可用的 plugin。** 只有 `enabledPlugins` 里为真的才可达。把 plugin cache 当
    可用集合会**报出不需要的屏蔽，同时把真正的缺口挡在后面**。
11. **`git commit -m "…\`x\`…"` 里的反引号是命令替换** —— 词会从消息里静默消失，提交成功、消息
    残缺、不报错。**永远写文件再 `-F`。** 本会话丢过两个词。
12. **fixture 打包别先建 `templates/`。** `mkdir -p templates && cp -R src/templates templates` 会得到
    `templates/templates/research`，`init` 报 `TEMPLATES_ABSENT` —— 那是**打包错误不是工具缺陷**，
    但会让 session 花时间去修 fixture。

### 下一步

按优先级：

1. `capability_map` 的形状（架构师的设计决定）
2. 若要做第二个客户端：#22 用现有任一 CLI 即可，不必等 codex
3. 消掉漂移检查的 8 条 warning（低价值，可长期挂着）
