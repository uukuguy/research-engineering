# RE 项目操作

## 项目恢复入口

日常入口是会话内的 `research-resume`，不是 Makefile：直接在项目根启动 Codex 后输入
`$research-resume`，或启动 Claude Code 后输入 `/research-resume`。清空上下文后同样适用。
恢复只读汇报并等待，不需要追加提示，不自动继续研究。Claude 的 `/resume` 是聊天历史
恢复，不是 RE 项目恢复。两客户端共用 `.research/`、代码和 dashboard。

换客户端前先用 `research-pause`，确认交接完整后关闭旧会话，再在新客户端恢复。
不要同时让两个客户端写同一份研究状态；聊天记忆、后台工具和子代理不会自动转移。

## 可选便捷启动

1. `make re-init`：安装/检查项目本地 RE，零模型调用，不创建研究结论。
2. `make re-start CLIENT=codex` 或 `make re-start CLIENT=claude`：打开全新客户端，
   自动调用同一个 research-resume（缺省 codex），汇报后等待。
   无状态时报告待初始化，不自动 bootstrap；有状态时不自动修复或继续研究。

第一次为新项目安装，在已完成 Git/uv/输入准备的项目根执行：

```sh
uv run python /path/to/research-engineering/tools/init_re_project.py --target .
```

安装后不再依赖源仓库。`make re-init` 重复执行只核验固定快照，不从源仓库
自动更新。遇到已有冲突文件会拒绝覆盖，需要显式合并；没有 reset/force 入口。

## 常用命令

会话内换新上下文：单独调用 `$research-pause`，确认交接后 `/clear`，再单独调用
`$research-resume`。无需退出重启，也不需要补充长提示；恢复只读汇报后等待指令。
这不是拦截 `/clear` 的自动 hook。恢复后 `$research-engineering` 或明确“按建议继续”
才开始下一轮有边界研究。

`$research-routes` 单独调用查看全局路线；“暂存 A，切换到 B”只更新研究焦点，不启动
实验。路线由 AI 在获准研究中维护，保留未选方案、依赖、证据、接续位置和重启条件。
旧项目未登记时会明确报告，不在只读恢复时自动迁移。AI 每轮提出下一条优先路线及理由，
架构师无需管理技术待办。环境受阻不等于路线被否定。

终端可用 `make re-routes`，单路线可用 `make re-route ROUTE=R-...`；都是只读诊断入口。

网页观测：`make re-dashboard` 启动本机只读页面，打开输出的 127.0.0.1 地址；Ctrl-C 退出。
`make re-dashboard-text` 保留终端诊断；`make re-watch` 每 5 秒刷新终端。
页面每 5 秒读取持久记录，不调用模型、不控制研究、不代表进程心跳。
中文摘要是带来源指纹的派生视图；记录变化会标记过期，不自动编造翻译或新结论。
在研究会话中说“更新 dashboard 摘要”即可由 research-status 综合并发布；无需手工写 JSON。
`make re-finding FINDING=FND-...` 查看一个结论的影响、局限、证据、替代关系和研究文档路径。
文档路径存在不代表内容已核实或跨机器可用；当前结论状态以 FINDINGS 为准。
高价值研究报告通过 evidence 的 `research-report` artifact 关联，不由 dashboard 自动编造。

日常在当前会话直接调用 `$research-status` 查看应用与架构进展，调用
`$research-pause` 检查并保存交接状态。收到“可退出”后关闭客户端；若报告
“交接未完成”，先看遗留风险。它不替代新会话的恢复检查，也不自动批准继续研究。
以下 Makefile 入口用于安装、启动或诊断，不要求架构师用 shell 做日常交接。

启动汇报后，单独调用 `$research-engineering` 即按已确认上下文开始一轮有边界的
自主实现与验证，不需要重述目标或追加长提示。应用交付目标不意味着切换到通用规划流程。
启动器以会话参数屏蔽已发现的 GSD / superpowers 流程技能，保留 RE 与必要诊断技能；
不修改用户全局设置。必须通过 make re-start/re-status 启动才带上此屏蔽，直接运行
codex 不会自动获得它。已运行客户端不会被追溯更改。

| 命令 | 用途 |
|---|---|
| `make re-help` | 命令表 |
| `make re-workers` | 只读查看分派问题、交回结果和主研究者审查状态 |
| `make re-check` | 核验工具、模板和 skills 的文件哈希 |
| `make re-state` | 输出 ACTIVE JSON；无研究状态时明确失败 |
| `make re-validate` | 校验 canonical state |
| `make re-reconcile` | 核对状态、Git 和证据 |
| `make re-status CLIENT=claude` | 可选新 Claude 会话，只调用 research-status |
| `make re-cli ARGS="record --help"` | 使用其他 RE 命令 |

`.codex/config.toml` 的 `model` 是项目默认模型，可由开发者修改。
启动器读取它并显式传给 Codex，同时限定 OpenAI/ChatGPT 认证，不自动改用 API
计费、不替换模型、不修改用户全局配置。登录或模型不可用时需处理客户端报错。

Claude Code 的模型可在 `.claude/settings.json` 配置 `model`；默认不指定，沿用该客户端
已有配置与登录/后端。RE 不注入模型别名、API key、权限绕过或自动切换计费方式。
该文件安装时只生成已发现工作流技能的精确 deny/skillOverrides，直接启动也可读取；
新装插件后的屏蔽覆盖需复核。Codex 的会话级屏蔽仍仅在启动器路径生效。
直接启动任一客户端均不经过终端字符集保护；这与 research-resume 的恢复语义无关。

安装清单 `re-install.json` 记录源 commit、源是否 dirty、实际部署文件的 SHA256。
AGENTS.md、Makefile、本文和模型配置是项目可编辑文件，不属于冻结工具快照。
快照校验只能检测相对清单的变化，不能替代科学判断或防恶意篡改机制。

此入口为交互式操作。
`make re-start` / `make re-status` 现在经本地 PTY 输出过滤，启动提示应包含
`terminal charset guard=ON`。它拦截 SO/SI、字符集指定/切换及非显示控制字符，
避免误读二进制后整个终端变成线框字；保留 TUI 光标、颜色和输入，不改原始日志。
仅在 POSIX 交互终端启用；直接运行 codex 或旧的已启动会话不经过这层防护。
不是通用 ANSI 安全过滤器，亦不保证任意显示/字体问题永不发生。

研究默认围绕一个明确问题，以约 30 分钟作为汇报窗口，不再默认限制为两次探针或
两条有效证据。AI 自主安排必要的对照和复核；执行次数衡量成本，不等于研究进展。
接近窗口时不再启动预计无法完成的新实验；已在执行的短时有界验证可以说明进度后
收完，但不能静默续开下一轮。结果明确或重复试错没有新信息时应提前汇报。
另留记录与归档时间，不能借收尾继续实验。明确的预算、硬截止、暂停、安全和外部
花费限制优先；单次执行超时与汇报窗口是两回事。已有运行块不因技能升级而自动放宽。
新块未指定证据计数上限时使用 max_evidence_iterations=null；这不解除时间和权限约束。
这些研究窗口规则由 agent 协议执行，不是操作系统超时保证。
`run --timeout` 在 POSIX 主机为本次命令建立独立进程组，超时时终止组内的普通后代
进程（包括 uv 启动的 Python），保存部分日志并记 interrupted，不作为科学反证。
命令自行创建新会话/脱离进程组的 daemon 不在此隔离范围内；若仍持有输出管道，工具
报告 RUN_OUTPUT_CAPTURE_INCOMPLETE，不能据此宣称后台工作已全部停止或交接完成。
Ctrl-C 的受监督收口已覆盖；SIGKILL、系统崩溃及外部任务仍需恢复时核对进程与产物。
自动验收仍需外部 supervisor、独立 transcript 和有效上下文检查。
新进程不等于完全隔离：用户级 skills、hooks、memories 等仍需在正式独立验收前审计。
工作区写沙箱也不代表外部文件不可读。

原始数据、既有 Git 历史和 uv 配置不由安装器修改；不复制先前研究的探针、
结论或 canonical state。正式首轮开始前，将部署文件作为清晰的 Git checkpoint。
