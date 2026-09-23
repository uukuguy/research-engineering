"""Read-only terminal/JSON overview of persisted records, not a live agent monitor."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from researchlog import jgit, repo, schema, state
from researchlog.commands import reconcile, validate
from researchlog.errors import Result
from researchlog.errors import Finding, SEVERITY_ERROR

NAME = "dashboard"
HELP = "read-only overview of persisted progress; liveness and missing telemetry stay unknown"


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--finding", default=None, help="inspect one FND id with evidence and report paths")
    parser.add_argument("--route", default=None, help="inspect a research route including pause/wake history")


def finding_index(paths, ledger):
    entries = []
    for entry in ledger.findings_entries:
        reports = []
        for evidence_id in entry.get("evidence") or []:
            ev = ledger.records.get(evidence_id, {})
            for artifact in ev.get("artifacts") or []:
                if artifact.get("role") != "research-report":
                    continue
                raw = artifact.get("path", "")
                resolved = (paths.root / raw).resolve()
                local = bool(raw) and resolved.is_relative_to(paths.root.resolve())
                reports.append({"path": raw, "evidence_id": evidence_id,
                                "availability": "present" if local and resolved.is_file()
                                else "missing" if local else "outside_project",
                                "recorded_sha256": artifact.get("sha256")})
        entries.append({**entry, "reports": reports})
    return entries


def line(value: object) -> str:
    # Persisted strings are untrusted terminal text, not ANSI control sequences.
    text = str(value if value is not None else "未记录")
    return " ".join("".join(c if c.isprintable() else " " for c in text).split())


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    active, recovered = state.load_active_with_findings(paths)
    current = schema.require_block(paths.current.read_text(), "current", source=paths.current.name)
    ledger = state.load_ledger(paths)
    from researchlog import delegation
    from researchlog.errors import StateInvalid
    try:
        workers = delegation.load(paths)
    except StateInvalid:
        workers = []  # validate/reconcile below report corruption, never hide it as clean.
    conclusions = finding_index(paths, ledger)
    requested = getattr(args, "finding", None)
    selected = [f for f in conclusions if f.get("id") == requested] if requested else conclusions
    route_id = getattr(args, 'route', None)
    from researchlog import routes
    route_problems = routes.check(current, set(ledger.records))
    portfolio = [] if route_problems else current.get('research_routes', [])
    route_rows = sorted([r for r in portfolio if not route_id or r['id'] == route_id],
                        key=lambda r: (r['priority'], r['id']))
    now = datetime.now(timezone.utc)
    updated = active.get("updated_at")
    age = None
    try:
        stamp = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
        if stamp.tzinfo is not None:
            age = max(0, int((now - stamp).total_seconds()))
    except ValueError:
        pass
    runs = [{"id": key, "recorded_status": value.get("status"),
             "result_present": paths.result(key).is_file()}
            for key, value in sorted(ledger.manifests.items())]
    recent = sorted(ledger.records.items(), key=lambda pair: str(pair[1].get("created_at") or pair[0]))[-5:]
    evidence = [{"id": key, **{k: ev.get(k) for k in
                ("created_at", "question", "observation", "research_outcome")}}
                for key, ev in recent]
    for item, (_, ev) in zip(evidence, recent):
        item["observation"] = ev.get("observations") or ev.get("observation")
    result = Result(payload={
        "generated_at": now.isoformat(), "root": str(paths.root),
        "sources": [str(paths.active), str(paths.current), "ledger", "run manifests/results"],
        "objective": current.get("objective"), "block": active.get("block"),
        "recorded_status": active.get("status"), "updated_at": updated,
        "state_age_seconds": age, "current_observation": active.get("current_observation"),
        "next_action": active.get("next_action"), "runs": runs, "recent_evidence": evidence,
        "liveness": "unknown", "heartbeat": "unavailable", "retry_history": "unavailable",
        "blocking_duration": "unknown", "git_dirty": bool(jgit.status_porcelain(paths.root)),
        "conclusions": selected, "conclusions_total": len(conclusions),
        "routes": route_rows, "routes_registered": 'research_routes' in current,
        "delegations": workers,
    })
    if requested and not selected:
        result.add(Finding("DASHBOARD_FINDING_UNKNOWN", SEVERITY_ERROR, requested,
                           "No finding with this ID; no state changed"))
    if route_id and not route_rows:
        result.add(Finding('DASHBOARD_ROUTE_UNKNOWN', SEVERITY_ERROR, route_id,
                           'No readable route with this ID; no state changed'))
    for finding in recovered + ledger.unreadable:
        result.add(finding)
    for check in (validate.run(argparse.Namespace(root=paths.root, print_schema=None, strict=False)),
                  reconcile.run(argparse.Namespace(root=paths.root, stale_after=120))):
        for finding in check.findings:
            result.add(finding)
        result.exit_code = max(result.exit_code, check.exit_code)
    lines = ["RE 终端概览 — 持久记录快照，不是实时存活证明",
             f"刷新时间：{now.isoformat(timespec='seconds')}",
             f"目标：{line(current.get('objective'))}",
             f"记录状态：{line(active.get('status'))} | 状态更新时间：{line(updated)} | 距今秒数：{line(age)}",
             "进程存活：未知 | 心跳/重试：尚未采集 | 阻塞持续时间：未知",
             f"最近进展（AI 记录）：{line(active.get('current_observation'))}",
             f"下一步/授权（AI 记录）：{line(active.get('next_action'))}",
             f"Git：{'有未提交改动' if result.payload['git_dirty'] else '干净'}",
             f"校验：{len(result.findings)} 项发现（通过也不证明研究结论正确）",
             "运行记录："]
    lines += [f"  {line(r['id'])}: {line(r['recorded_status'])}; result={'有' if r['result_present'] else '无'}" for r in runs[-8:]]
    lines += ["最近证据："]
    lines += [f"  {line(ev['id'])}: {line(ev['research_outcome'])} — {line(ev['observation'] or ev['question'])}" for ev in evidence]
    lines += ['研究路线（优先级是 AI 建议，不是授权；active 是研究焦点，不是进程存活）：']
    if not portfolio:
        lines.append('  路线记录无效，见校验发现。' if route_problems else '  尚未登记；不代表没有未解决问题。')
    labels = dict(queued='待探索', active='当前焦点', parked='暂存', blocked='受阻',
                  completed='已完成', rejected='已否定')
    for r in route_rows:
        lines += [f"  {line(r['id'])} [{labels[r['status']]}] P{r['priority']} {line(r['title'])}",
                  f"    原因：{line(r['reason'])}", f"    下一探针：{line(r['next_probe'])}"]
        if r['status'] in ('parked', 'blocked'):
            lines.append(f"    重启条件：{line(r['wake_when'])}")
        if route_id:
            for key, label in [('question', '问题'), ('value', '应用价值'), ('resume_point', '接续位置'),
                               ('evidence', '证据'), ('depends_on', '前置路线'),
                               ('alternatives', '替代路线'), ('history', '切换历史')]:
                lines.append(f"    {label}：{line(r[key])}")
    lines += ['分派研究（记录状态，不是进程存活证明；交回不等于结论获认可）：']
    for w in workers:
        c = w['contract']
        lines += [f"  {line(w['id'])} [{line(w['status'])}] {line(c.get('question'))}",
                  f"    应用价值：{line(c.get('application_value'))} | 路线：{line(c.get('route_id'))}",
                  f"    最近变化：{line(w['history'][-1]['at'])} {line(w['history'][-1]['reason'])} | 截止：{line(c.get('deadline'))}"]
        if w.get('result'):
            lines.append(f"    交回结果：{line(w['result'].get('summary'))}")
    lines += ["研究结论（当前状态来自 FINDINGS，文档不是批准）："]
    for f in selected:
        lines.append(f"  {line(f.get('id'))} [{line(f.get('status'))}] {line(f.get('title'))}")
        if requested:
            lines += [f"    影响：{line(f.get('implication'))}",
                      f"    局限：{line(f.get('limitation'))}",
                      f"    证据：{line(f.get('evidence'))}",
                      f"    替代/原因：{line(f.get('superseded_by'))} / {line(f.get('reason'))}"]
        if not f['reports']:
            lines.append("    研究文档：尚未关联")
        for doc in f['reports']:
            lines.append(f"    文档：{line(doc['path'])} [{doc['availability']}] ← {line(doc['evidence_id'])}")
    lines += [f"  ! {line(f.code)}: {line(f.message)}" for f in result.findings]
    result.human = "\n".join(lines)
    return result
