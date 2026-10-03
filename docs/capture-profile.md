# Capture at run time: the minimum record, and two emitters

*Portolan Software, 3 October 2026. Follows `case-study-acs.md`. Code in `src/nrr/capture/`, tests in
`tests/test_capture.py`, script `scripts/emit_capture.py`. Numbers come from the test run and emitter runs of the
session that wrote this.*

## 1. Why

Nine published studies have now been encoded after the fact. Every one of them lost the same things between the run
and the paper: who proposed a candidate and under which model, how many times something was run, which raw files a
claim rests on, and whether the run could have seen the effect it did not see. The assessment after study two already
said passive capture at generation time is the right design. This is the first code for it.

The question was whether the record can be emitted *by the system that produced the evidence*, at the moment it has
the information, without a human transcribing anything. Two open systems were tried, one on each side of the gap:

- **Robin** (FutureHouse, Apache-2.0): an agent that proposes assays and candidates, ranks them with a language-model
  judge, and analyses the resulting data with another agent. The agent side.
- **Data Hub** (Arcadia Science, MIT): a self-hosted service that captures raw instrument runs, extracts metadata and
  serves them through a REST API and an MCP server. The instrument side.

## 2. The capture profile

A capture record is an ordinary NRR v0.2 `attempt` that passes `nrr.schema.validate`, plus six things the post-hoc
ingest could never recover. `nrr.capture.profile.check_capture` returns errors and warnings.

| # | Requirement | Why it is required at capture and not later |
|---|---|---|
| 1 | At least one finding with question, target, outcome class and controls | The schema already requires it; capture is where the controls are known |
| 2 | Every finding has an evidence pointer with a `checksum` or a `runId` | The claim must be re-derivable from the bytes the instrument or agent produced |
| 3 | A negative finding carries `sensitivity` or `power`, or its `note` says none exists | The rule will mark it uninformative either way; silence is not allowed |
| 4 | At least one stage with a `startTime` or `endTime` | Anchored in the run's time, not a build date |
| 5 | Every software performer names a `model`, `commit` or `version` | Which model proposed what was the first thing lost in the Nature paper |
| 6 | `dateCreated` is the run's own time | A warning, not an error |

No schema change was needed. The profile is a check over the existing schema, and both emitters produce records that
also pass the full validator and are content-addressed like everything else.

## 3. Robin: what the run folder has and what it does not

`emit_robin_run` reads a Robin run folder and emits one attempt per step it finds: assay selection, candidate
proposal round one, round two if an experimental round exists, and the Finch data analysis. On the first sample run
(2025-05-28) that is four attempts; on the second (2025-05-29), two.

**What the folder has, and the paper did not.** Every proposed assay and candidate with its pairwise judgements and
Bradley-Terry rank (10 assays over 45 judgements; the candidate rounds with their full tournaments), so `proposedBy`
is *stated* rather than inferred, and `screened[].score` carries rank, wins and comparison counts for every item. Every
literature report with the query it answered and the DOIs it cited, as a `queries[]` entry with a trajectory id.
For the data analysis, the agent configuration with the model name (`anthropic/claude-3-7-sonnet-20250219`), the job
name, five task ids and their timestamps, which went straight into `performers[].trajectoryIds` and the stage's start
and end times. Every file is pointed to with a sha256.

**What the folder does not have.** Which model synthesised the hypotheses and which judged them. Robin holds that in
its configuration object, not in its output. The emitter takes a `run_config` for it; without one, the profile reports
three errors per proposal attempt ("software performer without model, commit or version") and the records are not
capture-complete. That is the right behaviour: the gap is named, not guessed. The experimental insights that steer
round two are passed to the model in the prompt and are not written anywhere either. And the proposal rounds carry no
scientific negative, because the experiment that tests the proposals is a separate attempt a lab system would emit.

The provided `capture/robin-config.yaml` carries the values the Nature paper reports for the published runs. A
deployment would read them from Robin itself.

## 4. Data Hub: the measurement layer, and nothing else

A local Data Hub was run from its repository at commit `5a2acaa5` with its seed data (26 users, 80 runs over nine
instrument types, 44 fixture files processed). `emit_datahub_run` takes a run's JSON from the REST API plus a *claim*
and emits one wet-lab attempt.

**What Data Hub has.** The instrument, the run id, acquisition time, extracted metadata (for the plate reader:
wavelength, measurement mode and type), every file with its S3 key, size, content type, category and processing
timestamps, and who claimed the run. All of it went into one `instrument-capture` stage and one evidence pointer per
file carrying `runId`.

**What Data Hub does not have.** A question, a control, an outcome, a detection limit. It is not supposed to; it is a
run store. Everything the informativeness rule reads came from the claim. Nor does its API expose a per-file checksum
(the only sha256 in the schema is over an archive's file list), so the pointer satisfies the profile through `runId`
and gets a `checksum` only when the emitter has read the bytes. The vendored run has both files and both checksums.

The example claim in `capture/datahub-claim-example.yaml` is labelled as an example throughout, because the seed run is
synthetic fixture data that measures nothing; what it shows is the shape. Delete its `sensitivity` line and the finding
becomes `inconclusive-underpowered` and the profile refuses the record with "no note saying why". That is the forcing
function at work: an agent that wants its negative to count has to write the detection limit while it still knows it.

## 5. What this showed

- **The record can be emitted by the producing system, and the profile tells it what is missing.** Fourteen capture
  checks and emitter tests pass; the two emitters produce schema-valid, content-addressed records with no change to
  the schema. The convergence claim extends from ingest to capture.
- **The two systems lose different things.** Robin keeps the ranking evidence and loses the model identity for its
  own reasoning steps. Data Hub keeps the bytes and the instrument context and has no claim layer at all. A record
  needs both, which is the argument for the claim layer being its own object that points at run stores rather than a
  field on the run.
- **Checksums are not where one would hope.** Neither Robin's folder nor Data Hub's API gives a file checksum. The
  emitters compute one when the bytes are at hand; the profile accepts a `runId` as the fallback. A registry that
  wants tamper-evidence end to end would ask run stores to publish hashes.
- **The forcing function works on the producer, not the publisher.** The four ACS papers showed what publishers cannot
  recover. The capture profile shows what producers must write. It is six lines, and two of them are things no paper
  carried: the model behind each software performer and the raw-file pointer behind each claim.

## 6. What it did not test

No real experiment was captured. The Robin sample runs are re-runs whose candidates differ from the paper's, and the
Data Hub run is seed data. The next step is one real run end to end: Data Hub capturing a plate read, an agent writing
the claim with controls and a detection limit, and the record arriving in a registry through `nrr_deposit`. That needs
a lab, which is the conversation with Arcadia.
