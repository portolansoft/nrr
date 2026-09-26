"""Converter for Ghareeb et al. 2026, 'A multi-agent system for automating scientific discovery'
(Nature 655:497-505, doi:10.1038/s41586-026-10652-y), the Robin and Finch repositories, and SRA PRJNA1464762."""
from __future__ import annotations

import ast
import csv
import math
import re
from pathlib import Path

import openpyxl

from nrr.ingest.common import (
    check_valid, compound_ref, data_pointer, entity, finalize, mean_sem, new_record, performer, read_csv, read_json,
    read_yaml, source,
)
from nrr.resolve import normalize
from nrr.rules import apply_informativeness

STUDY = "robin-damd"
PUB_DOI = "doi:10.1038/s41586-026-10652-y"
RUN1 = "dry_age-related_macular_degeneration_2025-05-28_16-51"
RUN2 = "dry_age-related_macular_degeneration_2025-05-29_12-11"
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>,;)\]]+)")

csv.field_size_limit(10**9)


# ---- parsers ------------------------------------------------------------------------------

def parse_ranked_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"name": r["hypothesis"].split("\n")[0].strip(), "index": int(r["index"]),
                         "strength_score": float(r["strength_score"]), "report": r["answer"]})
    rows.sort(key=lambda x: -x["strength_score"])
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows


def _parse_tuple(s: str) -> tuple[str, int] | None:
    """The judge was asked for '(name, id)'; it sometimes answers 'name (id)'. Accept both."""
    m = re.match(r"^\s*\(\s*\"?(.*?)\"?\s*,\s*\"?(\d+)\"?\s*\)\s*$", s.strip())
    if not m:
        m = re.match(r"^\s*(.*?)\s*\(\s*(\d+)\s*\)\s*$", s.strip())
    return (m.group(1).strip(), int(m.group(2))) if m else None


def parse_pairwise_csv(path: Path) -> tuple[list[tuple[int, int]], list[str]]:
    pairs: list[tuple[int, int]] = []
    names: dict[int, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            w, l = _parse_tuple(r["Winner"]), _parse_tuple(r["Loser"])
            for col in ("input_hypo_1", "input_hypo_2"):
                try:
                    d = ast.literal_eval(r[col])
                    names[int(d["index"])] = d["hypothesis"].split("\n")[0].strip()
                except Exception:
                    m = re.search(r"'hypothesis': '(.*?)', 'answer'", r[col])
                    m2 = re.search(r"'index': '(\d+)'", r[col])
                    if m and m2:
                        names[int(m2.group(1))] = m.group(1).split("\\n")[0].strip()
            if w and l and w[1] != l[1]:
                pairs.append((w[1], l[1]))
                names.setdefault(w[1], w[0])
                names.setdefault(l[1], l[0])
    n = max(names) + 1 if names else 0
    return pairs, [names.get(i, f"item-{i}") for i in range(n)]


def bradley_terry(pairs: list[tuple[int, int]], n: int, alpha: float = 0.1, iters: int = 500) -> list[float]:
    """Regularised Bradley-Terry strengths (log scale, mean zero) by the MM algorithm of Hunter (2004).

    Re-implements the ranking step of Robin (choix.ilsr_pairwise with alpha=0.1) closely enough to
    reproduce the ordering; alpha acts as a pseudo-count so unbeaten or winless items stay finite."""
    if n == 0:
        return []
    wins = [alpha] * n
    games: dict[tuple[int, int], int] = {}
    for w, l in pairs:
        wins[w] += 1
        key = (min(w, l), max(w, l))
        games[key] = games.get(key, 0) + 1
    p = [1.0] * n
    for _ in range(iters):
        denom = [alpha * n / sum(p) for _ in range(n)]
        for (i, j), c in games.items():
            d = c / (p[i] + p[j])
            denom[i] += d
            denom[j] += d
        p = [wins[i] / denom[i] for i in range(n)]
        s = sum(p) / n
        p = [x / s for x in p]
    logs = [math.log(x) for x in p]
    m = sum(logs) / n
    return [round(x - m, 6) for x in logs]


def parse_supp_table(xlsx: Path, sheet: str) -> dict[str, dict]:
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb[sheet]
    out: dict[str, dict] = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0 or row[0] is None:
            continue
        label = str(row[0]).strip()
        d = out.setdefault(label, {"values": [], "plates": [], "mfi": [], "background": []})
        d["values"].append(float(row[4]))
        d["plates"].append(str(row[2]))
        d["mfi"].append(float(row[1]))
        d["background"].append(float(row[3]))
    for label, d in out.items():
        d["n"] = len(d["values"])
        d["mean"], d["sem"] = mean_sem(d["values"])
    return out


def parse_ena_runs(tsv: Path) -> list[dict]:
    runs = []
    with open(tsv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            alias = r["sample_alias"]
            base = re.sub(r"_rep\d+$", "", alias)
            beads = base.endswith("_beads")
            runs.append(dict(r, condition=base.replace("_beads", ""), beads=beads,
                             md5_r1=r["fastq_md5"].split(";")[0], fastq_urls=["ftp://" + u for u in r["fastq_ftp"].split(";")]))
    runs.sort(key=lambda r: r["run_accession"])
    return runs


def parse_references(txt: Path) -> list[dict]:
    text = txt.read_text(encoding="utf-8")
    idx = text.rfind("References")
    body = text[idx:] if idx >= 0 else text
    seen, refs = set(), []
    for line in body.splitlines():
        for m in DOI_RE.finditer(line):
            doi = m.group(1).rstrip(".").lower()
            if doi in seen:
                continue
            seen.add(doi)
            refs.append({"doi": doi, "text": line.strip()[:300]})
    return refs


def parse_query_files(folder: Path) -> list[dict]:
    out = []
    for p in sorted(folder.glob("*.txt")):
        text = p.read_text(encoding="utf-8")
        m = re.search(r"^Query:\s*(.*?)$", text, re.M)
        traj = re.search(r"trajectories/([0-9a-f-]{8,})", text)
        out.append({"file": p.name, "query": (m.group(1).strip() if m else "")[:1000], "dois": [r["doi"] for r in parse_references(p)],
                    "trajectoryId": traj.group(1) if traj else None})
    return out


def parse_summary(path: Path, kind: str) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    items = []
    if kind == "assay":
        for m in re.finditer(r"Assay Candidate \d+:\nStrategy: (.*?)\nReasoning: (.*?)(?=\n\nAssay Candidate|\Z)", text, re.S):
            items.append({"name": m.group(1).strip(), "reasoning": m.group(2).strip()})
    else:
        for m in re.finditer(r"Therapeutic Candidate \d+:\nCandidate: (.*?)\nHypothesis: (.*?)\nReasoning: (.*?)(?=\n\nTherapeutic Candidate|\Z)", text, re.S):
            items.append({"name": m.group(1).strip(), "hypothesis": m.group(2).strip(), "reasoning": m.group(3).strip()})
    return items


# ---- helpers ------------------------------------------------------------------------------

def _drug_rows(cur: Path) -> dict[str, dict]:
    rows = read_csv(cur / "supp_table1_drugs.csv")
    return {normalize(r["label"]): r for r in rows}


def _lookup_drug(drugs: dict[str, dict], label: str) -> dict | None:
    return drugs.get(normalize(label))


def _dose_for(drugs, label) -> tuple[str, dict]:
    n = normalize(label)
    if n == "aicar + tudca":
        a, t = drugs.get("aicar"), drugs.get("tauroursodeoxycholic acid")
        return (f"{a['working_concentration']} AICAR + {t['working_concentration']} TUDCA", a) if a and t else ("not reported", None)
    if n == "simvastatin + resveratrol":
        s, r = drugs.get("simvastatin"), drugs.get("resveratrol")
        return (f"{s['working_concentration']} simvastatin + {r['working_concentration']} resveratrol", s) if s and r else ("not reported", None)
    row = drugs.get(n)
    return (row["working_concentration"], row) if row else ("not reported in Supplementary Table 1", None)


def _target_ref(resolver, label: str) -> dict:
    n = normalize(label)
    protein = {"mfge8": ("MFGE8", "uniprot:Q08431"), "gas6": ("GAS6", "uniprot:Q14393"), "pros1": ("PROS1", "uniprot:P07225")}
    if n in protein:
        gene, acc = protein[n]
        hit = resolver.protein(gene)
        return {"label": label, "identifier": (hit or {}).get("identifier", acc), "type": "protein"}
    if n in ("aicar + tudca", "simvastatin + resveratrol"):
        parts = [compound_ref(resolver, x.strip()) for x in n.split("+")]
        ids = [p.get("identifier") for p in parts if p.get("identifier")]
        return {"label": label, "type": "compound", "identifier": "+".join(ids) if len(ids) == 2 else None, "note": "combination of two compounds"} if ids else {"label": label, "type": "compound", "note": "combination; identifiers unresolved"}
    if n in ("rgd", "740 y-p"):
        return {"label": label, "type": "other", "note": "peptide; no single-compound identifier assigned"}
    ref = compound_ref(resolver, label)
    return ref


# ---- record construction ----------------------------------------------------------------

def build_robin_records(root: Path, resolver) -> list[dict]:
    cur = root / "curated" / "robin"
    raw = root / "raw" / "robin"
    run1 = raw / "robin_output" / RUN1
    facts = read_yaml(cur / "paper_facts.yaml")
    screens = read_yaml(cur / "screens.yaml")
    drugs = _drug_rows(cur)
    nrefs = read_json(cur / "nature_references.json")
    srefs = read_json(cur / "supplementary_references.json")
    xlsx = raw / "supplementary" / "41586_2026_10652_MOESM3_ESM.xlsx"
    pub = facts["publication"]
    code = facts["code"]

    operator = {"name": facts["operator"]["name"], "type": "Organization", "affiliation": facts["operator"]["affiliation"]}
    edison = facts["operator"]["dataDepositor"]

    sources_common = [
        source("source-publication", PUB_DOI, resolver, label=pub["title"], license=pub["license"], url="https://www.nature.com/articles/s41586-026-10652-y"),
        source("comparator", f"doi:{pub['preprint']['doi']}", resolver, label="arXiv preprint 2505.13400 (v1, 2025-05-19)", note="earlier version of the same work"),
        source("code-repository", code["robin"]["url"], label="Robin repository", url=code["robin"]["url"], checksum=f"git:{code['robin']['commit']}", license=code["robin"]["license"]),
        source("code-repository", code["finch"]["url"], label="Finch repository", url=code["finch"]["url"], checksum=f"git:{code['finch']['commit']}", license=code["finch"]["license"]),
        source("supplementary", "https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-026-10652-y/MediaObjects/41586_2026_10652_MOESM3_ESM.xlsx", label="Supplementary Tables 3-10 (workbook)", license=pub["license"]),
        source("supplementary", "https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-026-10652-y/MediaObjects/41586_2026_10652_MOESM1_ESM.pdf", label="Supplementary Information (Tables 1-2, Figs 1-20)", license=pub["license"]),
    ]
    prior_art = []
    for key, nums in (("prior-art", facts["priorArt"]["y27632PhagocytosisRefs"] + [facts["priorArt"]["mfge8Ref"], facts["priorArt"]["circadianPhagocytosisRef"]]),
                      ("reference", [facts["priorArt"]["rockWetAmdRef"]] + facts["priorArt"]["abca1ApoeRefs"])):
        for n in nums:
            ref = nrefs.get(str(n))
            if ref and ref.get("doi"):
                prior_art.append(source(key, f"doi:{ref['doi']}", resolver, label=f"ref. {n}: {ref['text'][:120]}"))

    m = facts["models"]
    agent_robin = performer("Robin", "software-agent", "hypothesis-generation", provider="FutureHouse", url=code["robin"]["url"], commit=code["robin"]["commit"], version="notebook implementation (paper: agentic implementation translated to a streamlined notebook)")
    agent_crow = performer("Crow", "software-agent", "literature-search", provider=m["crow"]["provider"], note="PaperQA2-based concise literature agent (now 'Literature' on the Edison platform)")
    agent_falcon = performer("Falcon", "software-agent", "literature-search", provider=m["falcon"]["provider"], note="PaperQA2-based deep literature agent")
    llm_synth = performer("o4-mini", "llm", "hypothesis-generation", provider="OpenAI", model="o4-mini")
    llm_judge = performer("Claude 3.7 Sonnet", "llm", "ranking", provider="Anthropic", model="claude-3-7-sonnet")
    llm_prompt = performer("Gemini 2.5 Pro Preview", "llm", "prompt-authoring", provider="Google", model="gemini-2.5-pro-preview", note=m["judgePromptAuthor"]["source"])
    humans = performer("FutureHouse experimental team", "person", "experiment-execution", affiliation="FutureHouse", note="human-generated protocol executed by human scientists; candidate list reviewed by human scientists")

    ent_common = [
        entity("MONDO:0100114", "disease", "dry age-related macular degeneration", scheme="MONDO", altIds=["MONDO:0005150"]),
        entity("NCBITaxon:9606", "organism", "Homo sapiens", scheme="NCBI Taxonomy"),
        entity("CL:0002586", "cellType", "retinal pigment epithelial cell", scheme="Cell Ontology"),
        entity("GO:0006909", "process", "phagocytosis", scheme="Gene Ontology"),
        entity("OBI:0000916", "assay", "flow cytometry assay", scheme="OBI"),
        entity("ror:01p9amb16", "organization", "Edison Scientific, Inc.", url=edison["ror"], role="data depositor and platform operator"),
        entity("agent:robin", "agent", "Robin", url=code["robin"]["url"], extra={"commit": code["robin"]["commit"]}),
        entity("agent:finch", "agent", "Finch", url=code["finch"]["url"], extra={"commit": code["finch"]["commit"]}),
        entity("agent:crow", "agent", "Crow (Edison platform literature agent)"),
        entity("agent:falcon", "agent", "Falcon (Edison platform literature agent)"),
    ]
    arpe = entity("RRID:CVCL_0145", "cellLine", "ARPE-19", scheme="Cellosaurus", extra={"source": "ATCC CRL-2302"})
    common = dict(operator=operator, sourceLicense="CC BY-NC-ND 4.0 (source article); records carry facts, short quotes and pointers only",
                  aiUseDeclaration={"statement": "All hypotheses, experimental directions, data analyses and data figures in the main text were produced by Robin (authors' statement); the wet-lab work and the RNA-seq alignment were human-performed.",
                                    "tools": [{"name": "Robin", "provider": "FutureHouse", "purpose": "hypothesis generation, ranking, data interpretation"},
                                              {"name": "o4-mini", "provider": "OpenAI", "purpose": "synthesis and hypothesis generation"},
                                              {"name": "Claude 3.7 Sonnet", "provider": "Anthropic", "purpose": "LLM judge for pairwise ranking; Finch base model"},
                                              {"name": "Gemini 2.5 Pro Preview", "provider": "Google", "purpose": "generated the judge prompt from expert preferences"}]})
    cost = facts["cost"]
    run_cost = {"llmUsd": cost["robinRunUsd"], "papersProcessed": cost["papersSynthesised"], "humanHours": cost["humanHoursManualWorkflow"],
                "agentCalls": {"crow": cost["crowCallsPerRobinRun"], "falcon": cost["falconCallsPerRobinRun"]},
                "note": f"Authors' estimate for one Robin run (num_queries=5, num_assays=10, num_candidates=30): {cost['crowCallsPerRobinRun']} Crow calls at US${cost['crowUsdPerRun']} and {cost['falconCallsPerRobinRun']} Falcon calls at US${cost['falconUsdPerRun']}; {cost['papersSynthesised']} papers in {cost['papersSynthesisedMinutes']} min vs ~{cost['papersHumanHours']} h for a human; whole workflow {cost['robinHoursWorkflow']} h vs {cost['humanHoursManualWorkflow']} human hours",
                "source": cost["source"]}

    # ---- path ---------------------------------------------------------------------
    path = new_record("path", STUDY, "robin-damd-path",
                      "Robin lab-in-the-loop discovery cycle for dry age-related macular degeneration: RPE phagocytosis enhancers",
                      question="Can a multi-agent system (Robin) propose an in vitro assay and therapeutic candidates for dAMD, analyse the resulting data, and refine candidates so that novel repurposing hits emerge?",
                      hypothesis="Literature-grounded synthesis by language agents can connect known biology (ROCK inhibition restores RPE phagocytosis) to an untried indication (dAMD).",
                      successCriteria="At least one Robin-proposed candidate significantly enhances RPE phagocytosis in vitro, reproducibly across a cell line and primary human RPE cells.",
                      pathType="mixed", outcomeClass="positive",
                      outcomeSummary="Robin selected RPE phagocytosis enhancement; Y-27632 (round 1), ripasudil (round 2) and KL001 (primary cells) enhanced phagocytosis; RNA-seq after ROCK inhibition showed ABCA1 upregulation. OpenAI Deep Research given the same prompt produced 17 candidates with no hits.",
                      confidence={"level": "high", "basis": "hits replicated in a second cell model (RPE-SC) with a different substrate; dose-response confirmed; authors note in vivo validation is still required"},
                      applicabilityConditions={"disease": "MONDO:0100114", "assay": "RPE phagocytosis of pHrodo-labelled beads or bovine ROS, 1 h drug pre-treatment, 3 h uptake", "cellModels": ["ARPE-19 (RRID:CVCL_0145)", "primary human RPE-SC, single donor > 60 y"], "agentStack": "Robin at commit " + code["robin"]["commit"][:7] + "; Crow/Falcon on the Edison platform; o4-mini; Claude 3.7 Sonnet judge; Finch"},
                      untriedBranches=[{"description": "In vivo validation of ripasudil and KL001 in a dAMD model and ultimately a randomized placebo-controlled trial", "status": "proposed-by-authors", "source": "Discussion"},
                                       {"description": "Validate the transcriptional autophagy effect of Y-27632 suggested by GO enrichment", "status": "proposed-by-authors", "source": "Main text, Automated RNA-seq analysis"},
                                       {"description": "RPE-SC ripasudil RNA-seq raw data (Plasmidsaurus 3' counting) is not in the deposited BioProject", "status": "inferred-by-ingest", "source": "Data availability statement lists only PRJNA1464762 (ARPE-19)"}],
                      invalidators=["failure of ripasudil or KL001 to enhance phagocytosis in an in vivo dAMD model", "evidence that the ARPE-19 and RPE-SC hits reflect substrate-specific artefacts of pHrodo labelling"],
                      cost=run_cost,
                      sources=sources_common + prior_art,
                      performers=[agent_robin, agent_crow, agent_falcon, llm_synth, llm_judge, llm_prompt, humans,
                                  performer("Finch", "software-agent", "data-analysis", provider="FutureHouse", url=code["finch"]["url"], commit=code["finch"]["commit"], model=m["finchBase"]["name"])],
                      entities=ent_common + [arpe],
                      provenanceNotes=[
                          "The repository's dAMD run folders (2025-05-28, 2025-05-29) are sample trajectories re-run after the experiments; the candidates they rank are not the ones the paper tested. Only the Finch flow-cytometry results in the repository analyse the real round-1 data.",
                          "Candidate counts per round are not consistent across the paper: the main text says five round-1 and ten round-2 drugs were tested and that Robin produced 19 candidates in total; Supplementary Table 1 lists 6 round-1 and 13 round-2 compounds. Records carry Table 1 groupings with attribution confidence 'inferred'.",
                          "Supplementary Table 5 (RPE-SC screen) contains about 60 arms, more than the 19 Robin + 17 Deep Research candidates the text describes; arms the paper does not attribute are recorded with proposedBy 'not-stated'.",
                          "Source article licence is CC BY-NC-ND 4.0; this record quotes at most short phrases and otherwise points to locations.",
                      ],
                      governance={"humanSubjectData": "RPE-SC cells from one de-identified donor (> 60 y, no known ocular conditions); only aggregate descriptors are recorded"},
                      hasPart=[], **common)
    finalize(path, check=False)
    pid = path["@id"]
    attempts: list[dict] = []

    def add(rec):
        rec.setdefault("relations", []).insert(0, {"type": "isPartOf", "target": pid})
        rec["isPartOf"] = pid
        attempts.append(finalize(rec))
        return rec

    # ---- 1. assay selection (hypothesis generation) -------------------------------
    assay_queries = parse_query_files(run1 / "experimental_assay_literature_reviews")
    assay_items = parse_summary(run1 / "experimental_assay_summary.txt", "assay")
    pairs, names = parse_pairwise_csv(run1 / "experimental_assay_ranking_results.csv")
    bt = bradley_terry(pairs, len(names))
    wins = [0] * len(names)
    for w, _ in pairs:
        wins[w] += 1
    order = sorted(range(len(names)), key=lambda i: -bt[i])
    rank_of = {i: r + 1 for r, i in enumerate(order)}
    assay_reports = {p.name: parse_references(p) for p in sorted((run1 / "experimental_assay_detailed_hypotheses").glob("*.txt"))}
    screened_assays = []
    for i, nm in enumerate(names):
        top = rank_of[i] == 1
        rep = next((v for k, v in assay_reports.items() if normalize(nm).split()[0] in k), [])
        screened_assays.append({"label": nm, "type": "assay", "proposedBy": "robin (o4-mini) from Crow literature reviews", "decision": "included" if top else "deferred",
                                "reason": "top-ranked" if top else "not-selected-for-testing",
                                "score": {"method": "bradley-terry-luce (portolan-ingest MM re-computation approximating choix.ilsr_pairwise, alpha=0.1)", "value": bt[i], "rank": rank_of[i], "comparisons": sum(1 for p in pairs if i in p), "wins": wins[i]},
                                "source": f"{RUN1}/experimental_assay_ranking_results.csv", "references": [r["doi"] for r in rep]})
    winner = names[order[0]]
    f_assay = {"id": "assay-choice", "question": "Which in vitro assay best models a druggable dAMD mechanism for a drug screen?",
               "target": {"label": winner, "type": "assay", "identifier": "OBI:0000916"}, "outcomeClass": "positive", "informativeness": "not-applicable",
               "controls": {"positive": {"kind": "none"}, "negative": {"kind": "none"}},
               "effect": {"metric": "Bradley-Terry strength (rank 1 of 10)", "value": bt[order[0]], "n": len(pairs), "direction": "not-applicable", "note": f"{wins[order[0]]} wins in {sum(1 for p in pairs if order[0] in p)} judged comparisons"},
               "evidence": [{"label": "experimental_assay_ranking_results.csv (45 pairwise judgements) and experimental_assay_summary.txt", "source": code["robin"]["url"], "locator": f"robin_output/{RUN1}/", "derivedBy": "portolan-ingest", "method": "Bradley-Terry MM over the judge's winner/loser columns"},
                            {"label": "Main text, Robin expedites hypothesis generation", "source": PUB_DOI[4:], "quote": "Robin proposed treating dAMD by increasing retinal pigment epithelium (RPE) cell phagocytosis"}],
               "note": "The sample run's choice matches the paper's: phagocytosis assay."}
    add(new_record("attempt", STUDY, "robin-damd-assay-selection", "Robin selects an in vitro assay for dAMD: RPE phagocytosis (sample trajectory of 2025-05-28)",
                   attemptType="hypothesis-generation", pathType="literature",
                   question="Which of ten literature-derived dAMD disease mechanisms and matching in vitro assays should be used to screen therapeutic candidates?",
                   successCriteria="A single assay ranked first by the LLM judge tournament and accepted by the human team.",
                   outcomeClass="positive", findings=[f_assay], screened=screened_assays,
                   screenedSummary={"proposed": len(names), "included": 1, "deferred": len(names) - 1, "judgedComparisons": len(pairs)},
                   stages=[{"stage": "literature-search", "label": "Crow literature reviews on dAMD mechanisms", "performedBy": [agent_crow],
                            "sourcesSearched": [{"name": "Edison platform literature index (PaperQA2 over full-text papers, clinical trial reports and Open Targets)", "platform": "platform.edisonscientific.com", "kind": "agentic retrieval-augmented search"}],
                            "queries": [{"text": q["query"], "file": q["file"], "recordsFound": len(q["dois"]), "trajectoryId": q["trajectoryId"], "verbatim": True} for q in assay_queries],
                            "recordsFound": len({d for q in assay_queries for d in q["dois"]}), "note": "recordsFound counts distinct DOIs cited in the returned reviews, not papers retrieved; the paper reports 151 papers for this stage"},
                           {"stage": "hypothesis-generation", "label": "10 assay strategies proposed", "performedBy": [llm_synth, agent_robin], "outputs": [data_pointer("experimental_assay_summary.txt", path=f"robin_output/{RUN1}/experimental_assay_summary.txt")]},
                           {"stage": "hypothesis-generation", "label": "Crow detailed report per assay", "performedBy": [agent_crow], "outputs": [data_pointer(k, path=f"robin_output/{RUN1}/experimental_assay_detailed_hypotheses/{k}") for k in assay_reports]},
                           {"stage": "ranking", "label": "LLM-judged round-robin tournament", "performedBy": [llm_judge, llm_prompt], "method": facts["ranking"]["method"], "parameters": {"comparisons": len(pairs), "items": len(names)}}],
                   applicabilityConditions={"disease": "MONDO:0100114", "corpusDate": "Edison platform index as of 2025-05-28", "prompts": "Supplementary Figs 2-3 and prompts.py in the repository"},
                   cost={"agentCalls": {"crow": len(assay_queries) + len(assay_reports)}, "llmUsd": round((len(assay_queries) + len(assay_reports)) * cost["crowUsdPerRun"], 2), "note": "derived by portolan-ingest from the authors' per-call cost", "source": cost["source"]},
                   sources=sources_common + [source("sample-trajectory", f"{code['robin']['url']}/tree/{code['robin']['commit']}/robin_output/{RUN1}", label="sample run folder")],
                   performers=[agent_robin, agent_crow, llm_synth, llm_judge], entities=ent_common,
                   provenanceNotes=["Sample trajectory re-run in the repository, dated 2025-05-28; the paper's original run is not published but reached the same assay choice.",
                                    "Scores are recomputed by portolan-ingest from the published pairwise judgements; the repository does not ship the ranked assay CSV."],
                   **common))

    # ---- helper for screens ----------------------------------------------------------
    assay = screens["assay"]

    def screen_findings(scr: dict, table: dict, proposer_filter=None, extra_evidence=None) -> list[dict]:
        roles = screens["labelRoles"]
        pos_label = scr["positiveControl"]["label"]
        pos = table.get(pos_label)
        pos_passed = bool(pos and pos["mean"] >= 1.3)
        findings = []
        for label, agg in table.items():
            role = roles.get(label, "candidate")
            if role == "vehicle":
                continue
            dose, row = _dose_for(drugs, label)
            proposed = (row["group"] if row else "not-stated") if role == "candidate" else f"{role} (authors)"
            if role == "positive-control":
                proposed = "positive-control (authors, ref. 34)"
            if proposer_filter and not proposer_filter(proposed, label):
                continue
            hit = label in scr["hits"]
            if role == "inhibitor-control":
                question = f"Does {label} (actin polymerisation inhibitor) decrease phagocytosis in this assay (directionality control)?"
                outcome = "positive" if agg["mean"] < 0.8 else "inconclusive"
            elif role == "positive-control":
                question = f"Does {label} (designated positive control) increase phagocytosis in this assay?"
                outcome = "positive" if pos_passed else "inconclusive-controls-failed"
            else:
                question = f"Does {label} at {dose} increase phagocytosis by {scr['cellModel']['label']} cells of {scr['substrate'].split(' (')[0]} (1 h pre-treatment, 3 h uptake)?"
                outcome = "positive" if hit else "negative-no-effect"
            ctrl_pos = ({"kind": "designated", "label": pos_label, "identifier": "uniprot:Q08431", "expected": "increase", "observed": f"{pos['mean']:.2f}x (n={pos['n']})" if pos else "not run", "passed": pos_passed, "source": scr["sheet"]}
                        if role != "positive-control" else {"kind": "internal-positive", "label": scr["hits"][0], "expected": "increase", "observed": f"{table[scr['hits'][0]]['mean']:.2f}x", "passed": True, "note": "the designated control is the target of this finding; the strongest hit serves as the internal positive"})
            f = {
                "id": f"{scr['id']}-{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')}",
                "question": question,
                "target": _target_ref(resolver, label),
                "outcomeClass": outcome, "informativeness": "not-applicable",
                "failureModes": ["no-hit-in-screen"] if outcome == "negative-no-effect" else [],
                "effect": {"metric": "normalised MFI of pHrodo signal (fold of DMSO, per plate)", "value": round(agg["mean"], 4), "n": agg["n"],
                           **({"sem": round(agg["sem"], 4)} if agg["sem"] is not None else {}), "direction": "increase" if agg["mean"] > 1.15 else "decrease" if agg["mean"] < 0.85 else "none",
                           "comparedTo": "DMSO vehicle (1.0)", "test": assay["test"], "significant": True if hit else "not reported as a hit",
                           "perReplicate": [round(v, 4) for v in agg["values"]], "note": "mean and s.e.m. computed by portolan-ingest from the per-well normalised values in the sheet"},
                "controls": {"positive": ctrl_pos,
                             "negative": {"kind": "vehicle", "label": assay["vehicle"], "observed": "1.0 by per-plate normalisation", "passed": True}},
                "sensitivity": assay["sensitivityStatement"],
                "replicates": {"wells": agg["n"], "plates": len(set(agg["plates"])), "note": f"one well per plate; plates {sorted(set(agg['plates']))}"},
                "conditions": {"dose": dose, "vendor": row["vendor"] if row else "not reported", "catalog": row["catalog"] if row else "not reported", "preTreatmentMinutes": 60, "uptakeHours": 3, "cells": scr["cellModel"]["label"], "substrate": scr["substrate"], "doseReference": (f"supplementary ref. {row['supp_ref']}" + (f" doi:{srefs[row['supp_ref']]['doi']}" if row and row.get("supp_ref") and srefs.get(row["supp_ref"], {}).get("doi") else "")) if row and row.get("supp_ref") else "none given"},
                "proposedBy": proposed, "proposedByConfidence": (row["attribution_confidence"] if row and role == "candidate" else "stated" if role != "candidate" else "not-stated"),
                "evidence": [{"label": f"Supplementary {scr['sheet']}, rows '{label}'", "source": PUB_DOI[4:], "locator": f"41586_2026_10652_MOESM3_ESM.xlsx#{scr['sheet']}", "values": {"normalisedMFI": [round(v, 4) for v in agg["values"]], "MFI": agg["mfi"], "background": agg["background"], "plates": agg["plates"]}, "derivedBy": "portolan-ingest", "method": "mean and s.e.m. of normalised MFI"}] + (extra_evidence(label) if extra_evidence else []),
            }
            if hit:
                f["evidence"].append({"label": scr["hitsSource"], "source": PUB_DOI[4:], "locator": scr["hitsSource"].split(";")[0]})
            apply_informativeness(f)
            findings.append(f)
        return findings

    def screen_record(slug, scr, table, findings, extra_sources=(), extra_notes=(), extra_performers=(), relations=()):
        cm = scr["cellModel"]
        ents = ent_common + ([arpe] if cm.get("identifier") == "RRID:CVCL_0145" else [entity("sample:rpe-sc-donor", "cellLine", "RPE-SC primary human RPE stem cells", role="cell model", extra={"source": cm["source"]})])
        ents += [entity("uniprot:Q08431", "protein", "MFGE8 (lactadherin), positive control", scheme="UniProt"),
                 entity("catalog:Thermo Fisher:A24858", "instrument", assay["instrument"])]
        seen = set()
        for f in findings:
            t = f["target"]
            if t.get("identifier") and t["identifier"] not in seen and t.get("type") in ("compound", "protein"):
                seen.add(t["identifier"])
                ents.append(entity(t["identifier"], t["type"], t["label"], role="screened treatment", scheme="PubChem" if t["identifier"].startswith("pubchem") else "UniProt"))
        n_hits = sum(1 for f in findings if f["outcomeClass"] == "positive" and "control" not in f["proposedBy"])
        n_neg = sum(1 for f in findings if f["outcomeClass"] == "negative-no-effect")
        return new_record("attempt", STUDY, slug, scr["title"], attemptType="wet-lab", pathType="experiment",
                          question=f"Which of the proposed candidates increase phagocytosis by {cm['label']} cells in the pHrodo flow-cytometry assay?",
                          successCriteria=f"Normalised MFI significantly above the DMSO vehicle ({assay['test']}).",
                          outcomeClass="partial" if n_hits else "negative-no-effect",
                          outcomeSummary=f"{n_hits} hit(s): {', '.join(scr['hits'])}; {n_neg} arms without effect; positive control MFGE8 {table.get('MFGE8', {}).get('mean', float('nan')):.2f}x.",
                          confidence={"level": "medium", "basis": f"n = {scr['wellsPerArm']} wells per arm; hits confirmed by both Finch and human analysis where reported; Dunnett's significance calls are in figure asterisks, not machine-readable"},
                          findings=findings,
                          stages=[{"stage": "experiment", "label": scr["title"], "performedBy": [humans], "protocol": assay["protocol"], "instrument": [assay["instrument"]],
                                   "conditions": {"cells": cm, "substrate": scr["substrate"], "vehicle": assay["vehicle"], "plates": scr["plates"]},
                                   "replicates": {"wellsPerArm": scr["wellsPerArm"]}, "note": f"{assay['dataExclusions']}; {assay['randomization']}; {assay['blinding']}"},
                                  {"stage": "analysis", "label": "human flow-cytometry analysis (FSC/SSC, singlets, DAPI or Hoechst, background gate)", "performedBy": [performer("FutureHouse scientist", "person", "data-analysis", affiliation="FutureHouse")],
                                   "method": scr["sheetDescription"], "outputs": [data_pointer(scr["sheet"], repository="Nature supplementary workbook", path=f"41586_2026_10652_MOESM3_ESM.xlsx#{scr['sheet']}")]}] ,
                          applicabilityConditions={"organism": "NCBITaxon:9606", "cellModel": cm, "assay": assay["label"], "process": "GO:0006909", "substrate": scr["substrate"],
                                                   "preTreatment": "60 min, 37 C, 5% CO2, 0.5% DMSO vehicle", "uptake": "3 h", "readout": "flow cytometry MFI, live singlets, per-plate normalisation to DMSO",
                                                   "doses": "single working concentration per drug from Supplementary Table 1 (highest literature concentration)", "replicates": f"n = {scr['wellsPerArm']} wells"},
                          invalidators=["a dose-response showing activity at other concentrations", "a different substrate (POS vs beads) or a longer uptake window", "replication in another RPE model"],
                          cost={"wetLabRuns": 1, "note": "USD and hands-on time not reported for the wet lab; plate count from the sheet", "source": scr["sheet"]},
                          sources=sources_common + list(extra_sources),
                          performers=[humans, agent_robin] + list(extra_performers), entities=ents,
                          relations=list(relations),
                          provenanceNotes=["Hit calls follow the main text and figure legends; every other arm is 'not reported as a hit' and is classed negative-no-effect with the measured fold change.",
                                           "Plate identifiers are as given in the sheet (250403_RPEassay for both ARPE-19 rounds), which the paper does not explain."] + list(extra_notes),
                          **common)

    # ---- 2. candidates round 1 ---------------------------------------------------------
    cand_queries = parse_query_files(run1 / "therapeutic_candidate_literature_reviews")
    ranked1 = parse_ranked_csv(run1 / "ranked_therapeutic_candidates.csv")
    reports1 = {p.name: parse_references(p) for p in sorted((run1 / "therapeutic_candidate_detailed_hypotheses").glob("*.txt"))}
    pairs1, _ = parse_pairwise_csv(run1 / "therapeutic_candidate_ranking_results.csv")

    def screened_from_ranked(ranked, tested: list[str], proposer: str, run_label: str):
        items = []
        for r in ranked:
            items.append({"label": r["name"], "type": "compound", "proposedBy": proposer, "decision": "deferred", "reason": "not-selected-for-testing",
                          "score": {"method": "bradley-terry-luce (choix.ilsr_pairwise alpha=0.1, as shipped in the repository)", "value": r["strength_score"], "rank": r["rank"]},
                          "source": run_label, "references": [x["doi"] for x in parse_references(Path(""))] if False else [],
                          "note": "sample re-run candidate; not among the candidates the paper tested"})
        for t in tested:
            ref = _target_ref(resolver, t)
            items.append({"label": t, "identifier": ref.get("identifier"), "type": "protein" if ref.get("type") == "protein" else "compound", "proposedBy": proposer, "decision": "included",
                          "reason": "positive-control" if t == "MFGE8" else "selected-for-testing", "source": "Main text; Supplementary Table 1",
                          "note": "from the paper's original run (trajectory not published); ranked list reviewed by human scientists"})
        return [{k: v for k, v in it.items() if v is not None and v != []} for it in items]

    tested_r1 = ["Y-27632", "AICAR + TUDCA", "Exendin-4", "Fingolimod", "MFGE8"]
    add(new_record("attempt", STUDY, "robin-damd-candidates-r1", "Robin proposes therapeutic candidates to enhance RPE phagocytosis (round 1)",
                   attemptType="hypothesis-generation", pathType="literature",
                   question="Which existing drugs could enhance RPE phagocytosis of photoreceptor outer segments and thereby treat dAMD?",
                   successCriteria="A ranked list of candidates with literature-grounded rationale from which the top candidates can be tested.",
                   outcomeClass="positive",
                   findings=[{"id": "r1-selection", "question": "Which candidates were selected for testing in round 1?", "target": {"label": "five candidates: " + ", ".join(tested_r1), "type": "other"},
                              "outcomeClass": "positive", "informativeness": "not-applicable", "controls": {"positive": {"kind": "none"}, "negative": {"kind": "none"}},
                              "evidence": [{"label": "Main text, ROCK inhibitor enhances phagocytosis", "source": PUB_DOI[4:], "quote": "We then selected the top five candidates from this ranking for experimental testing: exendin-4, fingolimod, MFGE8, Y-27632 and the combination of AICAR and TUDCA"}],
                              "note": "MFGE8 was included as a positive control."}],
                   screened=screened_from_ranked(ranked1, tested_r1, "robin-round-1", f"{RUN1}/ranked_therapeutic_candidates.csv"),
                   screenedSummary={"sampleRunRanked": len(ranked1), "sampleRunComparisons": len(pairs1), "paperTested": len(tested_r1)},
                   stages=[{"stage": "literature-search", "label": "Crow literature reviews on the therapeutic landscape", "performedBy": [agent_crow],
                            "sourcesSearched": [{"name": "Edison platform literature index (PaperQA2)", "platform": "platform.edisonscientific.com", "kind": "agentic retrieval-augmented search"}],
                            "queries": [{"text": q["query"], "file": q["file"], "recordsFound": len(q["dois"]), "trajectoryId": q["trajectoryId"], "verbatim": True} for q in cand_queries],
                            "recordsFound": len({d for q in cand_queries for d in q["dois"]}), "note": "distinct DOIs cited in the returned reviews; the paper reports about 400 papers for this stage"},
                           {"stage": "hypothesis-generation", "label": f"{len(ranked1)} candidates proposed (sample run)", "performedBy": [llm_synth, agent_robin]},
                           {"stage": "hypothesis-generation", "label": "Falcon evaluation report per candidate", "performedBy": [agent_falcon], "outputs": [data_pointer(k, path=f"robin_output/{RUN1}/therapeutic_candidate_detailed_hypotheses/{k}") for k in list(reports1)[:5]] , "note": f"{len(reports1)} reports in the sample run, {sum(len(v) for v in reports1.values())} DOIs cited"},
                           {"stage": "ranking", "label": "LLM-judged tournament", "performedBy": [llm_judge], "method": facts["ranking"]["method"], "parameters": {"comparisons": len(pairs1), "items": len(ranked1)}}],
                   applicabilityConditions={"disease": "MONDO:0100114", "goal": "enhance RPE phagocytosis of photoreceptor outer segments", "corpusDate": "Edison platform index as of 2025-05-28"},
                   cost={"agentCalls": {"crow": len(cand_queries), "falcon": len(reports1)}, "llmUsd": round(len(cand_queries) * cost["crowUsdPerRun"] + len(reports1) * cost["falconUsdPerRun"], 2), "note": "derived by portolan-ingest from the authors' per-call cost", "source": cost["source"]},
                   sources=sources_common + [source("sample-trajectory", f"{code['robin']['url']}/tree/{code['robin']['commit']}/robin_output/{RUN1}", label="sample run folder")] + [source("reference", f"doi:{d}", label="cited in Crow literature reviews (sample run)") for d in sorted({d for q in cand_queries for d in q["dois"]})],
                   performers=[agent_robin, agent_crow, agent_falcon, llm_synth, llm_judge, humans], entities=ent_common,
                   provenanceNotes=["The 59 ranked candidates come from the repository's sample re-run of 2025-05-28 (two generation passes merged in one folder); they are recorded as deferred because none was tested.",
                                    "The five tested candidates come from the paper's original run, whose trajectory is not published; they have no scores here."],
                   **common))

    # ---- 3. round 1 screen + 4. Finch analysis ----------------------------------------
    scr1 = next(s for s in screens["screens"] if s["id"] == "r1-arpe19")
    t3 = parse_supp_table(xlsx, scr1["sheet"])
    finch_dir = run1 / "data_analysis"
    fmeta = read_json(finch_dir / "finch_trajectories_meta.json")
    flow0 = read_csv(finch_dir / "d20ee48e" / "flow_results" / "flow_results_0.csv")
    cons = read_csv(finch_dir / "cedcd4d6" / "consensus_results.csv")
    flow_by = {r["drug"]: r for r in flow0}
    cons_by = {r["drug"]: r for r in cons}

    def finch_evidence(label):
        key = {"AICAR and TUDCA": "AICAR + TUDCA", "MFGE8": "MFGE8"}.get(label, label)
        out = []
        if key in flow_by:
            r = flow_by[key]
            out.append({"label": "Finch trajectory 0 flow_results.csv", "source": code["robin"]["url"], "locator": f"robin_output/{RUN1}/data_analysis/d20ee48e/flow_results/flow_results_0.csv",
                        "values": {"meanIntensity": float(r["mean_intensity"]), "stdError": float(r["std_error"]), "pVal": r["p_val"], "adjPVal": r["adj_p_val"]}})
        if key in cons_by:
            out.append({"label": "Finch consensus_results.csv", "source": code["robin"]["url"], "locator": f"robin_output/{RUN1}/data_analysis/cedcd4d6/consensus_results.csv", "values": {"meanIntensity": float(cons_by[key]["mean_intensity"])}})
        return out

    def _fid(prefix, label):
        return f"{prefix}-{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')}"
    human_to_finch = {"AICAR and TUDCA": "AICAR + TUDCA"}
    finch_to_human = {v: k for k, v in human_to_finch.items()}
    finch_ids = {_fid("finch", r["drug"]) for r in flow0 if r["drug"] != "DMSO control" and not r["drug"].startswith("No ")}
    f1 = screen_findings(scr1, t3, extra_evidence=finch_evidence)
    human_ids = {f["id"] for f in f1}
    for f in f1:
        target = _fid("finch", human_to_finch.get(f["target"]["label"], f["target"]["label"]))
        if target in finch_ids:
            f["relatedFindings"] = [f"robin-damd-finch-flow-r1#{target}"]
    rec_s1 = screen_record("robin-damd-screen-r1-arpe19", scr1, t3, f1,
                           extra_notes=["The designated positive control MFGE8 reads 1.46x in the human analysis (Supplementary Table 3, n = 2) but 1.04x in Finch trajectory 0; the wet-lab record uses the human analysis for control assessment and links the Finch record."])
    add(rec_s1)

    finch_perf = performer("Finch", "software-agent", "data-analysis", provider="FutureHouse", url=code["finch"]["url"], commit=code["finch"]["commit"],
                           model=fmeta["d20ee48e"]["tasks"][0]["agent"]["agent_kwargs"]["llm_model"]["name"], platformJob=fmeta["d20ee48e"]["tasks"][0]["job_name"],
                           trajectoryIds=fmeta["d20ee48e"]["task_ids"] + fmeta["cedcd4d6"]["task_ids"], version=fmeta["d20ee48e"]["tasks"][0]["agent"]["agent_type"])
    f_finch = []
    for r in flow0:
        d = r["drug"]
        if d == "DMSO control" or d.startswith("No "):
            continue
        adj = float(r["adj_p_val"]) if r["adj_p_val"] not in ("NA", "") else None
        val = float(r["mean_intensity"])
        is_ctrl = d == "MFGE8"
        pos_pass = flow_by["MFGE8"] and float(flow_by["MFGE8"]["adj_p_val"]) < 0.05
        if is_ctrl:
            # A designated control that fails is itself an informative negative *for this analysis* when an
            # internal positive (Y-27632) shows the analysis could detect increases; the other arms become
            # inconclusive-controls-failed through their controls block.
            outcome = "positive" if pos_pass else "negative-no-effect"
        elif adj is not None and adj < 0.05 and val > 1:
            outcome = "positive"
        else:
            outcome = "negative-no-effect"
        f = {"id": f"finch-{re.sub(r'[^a-z0-9]+', '-', d.lower()).strip('-')}",
             "question": f"Does {d} increase pHrodo MFI versus DMSO in the round-1 ARPE-19 data, as analysed by Finch (trajectory 0)?",
             "target": _target_ref(resolver, d), "outcomeClass": outcome, "informativeness": "not-applicable",
             "effect": {"metric": "fold change of MFI vs DMSO (Finch gating: flowMeans clusters, singlets, DAPI)", "value": val, "sem": float(r["std_error"]), "direction": "increase" if val > 1.15 else "decrease" if val < 0.85 else "none",
                        "comparedTo": "DMSO control", "test": "one-sided test with multiple-testing adjustment chosen by Finch", "pValue": r["p_val"], "adjustedPValue": r["adj_p_val"], "significant": bool(adj is not None and adj < 0.05)},
             "controls": {"positive": {"kind": "designated", "label": "MFGE8", "identifier": "uniprot:Q08431", "expected": "increase", "observed": f"{float(flow_by['MFGE8']['mean_intensity']):.2f}x, adj P {flow_by['MFGE8']['adj_p_val']}", "passed": bool(pos_pass)} if not is_ctrl else {"kind": "internal-positive", "label": "Y-27632", "observed": f"{float(flow_by['Y-27632']['mean_intensity']):.2f}x", "passed": True},
                          "negative": {"kind": "vehicle", "label": "DMSO control", "observed": "1.0", "passed": True}},
             "sensitivity": "not stated by Finch; the human analysis of the same data distinguished MFGE8 from vehicle at n = 3",
             "evidence": finch_evidence(d) + [{"label": "Fig. 2c-f (Finch trajectory plots, human-formatted)", "source": PUB_DOI[4:], "locator": "Fig. 2"}],
             "note": ("Finch trajectory 0 calls this significant; the paper's human analysis (Supplementary Table 3) does not report it as a hit." if outcome == "positive" and d != "Y-27632" else
                      "Designated positive control not distinguished from vehicle in this trajectory (1.04x); the human analysis found 1.46x." if is_ctrl else ""),
             }
        back = _fid("r1-arpe19", finch_to_human.get(d, d))
        if back in human_ids:
            f["relatedFindings"] = [f"robin-damd-screen-r1-arpe19#{back}"]
        if not f["note"]:
            f.pop("note")
        apply_informativeness(f)
        f_finch.append(f)
    add(new_record("attempt", STUDY, "robin-damd-finch-flow-r1", "Finch autonomous analysis of the round-1 ARPE-19 flow cytometry data (5 trajectories + consensus)",
                   attemptType="computational", pathType="computation",
                   question="Which round-1 treatments significantly increased pHrodo MFI over DMSO according to Finch's autonomous gating and statistics?",
                   successCriteria="A flow_results.csv per trajectory with fold change, s.e.m., P and adjusted P per drug, and a consensus across trajectories.",
                   outcomeClass="partial",
                   outcomeSummary="Y-27632 2.80x (adj P 3.8e-49) in trajectory 0; fingolimod, exendin-4 and AICAR also called significant at ~1.3x, which the human analysis did not confirm; MFGE8 positive control not distinguished from vehicle in this trajectory.",
                   confidence={"level": "low", "basis": "single trajectory values; 3 of 5 trajectories produced output; consensus values differ in scale; analysis-dependent control outcome"},
                   findings=f_finch,
                   stages=[{"stage": "analysis", "label": "gating, MFI and statistics (5 parallel trajectories, R, max 30 steps, 15 min timeout)", "performedBy": [finch_perf, agent_robin],
                            "method": "prompt ANALYSIS_QUERIES['flow_cytometry'] (prompts.py): flowMeans clustering of FSC/SSC, singlet and live gating, per-plate normalisation to DMSO, one-sided tests with multiple-testing adjustment",
                            "parameters": {"queryHashSha256": fmeta["d20ee48e"]["tasks"][0]["query_sha256"], "language": "R", "maxSteps": 30, "parallel": 5, "environment": fmeta["d20ee48e"]["tasks"][0]["environment_name"]},
                            "software": [{"name": "flowMeans (R)"}, {"name": "R"}],
                            "inputs": [data_pointer("round-1 .fcs files and well metadata (upload folder flow_250508)", note="raw FCS files are not in the repository or a public archive")],
                            "outputs": [data_pointer(f"flow_results_{i}.csv", path=f"robin_output/{RUN1}/data_analysis/d20ee48e/flow_results/flow_results_{i}.csv") for i in (0, 2, 4)],
                            "startTime": fmeta["d20ee48e"]["tasks"][0]["created_at"]},
                           {"stage": "analysis", "label": "consensus meta-analysis across trajectories", "performedBy": [finch_perf], "method": "prompt CONSENSUS_QUERIES['flow_cytometry']",
                            "outputs": [data_pointer("consensus_results.csv", path=f"robin_output/{RUN1}/data_analysis/cedcd4d6/consensus_results.csv")], "startTime": fmeta["cedcd4d6"]["tasks"][0]["created_at"]},
                           {"stage": "interpretation", "label": "Robin data interpretation and follow-up proposal (RNA-seq of Y-27632)", "performedBy": [llm_synth, agent_robin], "method": "DATA_INTERPRETATION and FOLLOWUP prompts (prompts.py); Fig. 3a"}],
                   applicabilityConditions={"data": "round-1 ARPE-19 pHrodo bead screen, 3 plates", "analysisDate": "2025-05-29", "agent": finch_perf["model"]},
                   invalidators=["re-running the trajectories yields different gates; the paper states Finch results vary between runs"],
                   cost={"agentCalls": {"finch": 6}, "note": "Finch cost excluded from the authors' run estimate (run once per iteration)", "source": cost["source"]},
                   sources=sources_common + [source("trajectory", f"https://platform.edisonscientific.com/trajectories/{t}", label="Finch trajectory (Edison platform, login required)") for t in finch_perf["trajectoryIds"]],
                   performers=[finch_perf, agent_robin], entities=ent_common + [arpe],
                   relations=[{"type": "analysed", "target": rec_s1["@id"]}, {"type": "wasDerivedFrom", "target": rec_s1["@id"]}],
                   provenanceNotes=["Trajectory metadata (ids, timestamps, model, job) extracted from results_20250529_115604.json in the repository; the 49 MB notebook states are not vendored.",
                                    "Control discrepancy: Finch trajectory 0 did not separate MFGE8 from vehicle, whereas the human analysis of the same data did; the paper treats the human analysis as confirmation."],
                   **common))

    # ---- 5. candidates round 2 ---------------------------------------------------------
    ranked2 = parse_ranked_csv(run1 / "ranked_therapeutic_candidates_experimental.csv")
    cand_queries2 = parse_query_files(run1 / "therapeutic_candidate_literature_reviews_experimental")
    reports2 = {p.name: parse_references(p) for p in sorted((run1 / "therapeutic_candidate_detailed_hypotheses_experimental").glob("*.txt"))}
    tested_r2 = [r["label"] for r in read_csv(cur / "supp_table1_drugs.csv") if r["group"] == "robin-round-2"]
    add(new_record("attempt", STUDY, "robin-damd-candidates-r2", "Robin proposes a second round of candidates informed by the round-1 results (ROCK inhibition)",
                   attemptType="hypothesis-generation", pathType="literature",
                   question="Given that Y-27632 enhanced RPE phagocytosis, which further drugs (excluding those already tested) could enhance RPE phagocytosis for dAMD?",
                   successCriteria="A new ranked candidate list incorporating the experimental insights, from which ten drugs can be tested.",
                   outcomeClass="positive",
                   findings=[{"id": "r2-selection", "question": "Which candidates were selected for round-2 testing?", "target": {"label": f"{len(tested_r2)} candidates incl. ripasudil, KL001, NECA", "type": "other"},
                              "outcomeClass": "positive", "informativeness": "not-applicable", "controls": {"positive": {"kind": "none"}, "negative": {"kind": "none"}},
                              "evidence": [{"label": "Main text, A repurposed drug for dAMD; Fig. 4a; Supplementary Table 1", "source": PUB_DOI[4:], "quote": "Robin also conducted a subsequent iteration of candidate drug hypotheses (Fig. 4a). We tested ten of these drugs experimentally"}],
                              "note": "Supplementary Table 1 lists 13 round-2 compounds (simvastatin and resveratrol were tested as one combination); the text says ten."}],
                   screened=screened_from_ranked(ranked2, tested_r2, "robin-round-2", f"{RUN1}/ranked_therapeutic_candidates_experimental.csv"),
                   screenedSummary={"sampleRunRanked": len(ranked2), "paperTested": len(tested_r2)},
                   stages=[{"stage": "interpretation", "label": "experimental insights from round 1 injected into query generation (EXPERIMENTAL_INSIGHTS_APPENDAGE)", "performedBy": [llm_synth, agent_robin]},
                           {"stage": "literature-search", "label": "Crow literature reviews (round 2)", "performedBy": [agent_crow],
                            "queries": [{"text": q["query"], "file": q["file"], "recordsFound": len(q["dois"]), "trajectoryId": q["trajectoryId"], "verbatim": True} for q in cand_queries2],
                            "recordsFound": len({d for q in cand_queries2 for d in q["dois"]})},
                           {"stage": "hypothesis-generation", "label": f"{len(ranked2)} candidates proposed (sample run)", "performedBy": [llm_synth, agent_robin, agent_falcon], "note": f"{len(reports2)} Falcon reports"},
                           {"stage": "ranking", "label": "LLM-judged tournament (300 random pairs)", "performedBy": [llm_judge], "method": facts["ranking"]["method"]}],
                   applicabilityConditions={"disease": "MONDO:0100114", "goal": "enhance RPE phagocytosis; drugs already tested excluded by prompt", "priorResults": "round-1 flow cytometry (Y-27632 hit)"},
                   cost={"agentCalls": {"crow": len(cand_queries2), "falcon": len(reports2)}, "llmUsd": round(len(cand_queries2) * cost["crowUsdPerRun"] + len(reports2) * cost["falconUsdPerRun"], 2), "note": "derived by portolan-ingest from the authors' per-call cost", "source": cost["source"]},
                   sources=sources_common + [source("sample-trajectory", f"{code['robin']['url']}/tree/{code['robin']['commit']}/robin_output/{RUN1}", label="sample run folder (files with _experimental suffix)")],
                   performers=[agent_robin, agent_crow, agent_falcon, llm_synth, llm_judge, humans], entities=ent_common,
                   relations=[{"type": "informedBy", "target": attempts[-1]["@id"], "note": "Finch round-1 analysis fed the candidate generation prompt"}],
                   provenanceNotes=["Sample re-run candidates (30) are deferred; the paper's round-2 compounds (Supplementary Table 1 order, attribution inferred) are included.",
                                    "Ripasudil, the paper's round-2 hit, is not among the sample re-run's 30 candidates."],
                   **common))

    # ---- 6. round 2 screen -------------------------------------------------------------
    scr2 = next(s for s in screens["screens"] if s["id"] == "r2-arpe19")
    t4 = parse_supp_table(xlsx, scr2["sheet"])
    f2 = screen_findings(scr2, t4)
    kl = next(f for f in f2 if f["target"]["label"] == "KL001")
    kl["relatedFindings"] = ["robin-damd-screen-rpesc#rpesc-kl001"]
    kl["note"] = "No effect in ARPE-19 with beads; KL001 was a hit in RPE-SC with ROS substrate (model- or substrate-dependent)."
    rec_s2 = screen_record("robin-damd-screen-r2-arpe19", scr2, t4, f2,
                           extra_notes=["Supplementary Table 4 repeats the round-1 arms on the same plate identifiers; round-2 compounds are those listed after MFGE-8 in Supplementary Table 1."],
                           relations=[{"type": "informedBy", "target": attempts[-1]["@id"]}])
    add(rec_s2)

    # ---- 7. RNA-seq -----------------------------------------------------------------
    runs = parse_ena_runs(raw / "sra" / "ena_read_run_PRJNA1464762.tsv")
    rna = facts["rnaSeq"]
    sra_ptrs = [data_pointer(f"{r['run_accession']} ({r['sample_alias']})", repository="NCBI SRA / ENA", accession=r["run_accession"], url=f"https://www.ebi.ac.uk/ena/browser/view/{r['run_accession']}",
                             checksum=f"md5:{r['md5_r1']}", size=int(r["base_count"]), role="raw reads (R1 md5; R2 md5 in ENA)", format="fastq.gz paired",
                             note=f"{r['condition']}{' + beads' if r['beads'] else ''}; {r['read_count']} reads; {r['instrument_model']}") for r in runs]
    unanalysed = sorted({r["condition"] for r in runs} - {"wildtype", "Y27632"})
    gene = resolver.gene("ABCA1") or {}
    f_rna = [
        {"id": "abca1-up", "question": "Which genes are differentially expressed in ARPE-19 cells treated with Y-27632 (with beads) versus vehicle?",
         "target": {"label": "ABCA1", "identifier": gene.get("identifier", "HGNC:29"), "type": "gene"}, "outcomeClass": "positive", "informativeness": "not-applicable",
         "effect": {"metric": "fold change (DESeq2 Wald test)", "value": rna["headline"]["foldChange"], "direction": "increase", "adjustedPValue": rna["headline"]["adjustedP"], "comparedTo": "untreated (vehicle) with beads", "n": 3, "significant": True},
         "controls": {"positive": {"kind": "none", "note": "no spike-in or known-response gene set used as positive control"}, "negative": {"kind": "vehicle", "label": "vehicle control", "observed": "reference condition", "passed": True}},
         "replicates": {"biological": 3, "note": "6 samples, 2 conditions, in the DGE contrast"},
         "evidence": [{"label": "Main text, Automated RNA-seq analysis", "source": PUB_DOI[4:], "quote": "The DGE analysis identified a threefold upregulation (adjusted P = 2.13 x 10-83) of ABCA1"},
                      {"label": "Fig. 3b-d; Supplementary Fig. 14 (human analysis)", "source": PUB_DOI[4:], "locator": "Fig. 3"}],
         "conditions": {"treatment": "Y-27632 20 uM, 1 h pre-treatment, pHrodo beads 3 h", "library": rna["library"], "sequencing": rna["sequencing"]}},
        {"id": "go-enrichment", "question": "Which processes are enriched among Y-27632-regulated genes?", "target": {"label": "actin filament organisation, small GTPase signalling, autophagy (GO BP)", "type": "process"},
         "outcomeClass": "positive", "informativeness": "not-applicable", "controls": {"positive": {"kind": "none"}, "negative": {"kind": "vehicle", "label": "vehicle", "passed": True}},
         "evidence": [{"label": "Fig. 3d; Supplementary Fig. 14b", "source": PUB_DOI[4:], "values": {"terms": rna["goTerms"], "consensusRule": rna["consensus"]}}],
         "note": "Authors: further work is necessary to validate any effects on autophagy."},
        {"id": "abca1-rpesc", "question": "Is ABCA1 also regulated by ripasudil in primary RPE-SC cells (with or without ROS)?", "target": {"label": "ABCA1", "identifier": gene.get("identifier", "HGNC:29"), "type": "gene"},
         "outcomeClass": "partial", "informativeness": "not-applicable", "controls": {"positive": {"kind": "none"}, "negative": {"kind": "vehicle", "label": "DMSO", "passed": True}},
         "effect": {"metric": "log2 fold change as printed in the legend (with ROS, without ROS)", "value": ", ".join(str(x) for x in rna["rpescValidation"]["abca1Log2FC"]), "pValue": ", ".join(rna["rpescValidation"]["pValues"]), "n": 4, "direction": "increase", "note": "the legend's sign is negative while the text and legend call ABCA1 upregulated; recorded as printed"},
         "evidence": [{"label": "Supplementary Fig. 17 legend", "source": PUB_DOI[4:], "locator": rna["rpescValidation"]["source"]}],
         "note": "Raw data for this experiment is not in the deposited BioProject."},
    ]
    add(new_record("attempt", STUDY, "robin-damd-rnaseq-arpe19", "RNA-seq of Y-27632-treated ARPE-19 cells proposed by Robin and analysed by Finch: ABCA1 upregulation",
                   attemptType="wet-lab", pathType="mixed",
                   question="What transcriptional changes accompany ROCK-inhibitor-enhanced phagocytosis in RPE cells?",
                   successCriteria="Differentially expressed genes (|log2FC| > 1, adjusted P < 0.05) reproducible across Finch trajectories, with an interpretable enrichment.",
                   outcomeClass="positive",
                   outcomeSummary="ABCA1 up 3-fold (adj P 2.13e-83); actin, small-GTPase and autophagy terms enriched; ABCA1 change also seen in RPE-SC with ripasudil.",
                   confidence={"level": "medium", "basis": "n = 3; consensus across 8 Finch trajectories and a human re-analysis; RPE-SC validation legend has a sign inconsistency"},
                   findings=f_rna,
                   stages=[{"stage": "experiment", "label": "ARPE-19 treatment, RNA extraction (Maxwell RSC 48, SimplyTissue kit), QC (Bioanalyzer)", "performedBy": [humans], "conditions": {"cells": "ARPE-19 in 24-well plates, triplicate", "conditions": sorted({r['condition'] for r in runs}), "beads": "with and without pHrodo beads"}},
                           {"stage": "sequencing", "label": rna["sequencing"], "performedBy": [humans], "instrument": ["Illumina NextSeq 2000"]},
                           {"stage": "computation", "label": "alignment and gene counting (human-performed)", "performedBy": [performer("FutureHouse scientist", "person", "data-analysis", affiliation="FutureHouse")], "method": rna["alignment"],
                            "software": [{"name": "HISAT2", "identifier": "RRID:SCR_015530"}, {"name": "samtools", "identifier": "RRID:SCR_002105"}, {"name": "featureCounts (Subread)", "identifier": "RRID:SCR_012919"}, {"name": "GENCODE", "version": "v44"}]},
                           {"stage": "analysis", "label": "differential expression and enrichment (Finch, 8 trajectories + consensus)", "performedBy": [performer("Finch", "software-agent", "data-analysis", provider="FutureHouse", url=code["finch"]["url"], commit=code["finch"]["commit"], model=m["finchBase"]["name"])],
                            "method": rna["dge"], "software": [{"name": "R", "version": "4.2.0", "identifier": "RRID:SCR_001905"}, {"name": "DESeq2", "version": "1.36.0", "identifier": "RRID:SCR_015687"}, {"name": "EnhancedVolcano", "version": "1.14.0", "identifier": "RRID:SCR_018931"}, {"name": "biomaRt"}]},
                           {"stage": "interpretation", "label": "Robin proposes the experiment (Fig. 3a) and interprets results", "performedBy": [agent_robin, llm_synth]}],
                   applicabilityConditions={"organism": "NCBITaxon:9606", "cellLine": "RRID:CVCL_0145", "treatment": "Y-27632 20 uM (Cayman 10005583), 1 h, then pHrodo beads 3 h", "readout": "bulk RNA-seq (OBI:0003090), 75 bp PE, NextSeq 2000", "contrast": "Y-27632 + beads vs wild type + beads"},
                   untriedBranches=[{"description": f"Deposited RNA-seq samples for {c} (with and without beads, n = 3) are in PRJNA1464762 but no analysis of them is reported", "status": "data-deposited-not-analysed", "source": "ENA run table vs Methods (six samples analysed)",
                                     "dataAvailable": [p for p in sra_ptrs if c.lower() in p["note"].lower().split(";")[0]]} for c in unanalysed]
                                  + [{"description": "Validate the transcriptional autophagy effect of Y-27632", "status": "proposed-by-authors", "source": "Main text"}],
                   invalidators=["a human re-analysis with different filters that removes ABCA1 from the significant set", "failure to replicate ABCA1 induction in primary RPE without pHrodo beads"],
                   cost={"wetLabRuns": 1, "agentCalls": {"finch": 9}, "note": "sequencing and hands-on cost not reported", "source": "Methods"},
                   sources=sources_common + [source("data-deposit", "https://www.ncbi.nlm.nih.gov/bioproject/PRJNA1464762", label=facts["data"]["sra"]["title"], note=f"BioProject {facts['data']['sra']['bioproject']} ({facts['data']['sra']['secondary']}), {len(runs)} runs, first public {facts['data']['sra']['firstPublic']}, center {facts['data']['sra']['centerName']}", data=sra_ptrs)]
                           + [source("reference", f"doi:{nrefs[str(n)]['doi']}", resolver, label=f"ref. {n}") for n in ("60", "61", "62") if nrefs.get(str(n), {}).get("doi")],
                   performers=[agent_robin, humans, performer("Finch", "software-agent", "data-analysis", provider="FutureHouse", url=code["finch"]["url"], commit=code["finch"]["commit"], model=m["finchBase"]["name"])],
                   entities=ent_common + [arpe, entity("OBI:0003090", "assay", "bulk RNA-seq assay", scheme="OBI"), entity(gene.get("identifier", "HGNC:29"), "gene", "ABCA1", scheme="HGNC", altIds=[f"ensembl:{gene.get('ensembl')}" if gene.get("ensembl") else "ensembl:ENSG00000165029", "uniprot:O95477"]),
                                          entity("bioproject:PRJNA1464762", "dataset", facts["data"]["sra"]["title"], url="https://www.ncbi.nlm.nih.gov/bioproject/PRJNA1464762")],
                   relations=[{"type": "informedBy", "target": attempts[2]["@id"], "note": "proposed by Robin after the round-1 analysis"}],
                   provenanceNotes=[f"ENA lists {len(runs)} runs across conditions {sorted({r['condition'] for r in runs})}, each with and without beads; the Methods describe a six-sample contrast (Y-27632 vs untreated).",
                                    "The RPE-SC ripasudil RNA-seq (Supplementary Fig. 17) has no accession in the Data availability statement."],
                   **common))

    # ---- 8. RPE-SC screen ------------------------------------------------------------------
    scr3 = next(s for s in screens["screens"] if s["id"] == "rpesc")
    t5 = parse_supp_table(xlsx, scr3["sheet"])
    f3 = screen_findings(scr3, t5)
    rec_s3 = screen_record("robin-damd-screen-rpesc", scr3, t5, f3,
                           extra_notes=["Arms whose proposer the paper does not state are recorded with proposedBy 'not-stated'; Deep Research arms are inferred from Supplementary Table 1 order.",
                                        "Two spellings of trehalose appear in the sheet ('trehalose' n = 4, 'trehelose' n = 2); both are kept as recorded."],
                           relations=[{"type": "confirms", "target": rec_s2["@id"], "note": "ripasudil and Y-27632 hits replicate in primary cells with ROS substrate"},
                                      {"type": "extends", "target": rec_s2["@id"], "note": "KL001 is a hit here but not in ARPE-19 with beads"}])
    add(rec_s3)

    # ---- 9. Deep Research comparator --------------------------------------------------------
    dr = facts["deepResearch"]
    dr_rows = [r for r in read_csv(cur / "supp_table1_drugs.csv") if r["group"] == "deep-research"]
    dr_labels = {normalize(r["label"]) for r in dr_rows}
    f_dr = [dict(f, id=f["id"].replace("rpesc-", "dr-")) for f in f3 if normalize(f["target"]["label"]) in dr_labels]
    dr_perf = performer("Deep Research", "software-agent", "candidate-generation", provider="OpenAI", dateUsed=m["deepResearch"]["dateUsed"], note="via the ChatGPT user interface; 2-3 clarifying questions answered by the authors")
    add(new_record("attempt", STUDY, "deep-research-damd-candidates", "OpenAI Deep Research given Robin's candidate-generation prompt: 17 unique candidates, none enhanced RPE-SC phagocytosis",
                   attemptType="hypothesis-generation", pathType="mixed",
                   question="Does a general-purpose research agent (OpenAI Deep Research) given the same prompt propose RPE phagocytosis enhancers for dAMD that validate experimentally?",
                   successCriteria="At least one Deep Research candidate significantly increases pHrodo-ROS uptake by RPE-SC cells (Dunnett's test).",
                   outcomeClass="negative-no-effect",
                   outcomeSummary=f"{dr['requested']} candidates requested, {dr['unique']} unique (duplicates: {', '.join(dr['duplicates'])}); {dr['hits']} hits; ROCK inhibition was not proposed.",
                   confidence={"level": "medium", "basis": "single prompt session (June 2025); screened at n = 4 wells alongside Robin's candidates with the same controls"},
                   findings=f_dr + [{"id": "dr-headline", "question": "Did any Deep Research candidate enhance RPE-SC phagocytosis?", "target": {"label": "Deep Research candidate set (17 unique)", "type": "other"},
                                     "outcomeClass": "negative-no-effect", "informativeness": "informative", "failureModes": ["no-hit-in-screen"],
                                     "effect": {"metric": "hits among unique candidates", "value": 0, "n": dr["unique"], "direction": "none", "comparedTo": "Robin: 3 hits among 19 candidates (ripasudil, Y-27632, KL001)", "significant": True},
                                     "controls": {"positive": {"kind": "designated", "label": "MFGE8", "identifier": "uniprot:Q08431", "expected": "increase", "observed": f"{t5['MFGE8']['mean']:.2f}x (n=4)", "passed": True}, "negative": {"kind": "vehicle", "label": assay["vehicle"], "passed": True}},
                                     "sensitivity": assay["sensitivityStatement"],
                                     "evidence": [{"label": "Main text, Validation of the Robin architecture; Extended Data Fig. 6", "source": PUB_DOI[4:], "quote": "None of the suggested drugs by Deep Research were hits in this assay, and notably, Deep Research did not suggest ROCK inhibition"}],
                                     "informativenessReason": "designated positive control passed; vehicle clean; sensitivity stated"}],
                   screened=[{"label": r["label"], "identifier": _target_ref(resolver, r["label"]).get("identifier"), "type": "protein" if normalize(r["label"]) == "pros1" else "compound", "proposedBy": "openai-deep-research", "decision": "included", "reason": "tested-in-comparator-arm",
                              "source": "Supplementary Table 1 (order-based attribution)", "note": r.get("note") or None} for r in dr_rows],
                   screenedSummary={"requested": dr["requested"], "unique": dr["unique"], "listedInTable1": len(dr_rows), "hits": 0},
                   stages=[{"stage": "hypothesis-generation", "label": "Deep Research session with Robin's candidate prompt (Supplementary Fig. 8)", "performedBy": [dr_perf], "method": dr["prompt"]},
                           {"stage": "experiment", "label": "screened in RPE-SC alongside Robin's candidates (same experiment)", "performedBy": [humans]}],
                   applicabilityConditions={"prompt": "Robin candidate-generation prompt (Supplementary Fig. 8)", "agentVersion": "OpenAI Deep Research as of June 2025", "assay": "RPE-SC pHrodo-ROS phagocytosis, n = 4"},
                   invalidators=["a later Deep Research version proposing ROCK inhibitors or other validated enhancers", "testing the candidates at other doses"],
                   cost={"agentCalls": {"deep-research": 1}, "note": "cost not reported", "source": "Methods"},
                   sources=sources_common, performers=[dr_perf, humans], entities=ent_common,
                   relations=[{"type": "comparedWith", "target": pid}, {"type": "wasDerivedFrom", "target": rec_s3["@id"], "note": "findings are the Deep Research arms of the RPE-SC screen"}],
                   provenanceNotes=["Deep Research attribution is inferred from Supplementary Table 1 order (15 named compounds) plus the stated duplicates; the 17th unique candidate could not be identified from the paper.",
                                    "Only 15 of the 17 unique candidates can be matched to sheet rows; the two duplicates (resveratrol, GW3965) are already listed."],
                   **common))

    # ---- 10. ablation reference check -----------------------------------------------------
    ab = facts["ablation"]
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    t9 = [r for r in wb["Supp Table 9"].iter_rows(values_only=True)][1:]
    crow = [r for r in t9 if r[0] and str(r[0]).startswith("Crow")]
    llm = [r for r in t9 if r[0] and str(r[0]).strip().startswith("LLM")]
    def frac(rows):
        refs = sum(int(r[2]) for r in rows); hal = sum(int(r[4]) for r in rows)
        return refs, hal, (hal / refs if refs else 0)
    c_refs, c_hal, _ = frac(crow); l_refs, l_hal, _ = frac(llm)
    f_ab = [
        {"id": "crow-refs", "question": "What fraction of references in Crow-generated assay proposals could not be found (hallucinated)?", "target": {"label": "Crow (PaperQA2 literature agent)", "type": "other", "identifier": "agent:crow"},
         "outcomeClass": "positive", "informativeness": "not-applicable", "effect": {"metric": "hallucinated references / unique references across 15 proposals", "value": f"{c_hal}/{c_refs}", "n": len(crow), "direction": "none", "significant": True},
         "controls": {"positive": {"kind": "none"}, "negative": {"kind": "none"}},
         "evidence": [{"label": "Supplementary Table 9 (Crow rows)", "source": PUB_DOI[4:], "locator": "41586_2026_10652_MOESM3_ESM.xlsx#Supp Table 9", "values": {"proposals": len(crow), "uniqueReferences": c_refs, "hallucinated": c_hal}, "derivedBy": "portolan-ingest", "method": "column sums"}],
         "note": ab["crowAssayProposalsHallucinated"]},
        {"id": "o4mini-refs", "question": "What fraction of references in o4-mini-generated assay proposals (Crow ablated) were hallucinated?", "target": {"label": "o4-mini without literature agent", "type": "other"},
         "outcomeClass": "positive", "informativeness": "not-applicable", "effect": {"metric": "hallucinated references / unique references across 15 proposals", "value": f"{l_hal}/{l_refs}", "n": len(llm), "direction": "increase", "comparedTo": "Crow 0%", "note": ab["o4miniAssayProposalsHallucinated"]},
         "controls": {"positive": {"kind": "none"}, "negative": {"kind": "none"}},
         "evidence": [{"label": "Supplementary Table 9 (LLM rows); Extended Data Fig. 4b", "source": PUB_DOI[4:], "values": {"proposals": len(llm), "uniqueReferences": l_refs, "hallucinated": l_hal}, "derivedBy": "portolan-ingest", "method": "column sums"}],
         "note": "The finding is positive for the architecture claim (literature agents suppress hallucinated references); it is a negative result for unaided LLM proposal writing."},
        {"id": "finch-rubric", "question": "How closely did Finch follow expert rubrics on the round-2 flow cytometry and RNA-seq tasks?", "target": {"label": "Finch", "type": "other", "identifier": "agent:finch"},
         "outcomeClass": "positive", "informativeness": "not-applicable", "effect": {"metric": "rubric adherence (mean +/- s.e.m., n = 3 runs)", "value": f"flow cytometry {ab['finchRubric']['flowCytometry']}; RNA-seq {ab['finchRubric']['rnaSeq']}", "n": 3, "direction": "not-applicable"},
         "controls": {"positive": {"kind": "none"}, "negative": {"kind": "none"}},
         "evidence": [{"label": "Extended Data Fig. 5a; Supplementary Figs 18-19 (rubrics)", "source": PUB_DOI[4:]}, {"label": "BixBench subset (Supplementary Table 10)", "source": PUB_DOI[4:], "values": ab["bixbench"]}]},
    ]
    add(new_record("attempt", STUDY, "robin-ablation-reference-check", "Validation of the Robin architecture: hallucinated-reference rates with and without literature agents, and Finch rubric adherence",
                   attemptType="evaluation", pathType="computation",
                   question="Do the literature agents (Crow, Falcon) and the analysis harness (Finch) measurably improve proposal grounding and analysis quality over the bare LLMs?",
                   successCriteria="Lower hallucinated-reference rates and better judge rankings for wild-type Robin than ablated Robin; Finch above the bare model on rubric and benchmark tasks.",
                   outcomeClass="positive",
                   outcomeSummary="Crow: 0 hallucinated references in 15 assay proposals vs 44.5% for o4-mini alone; ablating Falcon or both agents raised hallucinations and lowered judge rankings; Finch 100%/86% rubric adherence; BixBench 22.8% vs 1.6%.",
                   confidence={"level": "medium", "basis": "human reference check blinded to source; n = 10-15 proposals per arm; judge is itself an LLM"},
                   findings=f_ab,
                   stages=[{"stage": "computation", "label": "ablations: replace Crow and/or Falcon with o4-mini; 50 proposals per arm; blinded human reference check; LLM-judge tournament", "performedBy": [llm_judge, performer("FutureHouse scientist (blinded)", "person", "reference-check", affiliation="FutureHouse")], "method": "Methods, Crow and Falcon ablation experiments; permutation test (10,000 permutations) on mean rank difference"}],
                   applicabilityConditions={"agents": "Crow, Falcon, o4-mini, Claude 3.7 Sonnet judge, Finch on Claude 3.7 Sonnet", "date": "2025", "tasks": "dAMD assay and candidate proposals; BixBench 170-question subset"},
                   cost={"note": "not reported", "source": "Methods"},
                   sources=sources_common + [source("supplementary", "https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-026-10652-y/MediaObjects/41586_2026_10652_MOESM3_ESM.xlsx", label="Supplementary Tables 6-10")],
                   performers=[agent_crow, agent_falcon, llm_synth, llm_judge], entities=ent_common,
                   provenanceNotes=["Ablation tables 6-8 list per-proposal reference validation counts; only the assay-proposal check (Table 9) is summarised here."],
                   **common))

    path["hasPart"] = [a["@id"] for a in attempts]
    check_valid(path)
    return [path] + attempts
