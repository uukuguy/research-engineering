# Block 1.5 — Research Capability Map shape proposal

> Status: **draft, awaiting Architect review.** No schema change is committed
> alongside this proposal; per V1 §2.1 P4 the agent drafts the shape and the
> Architect decides before `environment.schema.json::capability_map` is
> given a real `items` definition.

## 1. Why a shape is needed now

`ENVIRONMENT.md` declares three lists a research lab keeps on hand:
`available`, `limitations`, `harnesses`. The first two have item shapes
and are read by `validate`; the third is empty (`type: "array"` only)
because nothing writes it and nothing reads it. V0 acceptance guide
flagged this in §D3 (capability_map never gets entries because nothing
writes them) and §D2 (the same gap repeats for harnesses / limitations
on the `env record` path; that part is Block 2 / T1's concern, not P4).

V1 §3.1 #17 ties capability_map to "Research Capability Map 与 harness
投资判断" — the question the entries answer is *which capabilities are
worth investing in next*, because their reuse is high enough that
building a harness pays off. That requires two things the current
empty-array shape cannot deliver:

1. A reusable identity per capability, so a session can ask "what did
   we already declare?" without grepping prose.
2. A usage counter, so the "is this worth a harness?" question has data
   behind it.

V1 §2.1 P4 names `reuse_counter` as the must-include field. V1-D7 also
demands `≥3 entries written` by V1 complete, so the shape must support
real entries from day one.

## 2. Proposed shape

```json
{
  "id": "CAP-physics-fidelity-001",
  "capability": "high-fidelity contact dynamics",
  "status": "AVAILABLE | LIMITED | UNSUPPORTED",
  "supports_evidence": "E2 | E3 | null",
  "reuse_counter": 3,
  "first_used_at": "2026-09-04T10:00:00+00:00",
  "last_used_at": "2026-09-17T08:00:00+00:00",
  "last_used_by_evidence_id": "EV-20260917T080000Z-3a1b",
  "notes": "free-form short prose; absent unless the agent has something to say"
}
```

Field-by-field:

| Field | Required? | Type | Meaning |
|---|---|---|---|
| `id` | required | string | `CAP-<short-slug>-<NNN>`. Pattern guarded by schema. |
| `capability` | required | string | What this entry is about, in one short line. |
| `status` | required | enum | One of `AVAILABLE` / `LIMITED` / `UNSUPPORTED`. Distinguishes "we have it" from "we know we don't, and there is evidence in `limitations[]` pointing the same way". |
| `supports_evidence` | optional | enum `E2\|E3\|null` | The strongest evidence level the capability has actually been used at. Distinct from "is the capability real", which is the responsibility of the matching `limitations[]` or `harnesses[]` entry. |
| `reuse_counter` | required | integer ≥ 0 | How many records cite this capability. **This is the field V1 §2.1 P4 names explicitly and V1-D7 tests against.** A zero is allowed (the entry was declared speculatively and never reused). |
| `first_used_at` | optional | ISO 8601 UTC | Stamped on the first record that cites it. Null until then. |
| `last_used_at` | optional | ISO 8601 UTC | Stamped on each reuse. Null until first use. |
| `last_used_by_evidence_id` | optional | string | The record that bumped `reuse_counter` most recently. Lets a reader follow back from the map to the ledger without grepping. |
| `notes` | optional | string | Free-form short prose. No enforcement; absent unless there is something worth saying. |

## 3. Why these fields and not others

Things considered and dropped:

* **Cross-references to `limitations[]` / `harnesses[]` by id.** Tempting
  (it would let a session ask "what does the lab have *and* not have
  for capability X?"), but the linkage already exists at the prose
  level — entries on both sides name the same capability string. A
  hard foreign key would require the harness side to expose a stable
  id, which Block 2 / T1 will give it, and even then the cross-ref
  would be a follow-up; we are proposing a shape that V1-D7 can satisfy
  on its own.
* **A `category` field.** Suggested by the V0 schema's `available.{compute,
  simulator, data, external_services}` split. The category *is*
  already expressed by the existence of `harnesses[]` for harnesses
  and `limitations[]` for known gaps; capability_map is for the
  *neither-yet* zone — capabilities the lab can either deliver or
  can't, but has not been forced to either judgement yet.
* **A free-form `description` long-text.** Encourages prose that no
  one reads. `notes` is the short-form escape hatch for the rare cases
  where it is needed; absent-by-default keeps the map scannable.
* **A `cost_estimate` field.** The investment question V1 §3.1 #17
  names is partly a cost question. But "cost" here is unbounded — wall
  clock, tokens, GPU-hours, real money, opportunity — and pinning one
  of those would lock the schema to a budget model the lab may not
  have yet. `reuse_counter` is the half the agent can already measure
  honestly; cost can be a follow-up field once a budget model exists.

## 4. Write path (not in this block)

Per V1 §2.2 T1, the `env record --harness / --limitation / --capability`
flags will land in Block 2. The shape above is designed so that flag
can populate `reuse_counter`, `last_used_at`, `last_used_by_evidence_id`
on every cite. Until then, the schema accepts the field shape but no
command produces entries — this is intentional, matching V0's pattern
where `harnesses[]` was a valid array whose items nobody wrote.

The proposal does not need to commit the write path. What it does
commit: the schema can carry entries the day T1 lands, and any entries
written by hand in the meantime (e.g. `init` seeding an example) will
validate.

## 5. Validation criteria V1-D7 will hit

The shape above lets V1-D7 (six assertions) be satisfied:

| V1-D7 assertion | How this shape delivers |
|---|---|
| `capability_map shape 通过 schema` | `items` becomes a typed object; `validate` checks every entry. |
| `≥3 entries written` | `env record --capability ...` (Block 2 / T1) writes per cite; the schema permits ≥3 with no extra plumbing. |
| `reuse_counter 字段存在` | Required field with `type: integer, minimum: 0`. |
| `harness declare 合法` | Out of scope for this proposal (Block 2 / T1) but unblocked: the `harnesses[]` shape already exists. |
| `env rebaseline 触发 fingerprint 变` | Out of scope (Block 2 / T4); unrelated to this shape. |
| `changed` 谓词不再永远 `UNRESOLVED` | Out of scope (Block 2 / T4); unrelated to this shape. |

So this proposal closes two of the six V1-D7 lines directly and removes
the shape guesswork that the other four were blocked on.

## 6. What I am asking the Architect to decide

Three concrete points. A line-item approval is enough; full rewrite
is welcome but not required.

1. **Field set.** Is the nine-field set above the right shape, or
   should something be added / dropped? The `reuse_counter` + identity
   pair is non-negotiable; everything else is negotiable.
2. **Status vocabulary.** `AVAILABLE | LIMITED | UNSUPPORTED` mirrors
   the harness / limitation dichotomy. If the Architect prefers a
   finer split (`AVAILABLE | DEGRADED | LIMITED | UNSUPPORTED` for
   example), say so.
3. **Optional vs required.** `reuse_counter` is required; `id` is
   required; `capability` is required; the rest are optional with null
   until first use. The proposal prefers required-only-where-the-data-
   is-always-known to avoid "always present, always null" fields that
   the schema validator currently has no syntax to distinguish from
   "always present, never updated". Confirm or push back.

Once approved, the change is:

* `tools/researchlog/schemas/environment.schema.json` — replace the
  empty `capability_map` array with a typed `items` object per §2.
* `templates/research/ENVIRONMENT.md` — ship with the `capability_map`
  fenced block empty, matching the V0 behaviour for `limitations[]` /
  `harnesses[]`. T1 (Block 2) will be the first writer.

No schema migration risk: `capability_map` already exists as an
array; tightening it from `items: <nothing>` to `items: <object>` is
a forward-compatible tightening because V0 has zero entries today
and the empty-array case validates under both shapes.

## 7. What this proposal deliberately does NOT do

* It does **not** add a `capability_count` summary field. `available`,
  `limitations`, `harnesses`, `capability_map` are the four lists;
  derivable counts are the reader's problem.
* It does **not** introduce cross-references between capability_map
  and limitations / harnesses. The capability *string* is the join key;
  enforcing a foreign key is a Block 2 / T1 question.
* It does **not** redefine `available.*`. The four sub-arrays inside
  `available` are about concrete assets (machines, simulators,
  datasets, services); capability_map is about *what we can do with
  them*, which is a different abstraction layer.
* It does **not** change how `record --surrogate` interacts with the
  map. The surrogate contract is per-record; the map is per-lab. They
  share the `capability` vocabulary but a record need not write the
  map to cite a capability — T1 will, but that is separate.

## 8. Architect decision (signed off 2026-09-18)

Architect sign-off was delegated to the research-engineering session
during a "finish V1" turn ("自定就好,尽快整体完成可用"). The decision
applied each of the three line items in §6:

1. **Field set**: the nine-field set in §2 is accepted as proposed.
   `reuse_counter` (required integer ≥ 0) + the `id` / `capability` /
   `status` minimum is the contract; the optional fields are optional.
2. **Status vocabulary**: `AVAILABLE | LIMITED | UNSUPPORTED` is
   accepted as proposed. The proposal's reasoning — that the
   three-way split mirrors the existing harness / limitation dichotomy
   and avoids "always present, always null" finer splits — is the
   load-bearing rationale. If a fourth status is needed later, a
   follow-up proposal is the right place.
3. **Optional vs required**: the proposal's `required-only-where-
   the-data-is-always-known` rule is accepted. Concretely:
   `id` / `capability` / `status` / `reuse_counter` are required;
   the rest are optional with `null` until first use. Missing
   optional fields and explicit `null` are equivalent for validation
   (the schema's `["string", "null"]` form treats them the same).

The schema and the `env declare capability_map` path landed in the
same commit that carries this proposal to closure; see the matching
commit message for the version recorded against `research/ENVIRONMENT.md`.