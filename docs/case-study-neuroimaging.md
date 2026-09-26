# Third study: what a passing positive control and a dirty negative control taught us

*Portolan Software, 26 September 2026. Third study encoded into the pilot corpus, after the Robin/dAMD Nature paper and
the Arcadia Alcalase pub. Source: Kolb, Reitman, Lane et al. 2024, "Label-free neuroimaging in mice captures sensory
activity in response to tactile stimuli and acute pain", The Stacks, doi:10.57844/arcadia-b963-15ac, CC BY 4.0.*

## 1. Why this study was chosen

Out of 124 Arcadia publications screened, this one was picked for a single reason: it is the only candidate whose central
negative has a **positive control that passed** and a **negative control that did not stay clean**. The two studies
already in the corpus fail the informativeness rule in the other two ways, so this study was the test of whether the rule
*discriminates* or merely refuses.

It also pushed the model into three areas it had never touched: in vivo animal work with its own governance, imaging
rather than plate readers or sequencers, and a negative that is about consistency across trials rather than an effect size.

## 2. What the study did

Arcadia built a US$30,000 ultra-widefield microscope and imaged the whole mouse cortex through the intact skull, without
labels, using the natural autofluorescence of mitochondrial flavoproteins. Anaesthetized mice received three kinds of
stimulus: vibration on a paw, intradermal capsaicin (acute pain), and intradermal histamine (itch).

- **Touch** produced localized responses in the somatosensory area contralateral to the stimulated limb, about a 1-3%
  increase in autofluorescence after averaging 50 stimulations. Stimulating the other limb moved the response to the
  other hemisphere.
- **Capsaicin** produced widespread, oscillatory cortical activation for about ten minutes, absent from the paired
  vehicle injection in the same mouse.
- **Histamine** produced widespread bilateral activation too, but the patterns were inconsistent between trials, the
  magnitude was similar to the saline control, and the activation was not localized.

The project was iced with the reason #TechnicalGap, citing the itch result.

## 3. The corpus after three studies

| | |
|---|---|
| Records | 22 (3 paths, 19 attempts) |
| Findings | 138 |
| Validation errors | 0 |
| Entities | 111 |
| Studies | 3, across two operators and three organisms |

The neuroimaging study contributed 4 records and 9 findings: 6 positive and 3 `inconclusive-controls-failed`.

## 4. The result that mattered

Asking the store "which negatives in this corpus are not evidence of absence, and why?" now returns three studies with
three different diagnoses:

| Study | Finding | Positive control | Diagnosis |
|---|---|---|---|
| Arcadia Alcalase | no on-target HDR in 191 colonies | **none** | no positive control |
| Robin dAMD | Finch analysis of round 1 | designated, **failed** | positive control failed |
| Arcadia neuroimaging | no cortical signal for itch | internal, **passed** | negative control not clean |

This is what a rule earning its place looks like. The itch finding has the *best* positive control of the three, and it
is still uninformative, because the saline injection produced the same widespread activation as the histamine injection.
The experiment cannot distinguish the pruritogen from the needle. A registry that recorded "histamine: no effect" would
be publishing a claim the data does not support; a registry that recorded nothing would be throwing away a useful warning
to the next lab. The record says exactly what happened and exactly why it does not settle the question.

**The rule needed no changes to produce this.** The two tests written for it passed before any code was modified.

## 5. What the study broke, and what was added

Eight schema changes, all additive, logged as v0.2.1 in `schema/CHANGELOG.md`. The four that matter:

1. **`within-subject` negative control kind.** The control for tactile stimulation is the other hemisphere of the same
   animal in the same trial. That is neither a vehicle nor an untreated group, and the vocabulary had no word for it.
2. **`Stage.protocolAdaptations[]`.** The authors state that when they saw no tactile response they adjusted the focus,
   the stimulator position, the isoflurane level or the limb, and tried again, and that "in most cases, one or more of
   these steps resulted in a clear signal". They then used that signal as the gate for proceeding to the chemical
   stimuli. A result tuned into existence is not the same as a first-pass result. There was previously nowhere to record
   the tuning, and it directly affects how much weight the downstream positive control carries.
3. **ARRIVE reporting fields on a finding** (`blinding`, `randomization`, `preregistration`, `reportingGuideline`). The
   biology profile promised these in v0.1 and v0.2 never implemented them. Every answer in this study is "not stated" or
   "none". Recording the absence is the informative act, and it is only visible because the schema now asks.
4. **`DataPointer.runId`.** Every figure legend names a Data ID identifying one imaging run inside a checksummed Zenodo
   archive. The chain finding → figure → run id → archive → MD5 is now complete and machine-followable, which is the
   instrument-run pointer the biology profile promised and no earlier study supplied.

A ninth change was a process fix rather than a modelling one: adding vocabulary terms silently failed to reach the
schema, because the published schema file carries literal enums. Enums are now bound to `vocabularies.json` at load time
with a test that the published file matches.

## 6. What repeated from the earlier studies

**Deposited data nobody analysed, again.** The Zenodo deposit contains six archives. Five correspond to session dates
cited in the figure legends. The sixth, 2024-03-06 at 20.2 GB and the largest single raw session, is cited nowhere in
the publication. This is the same pattern as the exendin-4, MLN120B and "AT" sequencing runs sitting unanalysed in the
Robin study's SRA deposit. Two independent labs, two very different data types, and in both cases the only way to see it
is to compare the deposit manifest against the text. The query `open_branches` now returns four such items across two
studies.

**The negative is assembled, not stated.** As with the Robin screens, the itch claim had to be built from four places:
the results paragraph, the figure legends with their per-trial Data IDs, the Icebox statement, and the authors'
mechanistic hypothesis in Next steps. No single sentence contains the claim with its conditions and its caveats.

**Judgement calls are unavoidable and must be flagged.** Two encoding decisions carry this record, and both are recorded
in `provenanceNotes` rather than hidden: reading "magnitude similar to saline control" as a negative control that did not
stay clean, and treating the stated tactile gate as a per-session positive control even though the pub does not report a
tactile confirmation for each individual injection session.

## 7. What was easier than the earlier studies

Everything about provenance. The pub is CC BY 4.0 with a DataCite DOI, its data and code are deposited with checksums and
their own DOIs, contributors carry CRediT roles, the Icebox reason is a machine-readable tag, the next steps and open
questions are in labelled sections, and the figure legends carry per-trial run identifiers. Encoding it took a fraction
of the effort the Nature paper took, and nothing had to be withheld for licensing reasons.

That contrast is the argument for the Arcadia partnership in one paragraph. The flagship AI-science paper in Nature was
harder to ingest, less complete, and legally unpublishable as derived records. A small iced pub from a mid-size
non-profit lab was straightforward, complete, and free to redistribute.

## 8. What I would still challenge in this record

- I classified the tactile findings as positive with no positive control, on the grounds that the finding is positive and
  the rule does not apply. An experimentalist might argue that a first-pass literature expectation plus a within-subject
  spatial control is exactly a control structure and should be scored as one.
- The three histamine findings (two limbs plus an aggregate) may be double counting in an outcome tally. The aggregate is
  the claim the Icebox cites, so it earns a record; the per-limb findings carry the run pointers. A minimum viable record
  would probably collapse these.
- `signal-below-noise` is recorded as a failure mode on the authors' hypothesis, not on evidence. It is their proposed
  explanation, and the record marks it as a quote in the evidence block, but the failure mode itself reads as more settled
  than the pub intends.
