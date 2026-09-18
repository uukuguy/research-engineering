# Durable Findings

What we currently believe, and the evidence for it. Findings are context compression,
not a log — every entry cites evidence IDs, and an entry that cannot cite real evidence
is not a finding.

The prose below is generated from the `research:findings` block by
`researchlog findings render`. Do not edit that block by hand, and do not edit the
prose expecting it to survive — the block wins.

<!-- researchlog:findings:begin -->

## Findings

No durable beliefs recorded yet.

<!-- researchlog:findings:end -->
```json research:findings
{
  "schema_version": "1.0",
  "entries": []
}
```

## Status vocabulary

| Status | Meaning |
|---|---|
| `Established` | Well supported. Must cite at least one completed evidence record. |
| `Provisional` | Supported but thin, or with an unresolved limitation. |
| `Refuted` | A hypothesis we held and then falsified. |
| `Superseded` | A finding we believed that has been replaced. Requires `superseded_by` and `reason`. |
| `Open` | A live contradiction between evidence records, not yet resolved. |

`Refuted` is the fate of a *hypothesis*. `Superseded` is the fate of a *finding* — a
belief that once stood and no longer does. Keeping them apart is what makes the
false-confidence rate computable, and it is why an `Established` entry is never quietly
deleted when it turns out to be wrong.

`max_evidence_level` is derived: the highest level among the cited records. The tool
recomputes it and rejects a supplied value that disagrees, so a belief can never claim
more maturity than its evidence.
