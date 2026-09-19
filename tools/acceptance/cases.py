"""Case registry — the hand-written source of truth for what gets verified.

This is intentional. We do NOT parse docs/RE_ACCEPTANCE_CASES.md into cases;
the guide is human-authored prose and parsing it would drift. Instead each
case is a CaseSpec that names where in the guide it lives (the ``source``
field) so the link stays bidirectional.

Three runner modes (driven by `runner_mode`, not by `expected`):
  - AUTO      runner completes in <60s; included in `make acceptance`
  - LONG_RUN  runner takes 60s–900s (claude-based drills); only run by
              `make acceptance-full`. Status becomes LONG_RUN_DONE /
              LONG_RUN_TIMEOUT / LONG_RUN_FAIL.
  - MANUAL    requires human; run by hand per the case notes
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

# Status symbols — kept in sync with RE_ACCEPTANCE_CASES.md §13.3.
PASS = "PASS"
FAIL = "FAIL"
ENV_BLOCKED = "ENV_BLOCKED"
MANUAL_FIXTURE_REQUIRED = "MANUAL_FIXTURE_REQUIRED"
UNJUDGED = "UNJUDGED"
SKIPPED = "SKIPPED"  # runner could not produce a verdict (internal error)
LONG_RUN_DONE = "LONG_RUN_DONE"        # ran end-to-end (whether g0/rows passed)
LONG_RUN_TIMEOUT = "LONG_RUN_TIMEOUT"  # subprocess exceeded timeout_s
LONG_RUN_FAIL = "LONG_RUN_FAIL"        # runner/shell exited non-zero
LONG_RUN_SKIPPED = "LONG_RUN_SKIPPED"  # pre-flight failed (e.g. claude endpoint not usable)

# Runner mode flags
AUTO = "AUTO"
LONG_RUN = "LONG_RUN"
MANUAL = "MANUAL"


@dataclass(frozen=True)
class CaseSpec:
    """One acceptance case.

    Fields:
      id              — short stable id, e.g. "V0.M1" or "V1.D1.c1"
      title           — one-line human label
      invariant       — 1..8, the AGENTS.md core invariant this case
                        primarily tests (None for cross-cutting fixtures)
      level           — "V0" or "V1" (which acceptance document)
      runner_mode     — AUTO / LONG_RUN / MANUAL — which `make acceptance*`
                        target picks this case up
      expected        — expected status from the AUTO-mode runner. For
                        LONG_RUN cases expected is informational only;
                        the actual verdict comes from verify_case.py.
      runner          — callable(ctx) -> CaseResult; never raises
      source          — pointer back to the guide chapter
      timeout_s       — per-case timeout override (None = runner default)
      notes           — Architect-facing next-step note (rendered in
                        report). For LONG_RUN cases this should name the
                        fixture builder + run_case.sh invocation +
                        verify_case.py parse rule. For MANUAL cases this
                        explains what the Architect must do themselves.
    """

    id: str
    title: str
    invariant: Optional[int]
    level: str
    runner_mode: str
    expected: str
    runner: Optional[Callable]  # None means "skip / manual only"
    source: str
    timeout_s: Optional[int] = None
    notes: str = ""


def all_cases() -> List[CaseSpec]:
    """Return the full registry in guide order.

    Order matches docs/RE_ACCEPTANCE_CASES.md so a reader can scan the
    report top-to-bottom without context switches.
    """
    # Import here (not at module top) to avoid an import cycle with
    # runner.py — and so Pyright sees the symbols through the
    # acceptance package namespace.
    from tools.acceptance.runner import (  # type: ignore[import-not-found]
        run_v0_1_multi_client,
        run_v0_2,
        run_v0_5,
        run_v0_8,
        run_v0_11,
        run_v0_12,
        run_v0_14,
        run_v0_15,
        run_v0_16,
        run_v0_18,
        run_v0_20,
        run_v0_21,
        run_v0_architect_source_text,
        run_v0_env_lim,
        run_v0_long_d1_recovery,
        run_v0_long_d2_rotation,
        run_v0_long_10_evaluator_conflict,
        run_v0_m1,
        run_v0_m2,
        run_v0_m3,
        run_v0_m5,
        run_v1_d1_sharded_ledger,
        run_v1_d2_replay,
        run_v1_d3_block_budget,
        run_v1_d4_status_cache,
        run_v1_d5_worktree,
        run_v1_d6_telemetry,
        run_v1_d7_capability_map,
        run_v1_d8_signals,
        run_v1_d9_client_matrix,
    )

    # Note: V0 case IDs use the V0 nomenclature (M1..M5, #1..#22). V1 uses
    # D1..D9 at the drill level; per-criterion cases use "D<N>.c<k>".
    cases: List[CaseSpec] = []

    # === V0 — Day-1 must (5) ===
    cases += [
        CaseSpec(
            id="V0.M1",
            title="全新 repo 建最小 canonical state，且不写重型 plan",
            invariant=1,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_m1,
            source="docs/RE_ACCEPTANCE_CASES.md §1.5.1; V0_ACCEPTANCE_GUIDE.md §V0 状态表 M1",
        ),
        CaseSpec(
            id="V0.M2",
            title="不默认写长 plan 与大量 tests",
            invariant=2,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_m2,
            source="docs/RE_ACCEPTANCE_CASES.md §2.5.3; V0_ACCEPTANCE_GUIDE.md §V0 状态表 M2",
        ),
        CaseSpec(
            id="V0.M3",
            title="连续 2–3 evidence-producing iterations（RB-001）",
            invariant=2,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_m3,
            source="docs/RE_ACCEPTANCE_CASES.md §2.5.1; V0_ACCEPTANCE_GUIDE.md §V0 状态表 M3",
        ),
        CaseSpec(
            id="V0.M4",
            title="Session Recovery Benchmark（演练 D1，7/7）",
            invariant=6,
            level="V0",
            runner_mode=LONG_RUN,
            expected=LONG_RUN_DONE,
            runner=run_v0_long_d1_recovery,
            source="docs/RE_ACCEPTANCE_CASES.md §6.5.1; V0_CASES.md §案例三/四",
            timeout_s=300,
            notes=(
                "LONG_RUN: `make acceptance-full` 会自动跑 build_recovery_drill.sh + "
                "run_case.sh recovery claude + verify_case.py recovery。"
            ),
        ),
        CaseSpec(
            id="V0.M5",
            title="不可行实验判为环境限制（ENV-LIM-001..006）",
            invariant=3,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_m5,
            source="docs/RE_ACCEPTANCE_CASES.md §3.5.1; V0_ACCEPTANCE_GUIDE.md §V0 状态表 M5",
        ),
    ]

    # === V0 — complete (16, M-class excepted above) ===
    cases += [
        CaseSpec(
            id="V0.1",
            title="另一客户端也能进入 Research Mode（codex 三路径 ENV_BLOCKED）",
            invariant=3,
            level="V0",
            runner_mode=AUTO,
            expected=ENV_BLOCKED,
            runner=run_v0_1_multi_client,
            source="docs/RE_ACCEPTANCE_CASES.md §3.5.3; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #1",
            notes="架构师 2026-09-17 改判：pi 替代 codex；codex 端 ENV_BLOCKED 不计 V0 失败；B 类清单不收录此条",
        ),
        CaseSpec(
            id="V0.2",
            title="没有 runnable system 也会自主做 probe",
            invariant=1,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_2,
            source="docs/RE_ACCEPTANCE_CASES.md §1.5.1; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #2",
        ),
        CaseSpec(
            id="V0.5",
            title="架构师不指定具体算法",
            invariant=1,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_5,
            source="docs/RE_ACCEPTANCE_CASES.md §1.4 case-table; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #5",
            notes="fuzzy-match：ACTIVE/CURRENT 不应含算法名（heuristic，可能 UNJUDGED）",
        ),
        CaseSpec(
            id="V0.8",
            title="自建 HARNESS-001（supports_evidence + preserves/missing 边界）",
            invariant=4,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_8,
            source="docs/RE_ACCEPTANCE_CASES.md §4.5.1; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #8",
        ),
        CaseSpec(
            id="V0.10",
            title="缺失/失真 evaluator 当 Research Subject（演练 D3）",
            invariant=8,
            level="V0",
            runner_mode=LONG_RUN,
            expected=LONG_RUN_DONE,
            runner=run_v0_long_10_evaluator_conflict,
            source="docs/RE_ACCEPTANCE_CASES.md §8.5.2; V0_CASES.md §案例三/四",
            timeout_s=300,
            notes="LONG_RUN:同 D3 fixture,verify_case.py evaluator-conflict 5/5 判据。",
        ),
        CaseSpec(
            id="V0.11",
            title="schema_version + 中断写入恢复（§26.4 五格探测）",
            invariant=5,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_11,
            source="docs/RE_ACCEPTANCE_CASES.md §5.5.1; V0_ACCEPTANCE_GUIDE.md §§26.4",
        ),
        CaseSpec(
            id="V0.12",
            title="Block Contract 阻止无界 exploitation（派生 count）",
            invariant=2,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_12,
            source="docs/RE_ACCEPTANCE_CASES.md §6.5.3; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #12",
        ),
        CaseSpec(
            id="V0.13",
            title="long-running 跨 session 不重复启动（演练 D2）",
            invariant=6,
            level="V0",
            runner_mode=LONG_RUN,
            expected=LONG_RUN_DONE,
            runner=run_v0_long_d2_rotation,
            source="docs/RE_ACCEPTANCE_CASES.md §6.5.2; V0_CASES.md §案例一",
            timeout_s=300,
            notes=(
                "LONG_RUN:`make acceptance-full` 用 30s 短版跑 build_rotation_drill.sh + "
                "run_case.sh rotation claude 30 + verify_case.py rotation 6/6。"
            ),
        ),
        CaseSpec(
            id="V0.14",
            title="mutable-input lineage（COMPARABLE / ATTRIBUTION_FORBIDDEN / REBASELINE_REQUIRED）",
            invariant=1,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_14,
            source="docs/RE_ACCEPTANCE_CASES.md §1.5.2; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #14",
        ),
        CaseSpec(
            id="V0.15",
            title="并行 writer 使用 collision-resistant IDs",
            invariant=5,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_15,
            source="docs/RE_ACCEPTANCE_CASES.md §5.4 case-table; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #15",
        ),
        CaseSpec(
            id="V0.16",
            title="Git/Evidence 无 self-referential commit hash",
            invariant=5,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_16,
            source="docs/RE_ACCEPTANCE_CASES.md §5.5.2; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #16",
        ),
        CaseSpec(
            id="V0.18",
            title="Git commit/diff 与 Evidence 双向定位",
            invariant=1,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_18,
            source="docs/RE_ACCEPTANCE_CASES.md §1.5.3; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #18",
        ),
        CaseSpec(
            id="V0.19",
            title="不依赖 hooks/MCP/GitHub 也能完成完整 V0 loop（--bare / --strict-mcp-config）",
            invariant=6,
            level="V0",
            runner_mode=MANUAL,
            expected=MANUAL_FIXTURE_REQUIRED,
            runner=None,
            source="docs/RE_ACCEPTANCE_CASES.md §V0 状态表 #19",
            notes=(
                "MANUAL:tests/main/run_case.sh 不支持裸模式启动 claude。"
                "架构师手工跑 `claude --bare` 或 `claude --settings '{\"hooks\":{}}' "
                "--strict-mcp-config` 验完整 V0 loop。"
            ),
        ),
        CaseSpec(
            id="V0.20",
            title="research-status 能只读生成全局中文 Project Working Model",
            invariant=8,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_20,
            source="docs/RE_ACCEPTANCE_CASES.md §8.5.3; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #20",
        ),
        CaseSpec(
            id="V0.21",
            title="状态汇报区分 Established/Provisional/Refuted/Open 与三维 maturity",
            invariant=8,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_21,
            source="docs/RE_ACCEPTANCE_CASES.md §8.5.3; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #21",
        ),
        CaseSpec(
            id="V0.22",
            title="status 报告交给另一客户端建立正确认知（跨客户端演练）",
            invariant=7,
            level="V0",
            runner_mode=MANUAL,
            expected=MANUAL_FIXTURE_REQUIRED,
            runner=None,
            source="docs/RE_ACCEPTANCE_CASES.md §7.5.1; V0_ACCEPTANCE_GUIDE.md §V0 状态表 #22",
            notes=(
                "MANUAL:跨客户端需要 pi 端配置 (.env + session dir),tests/main/run_case.sh "
                "bootstrap + verify_case.py bootstrap 6/6 是 claude 端,pi 端验证需要架构师手工。"
                "架构师按 V0_CASES.md §客户端矩阵 跑 pi。"
            ),
        ),
        CaseSpec(
            id="V0.ARCHITECT.source_text",
            title="ARCHITECT.md signal 原话不规范化",
            invariant=7,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_architect_source_text,
            source="docs/RE_ACCEPTANCE_CASES.md §7.5.3",
        ),
    ]

    # === V0 — ENV-LIM (compound case: all 6 limits + the runner checks each) ===
    cases.append(
        CaseSpec(
            id="V0.ENV-LIM",
            title="ENV-LIM-001..006 全部以 ENV_UNSUPPORTED 入档，无 refuted",
            invariant=3,
            level="V0",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v0_env_lim,
            source="docs/RE_ACCEPTANCE_CASES.md §3.5.1",
        )
    )

    # === V1 — 9 drills × criterion (Phase 1 ships D1 + DB-driven shortcut;
    #     Phase 2 expands the per-criterion breakdown.) ===
    cases += [
        CaseSpec(
            id="V1.D1",
            title="Sharded ledger partition（6/7 + 1 deferred）",
            invariant=5,
            level="V1",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v1_d1_sharded_ledger,
            source="docs/RE_ACCEPTANCE_CASES.md §5.5.3; V1_CASES.md §V1-D1",
        ),
        CaseSpec(
            id="V1.D2",
            title="E2/E3 replay contract（6/6 PASS）",
            invariant=2,
            level="V1",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v1_d2_replay,
            source="docs/RE_ACCEPTANCE_CASES.md §2.5.2; V1_CASES.md §V1-D2",
        ),
        CaseSpec(
            id="V1.D3",
            title="Bounded autonomous block across sessions（7/7 PASS）",
            invariant=6,
            level="V1",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v1_d3_block_budget,
            source="docs/RE_ACCEPTANCE_CASES.md §6.5.3; V1_CASES.md §V1-D3",
        ),
        CaseSpec(
            id="V1.D4",
            title="STATUS.md cache + stale-detection + synthesis（5/5 PASS）",
            invariant=5,
            level="V1",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v1_d4_status_cache,
            source="docs/RE_ACCEPTANCE_CASES.md §5.5.4; V1_CASES.md §V1-D4",
        ),
        CaseSpec(
            id="V1.D5",
            title="Worktree single-writer enforcement（5/5 PASS）",
            invariant=6,
            level="V1",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v1_d5_worktree,
            source="docs/V1_CASES.md §V1-D5",
        ),
        CaseSpec(
            id="V1.D6",
            title="Productivity telemetry（4/4 PASS）",
            invariant=6,
            level="V1",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v1_d6_telemetry,
            source="docs/V1_CASES.md §V1-D6",
        ),
        CaseSpec(
            id="V1.D7",
            title="Research Capability Map + harness investment judgement（6/6 PASS）",
            invariant=1,
            level="V1",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v1_d7_capability_map,
            source="docs/RE_ACCEPTANCE_CASES.md §1.5.4; V1_CASES.md §V1-D7",
        ),
        CaseSpec(
            id="V1.D8",
            title="Source-text enforcement + signals upgrade（4/4 PASS）",
            invariant=7,
            level="V1",
            runner_mode=AUTO,
            expected=PASS,
            runner=run_v1_d8_signals,
            source="docs/RE_ACCEPTANCE_CASES.md §7.5.2; V1_CASES.md §V1-D8",
        ),
        CaseSpec(
            id="V1.D9",
            title="Client matrix (claude × pi) — 0/4 verbatim, 4/4 ENV_BLOCKED",
            invariant=3,
            level="V1",
            runner_mode=AUTO,
            expected=ENV_BLOCKED,
            runner=run_v1_d9_client_matrix,
            source="docs/RE_ACCEPTANCE_CASES.md §3.5.2; V1_CASES.md §V1-D9",
            notes="minimax-compat 端点策略阻断；ARCHITECT D-004; A-3 待决策",
        ),
    ]

    return cases


def cases_by_filter(level: Optional[str] = None) -> List[CaseSpec]:
    """Return cases filtered by level ('V0' or 'V1'), preserving order."""
    if level is None:
        return list(all_cases())
    return [c for c in all_cases() if c.level == level]
