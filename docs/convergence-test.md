# Fifth study: a pre-registered test of whether the model has converged

*Portolan Software, 26 September 2026. Source: Morin, Patton et al. 2024, "A structurally divergent actin conserved in
fungi has no association with specific traits", The Stacks, doi:10.57844/arcadia-9768-f6c5, CC BY 4.0.*

## 1. The claim under test

After four studies the change counts were 12, then 8, then 5. That looked like convergence, but three points in a falling
sequence is not evidence, and the studies had been chosen for what they would teach rather than for what they would break.
So this round was set up as a test with the criterion fixed in advance.

**Converging** if the study needs two or fewer additive changes and nothing structural, meaning no new record level and no
change to the shape of a finding, a control or an effect. **Not converging** if it needs any structural change, or more
than four changes of any kind.

The study was chosen to maximise the chance of failure, not to pass. The compound 48/80 toxicity pub was the easiest
remaining candidate, being nearly the same shape as the Robin drug screens, and was deliberately not chosen.

## 2. Why this study was the hard case

It shares almost nothing structurally with the four already encoded:

| | Four earlier studies | This study |
|---|---|---|
| Experiment | wet lab, imaging, or spectra | none; public database analysis only |
| Unit of observation | cells, animals, spectra | species |
| Evidence | effect sizes, p-values, model accuracy | evolutionary model selection by Akaike information criterion |
| Negative shape | one question per finding | no association with *any* of six traits |
| Absence | observed | inferred from a database protein count |

## 3. Result: two changes, both single vocabulary terms

| # | Change | Forced by |
|---|---|---|
| 26 | `phenotype` entity type | The six fungal traits are the study's primary variables and there was no type for a species-level trait. Two earlier studies had already worked around this by typing a phenotype as an assay, so the gap predates this study. |
| 27 | `data-curation` performer role | A CRediT role used by the lead author, missing from the vocabulary, in the same family as three added in the previous round. |

Nothing structural. I predicted one change before encoding and got two; the second was a controlled-list term of exactly
the kind the previous round had already added three of, which is a gap in vocabulary coverage rather than in design.

**The test passes**, on the criterion set in advance.

## 4. What carried unchanged, and this is the substance of the result

- **Six per-trait findings plus an aggregate** fitted the existing finding structure with no alteration. The
  multiple-hypothesis shape needed nothing new.
- **`Effect` carried two unfamiliar statistics** with no new fields: an AIC model comparison through `value`, `comparedTo`
  and `test`, and a phylogeny-corrected regression slope through `pValue`.
- **`stage.sourcesSearched`**, designed for literature databases under PRISMA-S, carried six reference databases (Fun Fun,
  TimeTree, FUNGuild, UniProt, AlphaFold, NCBI Taxonomy) without modification. This was the change I most expected to need
  and did not.
- **`protocolAdaptations`**, added in the previous round for a mouse troubleshooting loop, carried the post-hoc recoding of
  trait categories to keep at least four species per level. A field added for a wet-lab bias turned out to fit a
  statistical one.
- **`resource-constraint`** already existed as an abandonment reason and matched the authors' stated reason exactly.
- **`insufficient-data`** already existed as a failure mode.

A field added for one domain fitting another domain unchanged is the kind of evidence that distinguishes convergence from
me simply not looking hard enough.

## 5. The rule found something the authors did not state

The authors attribute their null result to two causes: only six traits were available, and errors in calling the protein
absent. Both are real and both are in the record.

The rule adds a third that the pub does not mention. No positive control was run: the trait-mapping method was never
tested against a protein family with a known trait association. Without that, a null cannot be separated from a method
that would not have detected an association at these sample sizes, and the sample sizes are small, ranging from 10 to 71
species per trait with an average of 34. With AIC model selection this matters more than usual, because the criterion
penalises the more complex correlated model, so at small n the independent model can win regardless of the truth.

The record therefore reads `inconclusive-no-positive-control`, and the reason string carries all three failures at once:
"no positive control; no negative control; no sensitivity or power statement". That is a new *combination* across the
corpus rather than a new clause.

## 6. Where the corpus stands

| | |
|---|---|
| Studies | 5 |
| Records | 30 |
| Findings | 157 |
| Entities | 158 |
| Validation errors | 0 |
| Tests | 148 |
| Change count by study | 12, 8, 5, 2 |

| Diagnosis | Study |
|---|---|
| no positive control | Arcadia Alcalase |
| positive control failed | Robin dAMD |
| negative control not clean | Arcadia neuroimaging, Arcadia Raman |
| no sensitivity or power statement | Arcadia Raman |
| all three at once | Arcadia divergent fungal actin |

## 7. What I would not conclude from this

Five studies is still a small corpus, and four of the five come from one operator. The convergence claim is now supported
rather than proven, and the honest statement is narrower than "the model is done":

- **Nothing structural has been required since the first study.** That is four consecutive studies across wet lab, in vivo
  imaging, machine learning and comparative genomics.
- **What is still being added is vocabulary**, at a falling rate, and it is the kind of addition that a controlled list
  needs whenever it meets a new field. That will continue indefinitely and is not a defect.
- **The untested direction is other domains.** Everything so far is biology. A materials or chemistry study is the obvious
  next falsification attempt, and the materials profile in v0.1 has never been exercised against a real paper.

## 8. What I would still challenge in this record

- Recording each of the six traits as its own finding means a naive count of negatives for this study is seven, not one. I
  flagged it in the record's provenance notes, but any aggregate query over the corpus will over-weight this study.
- `negative-no-association` is the pub's own framing and it never survives into the record, because every per-trait
  finding is uninformative and gets remapped to an inconclusive class. The information is not lost, but the label the
  authors would recognise is not the label the record carries.
- The protein family is defined operationally as membership of three clustering outputs. There is no sequence-motif or
  experimental definition, so the entity at the centre of the study is a clustering decision, and the record says so but
  cannot do better.
