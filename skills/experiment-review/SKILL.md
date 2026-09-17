---
name: experiment-review
description: Load when a run just finished and ≥ 2 hypotheses are live. Walks what the run actually said against the registered hypotheses, decides which one(s) it differentiated, and what belief change to record. V0 router row carried over verbatim.
---

# Experiment review

The router row was lifted directly from the V0 reference list — the content lives in
[`skills/research-engineering/references/experiment-review.md`](../research-engineering/references/experiment-review.md)
to keep a single source of truth until the reference is moved here in full.

Load when a run just finished and at least two hypotheses are live. Owns the
`hypotheses_differentiated` / `belief_delta` choice that a record has to commit to.

This skill does not yet ship its own checklist — it is the V0 reference under a new
name. The next iteration moves the body of `experiment-review.md` into this file and
deletes the duplicate.