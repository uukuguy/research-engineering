# 下一会话从这里开始（工具开发轨道）

> 本文件是**工具开发**的交接。`research/` 是"这个工具所服务的研究"的状态，与本文件是两条
> 轨道 —— 见 `AGENTS.md § Resuming tool development`。本轮的 `research/ACTIVE.json` 保持
> `idle` 是**正确**的：没有研究在跑，不要为了"填满"而去改它。

## 一句话状态

评审 19 项**全部关闭**；设计文档 §20.1 的 22 条验收拆成 Day-1 must（5）/ V0 complete（16）
并操作化；§26.4 的故障注入在 CLI 层全部跑过；三个 session 级演练（D1 恢复 / D2 rotation /
D3 evaluator conflict）已脚本化、跑过、结果入档。**152 项测试全绿**，`validate`/`reconcile`
exit 0，两个 client 的 skill 无漂移，工作树干净。

```
HEAD       fb9a71a
branch     main
tests      152 OK  (constraints + integration + commands + schema)
```

## ⚠️ 未推送 —— 下次先做这件事

本会话**没有网络**：`git fetch` 报 `Error in the HTTP2 framing layer`。而且这个工作副本

- 没有配置 upstream（`branch.main.remote` 未设置）
- 没有任何 remote-tracking ref（`.git/refs/remotes` 不存在）
- reflog 里 0 条 push 记录

所以**远端的状态从这里无法得知**，本轮（以及此前）的 commit 都只存在于这个本地副本。远端
`https://github.com/uukuguy/research-engineering.git` 已存在。有网络时：

```bash
git push -u origin main
```

## 本轮做了什么

| commit | 一句话 |
|---|---|
| `93c9e71` | P1-3：边界信号必须保留原文（`constraints` 层强制 + skill + template + 8 测试） |
| `671b6b7` | P1-4 echo-back / P1-5 YAML snapshot basis / P1-6 下一步指引 / P1-10 E2/E3 隔离 |
| `bd6f6f2` | signal 字段契约收敛（`expiry` 取代从未被文档化的 `expires_at`；`DECISION FINAL` 不是类型） |
| `29344dd` | `UNKNOWN_HYPOTHESIS` 100% 误报（注册表接错了 ID 空间） |
| `df5c43b` | P1-11：V0 验收拆分 + D1 演练脚本化 |
| `f2ff926` | D1 执行结果入档 + fixture 自我指认的缺陷修复 |
| `8f5d714` | 块计数生命周期 + 预算真正实现（#12 此前根本没实现）+ 骨架不再自带幽灵约束 |
| `06c1497` | resume 路径不再对不可读的 ACTIVE 报 clean；comparison 拿到 code identity |
| `805cfbe` | §26.4 六个探测的结果入档 |
| `9bbee8f` | 更新版本 schema 在**读取**时被报告；`validate` 开始校验 manifest |
| `748c98c` | 探测表收尾 |
| `7ef9038` | D2 / D3 演练脚本化 |
| `4188882` | **修掉我自己引入的误报**：每条 finding 都被当成"来自别的工具版本的文档" |
| `f53966e` | 块拥有自己的证据（D3 的 session 发现的 V0 设计缺口） |
| `0e38cd7` | 文档：块归属语义 + 选项框文案不是架构师的原话 |
| `fb9a71a` | 三个 fixture 的内部一致性 + D2/D3 结果入档 |

每条 commit message 都写了**为什么**，并附变异验证结果 —— 它们比本文件更详细，值得读。

## 下一步（按优先级）

### 1. 在**修好的 fixture** 上重跑 D2 与 D3

现有结论对应的是旧 fixture（D1 的 7/7 不受影响 —— 那两个缺陷它是在做对的同时额外报出来的）。
D2 这次还会顺带验证**收紧后的判据 5**（要求把"在等什么"写进 `ACTIVE`）。

```bash
tests/main/build_rotation_drill.sh /tmp/rotation-drill 900
tests/main/build_evaluator_conflict.sh /tmp/eval-conflict
cd /tmp/rotation-drill && claude     # 然后只给两行：/research-engineering + Continue current research.
```

同法跑另一个。判据表在 `docs/V0_ACCEPTANCE_GUIDE.md` 的 D2 / D3 两节。
**收尾**：`kill $(jq -r .execution.pid_or_job_id research/runs/EXP-0200/manifest.json)`
（上一次的 run 已自然跑完并写了 `result.json`，所以那个目录现在不再"在飞"）。

### 2. 回填需要 transcript 的判据

D1 的判据 1（"说出正确的 branch/HEAD"）、D2/D3 的"说出……"那几项，只能从 transcript 判。
如果架构师保留了会话记录，按 `docs/V0_ACCEPTANCE_GUIDE.md` 的判据表回填结论；没有就标"未判定"，
不要猜。

### 3. V0 complete 里还没碰的项

`docs/V0_ACCEPTANCE_GUIDE.md` 的 V0 complete 表逐条列了"为什么不是 Day-1"。其中需要
**第二个客户端**（#1、#22）、**长时自治块**（#12 的完整形态）、**并发写入**（#15）的项还没做过。
#11 与 #14 已由 §26.4 探测覆盖。

## 动手前必须知道的三件事

1. **`researchlog` 按 cwd 向上找 `research/`，不看脚本路径。** 检查一个副本（例如演练 repo 里的
   `tools/researchlog`）时必须先 `cd` 进去，否则它会去检查你**当前所在**的仓库 —— 而且很可能
   报 clean，于是你得到一个关于错误对象的"通过"。我踩过，白白误读了一次演练结果。
2. **跑全量测试前必须先问架构师**，哪怕改动落在共享底座上（我此前给自己开过"共享底座所以全套
   = targeted"的例外，已被明确关闭）。先跑覆盖改动模块的定向测试并报告。
3. **两类工作分开**：`research/*` 是研究状态（权威、由 `researchlog` 维护）；工具开发的记录是
   commit log + `docs/`。本轮全是后者。

## 权威来源（不要重读全部历史）

- **`docs/V0_ACCEPTANCE_GUIDE.md`** —— 拆分判据、Day-1 must / V0 complete 两张表、三个演练的
  完整判据与执行结果、§26.4 六个探测的实测表、发现的每个缺陷与修法。**这是本轮最完整的单一入口**。
- **commit messages** —— 每条都写了取舍与"为什么"，含变异验证（改回去会不会让测试失败）。
- `research/ACTIVE.json` + `cd` 到仓库根跑 `reconcile --json`。

## 已知开放项（诚实列出，未解决）

- **D2 / D3 的结论对应旧 fixture**，需在新 fixture 上重跑（上面第 1 项）。
- **所有"说出……"类判据需要 transcript**，目前只核实了产物能证明的那一半。
- **`research/ACTIVE.json` 的 `git.base_commit` 仍是 bootstrap 的值 `403383d`。** 因为没有块开过，
  它从未被更新。`reconcile` 不检查它，无功能影响；但如果新会话据此以为状态落后 6 个 commit，
  那是误会。
- **三个 fixture 现在会自断言内部一致性**（观察有 artifact 支撑、两次 run 的 code identity 相同、
  delta 有成因且可归因）。若将来再改 fixture：**改 fixture，不要改判据** —— 一个跑在意料之外状态
  上的演练，产出的结论没人能归因。这条已经吃过两次亏。
