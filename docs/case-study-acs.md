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

## 2. TMEDA inhibition: a negative about a control method

*Macleod, Bage, Meyer and Thomas 2024, "Hidden Boron Catalysis: A Cautionary Tale on TMEDA Inhibition", Org. Lett. 26,
9564-9567, doi:10.1021/acs.orglett.4c03591, PMC11555781. Study id `acs-tmeda`.*

### Why this one

Because the thing that fails is the control. Trapping with TMEDA is how the field decides whether a proposed hydroboration
catalyst is real or is quietly decomposing pinacolborane to BH3, the actual catalyst. If TMEDA does not inhibit the
reaction, the catalysis has been called "true". This paper shows the TMEDA·(BH3)2 adduct is labile above 60 °C, so the
test passes reactions that are in fact BH3-catalysed, and 63 % of the published uses of the test ran it hotter than that.
It is the chemistry analogue of the Raman record, where the validation scheme was the problem, and the research note asked
how a record can say "this negative control is unreliable under these conditions" and point at the literature that relied
on it.

### What the record looks like

| Record | Kind | Headline | Findings |
|---|---|---|---|
| `acs-tmeda-path` | path, experiment | `partial` | 4 attempts |
| `acs-tmeda-adduct-kinetics` | wet-lab | `refuted` | 9: six kinetic points (two informative negatives at 60 °C, four positives at 80 and 100 °C), the refuted test, the deliberate hidden-catalysis demonstration, HBpin's own thermal decomposition at 80 °C |
| `acs-tmeda-amine-screen` | wet-lab | `negative-not-achievable` | 7: one per amine from the Table 1 grid plus the overall "no better trap" |
| `acs-tmeda-loading` | wet-lab | `partial` | 2: higher TMEDA loading completes inhibition for the alkyne, not the alkene |
| `acs-tmeda-literature-survey` | evidence-synthesis | `positive` | 2: uptake of hidden-catalysis testing, and 15 of 24 TMEDA tests run above 60 °C |

The numbers that matter are pinned in the tests: free BH3 gives 9.6 mM/s and 87 % at 60 °C where the adduct gives
0.3 mM/s and 4 %; the adduct gives 50 % at 80 °C and 94 % at 100 °C. Table 1 is a colour grid in an image and was read cell
by cell into a CSV with the row and column as locator for each of its 28 cells.

### The judgement calls, and where they are written

**The method is the target.** The TMEDA inhibition test is an entity of type `assay`, and it is the `target` of a finding
of class `refuted` whose `conditions` say `validUpToC: 60` and `falseNegativeFromC: 80`. The path's
`applicabilityConditions` repeat the limit. Nothing new was needed: the model already allowed an assay to be the thing a
finding is about, and `refuted` already carried "this inference is false".

**The first chemistry negatives to pass the rule.** At 60 °C the adduct does not catalyse. The designated positive control
(Me2S·BH3 as a free-BH3 source) ran at every temperature, the no-catalyst background is clean, and the paper defines its
threshold, less than 5 % product by NMR, which the record takes as the sensitivity statement. So `alkyne-60` and
`alkene-60` are `negative-no-effect`, informative. That matters for the corpus: before this study every chemistry negative
was inconclusive.

**A background control that is clean at one temperature and dirty at another.** In the amine grid the no-amine row shows
no product to 70 °C and product at 80 °C, because HBpin decomposes to BH3 on its own from 80 °C (SI S3.5, recorded as its
own finding). The rule has one `passed` boolean per control. The record sets it true, says in the control's `note` that
the 80 °C column cannot distinguish a failed trap from background, and restricts the interpretation accordingly. This is
a case the rule handles by annotation, not by a new clause. It would become a clause if a third study needed it.

**Linking forward to the invalidated literature, honestly.** The SI counts 15 of 24 published TMEDA tests as run above
60 °C but does not name them; its references 9 to 27 are "some examples" of papers using the method, with no statement of
which ran hot, and seven of the 24 applied the test to carbonyl substrates it was never valid for. The record therefore
does not assert a per-paper `refutes` or `contradicts` relation. It records the count as a finding with `relatedFindings`
back to the refutation, and attaches the 19 examples as `reference` sources, all 19 resolved to DOIs through Crossref,
each with a note saying exactly what the paper claims about it. The temptation to add an `invalidates` relation type was
resisted because the source does not support the per-paper claim.

### What it broke

Nothing. Zero schema changes. The only code change was tooling: `scripts/resolve_ids.py` gained a generic `citations:`
list so a Supporting Information reference list without DOIs can be resolved once, online, into the cache.

### What it did not test

The paper reports yields as the average of two runs with no error estimate, so `replicates.technical: 2` is all the record
can say. Schemes S3 and S4 give their yields only in images and were not transcribed; the record says so.

## 3. Laccase and PFAS: a replication failure with the artefact explained

*Steffens, Antell, Cook, Rao, Britt, Sedlak and Alvarez-Cohen 2023, "An Artifact of Perfluoroalkyl Acid (PFAA) Removal
Attributed to Sorption Processes in a Laccase Mediator System", Environ. Sci. Technol. Lett. 10, 337-342,
doi:10.1021/acs.estlett.3c00173, PMC10100556. Study id `acs-laccase`.*

### Why this one

The research note called it the cleanest fit to the rule in the set, and it was chosen to check that the rule can pass a
chemistry negative, not only diagnose one. The authors set out to optimise a reported enzymatic degradation of PFOA and
PFOS, could not reproduce it, showed the system was alive (carbamazepine transformed, radical seen by EPR, enzyme active),
then showed by mass balance that the loss other people would have reported as degradation was sorption to the enzyme and
the glass. The positive control is a different substrate rather than a different reagent, which is a shape the rule had
not met.

### What the record looks like

| Record | Kind | Headline | Findings |
|---|---|---|---|
| `acs-laccase-path` | path, experiment | `negative-not-replicated` | 4 attempts; `contradicts` the two prior reports by DOI |
| `acs-laccase-mediator-screen` | wet-lab | `inconclusive-no-positive-control` | 2: two laccases by five mediators, 28 days, p = 0.58 and 0.24 |
| `acs-laccase-system-checks` | wet-lab | `positive` | 3: carbamazepine 35 % removed (p < 0.001), BTNO radical by EPR, activity retained |
| `acs-laccase-pfaa-degradation` | wet-lab | `negative-not-replicated` | 3: PFOA over two weeks (p = 0.29, informative); 64 % and 67 % apparent losses at 0.1 µM, `refuted` by 99 ± 14 % and 111 ± 11 % mass recovery |
| `acs-laccase-sorption` | wet-lab | `positive` | 3: 18 ± 2 % PFOA and 34 ± 4 % PFOS to the protein, 40 ± 12 % PFOS to the glass without enzyme |

Tables S2 and S3 are images inside the SI PDF. All 24 cells were read from the images into a CSV and each is an evidence
item; the main text's "18 ± 2 %" is 100 minus the 82 % subsample recovery.

### The judgement calls, and where they are written

**A surrogate substrate as the designated positive control.** Carbamazepine was run in a separate reactor set with the
same enzyme, mediator and buffer. The ingest counts it as a `designated` positive control for the TvL/HBT findings and
says in the control's `note` that it is not an arm of the same experiment. With the untreated reactors as the negative
control and the LC-MS/MS quantification range plus the expected effect size as the sensitivity statement, the two-week
PFOA finding is `negative-not-replicated` and informative, the first chemistry negative to pass and the first informative
instance of that class in the corpus. The same control is *not* counted for the mediator screen, which used two other
laccases, so the screen is `inconclusive-no-positive-control`, the Alcalase diagnosis in chemistry. Both decisions are in
`provenanceNotes`.

**The apparent loss is `refuted`, with the artefact as its failure mode.** A less careful study would have published
"64 % PFOA removal in 24 h". The record keeps that number as a finding of class `refuted`, judged on the mass balance, and
links it to the sorption finding that explains it. This forced the one change of the study.

**What counts as a sensitivity statement.** There is no power analysis. The ingest reads the quantification range
(0.2 to 10 µg/L, isotope dilution, triplicates with standard deviations) together with the stated expected effect
(>20 % at 10 days) as the sensitivity statement, and says so in the finding and in `provenanceNotes`.

### What it broke

One vocabulary term, `measurement-artifact` as a failure mode (change 29), for an apparent effect produced by the
sampling pathway rather than by the process under test. Nothing else. `contradicts` already existed for the relation to
the two prior reports; `nearestPriorResult` carries their claims. Tooling gained a `taxon` resolver so the three fungi
carry NCBI Taxonomy ids from the cache rather than from memory.

### What it did not test

No deposit; the SI PDF is the only place the data lives, and two of its tables are pictures. No author-contribution
statement. PFOS with TvL was tested only at 0.1 µM over 96 h and 24 h, never over two weeks, and the record says so.
