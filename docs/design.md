# Portolan NRR pilot ingest: design

*Portolan Software, 2026-09-25. Written before implementation; the assessment in `assessment.md` records what actually happened.*

## 1. Purpose and success criteria

Prove, with two real published studies, that the Portolan Negative-Results Record (NRR) data model can hold what a
published discovery attempt actually contains, in a form another agent can query. The user's success test:

> take data from two published articles, reformat it, link it and insert it into a DB in a format that can then be
> reused by other agents.

Concretely this pilot must deliver:

1. A **machine-readable schema** for the NRR (v0.2), because v0.1 exists only as prose tables. Records that do not
   validate against it do not count.
2. **Converters** that turn each study's published artefacts (paper text, supplementary tables, code repository,
   data deposits) into NRR records, with every value traceable to a source location.
3. A **corpus** of records for both studies, serialised as canonical JSON and as RO-Crate JSON-LD.
4. A **database** (SQLite) loaded from the corpus, plus demonstration queries phrased the way an agent would ask them.
5. **MCP deposit payloads** prepared as if the Portolan MCP server existed (the server itself is out of scope).
6. A **schema change log** driven by what the studies forced, and an honest **assessment**.

## 2. The two sources

### 2.1 Ghareeb et al. 2026, "A multi-agent system for automating scientific discovery", Nature 655:497–505

- DOI 10.1038/s41586-026-10652-y. Received 23 May 2025, published 19 May 2026, version of record 1 July 2026.
  Licence CC BY-NC-ND 4.0. Operator: FutureHouse / Edison Scientific, Inc.
- The system (Robin) proposes an in-vitro assay for a disease, proposes drug candidates, ranks them with an LLM judge,
  humans run the experiment, the Finch agent analyses the data, and the loop repeats. Applied to dry age-related
  macular degeneration (dAMD): assay = RPE phagocytosis; hits = Y-27632 (round 1), ripasudil (round 2), KL001
  (primary cells only); RNA-seq found ABCA1 up 3-fold. A comparison arm gave the same prompt to OpenAI Deep
  Research: 17 candidates, zero hits.
- Artefacts used: main text and Methods (HTML); Supplementary Information PDF (Table 1: 34 drugs with vendor,
  catalogue number and working concentration; Table 2: antibodies; Figs 1–20: prompts and gating); Supplementary
  Tables 3–10 workbook (per-well normalised MFI for round 1 ARPE-19, round 2 ARPE-19, RPE-SC screen; ablation
  reference checks; BixBench results); Reporting Summary; GitHub `Future-House/robin` at commit 4a5cce3 (sample
  run outputs for dAMD dated 2025-05-28 and 2025-05-29: literature reviews, 10 assay hypotheses, 59 + 30 candidate
  reports, pairwise judge outputs, ranked CSVs, Finch flow-cytometry results and trajectory metadata); GitHub
  `Future-House/finch` at commit aea66fd; NCBI SRA BioProject PRJNA1464762 (29 runs, ARPE-19 RNA-seq).
- Important provenance fact: the repository's dAMD run is a **re-run** made after the experiments. Its ranked
  candidates (avacincaptad, risuteganib, ...) are not the five the paper tested (exendin-4, fingolimod, MFGE8,
  Y-27632, AICAR+TUDCA). The Finch flow-cytometry results in the repository do analyse the real round-1 data. The
  records must say which is which.

### 2.2 Caddell et al. 2026, "Evaluation of Alcalase pretreatment for Chlamydomonas reinhardtii CRISPR knock-in", The Stacks

- DOI 10.57844/arcadia-pdu7-q2zz (DataCite, publisher Astera Institute), published 11 Sep 2026, CC BY 4.0, pub type
  "Informative failure", status "Iced" (#TechnicalGap, #StrategicMisalignment), feedback requested. Operator: Arcadia
  Science. Data: Zenodo 10.5281/zenodo.22238548 (10 files with MD5 checksums).
- One experiment, one experimenter, one reagent batch: 16 conditions (Alcalase vs GeneArt × flask vs plate × 4
  guides on 3 loci) plus controls. Alcalase permeabilised walls (22% leakage vs 11% GeneArt vs 6% no enzyme) but
  cut viability at least 10-fold, gave near-background NAT-resistant colonies (0–16 CFU; 6 of 8 conditions at
  background), and 0/191 colonies by PCR and 0/40 by amplicon sequencing showed on-target editing under either
  reagent. Colony colour could not serve as a knockout screen.
- Artefacts used: full text with Tables 1–5 (guides with Phytozome locus ids, primers, conditions, colony counts,
  PCR/sequencing summary), the two Zenodo CSVs (wall permeability; per-colony index with PCR band and sequencing
  result), Zenodo file manifest, DataCite metadata.

## 3. Data model decisions (NRR v0.2)

The v0.1 sketch (core sections A–H, biology profile) is kept. The two studies forced these changes; each is
recorded with its reason in `schema/CHANGELOG.md`.

1. **Three record kinds, one schema.** `path` (a project or campaign; Arcadia's pub, Robin's whole cycle),
   `attempt` (one experiment, one agent run, one analysis; the unit of deposit), and attempts carry one or more
   `findings`. v0.1 asked "is the unit one attempt or one path?"; the answer from real data is both, with
   `isPartOf` from attempt to path. Arcadia's single experiment answers six different questions with different
   outcome classes; forcing one `outcomeClass` per record would either lose five or duplicate the protocol six times.
   `outcomeClass` stays at record level as the headline; `findings[]` carry the detail, each with its own
   `question`, `outcomeClass`, `informativeness`, `failureModes`, `effect`, `controls`, and `evidence`.
2. **Stage-level performers.** Robin generated hypotheses and analysed data; humans ran the wet lab; an LLM judge
   ranked; another LLM wrote the judge prompt. `agent` at record level is not enough. Every path stage has
   `performedBy[]` with `role` (hypothesis-generation, literature-search, ranking, experiment-execution,
   data-analysis, prompt-authoring, copy-editing) and, for software agents, `model`, `provider`, `version`,
   `commit`, `platformJob`, `trajectoryIds`.
3. **Controls with a kind, and a machine-checkable informativeness rule.** In Robin's round 1 the designated positive
   control (MFGE8) passed in the human analysis (1.46×) and failed in the Finch analysis (1.04×), while Y-27632 gave
   1.6–2.8×. Arcadia had a positive control for delivery (GeneArt) but none for editing. So `controls.positive.kind`
   ∈ {designated, internal-positive, none}, `controls.negative.kind` ∈ {vehicle, no-treatment, background, none},
   and the rule is a pure function `informativeness(finding)`: `informative` needs positive control passed (designated
   or internal), negative control clean, and sensitivity or power stated; otherwise the finding is `uninformative` and
   its outcome class must be an `inconclusive-*` value. New class `inconclusive-no-positive-control` for Arcadia's
   editing question (absent is not the same as failed).
4. **Screened items carry provenance and scores.** For hypothesis generation the screened items are compounds and
   assays, not papers. Each gets `identifier` (PubChem, UniProt, OBI), `proposedBy` (which agent or arm proposed it;
   Robin round 1, Robin round 2, OpenAI Deep Research, or `not-stated` when the paper does not say), `decision`
   (included = tested, deferred = ranked but not tested, excluded), `reason`, and `score` {method, value, rank,
   comparisons}. New reasons: `not-selected-for-testing`, `positive-control`, `negative-control`,
   `duplicate-candidate`, `human-reviewer-deselected`.
5. **Structured data pointers.** `evidence.data[]` = {repository, accession or url, checksum, label, role}. SRA
   runs with MD5, Zenodo files with MD5, supplementary tables with sheet and row keys.
6. **Abandonment and open questions.** Arcadia's Icebox tags map to `abandonmentReasons[]` (technical-gap,
   strategic-misalignment, resource-constraint, superseded, safety) and its "Weigh in" questions to
   `openQuestions[]`. These are the most reusable part of an iced project for an agent deciding whether to pick it up.
7. **Unanalysed deposited data is an untried branch.** SRA holds exendin-4, MLN120B and "AT" RNA-seq samples the paper
   never analyses. `untriedBranches[]` entries may carry `dataAvailable` pointers.
8. **AI-use declaration and source licence.** `aiUseDeclaration` (free text plus tool list) for both studies;
   `sourceLicense` on the record so that CC BY-NC-ND sources (Nature) are handled differently from CC BY (Stacks).
9. **Status at check for the record's own sources.** Every DOI the record depends on (source publication, data
   DOI, cited prior art) carries `statusAtCheck` from Crossref or DataCite at ingest time, re-checkable.
10. **Provenance caveat field.** `provenanceNotes[]` on a record for facts like "repository run is a re-run" or
    "candidate attribution inferred from table order". Registries that cannot say "we are not sure" will be trusted
    less, not more.

What is *not* changed: RO-Crate 1.2 packaging, PROV relations, NISO JAV/CREC status terms, PRISMA-S literature
fields, content addressing, embargo and visibility, the biology identifier table.

## 4. Corpus plan

Robin/dAMD (operator FutureHouse, source Nature paper):

| id (suffix) | kind | attemptType | headline outcome |
|---|---|---|---|
| robin-damd-path | path | – | positive (two hits, one target) |
| robin-damd-assay-selection | attempt | hypothesis-generation | positive; 10 assays screened, 9 deferred |
| robin-damd-candidates-r1 | attempt | hypothesis-generation | positive; 59 sample-run candidates deferred, 5 paper candidates included |
| robin-damd-screen-r1-arpe19 | attempt | wet-lab | partial; Y-27632 hit, 3 negatives, MFGE8 control |
| robin-damd-finch-flow-r1 | attempt | computational | positive; 5 trajectories + consensus, control discrepancy noted |
| robin-damd-candidates-r2 | attempt | hypothesis-generation | positive; 30 sample-run candidates deferred, 13 paper candidates included |
| robin-damd-screen-r2-arpe19 | attempt | wet-lab | partial; ripasudil hit, 12 negatives, 2 controls |
| robin-damd-rnaseq-arpe19 | attempt | wet-lab + computational | positive; ABCA1; 29 SRA runs; 3 untried branches |
| robin-damd-screen-rpesc | attempt | wet-lab | partial; ripasudil, Y-27632, KL001 hits; ~55 negatives incl. all Deep Research |
| deep-research-damd-candidates | attempt | hypothesis-generation (OpenAI Deep Research) | negative; 17 candidates, 0 hits |
| robin-ablation-reference-check | attempt | computational (evaluation) | positive; hallucinated-reference rates per configuration |

Arcadia/Alcalase (operator Arcadia Science, source Stacks pub):

| id (suffix) | kind | attemptType | headline outcome |
|---|---|---|---|
| arcadia-alcalase-path | path | – | abandoned (iced); 3 next steps; 3 open questions |
| arcadia-alcalase-wall-permeability | attempt | wet-lab | positive, n=1 |
| arcadia-alcalase-viability | attempt | wet-lab | negative-not-achievable / toxicity |
| arcadia-alcalase-transformation | attempt | wet-lab | negative-not-achievable / transformation-failed |
| arcadia-alcalase-hdr-knockin | attempt | wet-lab | inconclusive-no-positive-control (0/40, 0/191) |
| arcadia-alcalase-visual-screen | attempt | wet-lab | negative-not-achievable / phenotype-nonspecific |
| arcadia-alcalase-culture-format | attempt | wet-lab | inconclusive |

Linking: shared entity nodes (taxa, cell line, strain, genes, compounds, assays, instruments, software, agents,
operators) live in one entity table; both studies reference them by the same identifiers; PROV relations connect
attempts to paths and analyses to the experiments they analysed; cross-study queries run over the same tables and
vocabularies.

## 5. Pipeline

```
raw/            vendored inputs (paper-derived tables, repo outputs, ENA table, Zenodo CSVs, supp workbook)
curated/        hand-transcribed tables with a provenance column (which table, page, figure)
ingest/robin    converter: raw + curated -> list[Record]
ingest/alcalase converter: raw + curated -> list[Record]
core/           schema loading, validation, informativeness rule, content address, crate writer, resolver (cached)
out/records/    <id>.json (canonical) and <id>/ro-crate-metadata.json
out/mcp/        deposit payloads + manifest
out/portolan.sqlite  loaded DB; queries.sql + demo output
```

Identifier resolution (PubChem, OLS, Cellosaurus, HGNC, UniProt, ROR, RRID, Crossref, DataCite) runs once online and
writes `curated/identifiers.json`; converters and tests read the cache only.

## 6. MCP contract (prepared, not built)

Tools: `nrr_deposit(record, crate)`, `nrr_get(id)`, `nrr_search(text, filters)`, `nrr_prior_art(targets,
conditions)`, `nrr_recheck_status(id)`. Resources: `nrr://record/{id}`, `nrr://vocab/{name}`, `nrr://schema/0.2`.
Payload = canonical record JSON. Details in `docs/mcp-contract.md`.

## 7. Out of scope

Building the MCP server; signing keys and embargo workflow; ingesting the 49 MB Finch trajectory dumps beyond
metadata; re-analysing raw data (all statistics are the authors'; the only derived numbers are means and SEMs of
published per-well values and a rule-of-three detection limit, both labelled as derived).

## 8. Assumptions made because the user was unavailable

- Keep v0.1 field names where they exist; add, do not rename.
- Records are `public`; source licences are recorded; quotations are kept short.
- Where the paper is internally inconsistent (candidate counts per round), the record carries the paper's own
  statements plus a provenance note rather than a resolved number.
