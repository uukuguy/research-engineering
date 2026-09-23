---
name: research-pause
description: Close a research session for a deliberate pause, exit, or transfer to a fresh client. Persist decision-relevant state, verify recovery prerequisites, and report whether handoff is ready. Does not start experiments or authorize continued research.
---

# Research Pause

Provide an explicit session-local closing operation. The user invokes this skill
alone; do not require a supplementary checklist or shell commands from them.
Continuous write-ahead state remains the protection against unexpected interruption.
This skill adds a deliberate close; the next session must still reconcile independently.

## Scope and tools

Use the project's declared state directory and local CLI: installed projects may
use `.research/` and `uv run python tools/re`; this development repository uses
`research/` and `python3 tools/researchlog`. Do not initialize missing state.
Read the local research-engineering references `session-continuity.md` and
`git-research-infrastructure.md` before performing the close. Reuse their contents
if already read in this session and unchanged; do not reload them merely for ceremony.

Pause authorizes recording existing work and a scoped local checkpoint. It does not
authorize new experiments, new research conclusions, external spend, pushes,
architecture approval, termination of running jobs, or release of architect constraints.
Never repair uncertainty by inventing observations or editing immutable evidence.

## Close and verify

### Normal path and exception path

The normal path checks this session's changes, not the entire research history.
Obtain fresh Git status/diff, ACTIVE and relevant manifest status. Reuse already-read
TASK, canonical files, referenced evidence and protocol only when file identity is
unchanged and their relevant contents are still available in context. Read changed or
previously unverified files; do not re-open every completed run or rehash a large dataset
when no new claim depends on doing so. Batch independent reads and CLI checks.

Escalate to a targeted deeper check for an unexpected diff, missing artifact, uncertain
job liveness, inconsistent state, or unavailable prior context. Tell the user what needs
checking and why before expanding. Do not turn pause into a new research investigation.
If the close exceeds about a minute, report the actual remaining work; this is an
interaction target, not a deadline that permits skipping checks or declaring success.

1. Establish the relevant contents of ACTIVE, CURRENT, ARCHITECT, BOUNDARIES,
   ENVIRONMENT, FINDINGS and TASK using the reuse rules above, plus fresh Git and
   active/unfinished run state. Run `validate --json` and `reconcile --json` once for
   the final unchanged state, or before and after if repairs are required. They check
   implemented invariants, not semantic completeness. Do not repeat them without an
   intervening change or an unresolved finding.
2. Compare the session's decision-relevant changes with those files: results and their
   limits, withdrawn claims, architect instructions, current implementation, unresolved
   interpretation, completed and pending cases, and the next permitted action. Persist
   omissions using the tool's mutation verbs; ARCHITECT signals preserve source_text.
   Check CURRENT/ENVIRONMENT identity and effective availability statements explicitly.
   Check experiment_id, execution.run_manifest and execution.status against the same
   actual run even when ACTIVE is idle. Block-wide completion does not overwrite an
   older interrupted run's status; correct the pointer, not the historical manifest.
   For a newly reusable method, retain its entrypoint, required inputs/dependencies,
   evidence/output location and limits in working_pieces or capability/harness entries.
   Do not preserve only the remaining blocker and lose the method that already works.
   Use existing results; pause does not authorize rerunning it to strengthen the receipt.
   If the prior conversation is unavailable, do not claim to have audited it: check
   repository consistency and declare that limitation. Missing observations or an
   ambiguous correction block readiness; do not fabricate a resolution.
3. For unfinished runs, inspect job liveness and saved outputs. Query `delegate list`
   when `delegations/` exists,
   and read `parallel-research.md` for their close/recovery rules. Account for every
   prepared, dispatched or returned-but-unreviewed packet before claiming readiness;
   unknown worker survival is not an idle system. Do not issue replacement work.
   A detached job may
   continue only with a recorded identity, progress, output locations and observe/attach
   action. If survival after client exit is unknown, report handoff incomplete. Never
   start a duplicate or relabel unfinished work as completed merely to obtain idle.
   Preserve registered routes' resume points, evidence links, deferred reasons and wake
   conditions. Session pause does not reject routes or require parking the current focus.
   Persist already-decided route updates with the routes tool; do not generate a new
   research agenda merely to close the session.
4. Save next_action with the pause reason, next permitted step and any approval still
   required. For an architect-led interactive restart, the first step is read-only
   recovery and an application/architecture briefing, then wait for a new explicit
   architect instruction. Record the suggested scientific step separately as conditional
   on that instruction, not as automatic continuation. Apply this distinction to both
   ACTIVE.next_action and CURRENT.next_empirical_action when updating them. Neither a
   launcher message nor an inactive old constraint supplies fresh authorization.
   Update CURRENT when its research meaning changed. Leave an in-flight
   execution pointer intact. When no run is active, idle is appropriate; pause does not
   itself close a research block or justify a belief_delta.
5. Inspect `checkpoint --dry-run --json` before committing. Default screening may
   exclude logs and run artifacts. Verify each recovery-critical artifact is either
   versioned or durably stored at a recorded, accessible location with an identity.
   Distinguish record recovery from executable experiment recovery (see below).
   Include only identified research changes, never unrelated
   user work or `--all-expected` as a shortcut. If meaningful changes exist, checkpoint
   with explicit scoped paths after examining the selected files.
   Explicit `--paths` is exclusive and already includes untracked files within that
   scope; do not combine it with `--include-untracked` or `--all-expected`.
6. Re-read changed state and inspect final Git status/diff and relevant artifact
   accessibility. If any state or checkpoint changed after the last checks, run
   `validate --json` and `reconcile --json` on the final state. A post-checkpoint ACTIVE stamp
   can be an expected local change, but verify its exact diff and disclose it; do not
   chase an impossible self-referencing clean commit or whitelist arbitrary dirty files.
   Do not emit readiness on command failure, unresolved relevant findings, semantic
   contradictions, missing evidence or unaccounted recovery-critical work.

Before the final receipt, run `active --refresh-counts` and then
`reconcile --handoff --json` after the scoped checkpoint. Refreshing counts neither
closes the block nor changes belief. The handoff check requires a CURRENT reference
to the latest block evidence and local checkpoints for canonical records, the active
run and its identifiable script, and project-local evidence artifacts. It does not
prove their scientific validity or cross-machine portability. For large local artifacts,
use a verified external durable location with identity instead of forcing them into Git.
Keep code/output version ambiguity explicit; never choose a VALID_SURROGATE verdict
merely to satisfy the record schema. Read the final saved output before summarizing it.
Do not infer remaining wall-clock budget from an unused iteration slot. Account for
the actual authorized research interval; if exhausted or unknown, state that and wait
for renewed authorization. Pausing/clearing does not replenish it.

## Recovery scope is not one boolean

State separately what is saved and what can run:

- **Research records**: decision-relevant state, code and evidence have verified
  recovery locations. A local Git commit is a checkpoint, not an off-machine backup.
- **Same-workspace continuation**: required local artifacts and external paths are
  available here; report any known environment or access blockers separately.
- **Another checkout or machine**: do not claim executable portability from Git
  tracking alone. Inspect required input references and symlink targets, model/assets,
  ignored files, environment requirements and access dependencies. An absolute symlink
  tracks the link, not its target contents. Unless restoration and execution prerequisites
  were actually verified, say that records are versioned but cross-machine execution is
  unverified, and name the missing dependencies. No large copy or environment setup is
  authorized merely to strengthen a pause receipt.

Unknown experiment portability does not block a truthful same-workspace record handoff;
missing decision-relevant evidence does. Never erase a real environment limitation or
invent an environment ID just to make two state fields agree.

## Closing receipt

Return a short Chinese receipt, with no mandatory YAML or second handoff document:

- **可退出** or **交接未完成**, with separate record-recovery and experiment-recovery
  scope. Readiness means checked recovery prerequisites, not a mathematical
  guarantee of complete memory, successful future recovery, or correct research.
- What was saved, where the checkpoint is, and any expected residual diff.
- Any running job or unresolved issue and its concrete consequence.
- Next session: first recover read-only and brief the architect, then wait for explicit
  direction. Any proposed experiment is conditional, not authorized by this receipt.
  The user may stay in the client: clear the chat, then invoke research-resume alone.

If not ready, say exactly what remains and whether the agent can resolve it within
scope. Do not tell the user that they cannot physically close the client; explain what
would be at risk. Do not automatically continue research after issuing the receipt.
