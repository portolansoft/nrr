"""Emit capture-time records from a Robin run folder (FutureHouse, Apache-2.0).

What the post-hoc ingest of the Nature paper could not recover, the run folder has: every proposed candidate with
its pairwise judgements and Bradley-Terry rank, every literature report with the DOIs it cited, and for the data
analysis step the agent configuration, model name, task ids and timestamps. What the run folder does *not* record
is which model synthesised the hypotheses and which judged them; that lives in Robin's configuration, so the emitter
takes it as `run_config` and, without it, the capture profile reports the gap rather than guessing.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from nrr.ingest.common import data_pointer, finalize, new_record, performer, source
from nrr.ingest.robin import bradley_terry, parse_pairwise_csv, parse_query_files, parse_ranked_csv, parse_summary
from nrr.rules import apply_informativeness

ROBIN_REPO = "https://github.com/Future-House/robin"
RUN_RE = re.compile(r"^(?P<disease>.+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<time>\d{2}-\d{2})$")


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _pointer(run: Path, rel: str, role: str) -> dict:
    p = run / rel
    return data_pointer(rel, path=f"{run.name}/{rel}", checksum=_sha(p), size=p.stat().st_size, role=role)


def _run_time(run: Path) -> tuple[str, str]:
    m = RUN_RE.match(run.name)
    if not m:
        raise ValueError(f"run folder name does not carry a timestamp: {run.name}")
    return m.group("disease").replace("_", " "), f"{m.group('date')}T{m.group('time').replace('-', ':')}:00Z"


def emit_robin_run(run: Path, run_config: dict | None = None, operator: dict | None = None) -> list[dict]:
    """Records for one run folder: assay selection, candidate proposal (per round present) and data analysis."""
    run = Path(run)
    disease, started = _run_time(run)
    cfg = run_config or {}
    study = "robin-run-" + re.sub(r"[^a-z0-9-]+", "-", run.name.lower()).strip("-")
    operator = operator or {"name": cfg.get("operator", "unknown operator"), "type": "Organization"}
    common = dict(operator=operator, sourceLicense="Apache-2.0", domainTags=["biology"], dateCreated=started,
                  sources=[source("code-repository", ROBIN_REPO, label="Robin", url=ROBIN_REPO,
                                  note="run folder emitted by the Robin notebook; commit not recorded in the run output" if not cfg.get("commit") else None)])

    def agent(name: str, role: str, key: str, **kw) -> dict:
        model = cfg.get(key)
        return performer(name, "llm" if key.endswith("_model") else "software-agent", role, model=model,
                         provider=cfg.get(key + "_provider"), commit=cfg.get("commit") if key == "robin" else None,
                         note=None if model or cfg.get("commit") else f"{key} is not written into the run output; supply it in run_config", **kw)

    robin = agent("Robin", "hypothesis-generation", "robin", url=ROBIN_REPO)
    synth = agent("hypothesis synthesis model", "hypothesis-generation", "synthesis_model")
    judge = agent("ranking judge model", "ranking", "judge_model")
    records: list[dict] = []

    def ranking_attempt(slug_suffix, title, question, success, summary_file, ranked_file, pairwise_file, reports_dir, kind, proposed_by):
        items = parse_summary(run / summary_file, kind)
        ranked = parse_ranked_csv(run / ranked_file)
        pairs, names = parse_pairwise_csv(run / pairwise_file)
        strengths = bradley_terry(pairs, len(names))
        reports = parse_query_files(run / reports_dir) if (run / reports_dir).exists() else []
        wins = {i: 0 for i in range(len(names))}
        losses = {i: 0 for i in range(len(names))}
        for w, l in pairs:
            wins[w] += 1
            losses[l] += 1
        by_name = {r["name"]: r for r in ranked}
        screened = []
        for i, name in enumerate(names):
            r = by_name.get(name)
            screened.append({"label": name, "type": "assay" if kind == "assay" else "compound",
                             "proposedBy": proposed_by, "decision": "included" if (r and r["rank"] <= 10) else "deferred",
                             "reason": "top-ranked" if (r and r["rank"] <= 10) else "rank-below-cutoff",
                             "score": {"method": "Bradley-Terry over pairwise LLM-judge comparisons (recomputed, Hunter 2004 MM, alpha 0.1)",
                                       "value": strengths[i] if i < len(strengths) else 0.0, "rank": r["rank"] if r else None,
                                       "comparisons": wins[i] + losses[i], "wins": wins[i], "losses": losses[i]},
                             "source": pairwise_file})
        for s in screened:
            if s["score"]["rank"] is None:
                del s["score"]["rank"]
        top = ranked[0] if ranked else None
        outputs = [_pointer(run, f, "run output") for f in (summary_file, ranked_file, pairwise_file)]
        report_ptrs = [_pointer(run, f"{reports_dir}/{r['file']}", "literature report") for r in reports]
        finding = {"id": "top-ranked", "question": question,
                   "target": {"label": top["name"] if top else "none", "type": "assay" if kind == "assay" else "compound",
                              "note": "identifier not resolved at capture; a deployment would resolve against PubChem or OBI here"},
                   "outcomeClass": "positive" if top else "inconclusive", "informativeness": "not-applicable",
                   "effect": {"metric": "strength score of the top-ranked item", "value": top["strength_score"] if top else None, "n": len(ranked),
                              "direction": "not-applicable", "note": f"{len(pairs)} pairwise judgements over {len(names)} items"},
                   "controls": {"positive": {"kind": "none", "note": "a proposal round has no control; the experiment that tests the proposals is a separate attempt"},
                                "negative": {"kind": "none"}},
                   "conditions": {"disease": disease, "itemsProposed": len(items), "itemsRanked": len(ranked), "pairwiseJudgements": len(pairs),
                                  "reports": len(reports), "doisCitedInReports": sum(len(r["dois"]) for r in reports)},
                   "evidence": [{"label": ranked_file, "source": f"{ROBIN_REPO}#{run.name}", "locator": ranked_file, "data": outputs + report_ptrs}]}
        apply_informativeness(finding)
        rec = new_record("attempt", study, f"{study}-{slug_suffix}", title, attemptType="hypothesis-generation", pathType="literature",
                         question=question, successCriteria=success, outcomeClass=finding["outcomeClass"], findings=[finding],
                         screened=screened, screenedSummary={"proposed": len(items), "ranked": len(ranked), "pairwiseJudgements": len(pairs)},
                         stages=[{"stage": "hypothesis-generation", "label": f"{len(items)} {kind} candidates proposed", "startTime": started,
                                  "performedBy": [synth, robin], "outputs": outputs[:1],
                                  "queries": [{"text": r["query"], "file": r["file"], "trajectoryId": r["trajectoryId"], "verbatim": True} for r in reports if r["query"]][:50]},
                                 {"stage": "ranking", "label": f"pairwise tournament, {len(pairs)} comparisons", "startTime": started,
                                  "performedBy": [judge, robin], "outputs": outputs[1:]}],
                         performers=[robin, synth, judge], cost={"agentCalls": {"pairwiseJudgements": len(pairs), "literatureReports": len(reports)}, "note": "captured from the run folder; token and dollar cost are not written there"},
                         applicabilityConditions={"disease": disease, "note": "proposals, not results; see the experiment attempt that tests them"},
                         provenanceNotes=["Emitted from the run folder at capture time. proposedBy is stated, not inferred, because the emitter is reading the round that produced the list."],
                         **common)
        records.append(finalize(rec))
        return rec

    # Assay ranking: the ranked list lives in the pairwise file only (no separate ranked CSV), so build it from the pairs.
    assay_pairs, assay_names = parse_pairwise_csv(run / "experimental_assay_ranking_results.csv")
    assay_strengths = bradley_terry(assay_pairs, len(assay_names))
    order = sorted(range(len(assay_names)), key=lambda i: -assay_strengths[i])
    assay_items = parse_summary(run / "experimental_assay_summary.txt", "assay")
    assay_reports = parse_query_files(run / "experimental_assay_detailed_hypotheses") if (run / "experimental_assay_detailed_hypotheses").exists() else []
    a_outputs = [_pointer(run, f, "run output") for f in ("experimental_assay_summary.txt", "experimental_assay_ranking_results.csv")]
    a_screened = [{"label": assay_names[i], "type": "assay", "proposedBy": "robin-assay-round", "decision": "included" if rank == 1 else "excluded",
                   "reason": "top-ranked" if rank == 1 else "rank-below-cutoff",
                   "score": {"method": "Bradley-Terry over pairwise LLM-judge comparisons (recomputed)", "value": assay_strengths[i], "rank": rank,
                             "comparisons": sum(1 for w, l in assay_pairs if i in (w, l)), "wins": sum(1 for w, _ in assay_pairs if w == i)},
                   "source": "experimental_assay_ranking_results.csv"} for rank, i in enumerate(order, start=1)]
    a_finding = {"id": "assay-selected", "question": f"Which in vitro assay should be used to screen therapeutic candidates for {disease}?",
                 "target": {"label": assay_names[order[0]] if order else "none", "type": "assay", "note": "identifier not resolved at capture"},
                 "outcomeClass": "positive" if order else "inconclusive", "informativeness": "not-applicable",
                 "effect": {"metric": "Bradley-Terry strength of the top-ranked assay", "value": assay_strengths[order[0]] if order else None, "n": len(assay_names),
                            "direction": "not-applicable", "note": f"{len(assay_pairs)} pairwise judgements"},
                 "controls": {"positive": {"kind": "none", "note": "a proposal round has no control"}, "negative": {"kind": "none"}},
                 "conditions": {"disease": disease, "assaysProposed": len(assay_items), "pairwiseJudgements": len(assay_pairs)},
                 "evidence": [{"label": "experimental_assay_ranking_results.csv", "source": f"{ROBIN_REPO}#{run.name}", "locator": "experimental_assay_ranking_results.csv",
                               "data": a_outputs + [_pointer(run, f"experimental_assay_detailed_hypotheses/{r['file']}", "literature report") for r in assay_reports]}]}
    apply_informativeness(a_finding)
    records.append(finalize(new_record("attempt", study, f"{study}-assay-selection", f"Robin proposes and ranks in vitro assays for {disease}",
                                       attemptType="hypothesis-generation", pathType="literature", question=a_finding["question"],
                                       successCriteria="A ranked assay list with a clear top choice.", outcomeClass=a_finding["outcomeClass"], findings=[a_finding],
                                       screened=a_screened, screenedSummary={"proposed": len(assay_items), "pairwiseJudgements": len(assay_pairs)},
                                       stages=[{"stage": "hypothesis-generation", "label": f"{len(assay_items)} assay strategies proposed", "startTime": started, "performedBy": [synth, robin], "outputs": a_outputs[:1]},
                                               {"stage": "ranking", "label": f"pairwise tournament, {len(assay_pairs)} comparisons", "startTime": started, "performedBy": [judge, robin], "outputs": a_outputs[1:]}],
                                       performers=[robin, synth, judge], cost={"agentCalls": {"pairwiseJudgements": len(assay_pairs), "literatureReports": len(assay_reports)}, "note": "captured from the run folder"},
                                       applicabilityConditions={"disease": disease},
                                       provenanceNotes=["Emitted from the run folder at capture time."], **common)))

    ranking_attempt("candidates-r1", f"Robin proposes and ranks therapeutic candidates for {disease} (round 1)",
                    f"Which therapeutic candidates should be tested in the selected assay for {disease}?",
                    "A ranked candidate list from which the top ten can be ordered for testing.",
                    "therapeutic_candidates_summary.txt", "ranked_therapeutic_candidates.csv", "therapeutic_candidate_ranking_results.csv",
                    "therapeutic_candidate_detailed_hypotheses", "candidate", "robin-round-1")
    if (run / "ranked_therapeutic_candidates_experimental.csv").exists():
        ranking_attempt("candidates-r2", f"Robin re-proposes therapeutic candidates for {disease} after experimental insights (round 2)",
                        f"Given the round-1 experimental insights, which therapeutic candidates should be tested next for {disease}?",
                        "A new ranked candidate list incorporating the experimental insights.",
                        "therapeutic_candidates_summary_experimental.txt", "ranked_therapeutic_candidates_experimental.csv",
                        "therapeutic_candidate_ranking_results_experimental.csv", "therapeutic_candidate_detailed_hypotheses_experimental", "candidate", "robin-round-2")
        records[-1]["provenanceNotes"].append("The experimental insights that steered this round are not written into the run folder; they are passed in the prompt (EXPERIMENTAL_INSIGHTS_APPENDAGE) and would need to be captured by the agent itself.")
        finalize(records[-1])

    # --- data analysis (Finch) from the trajectories metadata -----------------------------------------------------
    meta_path = run / "data_analysis" / "finch_trajectories_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        analysis_files = sorted(p for p in (run / "data_analysis").rglob("*.csv"))
        outputs = [_pointer(run, p.relative_to(run).as_posix(), "analysis output") for p in analysis_files]
        findings, performers, stages = [], [], []
        for step, v in meta.items():
            tasks = v["tasks"]
            model = tasks[0]["agent"]["agent_kwargs"]["llm_model"]["name"] if tasks else None
            finch = performer("Finch", "software-agent", "data-analysis", provider=tasks[0]["build_owner"] if tasks else None, model=model,
                              trajectoryIds=[t["task_id"] for t in tasks], platformJob=tasks[0]["job_name"] if tasks else None,
                              dateUsed=min(t["created_at"] for t in tasks) if tasks else None)
            performers.append(finch)
            stages.append({"stage": "analysis", "label": f"Finch data analysis step {step}: {len(tasks)} trajectories", "startTime": min(t["created_at"] for t in tasks),
                           "endTime": max(t["created_at"] for t in tasks), "performedBy": [finch],
                           "outputs": [o for o in outputs if o["label"].startswith(f"data_analysis/{step}")],
                           "queries": [{"text": v["query"][:1000], "verbatim": True}]})
            f = {"id": f"analysis-{step}", "question": "Did the Finch data-analysis trajectories for this step complete?",
                 "target": {"label": f"Finch analysis step {step}", "type": "software"},
                 "outcomeClass": "positive" if v.get("success_rate") == 1.0 else "partial", "informativeness": "not-applicable",
                 "effect": {"metric": "trajectory success rate", "value": v.get("success_rate"), "n": len(tasks), "direction": "not-applicable"},
                 "controls": {"positive": {"kind": "none", "note": "the analysis results themselves, not their completion, carry the controls; they are in the flow_results files"},
                              "negative": {"kind": "none"}},
                 "conditions": {"model": model, "environment": tasks[0]["environment_name"] if tasks else None, "trajectories": len(tasks)},
                 "evidence": [{"label": "finch_trajectories_meta.json", "source": f"{ROBIN_REPO}#{run.name}", "locator": f"data_analysis/finch_trajectories_meta.json#{step}",
                               "data": [_pointer(run, "data_analysis/finch_trajectories_meta.json", "trajectory metadata")] + [o for o in outputs if o["label"].startswith(f"data_analysis/{step}")]}],
                 "note": "A capture record for the analysis step. The scientific findings of the analysis (which arms differed from control) are what a full deployment would emit here, from the flow_results tables, with the controls those tables carry."}
            apply_informativeness(f)
            findings.append(f)
        records.append(finalize(new_record("attempt", study, f"{study}-data-analysis", f"Finch analyses the experimental data for {disease}",
                                           attemptType="computational", pathType="computation",
                                           question="What do the experimental data show, as analysed by the Finch agent?",
                                           successCriteria="Completed trajectories with a consensus result table.", outcomeClass="positive" if all(f["outcomeClass"] == "positive" for f in findings) else "partial",
                                           findings=findings, stages=stages, performers=performers,
                                           cost={"agentCalls": {"trajectories": sum(len(v["tasks"]) for v in meta.values())}, "note": "captured from the trajectories metadata"},
                                           applicabilityConditions={"disease": disease},
                                           provenanceNotes=["Model name, task ids, job name and timestamps come from the run's own trajectories metadata, which is what the post-hoc ingest of the paper could not recover."],
                                           **common)))
    return records
