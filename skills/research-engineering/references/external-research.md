# External research and durable reports

Load when choosing a consequential mechanism/framework, entering an unfamiliar domain,
encountering repeated failure without a convincing next mechanism, or receiving a new
architect direction that changes the candidate space. Routine implementation details
do not each need a literature survey.

## Search to change a decision

First recover relevant working pieces, capability entries and implementation receipts
already in this project. If the index is incomplete, make a targeted code/artifact search,
not a replay of the entire history. Compare reusable local methods with primary SDK
examples before investing in a custom parser, large download or environment replacement.
An independent comparison may forbid reading a control project's code: respect that
boundary, use allowed primary sources, and never count an architect-supplied solution
or control-code transfer as independent discovery.

Use available web search and source retrieval proactively within the existing access
and spend policy. Start with the concrete uncertainty, constraints and alternatives.
Prefer primary papers, official documentation and maintained implementation repositories;
check dates/versions and inspect sources rather than trusting snippets. Search for
failure modes and competing approaches, not only support for the current favorite.
Do not send private code, data or credentials as search queries.

For a consequential question with conflicting evidence, perform a bounded deeper
investigation: follow citations, compare mechanisms and implementation requirements,
and identify the cheapest discriminating local test. Use a dedicated deep-research
capability only if actually available and authorized; otherwise perform ordinary
multi-source research and say what was checked. Never pretend an unavailable service
ran, or activate paid external services implicitly.

Record the question and a search timebox inside the research block budget. Stop when
the sources support an actionable candidate comparison and next test, or the budget
expires. Lack of consensus is an uncertainty to report, not a reason to browse forever.
Do not repeat unchanged searches merely because the session restarted.

Distinguish published claims, source-code observations and locally measured behavior.
SOTA or benchmark superiority elsewhere is not proof of suitability here. Recommend
the best-supported option under current constraints, not an unqualified "best solution".
External research produces E0 evidence with source URLs, access dates, versions and
limitations; local validation has its own evidence. Neither automatically promotes
architecture or changes the architect's authority boundaries.

## Preserve high-value results

When a method unlocks reusable capability, update CURRENT.working_pieces with its
entrypoint and evidence link, and the relevant ENVIRONMENT capability/harness through
the existing CLI. Capability-map `notes` can hold the invocation, dependencies/input
identity, output location and known limits; `verified_by` belongs in a harness or the
linked evidence, not an invented capability-map field. Preserve both what now works
and what remains unverified. Record an available method as limited when appropriate,
not simply as an environment blocker because stronger qualification is unavailable.
Reuse an existing entry when it already carries this information; no new report or
capability entry is required for a routine retry.

Write a concise Chinese report when a result changes the mechanism family, application
architecture, environment investment, or invalidates a costly prior assumption. Small
routine iterations need evidence, not another report. Use a versioned Markdown artifact
under `docs/research/`, with a descriptive stable filename or revision suffix.

Cover the decision question, practical conclusion, alternatives and tradeoffs, source
links/version/date, what was actually tested, limitations and impact on the next step.
Keep it readable without decoding protocol IDs. Include an English metadata header:

    DERIVED RESEARCH REPORT — NOT CANONICAL STATE
    Basis: EV-... (already existing records, when applicable)

Register the report as an evidence artifact using `record --artifact PATH
--artifact-role research-report` (plus the normal evidence fields), then link that EV
from a finding using the findings tool. A synthesis of existing evidence must explicitly
say it adds no independent measurement; do not inflate evidence iterations for writing.
If recording the initial external investigation, the report supplies its sources and
analysis; no pre-existing EV is required. Avoid circular self-citation.

FINDINGS remains the current conclusion/status/evidence index; reports explain it.
Do not hand-edit canonical JSON or rewrite old evidence. Revise a registered report
into a new version, record new evidence and supersede/demote the old finding when
appropriate. Historical reports remain historical: a polished document never overrides
a later refutation. Missing reports should appear as absent, not be invented by the UI.

The dashboard derives report links through finding -> evidence -> research-report
artifact. An architect can inspect a finding's basis, implications, limits, replacement
and document path without searching chat history.
