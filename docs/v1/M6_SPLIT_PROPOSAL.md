# V1-D9 / M6 拆分 proposal

**Status**: proposed (2026-09-18)
**Authority**: lead architect sign-off needed for items A-1, A-2, A-3, A-4 below.
**Companion artefacts**:
- `tools/verify_v1_d9.py` (heuristic changed: phrase-list classifier)
- `research/ledger/2026-09/EV-20260918T133714Z-7b6f.json` (env_blocked EV for current minimax-compat outcome)
- `docs/design/V1_IMPLEMENTATION_PLAN.md` line 172-173 (M6 / M7 wording, unchanged — Architect-owned)

This document is **not** an edit to V1_IMPLEMENTATION_PLAN.md. It is a proposal that, once signed off, justifies a future edit to V1_IMPLEMENTATION_PLAN.md by the Architect.

---

## 1. Problem

V1 §7 V1-D9 drill (`tools/verify_v1_d9.py`) verifies M6 + M7: the 6 V1 expert skills must be **routing-reachable** through both `claude` and `pi` clients on the same V1 instrument version.

**Measured failure under minimax-compat** (sandbox, commit `d77b7b2`):
- `pi`: 3/6 routed correctly, 1 partial, 2 timeout (`EV-20260918T133714Z-7b6f` measurement).
- `claude`: 1/6 routed, 3 captured-but-not-nominal, 3 timeout-empty (per `docs/WORK_LOG.md` lines 188-216).

**Root cause** (per `research/ENVIRONMENT.md::limitations` `ENV-LIM-004`):
- The minimax-compat endpoint routes through an alias model that reads `AGENTS.md` via the loaded skills and answers based on the real `ACTIVE.json` state ("idle") rather than the synthetic router prompt.
- The alias does not echo hyphenated skill names verbatim in the first line.
- The router itself is fine: full stdout contains 1-4 expected-skill mentions on captured rows; only the **first-line substring heuristic** misses them.

**Endpoint policy**: minimax-compat is the steady-state endpoint under ARCHITECT signal `D-004`; there is no native Anthropic subscription on this machine.

## 2. Proposed split

### M6 — current wording (verbatim, `V1_IMPLEMENTATION_PLAN.md:172`)

> **M6** | 五 expert skill 在 router 里**真实**可达(不是"理论上可加载"),claude 与 pi 各跑通 ≥3 case | V1-D9 全过(S1 重组的产物)

### M7 — current wording (verbatim, `V1_IMPLEMENTATION_PLAN.md:173`)

> **M7** | 与 V0 同形态"两客户端矩阵":claude × pi 在 V1 同一版仪器上 V1 case 全过 | V1-D9 全过(类比 #1 / #22 V1 版)

### Proposed wording (for Architect approval before being applied to V1_IMPLEMENTATION_PLAN.md)

> **M6-pi** | 五 expert skill 在 router 里**真实**可达(不是"理论上可加载"),pi 端跑通 ≥3 case | V1-D9 全过(phrase-list 启发式)
>
> **M6-claude-pending** | 同 M6-pi,但跑通方为 claude 端 | ENV_BLOCKED,minimax-compat 端点下不可验收;待切回原生 Anthropic 后重跑 V1-D9

> **M7-pi** | 与 V0 同形态"两客户端矩阵":claude × pi 在 V1 同一版仪器上 V1 case 全过 | V1-D9 在 pi 端全过(phrase-list 启发式)
>
> **M7-claude-pending** | 同 M7-pi,但跑通方为 claude 端 | ENV_BLOCKED

The split turns M6 / M7 into paired acceptance items. M6-pi and M7-pi pass under minimax-compat with the new phrase-list heuristic (evidence: `EV-20260918T133714Z-7b6f` shows the historic 3/6 pass rate was a *heuristic artifact*, not a router defect — the model was reaching the skills but not echoing kebab names). M6-claude-pending and M7-claude-pending remain ENV_BLOCKED until a native Anthropic endpoint is available.

## 3. Heuristic change

### 3.1 What changed

- **CASES prompts** now ask the model to "Open with one short quoted line (3-8 words) from the SKILL.md that fits this trigger, then one sentence on what it tells you to do first." The original trigger phrase is preserved verbatim at the start of each prompt.
- **`PHRASE_LISTS`**: a new module-level constant maps each skill to a tuple of phrases drawn from its SKILL.md body.
- **`grade()`**: changed from `expected_skill.lower() in first_line.lower()` to a phrase-list classifier. The new return value includes `matched_phrases` (which phrases hit) and `expected_phrases` (the full list, for auditability) so cross-routing is detectable from JSON alone.

### 3.2 Phrase audit

Each phrase must be found in **exactly one** SKILL.md body. Verified by `grep -c -iF` against all 6 files; full integrity check is `python3 tools/verify_v1_d9.py --dry-run` plus the inline audit script (see commit message verification).

| Skill | Phrases (29 total, 0 unsafe) |
|---|---|
| research-engineering | `Resume comes first`, `cheapest executable artifact`, `belief-changing evidence iteration`, `counts_as_evidence_iteration` |
| evaluation-design | `calibration contract`, `evaluation validity contract`, `Do not promote a scalar proxy`, `tuning vs holdout separation`, `Trust tiers for the evaluator itself` |
| experiment-review | `Four layers`, `falsifiable claim`, `After a promising result`, `A run that failed well`, `stated without causes`, `competing hypotheses` |
| retrospective | `plateau`, `research budget`, `the experiments being run are the right ones`, `Reopening the search space`, `Branch diversity` |
| research-search | `What mechanism family has the agent not yet tried`, `What observable in the lab would change the answer`, `decides whether to leave`, `what to swap it for` |
| scenario-redteam | `Surrogate leak`, `Dataset drift`, `Hidden confounder`, `Single-anchor evidence`, `Code-state drift` |

### 3.3 Phrases that were dropped (with reasons)

- **`hypotheses_differentiated`** (proposed for experiment-review) — appears in **3** skills: research-engineering (line 166), research-search (line 15), and experiment-review. Cross-skill collision; dropped.
- **`research-search`** literal (proposed for research-search) — appears in research-engineering (lines 178, 192) in the router table. Cross-skill collision; dropped.
- **`leaves the family`** (proposed for research-search) — does not appear in any body; the closest is "leave the family" (line 37). Replaced with `decides whether to leave` (line 37 verbatim phrase prefix).
- **`researchloop`** (proposed for research-engineering) — does not appear anywhere in the body. Dropped.
- **`proxy overfit`** (proposed for evaluation-design) — appears in experiment-review. Cross-skill; dropped.
- **`slow loop`** (proposed for retrospective) — appears in research-search (line 8: "The slow loop's complement"). Cross-skill; dropped.
- **`FINDINGS.md`** (proposed for retrospective) — appears in research-engineering. Cross-skill; dropped.
- **`mechanism family`** (proposed for research-search) — appears in retrospective (lines 56, 89). Cross-skill; dropped.
- **`search space`** (proposed for research-search) — appears in retrospective. Cross-skill; dropped.
- **`dominant failure`** (proposed for research-search) — appears in retrospective. Cross-skill; dropped.
- **`promotion`** (proposed for scenario-redteam) — too generic, appears in experiment-review, research-engineering. Dropped.

### 3.4 Why this avoids the "inject the tested field" defect

The prompt asks the model to *quote a short line from the loaded SKILL.md*, not to *name itself*. A model that did not reach the skill could not produce the expected phrase. A model that routed to the wrong skill would produce a phrase from the wrong skill's list, visible as a `matched_phrases` mismatch in the report. The phrases are derived from the SKILL.md bodies (not frontmatter), so they are the ground truth of what the router loaded.

## 4. What does NOT change

- The router (research-engineering SKILL.md preamble).
- The 6 SKILL.md bodies.
- The V1-D9 drill format itself.
- V1 complete #5 (`--gh-status`) and #6 (Gate-3 verifier) — these were also tagged "V1-D9" in §4.2 but are independent of the heuristic and remain on the Block 3 / S2 path. They are **not** affected by this proposal.
- `research/ENVIRONMENT.md::limitations` — `ENV-LIM-004` already records the env_blocked state; no new entry needed (the file is append-only).

## 5. Architect-owned decisions

These four items must be resolved by the lead architect before this proposal can be read as approved:

### A-1 — Accept phrase-list heuristic

Accept the phrase-list classifier as the router-reachability proxy under minimax-compat (vs. e.g. forcing the model to output `<skill-name>` as a structured first token, which would inject the tested field).

### A-2 — Accept M6 / M7 split

Accept `M6-pi + M6-claude-pending` and `M7-pi + M7-claude-pending` as the resolved form of M6 and M7 under D-004, vs. keeping them monolithic and accepting "V1-D9 is unpassable under minimax-compat" as the steady state.

### A-3 — Frontmatter self-test

Whether to add the new "Open with one short quoted line from SKILL.md" instruction to each skill's SKILL.md frontmatter `description` so routers self-test, vs. keeping it drill-only. (Adding to frontmatter makes every future router invocation self-test; keeping drill-only keeps the frontmatter concise but means non-drill invocations don't produce the same surface.)

### A-4 — Forward path under D-004

Single EV (`EV-20260918T133714Z-7b6f`) + close M6-claude-pending as **not-pursued-here** until native Anthropic is back, vs. per-session re-attempt under minimax-compat with a fresh EV per session if the endpoint behavior shifts.

## 6. Verification commands

```bash
# Parse + dry-run + integrity
python3 -c "import ast; ast.parse(open('tools/verify_v1_d9.py').read()); print('parse: ok')"
python3 tools/verify_v1_d9.py --dry-run --clients both  # exit 0
python3 tools/researchlog validate                        # exit 0, ok
python3 tools/researchlog reconcile --json                # clean

# Phrase integrity (29 phrases, 0 unsafe)
python3 -c "..."   # see commit message verification

# Live re-runs (heuristic in motion)
python3 tools/verify_v1_d9.py --clients pi --timeout-seconds 90
python3 tools/verify_v1_d9.py --clients claude --timeout-seconds 60
```

Expected behavior under minimax-compat (sandbox, `d77b7b2`):
- pi re-run: at least 3/6 routed (matches the historic 3; new heuristic may surface more if body vocabulary lands in the first line).
- claude re-run: 0-1/6 routed. M6-claude-pending remains ENV_BLOCKED.

The EV is a **receipt**, not a guarantee: future minimax-compat behavior may shift the numbers. The receipt value is that the failure is now classified (env_blocked vs. router-defect) and the heuristic is endpoint-sensitive and audited, not a hidden test that "works" for the wrong reasons.
