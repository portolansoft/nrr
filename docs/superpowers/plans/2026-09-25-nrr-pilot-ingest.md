# NRR Pilot Ingest Implementation Plan

> **For agentic workers:** This plan is executed natively in-session (the user chose autonomous execution). Steps use checkbox (`- [ ]`) syntax for tracking. TDD applies to every task: write the failing test, watch it fail, implement, watch it pass.

**Goal:** Turn two published studies into validated Portolan NRR v0.2 records, load them into SQLite, and prepare MCP deposit payloads.

**Architecture:** A small Python package `nrr` (schema + validation + crate writer + cached identifier resolver), two converter modules that read vendored raw/curated inputs and return records, a loader that writes SQLite, and a `build.py` that runs everything and writes `out/`.

**Tech Stack:** Python 3.12+, uv, jsonschema (draft 2020-12), openpyxl, sqlite3 (stdlib, FTS5), pytest.

**Spec:** `docs/design.md`

## Global Constraints

- No network access inside converters or tests; identifiers come from `curated/identifiers.json`, populated once by `scripts/resolve_ids.py`.
- Every record validates against `schema/nrr-0.2.schema.json`; the build fails otherwise.
- Every numeric value in a record has a `source` locator (table, sheet, row, page, file, or URL).
- All statistics are the authors'. Derived values are labelled `derivedBy: portolan-ingest` with the method.
- Record ids are content addresses (`sha256` of canonical JSON without `@id`, `contentAddress`, `dateCreated`).

## Review Focus

1. A finding with no positive control must never be `informative` (Arcadia HDR): test in Task 2.
2. A finding whose designated control failed but which has an internal positive must be `informative` and say why (Robin Finch round 1): test in Task 2.
3. Records for the repository's re-run candidates must be marked `provenanceNotes` and `decision: deferred`, never `included`: test in Task 5.
4. Cross-study queries must work on shared identifiers (NCBITaxon, PubChem, OBI): test in Task 7.
5. Re-running the build must produce byte-identical records (determinism, stable ids): test in Task 8.

---

### Task 1: Schema, vocabularies, validation

**Files:** Create `schema/nrr-0.2.schema.json`, `schema/vocabularies.json`, `src/nrr/schema.py`; Test `tests/test_schema.py`.

**Interfaces:** `load_schema() -> dict`, `load_vocab(name) -> list[str]`, `validate(record) -> list[str]` (empty list = valid), `minimal_attempt(**overrides) -> dict` (test helper in `tests/factories.py`).

- [ ] Test: minimal attempt validates; missing `question` fails; unknown `outcomeClass` fails; unknown `attemptType` fails; a `path` record needs `hasPart`.
- [ ] Implement schema (draft 2020-12, `$defs` for Finding, Control, ScreenedItem, DataPointer, Performer, StatusAtCheck, Cost, Score) and vocabularies.

### Task 2: Informativeness rule and content address

**Files:** Create `src/nrr/rules.py`, `src/nrr/identity.py`; Test `tests/test_rules.py`, `tests/test_identity.py`.

**Interfaces:** `informativeness(finding: dict) -> tuple[str, str]` returns (`informative`|`uninformative`, reason); `enforce_outcome(finding) -> list[str]` returns violations when uninformative findings carry a non-inconclusive class; `content_address(record: dict) -> str`; `canonical_json(obj) -> str`.

- [ ] Tests: 4 control combinations; absent positive control -> uninformative; key order does not change the address; changing a value changes the address.

### Task 3: RO-Crate writer

**Files:** Create `src/nrr/crate.py`; Test `tests/test_crate.py`.

**Interfaces:** `to_crate(record: dict) -> dict` (RO-Crate 1.2 JSON-LD with `ro-crate-metadata.json` descriptor, root Dataset conformsTo the profile, one entity per finding/screened item/performer, PROV relations).

- [ ] Tests: descriptor present; root `conformsTo` is the v0.2 profile URI; `isPartOf` becomes a PROV/Schema relation; finding count preserved.

### Task 4: Cached identifier resolver

**Files:** Create `src/nrr/resolve.py`, `scripts/resolve_ids.py`, `curated/identifiers.json`; Test `tests/test_resolve.py`.

**Interfaces:** `Resolver(cache_path, online=False)`, `.compound(name) -> dict|None`, `.ontology(label, ontologies) -> dict|None`, `.doi_status(doi) -> dict`, `.organization(name) -> dict|None`; cache keys are `kind:normalised-name`.

- [ ] Tests: offline resolver returns cached entry; offline miss returns `None` and records the miss; alias table maps `Dimethyl fumerate` to `dimethyl fumarate`.

### Task 5: Robin converter

**Files:** Create `src/nrr/ingest/robin.py`, `curated/robin/*.csv|yaml`, `raw/robin/...`; Test `tests/test_robin.py`.

**Interfaces:** `build_robin_records(root: Path, resolver) -> list[dict]`; helper parsers `parse_ranked_csv`, `parse_pairwise_csv`, `bradley_terry(pairs, n) -> list[float]`, `parse_supp_table(ws) -> dict[drug, list[row]]`, `parse_ena_runs(tsv) -> list[dict]`, `parse_references(txt) -> list[dict]`.

- [ ] Tests (facts pinned from the paper): 11 records; ripasudil round-2 mean 1.891 (n=3); KL001 negative in ARPE-19 round 2 and positive in RPE-SC; 29 SRA runs; untried branches name exendin4, MLN120B, AT; repo candidates are `deferred` with a provenance note; Deep Research attempt has 0 positive findings; all records validate.

### Task 6: Alcalase converter

**Files:** Create `src/nrr/ingest/alcalase.py`, `curated/alcalase/*.csv|yaml`, `raw/alcalase/...`; Test `tests/test_alcalase.py`.

**Interfaces:** `build_alcalase_records(root: Path, resolver) -> list[dict]`; helpers `parse_wall_permeability(csv)`, `parse_colony_index(csv) -> summary`, `rule_of_three(n) -> float`.

- [ ] Tests: 7 records; wall permeability Alcalase flask 23.36%; colony index gives 40 sequenced and 0 edited; HDR finding is `inconclusive-no-positive-control` and uninformative; transformation finding is `negative-not-achievable` with failure mode `transformation-failed`; path has 3 untried branches, 3 open questions, 2 abandonment reasons; all validate.

### Task 7: SQLite loader and queries

**Files:** Create `src/nrr/db.py`, `db/schema.sql`, `db/queries.sql`; Test `tests/test_db.py`.

**Interfaces:** `load(records: list[dict], db_path) -> None`, `query(db_path, name, **params) -> list[dict]`.

- [ ] Tests: load both corpora; `prior_art(target='ripasudil')` returns 3 records; `by_taxon('NCBITaxon:3055')` returns only Arcadia; `failed_or_missing_positive_controls()` returns Arcadia HDR and Robin Finch round 1; FTS search `alcalase chlamydomonas` hits the transformation record.

### Task 8: Build script, deposits, validation report

**Files:** Create `build.py`, `src/nrr/deposit.py`, `out/`; Test `tests/test_build.py`.

- [ ] Tests: build writes N records + N crates + N deposits + manifest; second build is byte-identical; validation report has zero errors.

### Task 9: Documentation

**Files:** `schema/README.md` (v0.2 human-readable), `schema/CHANGELOG.md`, `docs/mcp-contract.md`, `docs/assessment.md`, `README.md`, pointer line in `../outreach/nrr-schema-sketch-v0.1.md`, memory notes.
