# Gate-3 verifier — manual & automated

Gate-3 sits between **research branch** and **architect approves promotion** in
the V1 promotion pipeline (see `skills/research-engineering/references/git-research-infrastructure.md`
§Promotion). Its job is to **independently verify a candidate mechanism's
evidence contract on a clean machine, in a clean checkout, without depending
on the lead session's git tree or sandbox state**.

This document covers three things:

1. **What Gate-3 is and is not** — the boundary against the architect
   approval step and against Integration Mode.
2. **Manual Gate-3 procedure** — the steps a human follows to run a
   Gate-3 verification on any machine that has Python 3.10+ and git.
3. **Automated Gate-3 procedure** — how to invoke the same checks via
   `workflow_dispatch` so GitHub Actions can run the suite on-demand.

The corresponding V1 acceptance #6 ("manual Gate-3 verifier 文档完整,可走通一个完整流程") requires this document plus one verified end-to-end run recorded in `tools/`; see §4 for the run record format.

## 1. Boundary

| Stage | Owner | What it does | What it does NOT do |
|---|---|---|---|
| **research branch** | agent | mutate probe / instrument / record | judge whether the mechanism is ready for promotion |
| **Gate-3** (this doc) | machine / CI | re-run the evidence contract on a fresh checkout and report | approve promotion; rewrite history; merge into `main` |
| **architect approves promotion** | architect | inspect Gate-3 report + mechanism claim and decide | re-run the evidence (Gate-3 is owned by the machine; architect is the human reviewer) |
| **Integration Mode** | agent | extract the minimal validated mechanism; cherry-pick / clean implementation | run further research-mode probes |

**Failure mode**: confusing Gate-3 with the architect approval is the most
common mistake. Gate-3 produces a *report*; architect approval produces a
*decision*. The two are not interchangeable.

## 2. Manual Gate-3 procedure

This is the form a human runs from a shell. The shape mirrors V0 §D1
(recovery drill): everything scripted, the script asserts its own
state, and the assertion is the entry in `tools/`.

```bash
# 0. Pick a clean working directory. Not your dev sandbox.
GATE3_DIR=/tmp/gate3-$(date +%Y%m%d-%H%M%S)
git clone <repo-url> "$GATE3_DIR"
cd "$GATE3_DIR"

# 1. Pin to the candidate commit / branch. Gate-3 is on an immutable input.
git checkout <commit-or-branch>

# 2. Pre-flight: state must be clean before the verifier mutates it.
python3 tools/researchlog validate    # must exit 0
python3 tools/researchlog reconcile --json | jq -e '.payload.clean == true'
# If either fails, the input is not Gate-3-ready. Investigate, do not patch.

# 3. Run the V0-V1 drill suite that exists today.
tests/main/build_bootstrap_case.sh /tmp/v0-fixture  # V0 D1-style
python3 tools/verify_v1_d9.py --dry-run --clients both
python3 tools/researchlog env rebaseline --reason "Gate-3 verifier"
python3 tools/researchlog env show | jq '.capability_map | length'  # ≥3

# 4. Record a Gate-3 receipt — a single evidence record that names this run.
python3 tools/researchlog record \
  --question "Does the candidate commit pass Gate-3 verification on <host>?" \
  --subject-type environment --subject-id "GATE3-<short-host-slug>" \
  --level E0 \
  --execution-status completed --research-outcome none --confidence high \
  --observation "Gate-3 manual run on host <host>, commit <commit>" \
  --measurement gate3.drill_v0_v1=passed \
  --measurement gate3.capability_map_entries=<n> \
  --measurement gate3.rebaseline_advanced=true \
  --invalidated-if 'gate3.input_commit != "<commit>"'

# 5. Inspect the report.
python3 tools/researchlog snapshot
git log --oneline -3
```

**Assertion contract** (steps 2 + 3 must all pass before step 4):

- `validate` exits 0 and reports `ok`.
- `reconcile` reports `payload.clean == true`.
- `verify_v1_d9.py --dry-run` exits 0 (drill script is parseable and
  finds the 6 skills).
- `env rebaseline` advances the fingerprint (write succeeds).
- `capability_map` holds ≥3 entries (V1-D7 acceptance line 2).
- `run_case.sh` / drill scripts exit 0 on their respective assertions.

**Failure surface**: any assertion above failing means Gate-3 **rejected**
the candidate. The receipt is still recorded (`research_outcome: none`),
but the branch is not promotable. The fix lives upstream; Gate-3 is
read-only here.

## 3. Automated Gate-3 procedure

GitHub Actions exposes `workflow_dispatch` for on-demand suites, which is
what `skills/research-engineering/references/git-research-infrastructure.md`
says Gate-3 should use: not per-commit CI, but on-demand. The repository
ships a workflow file at `.github/workflows/gate-3.yml` that the
lead session calls from `tools/researchlog checkpoint --gh-status <run-url>`
to record the verification link in the evidence trail.

```yaml
# .github/workflows/gate-3.yml (sketch)
name: Gate-3
on:
  workflow_dispatch:
    inputs:
      commit:
        description: "candidate commit to verify"
        required: true
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ inputs.commit }}
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Gate-3 verification
        run: |
          set -euo pipefail
          python3 tools/researchlog validate
          python3 tools/researchlog reconcile --json | jq -e '.payload.clean == true'
          python3 tools/verify_v1_d9.py --dry-run --clients both
          python3 tools/researchlog env rebaseline --reason "Gate-3 CI"
          echo "GATE3_OK"
```

The `GATE3_OK` marker at the end is what `tools/researchlog checkpoint
--gh-status` greps for to confirm the run passed.

### `--gh-status` flag on `checkpoint`

`tools/researchlog checkpoint` is the canonical "make a checkpoint commit
and tag" command (V1 §3.1 #20). With `--baseline-tag <name>` it tags the
checkpoint as a promotion-bound baseline; with `--gh-status <run-url>` it
records the Gate-3 GitHub Actions run URL on the baseline tag's annotation
so a reader can trace the baseline back to its verifier output.

The flag is **optional** — Gate-3 also runs manually without GitHub — and
its absence does not block promotion. It exists so that promotion-bound
baselines carry a verifiable external link when one is available.

```bash
# Manual Gate-3 + auto-attach the run URL (only meaningful under CI).
python3 tools/researchlog checkpoint \
  --baseline-tag baseline/v1-promotion-$(date +%Y%m%d) \
  --message "v1 promotion: capability_map + drill suite land" \
  --gh-status "$GATE3_RUN_URL"
```

If `--gh-status` is omitted, the checkpoint still succeeds; the tag
annotation simply has no URL line. The flag does **not** fail when GitHub
is unreachable — that is the V1 #5 acceptance contract ("`--gh-status`
不报错" means optional + non-blocking).

## 4. Run record format

A Gate-3 run leaves two artifacts on the repo:

1. An **evidence record** in `research/ledger/` with `subject.id` of the
   form `GATE3-<short-host-slug>`. The record carries `gate3.*` measurements
   so a later reader can grep `Gate-3` across the ledger.
2. Optionally, a **checkpoint tag** in Git with the form
   `baseline/<purpose>-<YYYYMMDD>` annotated with the GitHub run URL.

A clean run is then:

```bash
python3 tools/researchlog validate | grep -q '"ok"'
git for-each-ref --format='%(refname:short) %(contents:subject)' refs/tags/baseline | head
```

## 5. Failure modes this document does NOT cover

- **Physical / simulation observation**: Gate-3 verifies the *evidence
  contract*, not the *physical world*. A passing Gate-3 means the
  reproducible scaffolding is correct, not that the underlying
  mechanism's claim is true. The architect's approval step is the
  human reading the evidence.
- **GPU / cloud-credential runs**: out of scope here; refer to the
  reference infra doc §Promotion and the project's environment file
  for protected environments.
- **Cross-machine parity at the byte level**: Gate-3 reports parity
  at the *evidence level* (`--measurement gate3.<x>=...`), not at
  the level of full environment capture. Floating-point / hardware
  differences are surfaced as `gate3.fingerprint_changed=true` and
  left to the architect to evaluate.
