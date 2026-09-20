# RE workspace operator entry points.
#
# Every target calls the RE protocol toolchain under
# PYTHONPATH so the cwd does not need to have its own copy of the
# researchlog package. The protocol source lives in
#  ~/sandbox/agentic-2026/research-engineering/tools/  and that is the
# single source of truth the cwd consumes.
#
# All reads (`state`, `references`, `telemetry`, `reconcile`, `ledger`,
# `watch`) operate on the `.research/` state in cwd. Writes
# (`record`, `manifest`, `run`, `active`) append to it.

RE_PROTOCOL := __RE_PROTOCOL_ROOT__
export PYTHONPATH := $(RE_PROTOCOL)/tools

ROOT := $(shell pwd)
RL  := python3 -m researchlog

.PHONY: help state ledger ledger-details references references-list \
        telemetry kpi reconcile sync-refs watch ready clean \
        session-spawn session-spawn-codex install-local

# Aggregate read-out: ACTIVE + ledger count + reference count + KPI, no JSON
# parsing required at the terminal. Default entry point when the operator wants
# a one-glance summary.
state:
	@echo "== ACTIVE =="
	@$(RL) active --show
	@echo
	@echo "== LEDGER =="
	@for d in $(ROOT)/.research/ledger/*/; do \
	    test -d "$$d" || continue; \
	    month=$$(basename "$$d"); \
	    count=$$(ls "$$d" | wc -l | tr -d ' '); \
	    echo "  $$month: $$count EV(s)"; \
	done
	@echo
	@echo "== REFERENCES =="
	@$(RL) references list

# Just the EV list, newest first. `ledger-details` shows each EV header.
ledger:
	@ls -lt $(ROOT)/.research/ledger/*/
ledger-details:
	@for f in $$(ls -t $(ROOT)/.research/ledger/*/*.json 2>/dev/null | head -10); do \
	    echo "--- $$f ---"; \
	    cat "$$f" | python3 -m json.tool 2>/dev/null | head -20; \
	done

# Both `references` and `references-list` are accepted.
references:
	@$(RL) references list
references-list: references

# KPI report
telemetry:
	@$(RL) telemetry --report
kpi: telemetry

# Reconcile check (no findings == consistent state)
reconcile:
	@$(RL) reconcile

# Re-pull git / sha256 fingerprints of every registered reference.
sync-refs:
	@$(RL) references sync

# The `watch` command is what the operator originally typed by hand: ACTIVE
# re-renders + `ls -lt` on the ledger partition every 5 s. Operators on
# macOS have `watch` from Homebrew by default; the fall-back keeps the
# target working if the binary is missing.
watch:
	@command -v watch >/dev/null && \
	    watch -n 5 '$(MAKE) -C $(ROOT) state' \
	    || ( \
	        echo "watch not found, falling back to 5 s tail"; \
	        while true; do clear; $(MAKE) -s -C $(ROOT) state; sleep 5; done \
	    )

# Ready check — runs the cheap sanity probes so the operator can confirm
# the cwd is fit before spawning a session. Exits non-zero if any of
# them fails, which halts the spawn in a Make-driven flow.
ready: reconcile state
	@echo
	@echo "==> ready (reconcile: clean; see status above)"

# Spawn Claude Code in the cwd. The protocol's `research-engineering` skill
# is not yet globally installed (Architect's gate: "don't ship globally
# during protocol development"). The skill lands here only when
# `install-local` below is run. Default flag set is the one Architect
# would type by hand for daily work.
session-spawn:
	@exec claude --model fable --bare

# Same, but Codex (so the spawn entry mirrors Architect's mental
# two-tab workflow when probing against the alternative model).
session-spawn-codex:
	@exec command codex

# Convenience: install the protocol's skill tree into this cwd's
# .claude/skills/ and .agents/skills/ so a freshly-spawned Claude/Codex
# session picks up the research-engineering / evaluation-design / etc.
# skills automatically. Mirrors what `install_research_skills.py --target`
# does; this is a *per-workspace* skill drop, the global one is gated.
install-local:
	@python3 $(RE_PROTOCOL)/tools/install_research_skills.py --target $(ROOT)

clean:
	@rm -rf /tmp/re-fixture-* /tmp/re-acceptance-* 2>/dev/null || true

# Catch-all `help` so `make` alone prints the surface.
help:
	@printf '%s\n' \
	    'make state          ACTIVE + ledger count + reference count' \
	    'make ledger         newest EV landing, top 10' \
	    'make ledger-details dump first 20 lines of each recent EV' \
	    'make references     registered external targets' \
	    'make telemetry      5 KPIs (KPI-aware ones stay unavailable until fed)' \
	    'make reconcile      one-shot reconcile check' \
	    'make sync-refs      re-pull git / sha256 of every reference' \
	    'make watch          5 s loop of `state` (like `watch -n 5 state`)' \
	    'make session-spawn         claude --model fable --bare in cwd' \
	    'make session-spawn-codex   codex in cwd' \
	    'make install-local         drop RE skills into .claude/skills/ + .agents/skills/' \
	    'make ready          reconcile + state, non-zero on dirty' \
	    'make clean          /tmp/re-fixture-*'
