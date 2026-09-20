# Acceptance pipeline — see docs/RE_ACCEPTANCE_CASES.md and
# tools/run_acceptance.py for the contract.

.PHONY: acceptance acceptance-full acceptance-v0 acceptance-v1 acceptance-manual \
        acceptance-list acceptance-scan-docs acceptance-fix-docs \
        acceptance-clean install-global install-global-check

# Fast run — AUTO cases only (≤60s each). Default entry point.
# 27 V0/V1 cases that don't need claude/pi.
acceptance:
	python3 tools/run_acceptance.py run --mode AUTO

# Full run — AUTO + LONG_RUN (drives tests/main/{build_*,run_case.sh,verify_case.py}).
# The 3 LONG_RUN cases (V0.M4 / V0.10 / V0.13) spin up real claude sessions
# against fixtures; each has a 300s subprocess timeout. Expect 1–5 minutes.
acceptance-full:
	python3 tools/run_acceptance.py run --mode ALL

# V0-only run.
acceptance-v0:
	python3 tools/run_acceptance.py run --level V0 --mode AUTO

# V1-only run — the 9 V1 drills.
acceptance-v1:
	python3 tools/run_acceptance.py run --level V1 --mode AUTO

# List cases that the Architect must run by hand (runner_mode=MANUAL).
# Currently: V0.19 (`--bare` / `--strict-mcp-config`) + V0.22 (cross-client pi).
acceptance-manual:
	python3 tools/run_acceptance.py list-manual

# List every registered case with its expected status + runner_mode.
acceptance-list:
	python3 tools/run_acceptance.py list

# Scan docs/RE_ACCEPTANCE_CASES.md for drift against the live repo.
acceptance-scan-docs:
	python3 tools/run_acceptance.py scan-docs

# Patch drift found by the scan.
acceptance-fix-docs:
	python3 tools/run_acceptance.py fix-docs

# Clean temp fixtures. The acceptance pipeline writes only to /tmp and
# docs/RE_ACCEPTANCE_REPORT_<timestamp>.md.
acceptance-clean:
	rm -rf /tmp/re-fixture-* /tmp/re-acceptance-* /tmp/re-case-* 2>/dev/null || true

# Install RE skills into the user's global client directories so every
# research workspace (~/sandbox/agentic-2026/<study>/) picks them up on
# next start. Scope is RE-owned skills only; other plugins sharing the same
# global home stay untouched.
install-global:
	python3 tools/install_research_skills.py --global

install-global-check:
	python3 tools/install_research_skills.py --global --check

# Symlink the no-PYTHONPATH entry script into ~/.local/bin/ so any cwd
# can call `re <verb>` after a single one-shot install. Goes through
# the user-level bin (not /opt/homebrew/bin) so it never collides with
# Homebrew-managed Python. PATH is left to the operator: this Makefile
# only writes the file.
install-shell:
	mkdir -p $$HOME/.local/bin
	ln -sf $(PWD)/tools/re $$HOME/.local/bin/re
	@echo "Linked $$(PWD)/tools/re -> $$HOME/.local/bin/re"
	@echo "Add to PATH if not already:  export PATH=\$$HOME/.local/bin:\$$PATH"
	@echo "Then: re init  /  re state  /  re record ..."

# Undo install-shell.
uninstall-shell:
	rm -f $$HOME/.local/bin/re
	@echo "Removed $$HOME/.local/bin/re"
