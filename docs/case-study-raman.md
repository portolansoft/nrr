# Fourth study: when the control is a validation scheme, not a reagent

*Portolan Software, 26 September 2026. Fourth study encoded into the pilot corpus. Source: Cheveralls et al. 2026,
"Leave-one-batch-out cross-validation reveals strong batch effects in Raman spectroscopy of yeast cultures", The Stacks,
doi:10.57844/arcadia-xdmk-yq0w, CC BY 4.0.*

## 1. Why this study was chosen

To try to break the model. The three studies already encoded were wet-lab or wet-lab-adjacent, and their controls were
reagents, genotypes or vehicle injections. This study has no reagent controls at all. It is a machine-learning analysis of
spectra in which the thing that exposes the failure is a *validation scheme*. If the informativeness rule only worked
because every earlier study happened to have a bottle of something to compare against, this is where it would show.

## 2. What the study did

Arcadia collected spontaneous Raman spectra from nine yeast strains across two species, on three plates that were full
end-to-end replicates: separate cultures, separate plates, separate imaging dates. They then trained classifiers to
predict strain and species identity from the spectra.

| Task | Validation scheme | Median MCC |
|---|---|---|
| Strain | standard 5-fold | **0.79** (range 0.71-0.93) |
| Strain | leave-one-plate-out | **0.32** (range 0.19-0.42) |
| Strain | leave-one-plate-out, after batch correction | 0.39 |
| Plate identity (adversarial) | leave-one-strain-out | **1.0** (range 0.50-1.0) |
| Plate identity, after batch correction | leave-one-strain-out | 0.10 |
| Species | leave-one-plate-out | 0.97 |
| Species | leave-one-plate-out, after batch correction | 0.93 |

MCC is the Matthews correlation coefficient: 1 is perfect, 0 is chance. Nothing about the data or the model changes
between the first two rows. Only the way the folds are drawn changes. The classifier was reading which plate a spectrum
came from and using that to guess the strain.

The adversarial row is the proof: a model trained to predict plate identity, which should be unpredictable because the
plates are replicates of one protocol, scores a perfect 1.0.

## 3. The two things this study taught the model

### Controls do not have to be reagents

The study has both controls, in computational form, and they are better controls than anything in the earlier studies:

- **Positive control**: species classification on the same spectra through the same pipeline. It scores 0.97 under
  replicate-held-out validation. If this failed, nothing about the measurement could be trusted.
- **Negative control**: the adversarial plate-identity task. Expected result is chance. It scores 1.0, so the control did
  not stay clean.

Two new vocabulary terms carry this: `known-positive-task` and `adversarial-label`. Both generalise well beyond Raman
spectroscopy, to permutation tests, label shuffling, negative-control genes and sham conditions. Arcadia's own closing
recommendation is that adversarial prediction of meaningless labels should be standard practice, which suggests the term
will be needed often.

### A claim whose sign depends on the analysis, in the sharpest possible form

The Robin study already taught us that a negative is a property of the data *and* the analysis, because the same flow
cytometry files gave a passing control under a human analyst and a failing one under an agent. This study makes the same
point with nothing left to argue about: identical data, identical model, opposite conclusions, and the difference is one
methodological choice that is not part of the experiment at all.

A registry that stored "strain is predictable from Raman spectra, MCC 0.79" would be storing the number a less careful
study would have published. The record instead stores that number as **`refuted`**, links it to the analysis that refutes
it, and records the cross-validation scheme, the dataset version and the model in every finding's conditions.

## 4. A deliberate narrowing of the rule

Recording the 0.79 as `refuted` broke the rule, and the fix is the most interesting change in this round.

The rule treated `refuted` as a kind of negative and demanded controls for it. But the standard-cross-validation run had
no controls, by construction, and the absence of controls is precisely what let it look strong. Demanding controls of it
would have rewritten it to `inconclusive-no-positive-control`, which is wrong: we are not uncertain about it, the study
affirmatively showed it was an artifact.

So `refuted` is now exempt from the control requirement, on the reasoning that an affirmative refutation is judged on the
refuting analysis rather than on the controls of the run it refutes. `negative-not-replicated` deliberately keeps the
requirement, because a failure to replicate is still an absence of evidence and can still be underpowered.

## 5. The fourth diagnosis

The rule needed no other change, and it produced a diagnosis the corpus had not yet seen. After batch correction, both
controls behave: the adversarial classifier drops to 0.10, and species classification still scores 0.93. Strain
classification is still only 0.39. What is missing is now nothing to do with controls, and the rule says so:

| Diagnosis | Study | Finding |
|---|---|---|
| no positive control | Arcadia Alcalase | no on-target HDR in 191 colonies |
| positive control failed | Robin dAMD | Finch analysis of round 1 |
| negative control not clean | Arcadia neuroimaging, Arcadia Raman | itch response; strain before correction |
| **no sensitivity or power statement** | **Arcadia Raman** | **strain after correction** |

That last row is `inconclusive-underpowered`, and it matches what the authors say themselves: the dataset is small, 248
spectra across nine strains, and the strains may be too genetically similar to produce detectable spectral differences.
The rule arrived there independently from the structure of the record.

All four clauses have now fired on real published data, each traceable to a different study. That is the strongest
evidence so far that the rule is a diagnosis rather than a filter.

## 6. What the study exposed that is not about the rule

- **Self-declared invalidity.** The authors state that their batch correction leaks across folds, so the corrected
  numbers are not valid estimates of generalisation to unseen plates, and they explain what they do mean instead. A
  registry needs somewhere for an author to say "this number of mine does not mean what it looks like". It went into the
  finding's conditions and evidence, plus a `train-test-leakage` failure mode, but a first-class field for
  author-declared limits on their own measurement is probably warranted.
- **Licences differ within one study.** The pub is CC BY 4.0 and the code and data archive is MIT. Per-source licences
  already existed in the schema and were the right call.
- **AI participated in the reasoning, not just the prose.** This is the only study of the four whose AI-use statement
  says the authors "chatted with Claude throughout the project to support ideation and analysis", alongside code writing
  and review, a Gemini pass over the manuscript, and Cursor for completion. For a registry meant to serve AI-assisted
  science, that is a provenance fact worth capturing precisely, and the declaration is recorded verbatim with a per-tool
  purpose.

## 7. What I would still challenge

- I recorded the strain findings as three separate findings across three analysis configurations. An alternative is one
  finding with three measurements. The three-finding version queries better and makes the sign flip visible; it also
  triples the apparent count of strain-level negatives in any naive tally.
- `signal-below-noise` appears as a failure mode on the corrected strain finding, drawn from the authors' explanation that
  the differences may be genuinely too subtle. As with the neuroimaging study, that is their hypothesis rather than a
  measurement, and the failure mode reads more settled than the pub intends.
- The robustness finding, that conclusions do not depend on classifier or correction method, is encoded as `positive` with
  a qualitative value because the pub reports no numbers for the support vector machine or ComBat runs. It is the weakest
  finding in the record.
