---
name: research-routes
description: Inspect or steer persistent RE research routes, including parking, switching and reopening them without losing alternatives. Bare invocation is read-only; explicit changes do not start experiments.
---

# Research Routes

Use this project's canonical CURRENT.research_routes via its local `routes` command.
Read research-engineering's `references/research-routes.md` before a mutation. No extra
prompt is needed for a bare invocation: read the routes and relevant current constraints,
then show a short Chinese portfolio with application value, status, reason, next test,
and wake conditions. No automatic state writes, migration, or experiment execution.

An explicit request such as "暂存 A，切换到 B" authorizes that bounded state change,
not a new research block. Resolve route names from state; ask only if the target is
genuinely ambiguous. For the chosen route, inspect its evidence and resume point,
check current Git/worktree and unfinished execution, then use lifecycle verbs. Never
discard a dirty diff or terminate an existing job to make a switch succeed.

For a wake request, state the observed trigger and cite the new evidence where applicable.
If it requires changing a HARD boundary, new spend or architect promotion, keep it blocked
until explicitly authorized. A user veto cannot be bypassed by a technical wake condition.

Do not ask the architect to choose routine technical details. Recommend the next route
and explain its advantage under the current goal and budget. If records are absent,
say so; registration belongs to an authorized research block, not this query.
The underlying commands are agent tools, not homework for the architect.

After an authorized route change, if a dashboard brief already exists, refresh its
Chinese view using research-status's `references/dashboard-brief.md` before the final
confirmation. This derived display update is part of the requested switch, not permission
to start research. Re-read the current sources and explain the changed focus and retained
route; never merely replace an old brief's source fingerprint. If publication fails,
report "路线已切换；中文摘要更新失败" with the reason, without rolling back a valid switch
or asking the architect to invoke another skill. Bare list/view remains read-only.

## Numbered selection contract

Bare invocation must call `routes list --json` and show a compact Chinese table:
`编号 | 路线 | 状态 | 应用价值 / 下一步`. Use the returned `choices` order and exact
`number` values, not a hand-numbered priority list. Include the stable R-* ID beside
the short Chinese title. Active is focus, not running. Flag conflicts with current
architect signals in the affected row; do not recommend stale instructions.

End with: `可以说“查看 2”或“切换到 2”；切换只保存焦点，不启动研究。`
Retain the returned `portfolio_revision` together with this displayed mapping.
For a later numbered selection, use `--select N --portfolio-revision REV` rather than
silently converting to `--id`. `查看 N` uses `routes list` and explains its details;
`切换到 N` uses lifecycle verbs with the required preservation/wake checks above.
If the list changed or the prior mapping is absent after a new session, show a fresh
table and ask for selection again. Never reinterpret an old number against a new list.
For multi-step wake/activate, resolve the old number with a guarded read first, then
retain the resolved stable ID across the authorized steps; never reuse its old number.
Do not switch on a bare number without clear selection intent. Explicitly requesting
research after a switch is separate authorization; do not add a new approval gate.
