# Portolan NRR pipeline

Turns published studies into validated Negative-Results Records. Eight studies are encoded. See `README.md` for what
the project is and `docs/` for why decisions were made. This file is how to work in the code.

## Commands

```bash
uv sync                                    # Python >= 3.12
uv run pytest -q                           # full suite; Robin tests self-skip if raw/robin is absent
uv run python scripts/fetch_sources.py --study robin-damd   # network; the only way to get raw/robin
uv run python build.py                     # writes out/ ; exits non-zero if any record is invalid
uv run python build.py --study arcadia-raman               # one study
uv run python demo_queries.py              # the questions an agent would ask
uv run python scripts/export_records.py --study <s> --dest ../nrr-records   # publishable studies only
uv run python scripts/resolve_ids.py       # network; only when adding new names or DOIs
```

`build.py` must stay offline. If it needs the network, something is wrong.

## Invariants: break these and the corpus stops meaning anything

- **Determinism.** Two builds produce byte-identical records. `dateCreated` comes from `INGEST_DATE`
  (`NRR_BUILD_DATE` env var, default fixed), never from the clock. Anything that reaches a record must be stable:
  a wall-clock timestamp leaking into a `statusAtCheck` once broke this silently.
- **Content addressing.** `@id` is sha256 over canonical JSON excluding `@id`, `contentAddress`, `dateCreated`,
  `integrity` and `hasPart`. `hasPart` is excluded because it is registry-derived; a path is finalised before its
  attempts exist, then `hasPart` is filled and `check_valid` is called.
- **Enums are bound to `vocabularies.json` at load time** via `ENUM_BINDINGS` and `sync_enums` in `schema.py`. The
  schema file carries literal enums so it can be published standalone. Adding a vocabulary term means editing
  `vocabularies.json` and re-running `sync_enums` over the schema file; a test catches drift. Editing an enum
  directly in the schema JSON is wrong.
- **The resolver is offline by default.** Converters and tests read `curated/identifiers.json` only. A cache miss
  returns `None` and is recorded in `resolver.misses`. Never make a converter hit the network.
- **All statistics are the authors'.** The pipeline never re-tests significance. Values it computes (means, SEMs,
  a rule-of-three bound, a Bradley-Terry re-computation) are marked `derivedBy: portolan-ingest` with a `method`.

## Honesty conventions, enforced by review not by code

- Every value carries a `source` or `evidence[].locator` pointing at where in the source it came from.
- Attribution the source does not state is marked `proposedByConfidence: inferred` or `not-stated`.
- Inconsistencies in the source go in `provenanceNotes`, unresolved. Do not silently pick a number.
- Judgement calls that drive an outcome class go in `provenanceNotes` naming them as the ingest's reading.
- Quotations stay short, and from NC-ND sources they stay shorter.

## Test-first, with facts pinned from the paper

Write the test before the converter, and pin real values from the publication (`ripasudil 1.891, n=3, 100 µM`).
That is what makes the tests worth anything: they fail if a parser drifts. Run the full suite, not just your file.

## Adding a study

1. Screen and choose. State why, and prefer the study most likely to break the model over the one most likely to fit.
2. `curated/<study>/` gets hand-transcribed tables with a provenance column naming the table, figure or page.
   `raw/<study>/` gets vendored sources, or a `fetch_sources.py` branch if the licence forbids redistribution.
3. Write `tests/test_<study>.py` first. Watch it fail.
4. Write `src/nrr/ingest/<study>.py`. Try it **without** schema changes and let validation tell you what is missing;
   that is the only honest way to count what a study forced.
5. Add any vocabulary or field, log it in `schema/CHANGELOG.md` with the reason and the study that forced it.
6. Wire into `build.py`, `scripts/export_records.py`, `tests/test_build.py` and `tests/test_db.py` record counts.
7. Rebuild, export if publishable, write up what it broke in `docs/`.

## The informativeness rule

`src/nrr/rules.py` is the intellectual core. A negative counts as evidence of absence only if a positive control
passed, the negative control stayed clean, and a sensitivity or power statement exists. Otherwise the finding is
`uninformative` and its class must be an `inconclusive-*` value; `apply_informativeness` does the remapping.

`refuted` is deliberately exempt: an affirmative refutation is judged on the refuting analysis, not on the controls
of the run it refutes. `negative-not-replicated` deliberately keeps the requirement.

All clauses have fired on real published data, each in a different study. Before changing this file, read
`docs/convergence-test.md` and check whether the case is genuinely new.

## Where this pipeline sits: one node of a federation

Since 2026-09-30 Portolan is a federation of NRR databases (decision and reasoning in
`../research/decision-open-core-federation-2026-09-30.md`). This repository is the reference implementation, and the
corpus it builds is the **open node**: CC BY records, published through `scripts/export_records.py`. Private nodes run
the same schema, rules and server contract over records a lab or company keeps to itself. The business model is
open-core: the software is what gets sold, records never are.

What that means in the code:

- **Access is already modelled. Do not add another field for it.** `visibility` (required; `private`, `embargoed`,
  `public`, `restricted`) plus `embargoUntil` are the access tier. `license` and `sourceLicense` are a separate
  question: what may be redistributed, not who may read. The converters set `visibility: public` in `ingest/common.py`
  because everything here is destined for the open node; a private node's ingest would set it differently, nothing
  else changes.
- **The pipeline must stay node-agnostic.** Nothing in `src/nrr/` may assume it is building the public corpus. The
  only place that knowledge lives is `scripts/export_records.py`, which is the open node's publishing step and the
  licence gate.
- **`docs/mcp-contract.md` is the contract for any node**, open or private. Federated query (resolve which nodes the
  caller may reach, then fan out) is the layer above it and is not yet designed. When it is, it belongs in a new doc,
  not in the converters.
- **The informativeness rule is the product in both tiers.** In a private node it is the quality guarantee the buyer
  pays for. Weakening it to make records easier to deposit is a business decision, not a convenience.

## Schema change discipline

Change count by study so far: 12, 8, 5, 2. Nothing structural since the first study. A new field or record level is
a strong claim and needs a study that genuinely cannot be encoded without it. Vocabulary terms are cheap and expected.
