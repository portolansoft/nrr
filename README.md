# Portolan NRR pilot: two published studies as Negative-Results Records

This folder holds the first machine-readable version of the Portolan Negative-Results Record (NRR v0.2) and a pilot that
encodes two published studies against it, end to end: source artefacts, curated tables with provenance, converters,
validated records, RO-Crates, a SQLite store with agent-style queries, and MCP deposit payloads prepared for the
server that does not exist yet.

| Study | Source | Records |
|---|---|---|
| Ghareeb et al. 2026, *A multi-agent system for automating scientific discovery* (Robin, dAMD), Nature 655:497-505, doi:10.1038/s41586-026-10652-y | paper, supplementary tables, `Future-House/robin` and `Future-House/finch` repositories, SRA PRJNA1464762 | 1 path + 10 attempts |
| Caddell et al. 2026, *Evaluation of Alcalase pretreatment for Chlamydomonas reinhardtii CRISPR knock-in*, The Stacks, doi:10.57844/arcadia-pdu7-q2zz | pub text and tables, Zenodo 10.5281/zenodo.22238548 | 1 path + 6 attempts |
| Kolb, Reitman, Lane et al. 2024, *Label-free neuroimaging in mice captures sensory activity in response to tactile stimuli and acute pain*, The Stacks, doi:10.57844/arcadia-b963-15ac | pub text and figure legends, Zenodo 10.5281/zenodo.11585535 (imaging) and 10.5281/zenodo.12770054 (code) | 1 path + 3 attempts |

Build output (`out/`): 22 records, 138 findings, 132 screened items, 0 validation errors.

## Run

```bash
git clone https://github.com/portolansoft/nrr && cd nrr
uv sync                                              # Python >= 3.12
uv run python scripts/fetch_sources.py --study robin-damd   # network: Robin sample runs (Apache-2.0) + Nature workbook (local use only)
uv run pytest -q                                     # 111 tests; Robin tests skip themselves if raw/robin is absent
uv run python build.py                               # out/records, out/crates, out/mcp, out/portolan.sqlite, out/validation-report.md
uv run python demo_queries.py                        # asks the store eleven agent-style questions
uv run python scripts/export_records.py --study arcadia-alcalase --dest ../nrr-records      # dataset repo content
uv run python scripts/export_records.py --study arcadia-neuroimaging --dest ../nrr-records
uv run python scripts/resolve_ids.py                 # only if you add names or DOIs; refreshes curated/identifiers.json
```

The Arcadia inputs are vendored (CC BY 4.0). The Nature-derived inputs are fetched, not committed, because the article
licence (CC BY-NC-ND 4.0) forbids redistributing adapted material; see `raw/README.md` and `NOTICE`. Records built from
the Nature paper are therefore not published in `portolansoft/nrr-records`; the converter is, so they can be rebuilt locally.

## Layout

```
schema/        nrr-0.2.schema.json, vocabularies.json, README.md (human-readable), CHANGELOG.md (v0.1 -> v0.2, with reasons)
src/nrr/       schema.py (validate), rules.py (informativeness), identity.py (content address), crate.py (RO-Crate),
               resolve.py (cached identifier resolution), db.py (SQLite + named queries), deposit.py (MCP payloads)
src/nrr/ingest/robin.py, alcalase.py, neuroimaging.py   the three converters; common.py shared constructors
raw/           inputs; alcalase/ vendored, robin/ fetched (see raw/README.md for origin and licence of each)
curated/       hand-transcribed tables with a provenance column, plus identifiers.json (resolver cache)
db/            schema.sql, queries.sql (the questions an agent asks)
docs/          design.md (spec written before coding), mcp-contract.md, assessment.md (honest verdict),
               case-study-neuroimaging.md (third study: what it tested and broke), superpowers/plans/
out/           build products (regenerable)
tests/         pytest suite; tests pin facts from the papers (e.g. ripasudil 1.891x, n = 3, 100 uM)
```

## What a record looks like

`out/records/robin-damd-screen-r2-arpe19.json` is a wet-lab attempt with 21 findings (one per arm of the screen), each
carrying the target's PubChem id, the dose from Supplementary Table 1, the per-well normalised values from Supplementary
Table 4, the designated positive control (MFGE8) with its observed value, the vehicle control, the sensitivity statement
from the Reporting Summary, the informativeness verdict computed by `nrr.rules`, and who proposed the compound.
`out/records/arcadia-alcalase-hdr-knockin.json` shows a negative that the rule refuses to call evidence of absence
(`inconclusive-no-positive-control`) with a derived detection limit (rule of three over 40 sequenced colonies).

## Provenance and honesty conventions

- Every number carries a `source`/`locator`; values the pipeline computed are marked `derivedBy: portolan-ingest` with a `method`.
- Attribution the paper does not state is marked `proposedByConfidence: inferred` or `not-stated`.
- Known inconsistencies in the sources are written into `provenanceNotes`, not resolved silently.
- All statistics are the authors'. The pipeline never re-tests significance.
