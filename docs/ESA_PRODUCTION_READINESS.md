# RE 在 esa-study 的生产就绪分析

日期：2026-09-21。范围：RE 核心协议、状态/执行/证据链代码，以及真实 ESA 发布数据的隔离集成验证。

后续更新：Architect 已确认全新重启；下文“live 恢复待确认”是隔离验证时点的历史状态。
esa-study 已在新研究分支完成两项 live E1 探针，见 `docs/WORK_LOG.md` 最新条目和
`../esa-study/docs/RESEARCH_START.md`。这仍不等于 fresh-agent 长跑或官方 GPU Runner 验收。

## 结论

**修复后的 RE 已通过本轮本地 E1 执行、记证、恢复重放与负对照验证；尚不能宣称 esa-study 长跑自治或 ESA 策略生产可用。**

这不是把历史的 304 tests / 45 PASS 当作生产验收。本轮从实际工作区边界复现缺陷、修复，
再用真实数据检验整条 CLI 路径：19 项新增定向测试 + 69 项受影响既有测试通过；未跑全量套件。
系统调试采用 `systematic-debugging` 的先复现、再定位、再验证流程。

真正的 esa-study 尚未被本轮修改：旧 `.research/`、两条证据及 `EXP-AUDIT-001` 已在到场前
暂存删除，磁盘上是空白新状态；`AGENTS.md` 被删除，新建的是空 `AGENETS.md`，
`CLAUDE.md` 链接悬空。这既可能是有意重置，也可能是未完成迁移。按 Resume Protocol，
须由 Architect 确认“新状态重启”还是“恢复旧实验”，不能替其丢弃任何一边。
修复后的只读 `reconcile --root ../esa-study --json` 已从原先误报 clean 变为退出 2，
准确列出意外路径及两条 `EVIDENCE_REMOVED_FROM_GIT`；没有执行自动恢复或修改索引。

## 设计与实现：自治发生在哪里

| 层 | 主要代码/协议 | 实际职责与边界 |
|---|---|---|
| 研究决策 | `AGENTS.md`、`skills/research-engineering/` 与条件触发的 expert skills | agent 提问、选实验、解释、转向；不是 CLI 自动替 agent 作科学判断 |
| 工作记忆 | `repo.py`、`state.py`、`active/current/boundaries/env/findings` | ACTIVE 是执行指针；CURRENT 是研究记忆；其余存约束、环境、信念；默认 `.research/`，兼容 `research/` |
| 机械约束 | `schema.py`、`schemas/`、`constraints.py`、`validate.py` | 检查结构、执行结果与科学结论分离、证据等级及预算；不能证明 observation 是真的 |
| 执行与恢复 | `run.py`、`job.py`、`manifest.py`、`reconcile.py`、`ioutil.py` | 写前 manifest、捕获 stdout/stderr/退出码、heartbeat、原子 JSON 与恢复检查；agent 仍须维护 ACTIVE 状态 |
| 证据与归因 | `record.py`、`compare.py`、`jgit.py` | 追加 EV、记录输入/环境/代码身份、限定比较；从 run 恢复要用 `record --from-orphan`，仅给 experiment ID 不等于继承 provenance |
| 持久化与观测 | `checkpoint.py`、`sessions.py`、`telemetry.py`、`synthesize.py` | Git checkpoint、session events、预算计数与总结；不是调度器或无人值守 daemon |
| 客户端适配 | `.agents/skills/`、`.claude/skills/` 与客户端上下文入口 | 让不同客户端能读同一协议；CLI 进程重启不等于模型上下文丢失后的自主恢复已验证 |

关键链条是：**恢复并核对状态 → 写执行意图 → 运行并保留原始产物 → 人工智能解释观察 →
追加证据 → 更新信念/下一步 → 新会话重建上下文**。19 个 CLI verb 是这条链的工具层，
不是完整研究主体。长跑质量取决于状态真实性、测量面有效性、agent 是否按协议自主作下一步，三者缺一不可。

设计上，把 `execution_status` 与 `research_outcome` 分开是正确的：本轮探针退出 1，
但 RE 成功保存 run，不能据此说 RE 运行失败，也不能自动认定某策略被证伪。
同样，环境未能运行仿真只限制证据等级，不反驳研究假设。

## 本轮已复现并修复的实现缺口

| 边界 | 原问题 | 本轮改动 |
|---|---|---|
| 初始化 | 模板有 null epoch，日志有 epoch，但 ACTIVE 未写入 | 持久化相同 epoch；无首个 commit 时也识别 branch |
| 恢复初始化 | `init --merge` 重写 Git capsule、重复 session，并可能创建 `.research/` 遮蔽 legacy state | 保留既有 ACTIVE/log；沿用既有目录；写前拒绝 newer schema |
| Git 提交范围 | `record` 和 `checkpoint` 会把用户预先暂存的无关工作一起提交 | 仅提交本次目标路径；checkpoint 的空变更判断也限制到目标路径 |
| 代码身份 | untracked 文件内容变化不改 fingerprint；legacy state 写入污染代码身份 | 对 untracked 内容、执行位/链接身份散列；排除实际 canonical 目录 |
| 比较 | 两次 clean commit 的 dirty diff 都为 null，可错误判为代码一致 | 增加 committed code tree hash；状态专用 commit 不破坏比较；旧记录按 commit 保守回退 |
| reconciliation | `dirty_expected=true` 可掩盖意外路径，分支不一致及索引中的证据删除漏报 | 增加 `ACTIVE_UNEXPECTED_PATHS`、`ACTIVE_BRANCH_MISMATCH`、`EVIDENCE_REMOVED_FROM_GIT` |
| 跨 session telemetry | 上一会话证据造成负耗时；同秒 rotation 把迭代分错 session | EV 新增可选 `session_epoch`，优先按 ID 归属；旧记录保留时间窗口回退；耗时只取当前会话证据 |

测试见 [`test_production_boundaries.py`](../tools/researchlog/tests/test_production_boundaries.py)。
既有 timestamp fixture 现在显式构造旧格式记录；另用真实 CLI rotation 检查新格式，不靠改写历史让测试通过。
本轮只对上述范围作保证，不把 schema 兼容性或原子性修复外推至所有 verb。

## 真实 ESA 数据验证

入口：[`verify_esa_readiness.py`](../tools/verify_esa_readiness.py)，探针：
[`esa_package_audit.py`](../tools/probes/esa_package_audit.py)。只读 esa-study 所引用的官方数据，
在 RE 的 `outputs/` 下创建独立 Git repo；不在 esa-study 中 bootstrap，也不更改官方配置。

最终报告：[`outputs/esa-validation-20260921-05/report.json`](../outputs/esa-validation-20260921-05/report.json)。
同目录保留 CLI transcript、独立仓库、manifest、stdout/stderr、EV、session log 与 Git 历史。
`outputs/` 不进入本仓库版本控制；关键结果持久记录于本报告，复跑需原数据。
先前 `-01` 至 `-04` 调试产物未覆盖：它们暴露了 CLI 用法与 telemetry 问题，不作为最终版本通过依据。

| 运行 | 观察 | 证据 ID |
|---|---|---|
| `EXP-ESA-BASELINE` | 24 tasks、3 scenes；207 项 metadata SHA256 通过；2 项内部索引不一致 | `EV-20260921T093304Z-6e4b` |
| `EXP-ESA-REPLAY` | rotation 后独立进程重放；完整探针 JSON 相等；`compare=COMPARABLE` | `EV-20260921T093305Z-26a4` |
| `EXP-ESA-NEGATIVE-CONTROL` | expected action dim 从 10 改成 11；错误从 2 增至 26，24 tasks 全部被拒绝 | `EV-20260921T093306Z-d6f1` |

三个 child exit 均为 1，但捕获、记证和最终 validate/reconcile 成功，隔离仓库 Git clean。
block 正确统计 1 evidence iteration、2 reproduction；session 计数 `[1, 0]`；当前会话
time-to-first-E1 为 1 秒，指向 replay 的 EV。该秒数只描述这个快速探针，不是一般研究效率估计。

发布包：`unified_q01_q24_20260813`。所有 task 的 action/state 维度为 10/25。
metadata manifest SHA256：`c21819eb7f6f6c66ac5936b139b85d57f1aecf96c545997a483ce5638b487dbf`。
probe SHA256：`5e8bb414f0256ae13ffe4820ff48e6e612705c95440c418ce0c658460bd23a79`。
RE 基线 HEAD：`072c7cfa5fed175898ac5a4691d482e03f60aad7`；验证使用本轮未提交修复，
实际非测试 Python/schema runtime digest：`58206a54e993cf9e5f1289d4dcb7dbf17e9ea7ca22e79bd98d7fe3b89731b320`。
脚本在开始/结束都核对 runtime digest；HEAD 单独不足以标识这次运行。

### 两项数据异常不是策略结果

Q17、Q21 的 attack profile 内容 SHA256 与各自 `index.json` 不一致，独立 `shasum -a256` 复核相同。
外层 metadata checksum 仍匹配：即已发布内容的内部引用不自洽，而非本次探针修改了数据。

| Task | index 声明 SHA256 | 文件实际 SHA256 |
|---|---|---|
| Q17 | `8f75b43f682968c61b23cae3dae79af9cfbe4a269486233cb7de2c41e66b0fff` | `1cfd4f633d0ac38c3bce03b6cc325a78adfd74da6b66e4d62cce3270df190afe` |
| Q21 | `97d6adf33a75c203fa4df1de50615274adbed939a9551fa5e509fb6314112860` | `a882178c4f5bb8ade7e453e49f09cdace4814bedb9335f3499e8c5e7736ff0f1` |

保留异常和原始文件；后续须明确 Runner 实际读取哪一份配置，不能修改官方数据来换取绿灯。
本轮读 attack metadata 仅为发布包审计，不授权把它作为策略运行时输入。

## 尚未验证或未修复的生产风险

以下前两项来自代码路径检查，不冒充本轮已执行的破坏/断电试验：

1. **finalized run 的 ID 可复用且覆盖原始产物。** `run.py` 允许重跑完成的 manifest，日志以 `w` 打开。
   本轮用三个唯一 EXP ID 绕开；无人值守前应明确 immutable attempt 或拒绝覆写的契约。
2. **canonical markdown 并非统一原子写。** `current/boundaries/env/findings` 仍有直接 `write_text`，
   各 verb 的 newer-schema guard 也不统一；不能把 ACTIVE/manifest 的恢复能力外推到全部状态。
3. **provenance 不覆盖任意外部运行环境。** symlink 散列的是链接身份，不是目标 16 GB 数据；
   未跟踪大文件会增加散列成本；本轮只校验 metadata，未加载 USD/ONNX/NPZ，未全量核验 content tree。
4. **自动归因较保守。** `compare` 的同代码判据适合重放，不是“算法实现变更有因果收益”的完整实验设计。
   旧记录没有 tree hash 时，证据专用 commit 也可能触发保守拒绝，需要重放建立锚点。
5. **长跑闭环仍缺实测。** 没有 fresh model session 的失忆恢复试验，没有真实长作业中断/接管和
   多 writer 竞态注入。本轮 rotation 是 CLI/process 层证据，不是 agent 自治证明。
6. **telemetry 仍有空项。** `session_recovery_accuracy` 和
   `discriminating_experiment_without_architect_correction` 尚未实现；E3 在此次 E1 实验中不可用。
7. **ESA 行为验收未发生。** 本机为 Darwin arm64；随附 Docker 文档要求 NVIDIA GPU 环境。
   本轮未启动官方 Runner、Policy WebSocket、模型推理或仿真；没有任务成功率、安全性或排名证据。
   contracts 中 endpoint 为 18011，随附 Docker 示例为 18021，联调时需核对启动参数的实际优先级。

因此，当前合适定位是：**有已验证本地执行路径、已知限制的研究工具；不是可无人值守交付的完整 ESA 系统。**

## 后续推进顺序

1. Architect 确认 esa-study 的重置意图；保留已有 staged/unstaged 变化与历史证据，再协调 ACTIVE/Git。
2. 按选择恢复旧研究或使用 `research-bootstrap` 初始化新研究；修复客户端入口文件名，登记
   TASK 目标、外部引用、HARD 边界、资源预算和环境能力。不可在空状态下假装旧实验已恢复。
3. 将真实 package audit 作为该研究自己的新 run 执行并记证，处理 Q17/Q21 引用歧义；不搬运隔离 EV 冒充 live run。
4. 按 `docs/TASK.md` 先作相关 SOTA 调研，再形成可区分的实验假设；先验证 Policy 接口与观测边界，
   有可用且已授权的 GPU 环境后建立官方 Runner baseline。环境失败与科学失败分别记录。
5. 用 fresh session 接续一个未完成 block，验证“恢复 → 选下一实验 → 产证 → 改信念 → 再继续”，
   再决定是否提升生产可用结论；不靠增加测试数量替代这一步。

复跑隔离验证（`--output` 必须是尚不存在的新目录）：

```bash
uv run --python 3.12 python tools/verify_esa_readiness.py \
  --data-root ../esa-study/data/question_to_player \
  --output outputs/esa-validation-next

PYTHONPATH=tools uv run --python 3.12 python -m unittest \
  researchlog.tests.test_production_boundaries
```

本轮没有模型 API 调用、付费计算、官方提交、push，也没有在 esa-study 执行提交或清理操作。
