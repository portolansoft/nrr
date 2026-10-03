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

## v0.2.2 (2026-09-26) — changes forced by a fourth study

Driven by encoding Cheveralls et al. 2026, *Leave-one-batch-out cross-validation reveals strong batch effects in Raman
spectroscopy of yeast cultures* (The Stacks, doi:10.57844/arcadia-xdmk-yq0w). Chosen because it is a purely computational
negative in which the controls are not reagents: the positive control is a different prediction task on the same data, and
the negative control is an adversarial task predicting a label that should carry no signal. Additive, plus one deliberate
narrowing of the rule.

| # | Change | Forced by |
|---|---|---|
| 21 | **`known-positive-task` positive control kind.** | The control that shows the pipeline works is species classification on the same spectra, run through the same processing and the same cross-validation. It is not a reagent, a genotype or another arm of the same assay. |
| 22 | **`adversarial-label` negative control kind.** | The control that shows the data is confounded is a classifier trained to predict which plate a spectrum came from. Plates are end-to-end replicates, so the label carries no biology and the expected result is chance. Scoring above chance means the control did not stay clean. This generalises to permutation tests, label shuffling and sham conditions. |
| 23 | **`train-test-leakage` failure mode.** | The authors declare that their batch correction was applied once to the whole dataset rather than per training fold, so the corrected estimates are not valid estimates of generalisation to unseen plates. |
| 24 | **`Effect.range`.** | Results are reported as a median across cross-validation folds with a range, for example MCC 0.32 (range 0.19-0.42). `sem` and `sd` could not express that. |
| 25 | **`refuted` is no longer subject to the control requirement** (`nrr.rules`). | The study's own headline number, MCC 0.79 under standard cross-validation, is recorded as `refuted`: the study demonstrates it reflects experimental batch rather than strain biology. An affirmative refutation is judged on the refuting analysis, not on whether the run being refuted carried controls. `negative-not-replicated` deliberately keeps the requirement, because a failure to replicate is still an absence of evidence. |

**What the study confirmed without change.** The rule's three clauses were already sufficient, and the fourth distinct
diagnosis in the corpus came out of them unmodified: after batch correction both controls behave and the only thing
missing is a detection limit, so the finding is `inconclusive-underpowered` with the reason "no sensitivity or power
statement" alone. That matches the authors' own caveat that the dataset is small and the strains may be too similar.

**Diagnoses now observed across four studies:**

| Diagnosis | Study | Finding |
|---|---|---|
| no positive control | Arcadia Alcalase | no on-target HDR in 191 colonies |
| positive control failed | Robin dAMD | Finch analysis of round 1 |
| negative control not clean | Arcadia neuroimaging, Arcadia Raman | itch response; strain classification before batch correction |
| no sensitivity or power statement | Arcadia Raman | strain classification after batch correction |

## v0.2.3 (2026-09-26) — a convergence test

Driven by encoding Morin, Patton et al. 2024, *A structurally divergent actin conserved in fungi has no association with
specific traits* (The Stacks, doi:10.57844/arcadia-9768-f6c5). This study was selected to try to falsify the claim that the
model is converging, so the criterion was set before encoding: **converging** if two or fewer additive changes and nothing
structural; **not converging** if any structural change or more than four changes.

The study shares almost nothing structurally with the four before it. There is no experiment. The unit of observation is a
species rather than a cell, an animal or a spectrum. The evidence is evolutionary model selection over a phylogeny, scored
by Akaike information criterion rather than by a p-value or an effect size. The negative takes the form "no association
with any of six traits", a multiple-hypothesis shape the corpus did not contain. The absence of the protein is inferred
from a database protein count rather than observed.

**Result: two changes, both single vocabulary terms, nothing structural.**

| # | Change | Forced by |
|---|---|---|
| 26 | **`phenotype` entity type.** | The six fungal traits are the study's primary variables: growth form, trophic mode, ascus dehiscence, auxin-responsive promoter, spore length, spore width. There was no type for a species-level trait, and two earlier studies had already worked around the gap by typing a phenotype as an assay. |
| 27 | **`data-curation` performer role.** | A CRediT role used by this study's lead author and absent from the vocabulary, in the same family as `validation`, `methodology` and `software` added in v0.2.1. |

**What did not need to change.** Findings held six per-trait results plus an aggregate without alteration. `Effect` carried
an AIC model comparison through `value`, `comparedTo` and `test`, and a phylogeny-corrected regression slope through
`pValue`, with no new fields. The trait databases the study depends on (Fun Fun, TimeTree, FUNGuild, UniProt, AlphaFold,
NCBI Taxonomy) went into `stage.sourcesSearched`, a field designed for literature databases that carried reference
databases unchanged. `protocolAdaptations`, added for a mouse troubleshooting loop in v0.2.1, carried the post-hoc
recoding of trait categories. `resource-constraint` already existed as an abandonment reason. `insufficient-data` already
existed as a failure mode.

**Change count by study:** 12, then 8, then 5, then 2. Nothing structural has been required since the first study.

**Diagnoses now observed across five studies:**

| Diagnosis | Study |
|---|---|
| no positive control | Arcadia Alcalase |
| positive control failed | Robin dAMD |
| negative control not clean | Arcadia neuroimaging, Arcadia Raman |
| no sensitivity or power statement | Arcadia Raman |
| no positive control, no negative control, and no sensitivity statement | Arcadia divergent fungal actin |

The last row is a new combination rather than a new clause. It is also the only case where the rule surfaced a limitation
the authors do not list: they attribute their null to trait coverage and to errors in calling the protein absent, and do
not note that without a positive control a null result cannot be separated from a method that would not have detected an
association at these sample sizes.

## v0.2.4 (2026-10-02) — changes forced by four ACS chemistry studies

The first studies outside biology, all American Chemical Society articles under CC BY 4.0, chosen from the screen in
`../research/acs-negative-results-candidates-2026-10-02.md` to exercise the materials profile sketched in v0.1 and never
used against a real paper. Encoded one at a time; the change count per study is appended to the series 12, 8, 5, 2.

### Study 6: Altundal et al. 2025, computationally guided synthesis of aluminosilicate STF and IFR zeolites

Driven by encoding Altundal, Galvez-Llompart, Cantin et al. 2025, *Lessons from Failed Attempts of Computationally Guided
Synthesis of Aluminosilicate STF and IFR Zeolites in Hydroxide Media* (Chem. Mater. 37, 9689-9702,
doi:10.1021/acs.chemmater.5c01751). A whole pipeline: machine-learning classifiers, de novo design and synthesis-energy
ranking over more than 10,000 organic structure-directing agents, three taken to the bench, every hydrothermal synthesis
amorphous or the wrong phase.

| # | Change | Forced by |
|---|---|---|
| 28 | **`material` entity type.** | The study's targets and products are zeolite framework types (STF, IFR, AEI, CHA, MTW, MOR), identified by IZA three-letter codes. A framework is neither a compound nor a reagent: it is a crystalline topology that many compositions can adopt. The v0.1 materials profile anticipated this and v0.2 had no type for it. |

**Change count for this study: 1.** Nothing structural.

**What did not need to change.** Three failure modes written for materials in v0.1 and never used (`phase-not-formed`,
`impurity-phase`, `decomposition`) fired for the first time, on real syntheses. `refuted` carried the computational
predictions, judged on the authors' own verdict in the Conclusions, with `relatedFindings` pointing at the syntheses that
refute them. `screened` with `score.rank` carried the 18 shortlisted OSDAs and which three were synthesised. `Stage`
with `stage: ranking` and `sourcesSearched` carried a 1,190-entry chemistry database as naturally as it carried PubMed.

**Judgement recorded, not resolved by code.** The synthesis negatives are `inconclusive-no-positive-control`: no OSDA known
to crystallise a zeolite was run through the same hydroxide protocol, no XRD detection limit is stated, and the classifier
sensitivity and specificity in SI Tables S7 to S12 describe the screen, not the synthesis, so they do not count as a
sensitivity statement. The predictions are therefore refuted by experiments that are themselves uninformative negatives
for their own targets, and two of the three OSDAs degraded during synthesis. Both verdicts are kept and the link between
them is recorded; the record says in `provenanceNotes` that what is refuted is the pipeline's prediction of the outcome
under the conditions actually run, not the thermodynamic ranking as such.
