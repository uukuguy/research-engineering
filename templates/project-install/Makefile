.DEFAULT_GOAL := re-help
UV ?= uv
CLIENT ?= codex
RE_PYTHON = $(UV) run python

.PHONY: re-routes re-route
.PHONY: re-workers
re-workers:
	$(RE_PYTHON) tools/re delegate list

re-routes:
	$(RE_PYTHON) tools/re routes list

re-route:
	$(RE_PYTHON) tools/re dashboard --route "$(ROUTE)"

.PHONY: re-dashboard re-dashboard-text re-watch
.PHONY: re-finding
re-finding:
	$(RE_PYTHON) tools/re dashboard --finding "$(FINDING)"

re-dashboard:
	$(RE_PYTHON) tools/re_dashboard.py

re-dashboard-text:
	$(RE_PYTHON) tools/re_dashboard.py --text

re-watch:
	$(RE_PYTHON) tools/re_dashboard.py --watch 5

.PHONY: re-help re-init re-check re-state re-validate re-reconcile re-start re-status re-cli
re-help:
	@echo 'make re-workers    Inspect durable worker packets; no model calls'
	@echo 'make re-routes     List persistent research routes; no model calls'
	@echo 'make re-route ROUTE=R-...  Inspect route evidence and pause/wake history'
	@echo 'make re-finding FINDING=FND-...  Inspect conclusion, evidence and report paths'
	@echo 'make re-dashboard  Local read-only web dashboard; no model calls'
	@echo 'make re-dashboard-text  Terminal diagnostic snapshot'
	@echo 'make re-watch      Refresh terminal snapshot every 5 seconds; Ctrl-C exits'
	@echo 'make re-init       Check/install local RE deployment; no model calls or research reset'
	@echo 'make re-check      Verify frozen tools and skills'
	@echo 'make re-start CLIENT=codex|claude  Optional new client + research-resume'
	@echo 'make re-status CLIENT=codex|claude Optional new client + research-status'
	@echo 'make re-state      Read ACTIVE as JSON (requires research bootstrap)'
	@echo 'make re-validate   Validate research state (requires research bootstrap)'
	@echo 'make re-reconcile Reconcile Git/state/evidence (requires research bootstrap)'
	@echo 'make re-cli ARGS="record --help"  Other researchlog commands'

re-init:
	$(RE_PYTHON) tools/init_re_project.py --target .

re-check:
	$(RE_PYTHON) tools/init_re_project.py --target . --check

re-state:
	$(RE_PYTHON) tools/re active --get-json

re-validate:
	$(RE_PYTHON) tools/re validate --json

re-reconcile:
	$(RE_PYTHON) tools/re reconcile --json

re-start: re-check
	$(RE_PYTHON) tools/re_client.py --client "$(CLIENT)" start

re-status: re-check
	$(RE_PYTHON) tools/re_client.py --client "$(CLIENT)" status

re-cli:
	$(RE_PYTHON) tools/re $(ARGS)
