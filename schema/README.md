# Portolan Negative-Results Record (NRR) v0.2

*Machine-readable successor to the v0.1 sketch. Files: `nrr-0.2.schema.json` (JSON Schema draft 2020-12),
`vocabularies.json` (controlled lists), `CHANGELOG.md` (what v0.2 changed and why). Validation: `nrr.schema.validate`
applies the schema and the informativeness rule. Serialisation: canonical JSON is the source of truth; `nrr.crate.to_crate`
derives an RO-Crate 1.2 JSON-LD with PROV terms.*

## 1. Record kinds

- **path**: a project or campaign (a Stacks pub, a Robin discovery cycle). Carries the question, headline outcome,
  abandonment reasons, next steps, open questions, cost, sources, performers and `hasPart` (registry-derived).
- **attempt**: one experiment, one agent run, or one analysis. Carries `attemptType`, one or more `findings`, `stages`,
  `screened` items, `applicabilityConditions`, `invalidators`, `untriedBranches`, `cost`, sources and relations, and
  `isPartOf` its path.

Identity: `@id` = `urn:portolan:nrr:sha256:<sha256 of canonical JSON without @id, contentAddress, dateCreated, integrity, hasPart>`.

## 2. Sections (v0.1 letters kept)

| v0.1 | v0.2 fields | Notes |
|---|---|---|
| A identity, provenance | `@id`, `kind`, `profile`, `version`, `isNewVersionOf`, `dateCreated`, `license`, `sourceLicense`, `visibility`, `embargoUntil`, `studyId`, `slug`, `title`, `operator`, `performers[]`, `aiUseDeclaration`, `provenanceNotes[]` | `performers[]` replaces the single `agent`; each has `type` (software-agent, llm, person, organization, service) and `role`. |
| B question | `question`, `hypothesis`, `successCriteria`, `pathType`, `target[]`, `domainTags[]`, `attemptType` | `successCriteria` required: without it "negative" has no meaning. |
| C path | `stages[]` with `stage`, `performedBy[]`, `method`, `protocol`, `instrument[]`, `conditions`, `parameters`, `sourcesSearched[]`, `queries[]` (verbatim), `recordsFound`, `software[]`, `inputs[]`, `outputs[]`, times | PRISMA-S fields live on literature-search stages. |
| D screened items | `screened[]` with `label`, `identifier`, `type`, `proposedBy`, `decision`, `reason`, `score`, `references[]`, `statusAtCheck`; `screenedSummary` | Reasons are controlled; free text goes in `note`. |
| E outcome | `outcomeClass` (headline), `outcomeSummary`, `confidence{level, basis}`, `findings[]` | See section 3. |
| F reuse guidance | `applicabilityConditions`, `invalidators[]`, `untriedBranches[]{description, status, dataAvailable[]}`, `openQuestions[]`, `nextSteps[]`, `abandonmentReasons[]`, `cost` | `cost` is required; `{note: "not reported"}` is acceptable and honest. |
| G relations | `relations[]{type, target}`, `isPartOf`, `hasPart[]`, `sources[]{role, identifier, statusAtCheck, data[]}`, `entities[]` | Entities are the shared nodes (taxa, cell lines, genes, compounds, assays, agents, organisations) that link records across studies. |
| H integrity | `contentAddress`, `integrity{signature, signer, trustTier, injectionScreen, duplicateOf}`, `governance{humanSubjectData, biosecurityTier, complianceIds}` | Signing not implemented in the pilot. |

## 3. Finding

```
id, question, target{label, identifier, type}, outcomeClass, informativeness, informativenessReason,
failureModes[], effect{metric, value, unit, n, sem, direction, comparedTo, test, pValue, adjustedPValue, significant, perReplicate[]},
controls{positive{kind, label, expected, observed, passed}, negative{kind, ...}}, sensitivity, power, replicates{},
statistics, conditions{dose, ...}, proposedBy, proposedByConfidence, evidence[]{label, source, locator, values, quote, derivedBy, method, data[]},
nearestPriorResult, relatedFindings[], note
```

**Informativeness rule** (biology profile, now enforced): for a negative or inconclusive finding, `informative` requires
a passed positive control (`designated` or `internal-positive`), a clean negative control, and a `sensitivity` or `power`
statement. Otherwise the finding is `uninformative` and its `outcomeClass` must be one of `inconclusive-controls-failed`,
`inconclusive-underpowered`, `inconclusive-reagent-failed`, `inconclusive-no-positive-control`, `inconclusive`.
Positive and partial findings are `not-applicable`.

## 4. Vocabularies (see `vocabularies.json`)

`outcomeClass` (17), `failureMode` (materials, computation, wet-lab, evidence synthesis, hypothesis generation),
`screenedReason`, `screenedDecision`, `abandonmentReason`, `performerRole`, `performerType`, control kinds, `entityType`,
`sourceRole`, `relationType`, `stageName`, NISO JAV/CREC status terms plus `preprint-v{n}`, `reviewed-preprint`, `v1`,
`dataset`, `untriedBranchStatus`.

## 5. Identifiers used in the pilot corpus

NCBI Taxonomy (`NCBITaxon:9606`, `NCBITaxon:3055`), Cellosaurus (`RRID:CVCL_0145`), Chlamydomonas Resource Center strain
(`chlamycollection:CC-124`), HGNC (`HGNC:29`), UniProt (`uniprot:Q08431`), Phytozome loci (`phytozome:Cre04.g231026`),
PubChem (`pubchem:CID9863672`), MONDO (`MONDO:0100114`), Cell Ontology (`CL:0002586`), GO (`GO:0006909`), OBI
(`OBI:0000916`, `OBI:0003090`, `OBI:0302912`, `OBI:0002767`, `OBI:0003583`), ROR (`ror:052zd4v68`, `ror:01p9amb16`),
RRID software (`RRID:SCR_002285`, `RRID:SCR_015687`, ...), SRA/ENA run accessions, Zenodo file MD5s, vendor catalogue
numbers (`catalog:Sigma-Aldrich:126741`), agent ids (`agent:robin`, `agent:finch`).

## 6. Minimal valid attempt (abridged)

See `tests/factories.py` for a complete minimal record; the corpus in `out/records/` has full examples.
