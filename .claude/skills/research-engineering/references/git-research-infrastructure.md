# Git Research Infrastructure

Load before committing, branching, creating a worktree, tagging, or promoting.

Git is the normative executable-state layer, not bookkeeping:

```
Evidence  = what was learned
Git       = the exact executable state that produced it
ACTIVE    = what is being attempted right now
```

Each answers a question the other two cannot. When someone asks "how did we know this",
the answer is an `EV-*`; when they ask "what exactly was running", it is a commit plus a
diff hash.

GitHub is an optional remote research plane. Everything here must work without it.

## Research transactions

Commit at meaningful-evidence and session-checkpoint boundaries. Not on every edit, not
once at the end of the day.

```
research question → intervention → run → observe → evidence obtained
→ transaction boundary → commit + evidence reference
```

```
research(EXP-0142): add motion-aware recovery release

Hypothesis: H-037
Evidence: EV-0821
Outcome: promising
Level: E2
```

A failed-but-informative experiment commits the same way with `Outcome: informative_failure`.
Whether it reaches `main` is a promotion decision, not a commit decision.

## Provenance contract

Every E1+ evidence record carries as much of this as the situation allows:

```
HEAD commit          parent / base commit     dirty flag
diff hash            branch / worktree        config / model / data / environment hash
```

Evidence produced from a dirty tree must be reconstructible from `base_commit` +
`diff_sha256` + the expected touched files. High-value or cross-session experiments get a
checkpoint commit instead.

### Ordering — do not create a self-referential transaction

An evidence record must never try to name the commit that contains it. That hash does not
exist yet, and ordering the two writes so it does is a trap.

1. `EXP-ID` is assigned before the experiment. When a two-way index is wanted, `EV-ID` may
   also be pre-allocated — and it must be collision-resistant.
2. `code_state` points at the state that **produced** the evidence: a commit SHA for a
   clean run, `base_commit + diff_sha256` for a dirty one.
3. The Git commit may reference `EXP-ID` / `EV-ID` in its message or footer.
4. The ledger records `code_state` and does not record the commit that later adds the
   record. "Which commit landed this record?" is a Git history question.
5. If a commit succeeds and the evidence append is interrupted, resume reconstructs the
   record from the `EXP` id, the run result, and the commit footer — and does not
   reclassify it as a scientific failure.

`reconcile` reports `SELF_REFERENTIAL_COMMIT` when this ordering has been violated, which
turns what used to be a manual review item into one command.

## Checkpoints

`git stash` is fine for a person mid-thought. It is not the session-continuity mechanism —
an anonymous stash does not say what it was for or what remains to be done.

```
checkpoint(EXP-0142): recovery replay partially complete
```

Record `checkpoint_commit`, `completed_cases`, and `pending_cases` in `ACTIVE.json`. The
research branch's history does not need to be production-clean; recoverability outranks
tidiness. Integration Mode is where history gets squashed.

## Branches and worktrees

| Situation | Granularity |
|---|---|
| micro mutation | the current research branch |
| independent or risky mechanism | `research/<topic>` |
| architecture alternative, or parallel write-heavy work | `research/<architecture-family>` + worktree |

Do not produce one branch per hypothesis. `research/H001…H999` is a branch explosion that
makes `git log` useless and merges nothing. One branch holds many `EXP-*` from the same
direction.

Worktree rules:

- Write-heavy parallel branches do not share a working tree.
- Read-heavy exploration does not need a worktree.
- A worktree worker does not rewrite the global `CURRENT` / `ARCHITECT` / `BOUNDARIES`.
- Workers emit immutable evidence and artifacts; the lead research session synthesizes.
- A rejected branch may be deleted. Its evidence is not deleted.

Keep `CURRENT.md`, `ARCHITECT.md`, `BOUNDARIES.md`, and `ENVIRONMENT.md` single-writer.

## Promotion

The object of promotion is the validated mechanism, not the branch.

```
research branch
→ Gate-3
→ architect approves promotion
→ Integration Mode
→ extract the minimal validated mechanism
→ cherry-pick / clean implementation
→ main
→ annotated baseline tag
```

```
baseline/e3-recovery-v2
baseline/system-v0.4
submission/2026-09-21-004
```

An official submission binds an immutable commit or tag plus a config / model / data
manifest, and its external score comes back as E5 evidence. "We submitted a zip and we are
not sure which version it was" is a state this protocol exists to prevent.

## GitHub, if present

Optional, and never canonical. Local research state plus commits plus evidence records are
the source of truth; the remote is a derived coordination plane.

- **Push** at substantial checkpoints, important branches, and promoted baselines. Not on
  every micro mutation.
- **Actions** are for expensive or independent verification: on-demand Gate-3 suites,
  clean cross-machine benchmarks, protected Gate-4 verifiers, GPU runners, submission
  adapters. Prefer `workflow_dispatch` over a per-commit trigger. Recreating per-patch CI
  inside Research Mode undoes the entire point of the mode.
- **Environments** with protection rules are how "do not submit on your own" stops being a
  prompt instruction and becomes an out-of-band control. Put `official-judge`, expensive
  cloud GPU, and physical-robot credentials behind reviewer approval; the agent recommends
  the call and does not hold the credential.
- **PRs** only at promotion, as the review boundary between a research artifact and a
  stable component. **Issues** only for long-lived items a human must track: architecture
  challenges, capability gaps, rule ambiguities, external blockers. **Releases** only for
  promoted baselines, submissions, and reproducible milestones.

If GitHub state and local state disagree, local wins and the difference is reported.

## Large artifacts

Models, datasets, trajectories, and video do not go into ordinary Git. Git holds the
pointer:

```json
{"artifact": {"uri": "nas://lab/runs/EXP-0142/trace.jsonl",
              "sha256": "…", "size": 812934112, "producer": "EXP-0142"}}
```

LFS, DVC, and object storage are all fine and none of them is a V0 dependency.

## Evaluator isolation

Protection scales with maturity. At E0/E1 there is no evaluator, and what needs protecting
is external truth: rules, SDK semantics, hidden labels.

| Trust tier | Mechanism |
|---|---|
| low | `BOUNDARIES.md` entry plus a hash — prevents accidental edits only |
| medium | sibling evaluator checkout, a verify command a human owns |
| high | local container or a separate OS user; evaluator and holdout read-only |
| stronger | protected remote verifier, architect-controlled holdout |
| strongest | official judge credentials invisible to the agent |

The distinction that matters is between a prompt-level "please do not modify the
evaluator" and an actual out-of-band control. Only the second one is protection. Do not
let a hook-based deterrent get described as if it were the second.

Reward hacking paths to keep closed: the candidate reading judge-only labels; the agent
editing the metric so the system "improves"; synthetic red-team scenarios quietly becoming
a training set; a leaderboard treated as an unlimited tuning signal; a local proxy drifting
away from real behavior. The dev-versus-held-out verifier split is the useful pattern —
optimize freely against the development artifact while the judge is injected
independently.

## Gitignore

`runs/` in a `.gitignore` without a leading slash matches at any depth, and Git cannot
re-include a file whose parent directory is excluded — so a negation for
`research/runs/**/manifest.json` does not work, silently. The failure mode is quiet and
severe: manifests never enter the repository, cross-machine recovery loses run identity,
and orphan detection misreports on every machine but the one that produced the run.

Anchor root patterns (`/runs/`, `/data/`, `/logs/`) and ignore heavy outputs individually.
`reconcile` reports `RUNS_DIR_IGNORED_BY_GITIGNORE` when this has regressed; verify with:

```bash
git check-ignore -v -- research/runs/EXP-1/manifest.json   # expect exit 1
```
