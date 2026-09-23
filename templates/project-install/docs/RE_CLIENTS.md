# RE 跨客户端恢复

项目恢复的日常入口：

| 客户端 | 直接启动后输入 | 可选受保护启动器 |
|---|---|---|
| Codex | `$research-resume` | `make re-start CLIENT=codex` |
| Claude Code | `/research-resume` | `make re-start CLIENT=claude` |

启动器仅负责客户端设置及终端字符集保护，并调用相同的恢复 skill。直接启动同样可以
恢复项目，但没有 PTY 防乱码过滤；Codex 的额外工作流技能屏蔽也仅由启动器参数提供。
Claude 项目 settings 中安装了已发现工作流技能的精确屏蔽项；不是永久覆盖未来插件的保证。

两端的暂停、状态、路线和研究技能同源，只是 `$` 与 `/` 调用形式不同。Claude 的 `/resume`
是客户端聊天历史，不代替 `/research-resume`。切换客户端不转移聊天记忆或后台工具进程。

先在旧会话 research-pause，确认完整交接并退出，再在新客户端 research-resume。
新客户端应汇报目标、架构师决策、未完成研究和路线，随后等待，不自行执行。
不要让两个客户端同时写 `.research/`；无需复制目录或建立第二套研究状态。

Codex 模型保留在 `.codex/config.toml`。Claude 可在 `.claude/settings.json` 设置 `model`，
未设置时沿用已有客户端配置。RE 不注入 Claude 模型别名、API key、后端或权限绕过；
已有 Claude 配置可能使用订阅或 API，启动前确认自己的配置，不把 Codex 订阅当作 Claude 授权。
Claude 权限同样沿用自己的配置，不把 Codex 的 Full Access 自动迁移过去。

验收：先只读恢复一次，再经授权做有界研究并暂停，最后换回另一客户端恢复。检查
速度决策、路线接续点、证据局限、未完成任务均保留，无重讲背景或自动继续研究。
安装/参数测试通过不等于真实模型双向交接已通过。
