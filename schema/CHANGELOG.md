# NRR schema change log

## v0.2 (2026-09-25) — changes forced by two real studies

Driven by encoding Ghareeb et al. 2026 (Nature, Robin/dAMD) and Caddell et al. 2026 (The Stacks, Alcalase/Chlamydomonas).
The v0.1 sketch is in `../outreach/nrr-schema-sketch-v0.1.md` and `../outreach/nrr-biology-profile-v0.1.md`; nothing there is
renamed. v0.2 is the first machine-readable version (`nrr-0.2.schema.json`, `vocabularies.json`).

| # | Change | Forced by |
|---|---|---|
| 1 | **Two record kinds**: `path` (project or campaign) and `attempt` (experiment, agent run, analysis). Attempts point up with `isPartOf`; paths list `hasPart`, which is registry-derived and outside the content address (Merkle links go one way). | v0.1 open question 1. Arcadia's pub is one path with six distinct questions; Robin's paper is one path with ten attempts. |
| 2 | **`findings[]` on an attempt**, each with its own `question`, `target`, `outcomeClass`, `informativeness`, `controls`, `effect`, `evidence`. Record-level `outcomeClass` stays as the headline. | One Alcalase experiment answered six questions with four different outcome classes; one Robin screen holds 60 arms. One outcome per record would lose or duplicate. |
| 3 | **Controls carry a `kind`**: positive ∈ {designated, internal-positive, none}; negative ∈ {vehicle, no-treatment, background, isotype, none}. | Robin round 1: designated control MFGE8 passed in the human analysis and failed in Finch's, while Y-27632 gave 1.6-2.8x. Arcadia: GeneArt is an internal positive for delivery; no positive control existed for editing. |
| 4 | **Informativeness rule as code** (`nrr.rules.informativeness`): informative needs a passed positive control (designated or internal), a clean negative control, and a stated sensitivity or power; otherwise uninformative, and the outcome class must be `inconclusive-*`. Validation enforces it. New class `inconclusive-no-positive-control`. | Arcadia HDR (0/40 edits, no editing control) must not be read as "HDR does not work". Absent is not the same as failed. |
| 5 | **Stage-level performers** with `role` (hypothesis-generation, literature-search, ranking, prompt-authoring, experiment-execution, data-analysis, copy-editing, ...) and, for software, `model`, `provider`, `commit`, `platformJob`, `trajectoryIds`. | Robin: o4-mini synthesised, Claude 3.7 Sonnet judged, Gemini wrote the judge prompt, Finch analysed, humans pipetted. Arcadia: humans did the science, four LLMs edited prose. |
| 6 | **Screened items** gain `proposedBy`, `proposedByConfidence` (stated / inferred / not-stated), `score` {method, value, rank, comparisons, wins} and new reasons (`selected-for-testing`, `top-ranked`, `not-selected-for-testing`, `positive-control`, `tested-in-comparator-arm`, `not-stated`). Types include compounds, proteins and assays, not only papers. | Robin ranks 30-59 candidates by Bradley-Terry strength and tests a handful; the paper does not state which arm proposed ~25 of the 60 RPE-SC compounds. |
| 7 | **Structured data pointers** (`DataPointer`: repository, accession, url, checksum, size, role) on sources, evidence, stages and untried branches. | 29 SRA runs with MD5s; 10 Zenodo files with MD5s; supplementary sheets with row keys. |
| 8 | **`untriedBranches[].status`** ∈ {proposed-by-authors, data-deposited-not-analysed, inferred-by-ingest} with optional `dataAvailable` pointers; **`abandonmentReasons[]`**, **`openQuestions[]`**, **`nextSteps[]`**. | SRA holds exendin-4, MLN120B and "AT" RNA-seq that the paper never analyses. Arcadia's Icebox tags and "Weigh in" questions are the most reusable part of an iced project. |
| 9 | **`aiUseDeclaration`**, **`sourceLicense`**, **`provenanceNotes[]`**. | Both papers declare AI use in different forms. Nature's CC BY-NC-ND licence constrains what a derived record may carry. Repository trajectories are re-runs, candidate counts disagree between text and tables: the record has to be able to say so. |
| 10 | **`statusAtCheck` on every DOI-bearing source**, filled at ingest from Crossref or DataCite (version, integrity, assertedBy, checkedAt). | Both studies cite prior art whose status a re-reader should re-check; the Stacks DOI is DataCite-registered, so a Crossref-only check would miss it. |
| 11 | **Evidence can be derived**: `evidence[].derivedBy` and `method` mark values computed by the ingest (means, SEMs, rule-of-three bounds, Bradley-Terry re-computation) versus values transcribed from the source. | Supplementary tables give per-well values, not summaries; the assay ranking CSV ships pairwise judgements, not scores. |
| 12 | Vocabulary additions: failure modes `phenotype-nonspecific`, `selection-escape`, `low-editing-efficiency`, `hallucinated-reference`, `no-hit-in-screen`; attempt type `evaluation`; performer types `llm`, `service`. | Alcalase colour screen; Robin ablations. |

Not changed: RO-Crate 1.2 packaging, PROV relations, NISO JAV/CREC terms, PRISMA-S literature fields, content addressing
(`sha256` over canonical JSON without identity fields), embargo and visibility, the biology identifier table.

Open after v0.2:
- Signing and key registration are stubbed (`integrity.signature: null`, `trustTier: pilot-unsigned`).
- `hasPart` and the cross-record `relations` that would create hash cycles are registry-maintained; the schema does not yet say which relation types are allowed to point "up".
- Finding-level `relatedFindings` uses `slug#finding-id` strings; a registry would resolve these to addresses.

## v0.2.1 (2026-09-26) — changes forced by a third study

Driven by encoding Kolb, Reitman, Lane et al. 2024, *Label-free neuroimaging in mice captures sensory activity in
response to tactile stimuli and acute pain* (The Stacks, doi:10.57844/arcadia-b963-15ac). The study was chosen because
its itch arm had a *passing* positive control and a negative control that did not stay clean, which is the one clause of
the informativeness rule that neither earlier study exercised. Additive only; nothing was renamed.

| # | Change | Forced by |
|---|---|---|
| 13 | **`within-subject` negative control kind.** | The control for tactile stimulation is the ipsilateral hemisphere of the same animal in the same trial: stimulating the other limb moves the response to the other hemisphere. That is neither a vehicle nor an untreated group. |
| 14 | **ARRIVE-style reporting fields on a finding**: `blinding`, `randomization`, `preregistration`, `reportingGuideline`. The biology profile v0.1 specified these; v0.2 had not implemented them. | First in vivo animal study in the corpus. All four answers here are "not stated" or "none", and recording that absence is the informative act. |
| 15 | **`Stage.protocolAdaptations[]`.** | The authors adjusted focus, stimulator position, isoflurane level or limb and retried until a tactile signal appeared, then used that signal as the gate for proceeding. A result obtained after tuning is not the same as a first-pass result, and there was nowhere to say so. |
| 16 | **`DataPointer.runId`.** The biology profile v0.1 promised instrument run pointers; this is the first study that supplies them. | Every figure legend names a Data ID such as `2024-02-29/Zyla_5min_RHLstim_2son4soff_1pt25pctISO_1`, which identifies one imaging run inside a checksummed session archive. Finding → figure → run id → archive → MD5 is now a complete chain. |
| 17 | **Failure modes `irreproducible-across-trials` and `signal-below-noise`.** | "The activity patterns were inconsistent between trials"; and the authors' own hypothesis that too few itch-responsive neurons produce too little autofluorescence to exceed noise. |
| 18 | **`anatomicalStructure` entity type**, and `note` on an entity. | Brain regions (UBERON). The note field records that no exact OBI term exists for label-free flavoprotein autofluorescence imaging, so the nearest exact match (a CHMO term) was used. |
| 19 | **CRediT performer roles** `validation`, `methodology`, `software`. | Arcadia credits contributors with CRediT roles; three were missing from the vocabulary. |
| 20 | **Enums are bound to `vocabularies.json` at load time** (`nrr.schema.ENUM_BINDINGS`, `sync_enums`), with a test that the enums inlined in the published schema file match. | Adding vocabulary terms silently failed to reach the schema, because the schema file carries literal enums so that it can be published standalone. The two can no longer drift. |

**Confirmed without change:** the informativeness rule itself. The two rule tests written for this study passed before any
code was modified: a dirty negative control already produced `uninformative` with the reason "negative control not clean",
and already mapped to `inconclusive-controls-failed` rather than to the no-positive-control class. All three clauses of the
rule have now fired on real published data, each in a different study.
