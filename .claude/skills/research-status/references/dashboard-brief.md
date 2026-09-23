# Local dashboard briefing

Read this only when the architect asks to refresh/save the dashboard, or an authorized
milestone needs a new briefing and a dashboard brief already exists. This is derived
display data, never research state or execution authority. No model calls on page refresh.

If `tools/researchlog/web.py` is absent, report that this installation predates web
support; do not install or upgrade during a status query.

1. Before reading/synthesizing, run `python3 tools/researchlog/web.py --basis` and retain
   that exact source_revision. Read canonical sources under the normal status protocol.
2. Write an input JSON under the ignored `.research/.derived/` (legacy `research/`
   follows the discovered state location). Do not dirty tracked state to save a view.
3. Publish with `python3 tools/researchlog/web.py --publish-brief INPUT.json`.
   If the sources changed, re-read and re-synthesize; never stamp an old summary with
   a new fingerprint. Do not start research or repair merely to publish a brief.

Format (all displayed text is Chinese):

```json
{
  "version": 1,
  "source_revision": "<exact --basis output captured before synthesis>",
  "activity": {"text": "Current block objective in Chinese, distinct from the saved route focus", "refs": ["ACTIVE.json"]},
  "headline": {"text": "Application-level position in one sentence", "refs": ["CURRENT.md"]},
  "goal": {"text": "Application objective, not the current probe", "refs": ["TASK.md"]},
  "capability": {"text": "What exists and what was demonstrated", "refs": ["FND-..."]},
  "gap": {"text": "Missing capability and evidence boundaries", "refs": ["FND-..."]},
  "next": {"text": "Recommendation and why it matters; not authorization", "refs": ["R-..."]},
  "decision": {"text": "Only genuine architect choices, or explicitly none", "refs": ["ACTIVE.json"]},
  "routes": {"R-...": {"text": "Short application-level title", "detail": "Value, hold reason or wake condition"}},
  "conclusions": {"FND-...": {"text": "Conclusion with its essential limit"}},
  "events": {"EV-...": {"text": "What changed and why it matters"}}
}
```

Route events use `R-ID:zero_based_history_index`. Preserve IDs; do not translate them.
Summaries explain existing sources; they cannot close routes, accept evidence or give
execution approval. Do not replace raw records. Publishing binds translated rows to their
individual source records, and activity to the current block. The page preserves unchanged
translations, keeps the previous overall judgment expanded with its timestamp and a pending-update label, and uses Chinese pending-summary
notices for changed/untranslated rows; raw English remains available in details. Include
activity and translations for current routes, recent events and material conclusions.
This is derived display text, not bilingual canonical state. Missing fields
must say unknown/uninvestigated, not invent progress. The fingerprint covers canonical
records and TASK, not arbitrary code or external data; do not call it scientific validation.
