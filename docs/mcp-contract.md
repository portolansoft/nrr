# Portolan MCP contract (prepared, not built)

*What the pilot files assume about the server that will consume them. Tool names follow MCP conventions; payloads are the
canonical NRR v0.2 JSON. The SQLite store built by `build.py` is the storage layer the server would wrap; `db/queries.sql`
holds the query shapes.*

## Tools

| tool | arguments | returns | notes |
|---|---|---|---|
| `nrr_deposit` | `profile`, `idempotencyKey` (= record `@id`), `record` (canonical JSON), `crate` (RO-Crate JSON-LD), `visibility`, `attachments[]` | `{id, status: created|exists|rejected, problems[]}` | Validates against the profile schema and the informativeness rule; rejects with the same messages `nrr.schema.validate` produces. Idempotent on the content address. Paths may be deposited before their attempts; `hasPart` is recomputed from `isPartOf`. |
| `nrr_get` | `id` or `slug`, `format: record|crate` | the record | Re-checks `statusAtCheck` for DOI sources older than the configured window and flags drift in `statusDrift[]`. |
| `nrr_search` | `text`, filters `{studyId, kind, attemptType, outcomeClass, informativeness, entityId, performer, dateFrom}` | ranked list of `{id, slug, title, outcomeClass, snippet}` | FTS over title, question, summary, applicability and findings (query `search`). |
| `nrr_prior_art` | `targets[]` (labels or identifiers), `conditions{}` (organism, cell model, assay, dose) | findings and screened items touching the targets, each with outcome, informativeness, dose, applicability and evidence pointers | The question an agent asks before spending money (queries `prior_art`, `prior_art_by_identifier`, `negatives_for_target`). |
| `nrr_open_branches` | `studyId?`, `status?` | untried branches, open questions, next steps, with data pointers | Where to pick work up (query `open_branches`). |
| `nrr_recheck_status` | `id` | updated `statusAtCheck` per DOI | Crossref `update-to`, DataCite state; never only at write time. |
| `nrr_entities` | `entityId` or `type` | records mentioning the entity | Cross-study linking on shared identifiers (query `by_entity`). |

## Resources

- `nrr://record/{id}` (canonical JSON), `nrr://crate/{id}` (JSON-LD), `nrr://schema/0.2`, `nrr://vocab/{name}`,
  `nrr://study/{studyId}` (manifest of a study's records).

## Files in `out/mcp/`

- `manifest.json`: record list in deposit order with counts and the unresolved-identifier list.
- `deposits/<slug>.json`: one `nrr_deposit` call each, `{"tool": "nrr_deposit", "arguments": {...}}`.

## Trust and governance hooks the server must add

- Signatures (operator key plus agent key) and `trustTier`; the pilot deposits are unsigned.
- Embargo enforcement from `visibility` and `embargoUntil`.
- Injection screening of quoted text (`integrity.injectionScreen`).
- Licence-aware serving: records derived from NC-ND sources carry `sourceLicense` and quote at most short phrases.
