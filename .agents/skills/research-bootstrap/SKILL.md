---
name: research-bootstrap
description: Use only when a repository or applied-AI problem has no valid Research Engineering canonical state, when that state is unrecoverable, or when the lead architect explicitly asks for a clean research-state re-initialization. Inspects the problem, rules, assets, and environment; creates the minimum durable state needed to begin evidence-driven research. Not a planning skill.
---

# Research Bootstrap

Turn a zero-state repository or problem into the minimum valid Research Engineering state,
then hand off to `research-engineering`. The success condition is not a plan. It is that
**the first technical uncertainty now has a concrete, cheap, executable next action.**

`AGENTS.md` carries the precedence rules, the authority split, the invariants, and the
language policy. This skill does not restate them.

## When to run

- `research/ACTIVE.json` and the canonical state do not exist;
- the repository has been newly adopted into Research Engineering;
- existing state is declared invalid or unrecoverable by the architect;
- the architect explicitly asks for a clean re-initialization.

**Do not re-run bootstrap because a new session started.** If canonical state exists, the
job is to resume it, not to rebuild it. Re-initializing over a live state destroys the
record of what was already learned, and it is the failure this skill's narrow trigger list
exists to prevent.

If state exists but looks wrong, that is a reconciliation problem — say so, and do not
overwrite it with a fresh skeleton.

## Procedure

1. **Inspect the problem.** Rules, competition statement or requirements, `README`, docs,
   repository layout, SDK, data, baselines, and whatever execution surfaces already exist.
2. **Separate external facts from assumptions.** "The SDK exposes a controller
   interception point" and "the rubric scores recovery separately" are facts, checkable in
   the SDK and the rules. "The final system needs a trust estimator" is an assumption and
   is not allowed into `BOUNDARIES.md` as HARD.
3. **Identify HARD boundaries and unresolved rule ambiguities.** HARD means: competition
   rules, external data policy, official metric semantics, verified SDK coordinate and unit
   conventions, the physical safety envelope, judge credentials, spend caps. Ambiguities
   that cannot be resolved from the material go to the architect — this is one of the few
   cheap questions.
4. **Discover the research environment.** Compute and devices, simulator and SDK, replay
   and data, external services, and the obvious capability gaps. What can this lab actually
   measure, and at what evidence level? Limitations discovered here are recorded, not
   worked around silently.
5. **Map the unknowns.** Rank the highest-value technical uncertainties. Do not design the
   solution to them.
6. **Create the versioned canonical state:**

   ```bash
   python3 tools/researchlog init
   python3 tools/researchlog validate --json
   ```

   This creates `research/ACTIVE.json`, `CURRENT.md`, `ARCHITECT.md`, `BOUNDARIES.md`,
   `ENVIRONMENT.md`, `FINDINGS.md`, the evidence ledger, and the run directories. The
   skeleton is copied whole; the tool owns the fenced blocks inside each file and the agent
   never hand-edits that JSON.

7. **Record only the E0 evidence that is actually justified.** Reading the rules and
   inspecting the SDK produce E0 evidence and legitimately belong in the ledger. A design
   intuition does not; it belongs in `CURRENT.md` as provisional.

   ```bash
   python3 tools/researchlog record --help
   ```

8. **Choose the first executable target.** The cheapest valid evidence that materially
   reduces the highest-value uncertainty. Record it in `ACTIVE.next_action`.
9. **Hand off.** Leave `ACTIVE.status` at `idle` or `planning_evidence` with a clear next
   empirical action, and continue in `research-engineering`.

## Verify premises that change the research direction

Before declaring supplied data absent/empty or an environment unusable, corroborate
the exact scope with a second, direct observation. For a supplied filesystem path,
inspect whether it is a symlink, resolve its target, and list/open the target within
the authorized input scope. A non-following `find`, a depth limit, ignored files, a
permission error, or an unsuccessful command is not proof of absence. Distinguish
missing target, inaccessible target, empty directory, and not yet inspected. Do not
silently suppress errors in a check used to justify a research constraint.

Retain the path, check result and scope in evidence before using an absence claim
to abandon real inputs for synthetic work. This does not require reading every
large asset; an actual directory listing and a representative file can disprove
"empty" cheaply. Do not generalize a host limitation to all evidence paths.

If TASK or an architect instruction requires investigation followed by architecture
discussion, preserve that decision gate. Bootstrap completion is not architecture
approval. Continue the authorized investigation, then report supported alternatives,
uncertainties and a recommendation before crossing that gate; routine probe choices
remain autonomous. A run budget ending is not proof the investigation is complete.

## Worked shape — embodied safety competition

Day 0: a competition statement, a simulation SDK, a baseline, and no system.

```
inspect    rubric scores detection, localization, blocking, degradation, recovery,
           and task completion as separate dimensions
           SDK confirms camera / LiDAR / IMU timestamps, a controller interception
           point, and a baseline navigation interface
unknowns   U1 does a general attack-agnostic integrity signal come from sensor-specific
              anomaly, or from temporal / cross-modal consistency?
           U2 which layer should arbitrate safety?
           U3 how does the system return to a trusted state after an untrusted one?
           U4 can task/language attacks and physical sensor attacks share one trust
              abstraction?
CURRENT    states explicitly: no complete safety system exists; architecture is NOT frozen
first      the cheapest question is U1 restricted to LiDAR deletion, because data exists
action     replay raw LiDAR → angular/occupancy temporal residual → plot and statistics
```

That first action is an E1 probe of a few dozen lines. The architecture document that
would normally be written here is not written, because the answer to U1 changes it.

## Do not

- generate a large task backlog, a milestone plan, or a phase breakdown;
- freeze a speculative final architecture, or write the full design document;
- build broad test suites before they protect research validity;
- implement the full system during bootstrap;
- promote a guessed requirement into a HARD boundary;
- record an assumption as an established finding;
- ask the architect to select routine algorithms, libraries, or thresholds;
- produce a heavy visible report. The architect gets a short Chinese summary of what was
  found — facts, boundaries, and the first research question — not a planning document.

## Output and handoff

Use AGENTS.md's plain-language reporting contract. Tell the architect what inputs
and capabilities actually exist, what is still unknown, and the first useful check.
Explain the consequence of a missing capability rather than reporting only its
status code. Do not present initialization or document counts as research success.

Canonical state is English. The visible bootstrap summary to the architect is Chinese,
keeping technical terms, SDK and library names, and IDs in their original English form,
and it states the first technical uncertainty and the first planned probe.

Bootstrap is complete when:

- the canonical state exists and `researchlog validate` passes;
- the environment's known capabilities and limitations are recorded with their status;
- the initial uncertainties are ranked and written into `CURRENT.md`;
- the first evidence-producing action is written into `ACTIVE.next_action`;
- nothing in the state asserts a conclusion that no evidence supports.

Then continue with `research-engineering`, which owns the loop from there.
