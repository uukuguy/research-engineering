# Session Continuity

Load on a new session, when `ACTIVE.status != idle`, or when a run manifest is `running`
with no `result.json`.

The target is **semantic and operational lossless recovery**: a new client session, given
only the repository, reconstructs every decision-relevant piece of the research and picks
the action that continues the last one. Chain-of-thought is not preserved and is not the
goal. Session context is disposable; the repository is durable.

## What must survive

```
research intent + architect steering + boundaries + environment capability
current uncertainty + live hypotheses + active experiment intent + exact code state
execution progress + observed evidence + unresolved interpretation + next action
```

## ACTIVE.json — the session continuation capsule

`CURRENT.md` answers "where has the research got to". `ACTIVE.json` answers "what is
happening right now". It is short, mechanical, rewritten often, and never carries long
reasoning.

```json
{
  "schema_version": "1.0",
  "session_epoch": "SE-20260910-014",
  "status": "running",
  "research_question": "Does motion-aware release reduce recovery oscillation without delaying safe stop?",
  "subject": {"type": "component", "id": "recovery-policy"},
  "hypothesis_ids": ["H-037", "H-039"],
  "chosen_hypothesis": "H-037",
  "experiment_id": "EXP-0142",
  "intent": "Add motion-aware recovery release; keep detection and navigation unchanged.",
  "expected_evidence": {
    "supports_if": "oscillation decreases while attack-stop latency is unchanged",
    "weakens_if": "oscillation persists despite correct release timing"
  },
  "block": {"id": "RB-024", "objective": "Resolve recovery oscillation",
            "max_evidence_iterations": 6, "max_wall_clock_minutes": 180,
            "max_tokens": 400000, "completed_evidence_iterations": 2,
            "belief_delta": null,
            "stop_conditions": ["question_resolved", "hard_boundary",
                                "major_architecture_decision", "no_valid_evidence_path"]},
  "git": {"branch": "research/recovery", "base_commit": "83ab21c",
          "checkpoint_commit": null, "dirty_expected": true,
          "expected_touched_files": ["src/safety/recovery.py",
                                     "research_probes/recovery/replay.py"]},
  "execution": {"status": "partial", "completed_cases": ["case17"],
                "pending_cases": ["case21", "case31", "case37"],
                "run_manifest": "research/runs/EXP-0142/manifest.json"},
  "current_observation": "case17 oscillation reduced; insufficient for a conclusion",
  "next_action": "Run remaining replay cases before modifying the mechanism again.",
  "updated_at": "2026-09-10T19:28:41+08:00"
}
```

`status` moves through `idle / planning_evidence / implementing / ready_to_run / running /
reviewing / blocked / interrupted`. `execution.status` is the separate, finer axis carrying
the non-scientific outcomes — see `evidence-model.md § The two axes`. A disagreement like
`execution.status: env_unsupported` with `ACTIVE.status: reviewing` is worth reconciling.
The block fields are documented in the main `SKILL.md § Block contract`, including why
`max_tokens` is telemetry and why `completed_evidence_iterations` is derived.

## Write-ahead ordering

A graceful shutdown is not guaranteed. Context exhaustion, `Ctrl-C`, a terminal crash, and
a process kill all skip the "write a summary at the end" step. So intent is written before
the action, not after:
choose experiment
→ write ACTIVE intent
→ modify code
→ ACTIVE = ready_to_run
→ create run manifest
→ ACTIVE = running
→ execute
→ append evidence
→ ACTIVE = reviewing
→ update CURRENT / FINDINGS if justified
→ ACTIVE = idle, or next experiment
```

Every interruption point is then reconstructible. A summary written at the end is worth
nothing at the moment it is most needed.

## Run manifests

A meaningful experiment gets an identity before it runs:

```
research/runs/EXP-0142/
├── manifest.json
├── stdout.log
├── stderr.log
├── artifacts/
└── result.json          # only after completion
```

```json
{
  "schema_version": "1.0",
  "experiment_id": "EXP-0142",
  "question": "...",
  "hypothesis_ids": ["H-037"],
  "subject": {"type": "component", "id": "recovery-policy"},
  "environment": {"id": "ENV-local-v1", "fingerprint": "sha256:41d0...", "comparability": "COMPATIBLE"},
  "code_state": {"branch": "research/recovery", "commit": null, "base_commit": "83ab21c",
                 "dirty": true, "diff_sha256": "9f1c..."},
  "inputs": {"replay_suite": "recovery-12@sha256:...", "config": "configs/H037.yaml@sha256:..."},
  "command": ["python3", "research_probes/recovery/replay.py", "--cases", "recovery-12"],
  "status": "running",
  "execution": {"host": "workstation-a", "launcher": "local_process",
                "pid_or_job_id": "48123", "pid_started_at": "...", "started_at": "...",
                "heartbeat_or_last_observed_at": "...", "stdout": "stdout.log",
                "stderr": "stderr.log", "expected_outputs": ["artifacts/metrics.json"]}
}
```

`status: running` with no `result.json` means interrupted or still in flight. It never
means the mechanism failed.

`inputs` gives every mutable input a stable identity. A comparison that changes the
dataset, the model checkpoint, the prompt, and the config at once cannot attribute its
delta to the algorithm, and the manifest is where that becomes visible rather than
remembered.

## Long-running runs

A training job or a long simulation outlives sessions. Rotation is not permission to kill
it or to start it twice.

On resume, before anything else: read the manifest's `execution` block, check liveness with
`researchlog job EXP-0142` for a `local_process` launcher, then decide `attach / observe`,
`finalize`, `mark interrupted`, or `rerun`.

`pid_or_job_id` is meaningful only on the same host, and `pid_started_at` exists so a
recycled PID is not mistaken for a live run. `job` never kills anything — PID reuse makes
that dangerous — it only reports and suggests a command. For Slurm, tmux, Docker, or a
remote runner, `launcher` names the mechanism and liveness is reported as **unknown**
rather than guessed. Those launchers are not part of the common core; they are an
extension point.

Never start a second copy of an expensive run because the session that started it is gone.

## Orphan runs

An orphan is a run that happened but has no evidence record: a manifest and artifacts on
disk, an `EXP-*` that no `EV-*` references.

`reconcile` detects these and reports them. **That is the whole of what the tool can do
here, and it is worth being precise about the limit**: enforcement lives in this resume
protocol, not in the detector. `researchlog` cannot know whether an unrecorded run ought
to have produced evidence; it makes the detection one command instead of an archaeology
project. The rule that actually prevents orphans is the one you are following right now —
reconcile before starting new work.

And `reconcile` never repairs them. There is no `--fix-orphans` and there will not be:
backfilling an evidence record means inventing its observations, its outcome, and its
belief delta. A tool that generates those is inventing evidence, which is a worse failure
than a lost record. The supported path is a template:

```bash
python3 tools/researchlog record --from-orphan EXP-0142
```

This prefills the mechanical fields from the manifest — question, subject,
`hypothesis_ids`, `code_state`, `artifacts` — and reads the scientific fields from stdin.
Missing scientific content exits 2. The tool hands you a form; it does not fill in the
science.

## Resume protocol

Already normative in the main `SKILL.md`, and the reconciliation table there is the
authoritative version. The rules that are easy to skip:

- If `ACTIVE` is not `idle`, reconstruct that experiment before starting a new one.
- Read only the evidence that `ACTIVE` / `CURRENT` / `FINDINGS` reference. Replaying the
  whole ledger is what the compression hierarchy exists to avoid.
- If `ACTIVE` and Git disagree, enter `RECOVERY_RECONCILIATION`. Do not reset, do not
  `checkout` over the working tree, do not start a fresh experiment.

```bash
python3 tools/researchlog reconcile --json
```

## Context compression hierarchy

```
raw artifacts / traces  →  immutable Evidence  →  FINDINGS  →  CURRENT  →  ACTIVE
       GB–TB                 many records        durable     research    execution
                                                  knowledge   model       pointer
```

A new session reads from the right and descends only on conflict or during diagnosis.
`FINDINGS.md` is context compression, not a log. `CURRENT.md` holds objective, maturity,
working pieces, provisional system shape, uncertainties, active research, next action —
and nothing that belongs in a timeline.

## Rotation

Treat the session as disposable compute, not as something to stretch to its limit. Rotate
at a semantic boundary: an iteration just closed cleanly; a major direction just changed;
a retrospective just rewrote the working model; raw logs have visibly polluted the
context; or you notice yourself re-deriving context, confusing old hypotheses, or citing
the wrong `EV-*`.

Rotation does not need a handoff document. Update `ACTIVE`, `CURRENT`, and the evidence
ledger; make a checkpoint commit if meaningful work is dirty. See
`git-research-infrastructure.md § Checkpoints`.

## Interrupted execution

`interrupted` carries a reason — `session_boundary`, `client_restart`, `process_signal`,
`machine_shutdown`, `timeout`, or `unknown`. It never updates scientific belief, and
neither do `infra_failed`, `env_blocked`, `env_unsupported`, `resource_exceeded`, or
`invalid`.

## Schema versioning and crash-safe writes

Every canonical machine-readable artifact declares `schema_version`. The compatibility
rule is asymmetric on purpose:

| Class | Read | Write |
|---|---|---|
| `CURRENT` | yes | yes |
| `OLDER` (minor) | yes | yes, unknown fields preserved |
| `OLDER` (major) | yes | only with a registered migration, else refused |
| `NEWER` | yes, with a warning | **refused**, file left byte-identical |
| `INVALID` | no | no |

`SCHEMA_NEWER_REFUSED` is not an obstacle to route around by editing the file. A document
written by a newer tool may contain fields whose meaning you would silently destroy.

Canonical writes are crash-safe: write a temp file, flush, `fsync`, validate syntax and
required fields, atomic replace, `fsync` the directory. You do not implement this — you
use the mutation subcommand, which does. Recovery order when the canonical file is
unusable is `canonical → .tmp → git`, and the source is always reported, never silently
chosen. If all three fail, the state is `RECOVERY_REQUIRED` and that is a report to the
architect, not a `JSONDecodeError` to work around.

## The acceptance test

The only real test of this file is the amnesia test: run session A to `ACTIVE = running`,
kill the client mid-experiment, start session B with no access to the old conversation, and
check that it finds the right branch and HEAD, understands the dirty diff's intent, knows
the completed and pending cases, preserves the architect signals and environment
limitations, does not restart the run that already exists, and picks the same next action A
would have. Then run it in the other direction, Codex to Claude Code.

If B has to guess, something above was left in the chat instead of the repository.
