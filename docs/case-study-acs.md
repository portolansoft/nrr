# Studies six to nine: four ACS chemistry papers, the first outside biology

*Portolan Software, 2 October 2026. Four American Chemical Society articles, all CC BY 4.0, chosen from the screen in
`../research/acs-negative-results-candidates-2026-10-02.md` and encoded one at a time. Full text came from Europe PMC
(`pubs.acs.org` refuses scripted fetches); every Supporting Information PDF was read and its tables transcribed by hand
with a locator per row. Nothing in this document is a number from memory: counts come from the build and the test run of
the session that wrote each section.*

The convergence test closed with one untested direction: "Everything so far is biology. A materials or chemistry study is
the obvious next falsification attempt, and the materials profile in v0.1 has never been exercised against a real paper."
These four are that attempt. Each section states why the study was chosen, what the record looks like, what judgement
calls were made and where they are written down, and what the study broke or did not. The change count per study is
appended to the series 12, 8, 5, 2 at the end.

## 1. Zeolite STF and IFR: a computational pipeline refuted by three syntheses

*Altundal, Galvez-Llompart, Cantin et al. 2025, "Lessons from Failed Attempts of Computationally Guided Synthesis of
Aluminosilicate STF and IFR Zeolites in Hydroxide Media", Chem. Mater. 37, 9689-9702, doi:10.1021/acs.chemmater.5c01751,
PMC12747119. Study id `acs-zeolite`.*

### Why this one first

It is the one most likely to break the model. The attempt is not an experiment but a pipeline: three machine-learning
classifiers and two de novo design algorithms over a 1,190-entry database of organic structure-directing agents (OSDAs)
plus thousands of designed ones, a synthesis-energy ranking across 18 to 22 competing frameworks, three OSDAs synthesised,
and 42 hydrothermal phase determinations that never gave the target. The research note asked two questions of it: can a
record hold a computational prediction refuted by experiment, and do the classifiers' own sensitivity and specificity
count as the sensitivity statement the informativeness rule demands. It also has no positive-control synthesis, which the
rule should catch.

### What the record looks like

| Record | Kind | Headline | Findings |
|---|---|---|---|
| `acs-zeolite-path` | path, mixed | `negative-not-achievable` | 4 attempts |
| `acs-zeolite-osda-screen` | computational | `refuted` | 10: the E_syn landscape, STF and IFR candidate counts, a de novo negative, three classifier validations, three predictions marked refuted |
| `acs-zeolite-stf-synthesis` | wet-lab | `inconclusive-no-positive-control` | 16 phase determinations, all amorphous; OSDA degraded |
| `acs-zeolite-ifr-synthesis-qg001780m` | wet-lab | `inconclusive-no-positive-control` | 12 determinations, all amorphous; OSDA degraded |
| `acs-zeolite-ifr-synthesis-qg001780m2` | wet-lab | `inconclusive-no-positive-control` | 14 determinations: amorphous, MOR, ZSM-12 (MTW), dense; OSDA 97 % intact |

Every one of the 42 rows in SI Tables S18, S20, S21 and S22 is an evidence item with its table and entry as locator. The
18 shortlisted OSDAs from SI Tables S14 to S17 are `screened` items with the target's rank as score, and the three that
were synthesised are `included` with reason `selected-for-testing`. The classifier matrices in SI Tables S7 to S12 are
findings in their own right: Model 2 has 99 % specificity and 21 % sensitivity on its training set and recognised none of
the eight STF-directing OSDAs in its external set.

### The judgement calls, and where they are written

**The synthesis negatives are inconclusive, and the classifier metrics do not rescue them.** No OSDA known to crystallise
a zeolite was run through the same hydroxide protocol, no OSDA-free gel was run, and powder XRD is reported with no
detection limit for a minority crystalline phase. The rule fires all three clauses at once, the same combination as the
divergent fungal actin study. The research note floated the idea that the models' sensitivity and specificity might stand
in for the sensitivity statement. They do not: they describe the classifier's recall on literature OSDAs, not whether the
synthesis could have shown a crystalline phase had one formed. That reasoning is in the path's `provenanceNotes` and in
each synthesis finding's `controls` notes.

**The predictions are `refuted`, on the authors' own verdict.** The Conclusions say "our predictions from calculations must
be considered a failure", and each of the three predicted phase orders (CHA, AEI, then STF or IFR) is a finding of class
`refuted` with `relatedFindings` pointing at the synthesis finding that refutes it. This exposes something the Raman study
did not: the refuting evidence is itself an uninformative negative for its own target, and two of the three OSDAs were
shown by NMR to degrade in the mother liquor. What is refuted is the pipeline's prediction of the outcome under the
conditions actually run, not the thermodynamic ranking as such. The record says exactly that, in the finding `note` and
in the screen's `provenanceNotes`, rather than picking one verdict.

**Source inconsistencies kept, not resolved.** Main-text Table 2 reports QG001780m2 as "amorphous" and "amorphous + MTW";
the SI tables it cites also list mordenite and dense phases, which neither Table 2 nor the Discussion mentions. The SI
says a "cyclohexyl-derived" cation was made in place of the pyridine-containing design; the compound named, characterised
and shown in Table 2 is the N-benzyl (phenyl) cation. The STF OSDA was a mixture of four diastereomers of which the
computed isomer was about a quarter, and its elemental analysis is five points of carbon off the calculated value. All four
are in `provenanceNotes`.

### What it broke

One vocabulary term: `material` as an entity type (change 28). A zeolite framework type is a crystalline topology
identified by an IZA code, not a compound, and v0.2 had nothing for it. Everything else held. Three failure modes written
for materials in v0.1 and never used, `phase-not-formed`, `impurity-phase` and `decomposition`, fired for the first time
on real syntheses. `stage: ranking` and `sourcesSearched`, built for PRISMA-style literature search, carried a chemistry
database and a reagent catalogue unchanged. `refuted` plus `relatedFindings` carried prediction-versus-outcome without a
new relation.

### What it did not test

The study has no deposited data, which is normal for ACS and a point for the CTO conversation: the only machine-unfriendly
place its evidence lives is a 39-page PDF, and the detailed classifier screening results are "available from the authors
upon request". It also has no author-contribution statement, so every author is recorded as `writing` only.
