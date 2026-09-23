# Supervised parallel research pilot

Use inside an authorized block when two independent questions justify parallel work
and the client offers permitted agent delegation. Do not manufacture two tasks to fill
slots. Serial work remains appropriate for shared dependencies, cheap probes or scarce
compute. Routes persist; workers are temporary, narrowly scoped executors.

## Allocation and authority

The lead explains why the selected questions matter to the application: complementary
capabilities, competing mechanisms, or an independent challenge to a consequential claim.
Keep useful unselected routes with restart conditions. The architect chooses direction
and boundaries; routine probe selection and technical comparison belong to the lead.

Use at most two outstanding workers in this pilot. Their combined probes/compute must
fit the parent's remaining budget; do not give each worker the whole parent budget.
Record the originating architect signal and block in each packet. No implicit cloud
spend, paid research service, promotion, new block, nested delegation, or background
continuation after a pause. Use project model configuration, never an invented model tier.

The lead is the only writer of canonical state, packets, evidence and findings. Workers
return artifacts from isolated workspaces, not edits to the lead's CURRENT/ACTIVE/ledger.
Global ACTIVE remains the lead execution pointer; packet state describes delegation,
not a second research truth or an assertion that a process is alive.

## Dispatch and return

1. Choose a cheap discriminating question per worker and prepare an isolated workspace.
   For code changes use the available worktree skill and explicit source revision;
   for inspection/probes a separate scratch directory with pinned inputs can suffice.
   Do not clone uncommitted changes invisibly or share a writable application tree.
2. Prepare a JSON contract with `delegate prepare --id W-... --file CONTRACT --reason ...`.
   Required fields: `route_id`, `question`, `application_value`, `authority` (signal/source
   and permitted actions), `block_id`, `deadline` (UTC/offset), absolute `workspace`,
   `inputs` (relative files), `allowed_writes` (relative files/directories),
   `max_probe_executions`, `stop_conditions`, `return_expectation`.
   The tool fingerprints supplied inputs, not every external dependency. Pin additional
   source/data/config identity explicitly where the conclusion depends on it.
3. Dispatch via the client's native agent facility, providing the full saved contract,
   worker directory, task ID, input hashes, return format, and the constraints above.
   Workers must check input hashes before using them, record actual inputs/commands,
   and save raw outputs plus limitations. They must not revert others' work.
   Immediately bind the returned client/session/task identity with
   `delegate dispatch --id W-... --worker-ref ... --reason ...`.
   Preparation precedes launch; a crash between launch and identity binding is ambiguous,
   not permission to relaunch. Inspect client history first. The deadline and budget are
   agent/client responsibilities, not enforced by this bookkeeping tool.
   On a meaningful worker update, persist `delegate progress --id W-... --reason ...`.
   Record the observed progress, obstacle or changed expectation, not a fabricated
   heartbeat. The dashboard shows its timestamp and explanation while other work runs.
4. Worker writes a result JSON in its own directory: `packet_id`, `execution_status`
   (`completed`, `ENV_BLOCKED`, `INFRA_FAILED`, `EVIDENCE_INVALID`, `RESOURCE_EXCEEDED`),
   `input_sha256` (actual verified input mapping), `summary`, `limitations`, `next_probe`,
   and `artifacts` (workspace-relative raw output/report files).
   Lead imports it with `delegate collect --id W-... --file RESULT --reason ...`.
   Collection fingerprints returned artifacts; it neither confirms a hypothesis nor
   writes EV. Keep those paths available through review and checkpoint/archival.
5. Lead checks original outputs, input identity, controls, causal validity and whether
   observations answer the question. Record evidence with existing record tooling,
   citing the packet and original worker artifacts/provenance. Do not attribute worker
   code execution to the lead's code snapshot: preserve the worker manifest/source
   identity; if existing EV cannot honestly represent it, use an inspection-level
   record and leave the execution claim unpromoted pending a provenance adapter.
   Use `delegate review --id W-... --outcome accepted --evidence EV-... --reason ...`
   or `--outcome needs_followup`. Accepted means the receipt was reviewed and indexed,
   NOT scientific support or promotion. Environment failures retain their own status.
6. Compare results, update existing FINDINGS/routes, and report application impact and
   the next recommendation. Conflicts require a discriminating check, not a majority
   vote. Follow-up gets a new packet ID; never overwrite returned work or retry invisibly.

## Pause, resume and observation

`delegate list`, dashboard, validate and reconcile expose saved packets read-only.
Unfinished packets must be accounted for before changing route lifecycle or declaring
handoff ready. Fresh sessions inspect saved worker identity and artifacts first; never
assume dispatched means alive/dead. Unknown survival after client exit prevents a
claim of complete execution handoff. Returned work awaits review, not another run.

Default research-pause stops issuing work and closes/collects existing work if feasible
within authority. It does not kill jobs. Actual interruption uses the client's controls
only with appropriate authority; after observing stopped/never-started state, persist
`delegate cancel --id W-... --stop-confirmation ... --reason ...`. The command itself
does not stop a process. Architect-away continuation needs explicit scope/budget.

This pilot is a client-native supervised protocol plus durable tooling, not an autonomous
daemon, sandbox, authentication layer, automatic retry or multi-client scheduler. A
worker can violate instructions when given filesystem access; isolation here prevents
accidental overlap, not malicious access. Mutations serialize using a directory lock;
after an interrupted writer, inspect processes and packets before manually removing
the stale lock. Read-only recovery never removes it.
