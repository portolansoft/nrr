# Assessment: what encoding two real studies taught us about Portolan

*Portolan Software, 2026-09-25. Written at the end of the pilot by the agent that did the work. Opinions are mine; the
numbers are reproducible from `build.py`.*

## 1. Did it work?

Yes, on the terms set: two published studies, from two very different kinds of source (an AI-driven drug-repurposing
paper with a human wet lab, and a human-run method-development "informative failure"), were reformatted into one data
model, validated, linked through shared identifiers and vocabularies, loaded into a database, and queried the way an
agent would query them. The schema had to change, and the changes are the most valuable output.

| | |
|---|---|
| Records | 18 (2 paths, 16 attempts) |
| Findings | 129 (97 informative negatives, 25 positives, 3 partial, 4 uninformative negatives correctly demoted to inconclusive) |
| Screened items | 132 (compounds, assays, with Bradley-Terry scores where the source had them) |
| Identifiers resolved | ~90 DOIs status-checked (Crossref/DataCite), 31 of 32 supplementary citations resolved to DOIs from free text, 60 of 63 compound names to PubChem (the other 3 are proteins, resolved via UniProt), terms to MONDO/CL/GO/OBI, organisations to ROR |
| Hand curation | 7 curated files (about 35% of the effort): tables transcribed from the Stacks text, Table 1 parsed from a PDF and corrected by hand, control roles and hit calls taken from the main text |
| Schema changes | 12, all about provenance and epistemic status, none about biology (see `schema/CHANGELOG.md`) |

## 2. The single most important finding

**The negative results were never stated.** The Robin paper reports three hits. It also contains, in a supplementary
workbook, per-well measurements for roughly ninety compound-by-assay arms that did nothing. Nobody wrote "fingolimod at
1 µM does not increase ARPE-19 phagocytosis of pHrodo beads over 3 h"; that claim exists only as three numbers in a
sheet plus a dose in a PDF table plus a sample-size sentence in the Reporting Summary plus a hit call in the main text.
Assembling one informative negative took four sources. That is exactly the gap Portolan claims to fill, and the pilot
shows the gap is real and the assembly is mechanisable once someone decides what counts as a claim.

The Robin system itself already knows it needs this: its round-2 prompt appends "these drugs have already been tested,
DO NOT SUGGEST THESE DRUGS AGAIN". That is a single-lab, single-run, in-context memory. Portolan is the same memory made
durable and cross-lab. The hook is concrete: the `experimental_insights` object Robin passes between rounds is, field for
field, a subset of an NRR finding.

## 3. What the data model got right

- **Findings inside attempts.** The v0.1 rule "one record, one attempt, one outcome" broke on the first record. One
  Arcadia experiment answered six questions with four different outcome classes; one Robin screen has 60 arms. The
  durable structure is three levels: path (cite it), attempt (deposit it), finding (query it).
- **Controls with a kind, and the informativeness rule as code.** This was the best decision in v0.1 and the pilot
  confirms it. Three cases only the rule caught:
  - Arcadia's 0/40 edited colonies cannot be read as "HDR does not work in CC-124" because no positive editing control
    existed; the record says `inconclusive-no-positive-control` and gives a derived detection limit (7.5%).
  - Finch trajectory 0 lost the MFGE8 positive control (1.04x) while the human analysis of the same data found 1.46x.
    The Finch negatives are therefore uninformative *for that analysis*, and the record links the two.
  - Ninety-plus Robin negatives are informative only because Nature's Reporting Summary states the sample-size rationale
    ("3 replicates could reliably distinguish MFGE8 from vehicle"). Without that one sentence the whole screen would be
    `inconclusive-underpowered` by the rule. The Reporting Summary was the most valuable structured input in the paper.
- **Stage-level performers.** "Who did this" is not one field. In Robin, o4-mini synthesised, Claude 3.7 Sonnet judged,
  Gemini 2.5 Pro wrote the judge's prompt, Finch analysed, humans pipetted, and Deep Research was the comparator. In
  Arcadia, humans did the science and four LLMs edited the prose. Trust and cost attach to the stage, not the record.
- **Untried branches with data pointers.** SRA holds exendin-4, MLN120B and "AT" RNA-seq samples (with and without beads,
  n = 3) that the paper never analyses. No sentence in the paper says so; the ENA run table does. That is a free
  experiment sitting in a public archive, and the record is the only place it is written down.

## 4. What was harder than expected

1. **Provenance in the flagship AI-science paper is thin.** The GitHub "sample trajectories" are re-runs made after the
   experiments; their ranked candidates are not the ones the paper tested. Candidate counts disagree between the main
   text and Supplementary Table 1. About 25 compounds in the primary-cell screen have no stated proposer. The primary-cell
   RNA-seq has no accession. Finch trajectories are behind a platform login. None of this is unusual for a paper; all of it
   would have been captured for free had the agent deposited at run time. Post-hoc ingestion from PDFs is lossy and
   slow; passive capture at generation time is the right design, and the pilot is the evidence.
2. **Negatives are a property of (data, analysis), not of data.** The same FCS files gave different control outcomes
   under Finch and under a human. A registry that stores "compound X: no effect" without the analysis identity will be
   wrong some of the time. Modelling the analysis as its own attempt, linked to the wet-lab attempt, is not optional.
3. **Licences.** Nature's CC BY-NC-ND 4.0 forbids sharing adapted material. A record that carries per-well values and
   quotations from such a paper is arguably adapted material. Records built from NC-ND sources must be facts plus
   pointers, and the vendored supplementary workbook cannot be redistributed. Arcadia's CC BY had no such friction.
   This should shape the beachhead: CC BY venues, preprints, and lab-native capture first.
4. **Curation judgement is the real work.** Roughly ten decisions in this pilot were mine, not the authors': which arms
   are controls, whether Cytochalasin D is an inhibitor control, that every non-hit is `negative-no-effect`, that Table 1
   order encodes which agent proposed which compound. Each is flagged (`proposedByConfidence`, `provenanceNotes`,
   `derivedBy`), but an expert should review them. A production ingest is an agent proposing records and a human or a
   second agent approving them, not a converter.
5. **Identifiers are the weak link for biologics and combinations.** Small molecules resolved cleanly through PubChem
   (after a rate-limit fight). Peptides ("740 Y-P", "RGD"), proteins used as reagents (MFGE8, GAS6, PROS1), combinations
   ("Sim + Res"), enzymes (Alcalase) and Chlamydomonas loci needed special handling or stayed label-only. Prior-art queries
   by identifier only work as well as this resolution.
6. **The schema is now heavy.** About a hundred fields. Nobody will fill that by hand. The minimum viable deposit should
   be: question, target, outcome class, controls, sensitivity, conditions (dose), one evidence pointer; everything else
   optional and mostly machine-filled.

## 5. Feasibility and usefulness verdict

**Feasibility.** The data model is not the risk; it took one session to make it machine-readable and to encode two
studies without renaming anything. The risks are upstream and downstream of the model: getting attempts at generation
time (integration with agent frameworks such as Robin's `experimental_insights` and platform trajectory exports,
Arcadia Data Hub run webhooks), licence-clean sources, and a review loop for the judgement calls. Ingesting a published
paper post hoc cost this pilot several hours of agent time per paper plus curation; that is affordable for a seed
corpus and unaffordable as the main intake.

**Usefulness.** Three concrete uses fell out of the corpus without being designed for:
- *Prior art before spending money:* "has fingolimod been tried as an RPE phagocytosis enhancer?" returns three
  informative negatives with dose, model and sensitivity. The next Robin-like run should read this before proposing.
- *Free experiments:* deposited-but-unanalysed data (three RNA-seq conditions) and iced projects with the authors' own
  next steps and open questions (Arcadia's three "Weigh in" questions) are pick-up points for an agent with a budget.
- *Agent evaluation with wet-lab ground truth:* the Deep Research arm (17 candidates, zero hits, ROCK inhibition never
  proposed) and the hallucinated-reference table are negative results *about agents*. Portolan should court this
  record type; nobody else stores it in a queryable form.

**Where Portolan fits.** The pilot used ENA, Zenodo, Crossref, DataCite, PubChem, UniProt, OLS, Cellosaurus, HGNC and ROR
as sources and added one thing none of them has: the claim layer with control semantics and applicability conditions,
queryable across labs and agents. That is consistent with the earlier positioning (a layer above existing endpoints, not
a host). The Stacks publishes informative failures for humans; Edison keeps trajectories behind a login; neither offers
"has X been tried under Y, and would the assay have seen it" as an API. That gap is the product.

## 6. What I would do next

1. Define the minimum viable record (finding-centric) and publish v0.2 with it; keep the full schema as the superset.
2. Build the ingest as an agent-plus-review loop and run it on ten more CC BY sources (The Stacks Icebox, bioRxiv methods
   preprints, one materials paper) to see which schema additions recur.
3. Prototype the passive-capture path with Robin: a small adapter that turns `experimental_insights` and the flow
   results CSV into a deposit at the end of a run.
4. Put the KL001 discrepancy (no effect in ARPE-19 with beads, hit in primary cells with ROS) and the Finch/human control
   discrepancy in front of a biologist; they are the two records most likely to teach us whether the outcome vocabulary
   is right.
5. Resolve the licence question with a lawyer before ingesting more NC-ND content.

## 7. Caveats on this assessment

I classified every non-hit arm as an informative negative at its single tested dose; an experimentalist may prefer
`partial` for n = 3 single-dose screens. I inferred Deep Research and round-2 membership from table order. I recorded
Supplementary Fig. 17's negative log2 fold changes as printed although the legend calls ABCA1 upregulated. The 17th
Deep Research candidate is unidentified. Finch's trajectory-0 "positives" for fingolimod, exendin-4 and AICAR are
recorded as Finch's calls with the human disagreement noted, not as the paper's claims. The corpus is two studies;
every generalisation above is a hypothesis.
