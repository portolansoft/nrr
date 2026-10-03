"""Converter for Altundal et al. 2025, 'Lessons from Failed Attempts of Computationally Guided Synthesis of
Aluminosilicate STF and IFR Zeolites in Hydroxide Media' (Chem. Mater. 37, 9689-9702,
doi:10.1021/acs.chemmater.5c01751, CC BY 4.0; full text from Europe PMC, PMC12747119).

First chemistry and materials study in the corpus, chosen because it is a whole pipeline rather than one
experiment: machine-learning classifiers, de novo design and synthesis-energy ranking over more than 10,000
organic structure-directing agents (OSDAs), three OSDAs taken to the bench, and every hydrothermal synthesis
giving amorphous material or the wrong phase. It tests whether a record can hold a computational prediction
refuted by experiment, and whether the model's own validation metrics can stand in for a sensitivity statement
(they cannot: they describe the classifier, not the synthesis).
"""
from __future__ import annotations

from pathlib import Path

from nrr.ingest.common import (
    check_valid, data_pointer, entity, finalize, new_record, performer, read_csv, read_json, read_yaml, source,
)
from nrr.rules import apply_informativeness

STUDY = "acs-zeolite"
PUB_DOI = "doi:10.1021/acs.chemmater.5c01751"
PMCID = "PMC12747119"
SI_FILE = "cm5c01751_si_001.pdf"
IZA_URL = "https://europe.iza-structure.org/IZA-SC/framework.php?STC={code}"
FRAMEWORKS = {
    "STF": "STF (SSZ-35 type), one-dimensional 10-ring medium-pore zeolite; target",
    "IFR": "IFR (ITQ-4 / SSZ-42 / MCM-58 type), one-dimensional 12-ring large-pore zeolite; target",
    "AEI": "AEI, predicted most stable phase for many OSDAs",
    "CHA": "CHA (chabazite), predicted most stable phase for most OSDAs",
    "MTW": "MTW (ZSM-12), obtained with QG001780m2 although ranked 13th in the prediction",
    "MOR": "MOR (mordenite), obtained with QG001780m2 in sodium- or potassium-containing gels",
}
OSDA_IDS = {"QHGWEBIGEQBZPY": "inchikey:QHGWEBIGEQBZPY-RWMBFGLXNA-N", "QG001780m": "osda:qg001780m", "QG001780m2": "osda:qg001780m2"}


def _int(v):
    return int(v) if v not in (None, "") else None


def parse_syntheses(path: Path) -> list[dict]:
    rows = read_csv(path)
    for r in rows:
        r["entry"] = int(r["entry"])
        r["temperature_c"] = int(r["temperature_c"])
        r["time_days"] = int(r["time_days"])
    return rows


def parse_candidates(path: Path) -> list[dict]:
    rows = read_csv(path)
    for r in rows:
        r["rank_of_target"] = int(r["rank_of_target"])
        r["synthesized"] = r["synthesized"] == "yes"
    return rows


def parse_models(path: Path) -> list[dict]:
    rows = read_csv(path)
    for r in rows:
        for k in ("accuracy_pct", "classified_stf", "classified_non_stf", "n"):
            r[k] = _int(r[k])
    return rows


def _row_evidence(r: dict) -> dict:
    return {"label": f"{r['table']} entry {r['entry']}: Si/Al {r['si_al']}, {r['temperature_c']} °C, {r['time_days']} d: {r['phase']}",
            "source": PUB_DOI[4:], "locator": r["source"],
            "values": {k: v for k, v in r.items() if k not in ("source", "osda_name") and v not in ("", None)}}


def build_zeolite_records(root: Path, resolver) -> list[dict]:
    cur, raw = root / "curated" / "zeolite", root / "raw" / "zeolite"
    facts = read_yaml(cur / "pub_facts.yaml")
    syntheses = parse_syntheses(cur / "syntheses.csv")
    candidates = parse_candidates(cur / "candidates.csv")
    models = parse_models(cur / "models.csv")
    fetched = read_json(raw / "europepmc" / "record.json")["fetched"]

    pub, scr, ml, hyd, osdas, res = (facts["publication"], facts["screening"], facts["machineLearning"],
                                     facts["hydrothermal"], facts["osdas"], facts["results"])
    org_hit = resolver.organization(facts["operator"]["name"]) or {}
    operator = {"name": facts["operator"]["name"], "type": "Organization"}
    if org_hit.get("identifier"):
        operator["identifier"] = org_hit["identifier"]

    si_meta = fetched["files"][f"si/{SI_FILE}"]
    si_pointer = data_pointer(SI_FILE, repository="Europe PMC", accession=PMCID, url=fetched["supplementaryFiles"],
                              checksum="sha256:" + si_meta["sha256"], size=si_meta["size"], format="application/pdf",
                              role="Supporting Information: methods, candidate OSDA tables S14-S17, synthesis tables S18-S22")
    sources_common = [
        source("source-publication", PUB_DOI, resolver, label=pub["title"], url=pub["url"], license=pub["license"],
               note=pub["licenseStatement"]),
        source("supplementary", f"pmc:{PMCID}/{SI_FILE}", resolver, label="Supporting Information (PDF)",
               url=fetched["supplementaryFiles"], license=pub["license"], data=[si_pointer],
               note=pub["dataAvailability"]),
    ]
    prior = ([source("prior-art", f"doi:{d}", resolver, label="synthesis-energy descriptor, earlier validation") for d in facts["priorArt"]["esynMethod"]]
             + [source("prior-art", f"doi:{facts['priorArt']['osdb']}", resolver, label="OSDB: a priori control of zeolite phase competition"),
                source("prior-art", f"doi:{facts['priorArt']['stfOsdaPreviousSynthesis']}", resolver, label="earlier synthesis of the STF candidate OSDA (Shvets et al.)"),
                source("prior-art", f"doi:{facts['priorArt']['aluminosilicateIfrFluoride']}", resolver, label="aluminosilicate IFR in fluoride media with benzylquinuclidinium")]
             + [source("reference", f"doi:{d}", resolver, label="de novo OSDA design method") for d in facts["priorArt"]["deNovoDesign"]]
             + [source("comparator", f"doi:{d}", resolver, label="computationally guided zeolite synthesis that succeeded") for d in facts["priorArt"]["computationallyGuidedSuccesses"]])

    # --- entities -------------------------------------------------------------------------------
    ents = [entity(f"iza:{code}", "material", desc, scheme="IZA-SC framework type code", url=IZA_URL.format(code=code),
                   role="target zeolite framework" if code in ("STF", "IFR") else "competing or obtained framework")
            for code, desc in FRAMEWORKS.items()]
    for code, o in osdas.items():
        ents.append(entity(OSDA_IDS[code], "compound", f"{o['name']} ({code})", role="organic structure-directing agent synthesised and tested",
                           scheme="InChIKey" if code == "QHGWEBIGEQBZPY" else None,
                           note=o.get("purity") if code == "QHGWEBIGEQBZPY" else "no InChIKey or registry number is given in the article; named in SI Section S8",
                           extra={"predictedPhasesInOrder": o["prediction"], "counterion": o["counterion"]}))
    for sw in facts["software"]:
        ents.append(entity(f"software:{sw['name']}", "software", sw["name"], role=sw["role"],
                           extra={k: v for k, v in {"version": sw.get("version"), "publisher": sw.get("publisher")}.items() if v} or None))
    for db in facts["databases"]:
        ents.append(entity(f"database:{db['name'].split(' ')[0].lower()}", "dataset", db["name"], role=db["role"], url=db["url"],
                           extra={"doi": db["doi"]} if db.get("doi") else None))
    ents.append(entity(org_hit.get("identifier", "org:itq-upv-csic"), "organization", facts["operator"]["name"], note=facts["operator"]["note"]))

    people = [performer(c["name"], "person", "writing", affiliation=c["affiliation"],
                        note="listed author; the article carries no author-contribution statement") for c in facts["contributors"]]

    applicability = {
        "medium": facts["targets"]["constraint"],
        "targets": {k: v for k, v in facts["targets"].items() if k != "constraint"},
        "gelCompositions": [t["gel"] for t in hyd["table1"]],
        "siAlRange": "pure silica to Si/Al 10 (Al2O3 per SiO2 from 0 to 0.05)",
        "temperatureRangeC": "150 to 200", "durationDays": "7 to 50",
        "inorganicCations": "none for the STF and first IFR series; Na+ up to 0.18 Na2O and K+ up to 0.29 K2O per SiO2 for the second IFR series",
        "modelAssumptions": "framework aluminium as the only charge compensation (no silanol defects), intact OSDA, no solvent or counter-cation effects, thermodynamic ranking by synthesis energy without nucleation kinetics",
        "productIdentification": hyd["productIdentification"],
        "osdasScreened": scr["totalsStated"],
        "note": "conclusions are bounded to hydroxide media; the authors note that both frameworks may remain accessible in fluoride or pure-silica systems",
    }
    common = dict(operator=operator, sourceLicense="CC BY 4.0", domainTags=["chemistry", "materials"],
                  aiUseDeclaration={"statement": facts["aiUse"]["statement"]})
    cost = {"wetLabRuns": len(syntheses), "wallClockDays": max(r["time_days"] for r in syntheses),
            "note": f"{len(syntheses)} phase determinations across {len({(r['table'], r['entry']) for r in syntheses})} gel compositions, the longest run 50 days; the number of autoclaves per table entry is not stated; no monetary or compute cost is reported",
            "source": "SI Tables S18, S20, S21, S22"}

    # --- stages ---------------------------------------------------------------------------------
    searched = [{"name": db["name"], "kind": "database", "url": db["url"], "coverage": db["role"]} for db in facts["databases"]]
    stage_screen = {
        "stage": "computation", "label": "stabilisation-energy screen of OSDB and Pareto-front selection (Strategy 1 for STF, shoebox filter for IFR)",
        "performedBy": people, "software": [{"name": "zeodock"}],
        "sourcesSearched": searched,
        "parameters": {"osdbTotal": scr["osdbTotal"], "osdbInPapers": scr["osdbInPapers"], "osdbNotInPapers": scr["osdbNotInPapers"],
                       "activeForStf": scr["activeForStf"], "inactiveCloseToPareto": scr["inactiveCloseToPareto"],
                       "paretoTolerance": scr["paretoTolerance"], "ifrShoeboxMatches": scr["ifrShoeboxMatches"]},
        "recordsFound": scr["osdbTotal"],
    }
    stage_design = {
        "stage": "computation", "label": "de novo design and stochastic (multiple) virtual combinatorial chemistry of quaternary ammonium OSDAs",
        "performedBy": people, "software": [{"name": "Synopsis de novo design"}, {"name": "zeodock"}],
        "parameters": {"designedForStf": scr["deNovoDesignedForStf"], "stfNearPareto": scr["deNovoNearPareto"],
                       "generatedForIfr": scr["ifrGenerated"], "ifrPassedFilters": scr["ifrPassedFilters"],
                       "searchSpace": scr["searchSpace"], "reagentPriceCap": scr["reagentPriceCap"]},
        "sourcesSearched": [s for s in searched if s["name"] == "ChemSpace"],
    }
    stage_ml = {
        "stage": "analysis", "label": "machine-learning classifiers for STF-directing OSDAs (LDA and two neural networks)",
        "performedBy": people, "software": [{"name": "STATISTICA", "version": "12"}],
        "parameters": {"descriptors": ml["descriptors"], "model1": ml["model1"], "model2": ml["model2"], "model3": ml["model3"],
                       "selectionRule": ml["selectionRule"]},
        "note": ml["source"],
    }
    stage_rank = {
        "stage": "ranking", "label": "synthesis-energy (E_syn) ranking of each OSDA across the target and its competing phases",
        "performedBy": people, "software": [{"name": "zeoTsda"}],
        "parameters": {"competingPhasesStf": scr["competingPhasesStf"], "competingPhasesIfr": scr["competingPhasesStf"] + scr["competingPhasesIfrExtra"],
                       "mostStablePhaseAmongInPapers": scr["esynMostStableAmongInPapers"], "selectionCriterion": "target among the top three phases by E_syn"},
        "note": scr["loadingExplanation"],
    }

    def synth_stage(label, rows, extra_method=""):
        return {"stage": "experiment", "label": label, "performedBy": people,
                "method": ("TEOS and an aluminium source added to the OSDA hydroxide solution, ethanol evaporated, static heating in Teflon-lined "
                           "stainless-steel autoclaves, filtration, washing, drying at 100 °C; OSDA iodide or bromide exchanged to hydroxide on Amberlite IRN-78 "
                           + extra_method).strip(),
                "instrument": ["Teflon-lined stainless-steel autoclaves", "powder X-ray diffractometer"],
                "conditions": {"gelCompositions": sorted({r["table"] for r in rows}), "siAl": sorted({r["si_al"] for r in rows}),
                               "temperaturesC": sorted({r["temperature_c"] for r in rows}), "timesDays": sorted({r["time_days"] for r in rows}),
                               "aluminiumSources": sorted({r["al_source"] for r in rows}), "agitation": sorted({r["agitation"] for r in rows})},
                "replicates": {"phaseDeterminations": len(rows), "gelCompositions": len({(r["table"], r["entry"]) for r in rows}),
                               "note": "two sampling times per entry; number of autoclaves per entry not stated"}}

    stage_xrd = {"stage": "analysis", "label": "phase identification by powder X-ray diffraction and OSDA stability by NMR of the mother liquors",
                 "performedBy": people, "method": "PXRD of the recovered solids (SI Figures S10, S12, S14); liquid 1H and 13C NMR of mother liquors (SI Figures S9, S11, S13, S15)",
                 "note": hyd["productIdentification"]}

    # --- path -----------------------------------------------------------------------------------
    path = new_record(
        "path", STUDY, "acs-zeolite-path",
        "Computationally guided search for OSDAs to crystallise aluminosilicate STF and IFR in hydroxide media",
        question="Can synthesis-energy ranking, machine-learning classification and de novo design over more than 10,000 OSDAs find an organic structure-directing agent that crystallises aluminosilicate STF or IFR in hydroxide media?",
        hypothesis=facts["purpose"],
        successCriteria="A hydrothermal synthesis in hydroxide media whose powder X-ray diffraction pattern matches aluminosilicate STF or IFR, with an OSDA predicted by synthesis energy to favour that phase.",
        pathType="mixed", outcomeClass="negative-not-achievable",
        outcomeSummary=f"{res['headline']} {res['verdict']}.",
        confidence={"level": "low", "basis": "no positive-control synthesis with a known-good OSDA, no XRD detection limit, the STF OSDA a mixture of stereoisomers, and all three OSDAs degraded under the hydrothermal conditions"},
        nextSteps=facts["nextSteps"], openQuestions=facts["openQuestions"],
        untriedBranches=[{"description": s, "status": "proposed-by-authors", "source": "Conclusions"} for s in facts["nextSteps"]]
                       + [{"description": "Run one of the 36 OSDAs known to direct pure-silica STF through the same hydroxide aluminosilicate protocol, as a positive control for the protocol.", "status": "inferred-by-ingest", "source": "ingest reading of Table 1 and SI Section S9"},
                          {"description": "Synthesise and test the ten shortlisted candidates in SI Tables S14 to S17 that were not taken to the bench.", "status": "inferred-by-ingest", "source": "SI Tables S14 to S17"}],
        invalidators=["crystallisation of aluminosilicate STF or IFR in hydroxide media with any of the shortlisted OSDAs once OSDA stability is controlled",
                      "a positive-control synthesis showing the protocol yields a known phase, which would turn the amorphous results into evidence against the predictions",
                      "a synthesis-energy model including OSDA degradation, solvation and counter-cations that predicts the amorphous outcomes"],
        applicabilityConditions=applicability, cost=cost,
        sources=sources_common + prior, performers=people, entities=ents,
        governance={"humanSubjectData": "none", "biosecurityTier": "none"},
        provenanceNotes=[
            f"The STF OSDA was obtained as a mixture of stereoisomers: {osdas['QHGWEBIGEQBZPY']['purity']}. Its elemental analysis is off: {osdas['QHGWEBIGEQBZPY']['elementalAnalysis']}.",
            f"Source inconsistency on the first IFR OSDA: {osdas['QG001780m']['inconsistency']}.",
            hyd["table2Note"],
            "The article has no author-contribution statement; every author is recorded with the role 'writing' only.",
            "Table 1 of the article is machine-readable in the JATS XML; Table 2 is an image and was transcribed from the PMC figure file; the synthesis outcomes come from SI Tables S18, S20, S21 and S22, which are text in the PDF.",
            "The computational screen's sensitivity and specificity figures (SI Tables S7 to S12) are recorded as findings about the classifiers. The ingest does not count them as a sensitivity statement for the hydrothermal findings, because they describe the classifier's recall on literature OSDAs, not the synthesis's ability to detect a crystalline phase.",
        ],
        hasPart=[], **common)
    finalize(path, check=False)
    pid = path["@id"]
    attempts: list[dict] = []

    def attempt(slug, title, question, success, outcome, findings, stages, attempt_type, **kw):
        rec = new_record("attempt", STUDY, slug, title, attemptType=attempt_type, pathType="computation" if attempt_type == "computational" else "experiment",
                         question=question, successCriteria=success, outcomeClass=outcome, findings=findings, stages=stages,
                         applicabilityConditions=applicability, cost=kw.pop("cost", cost), sources=sources_common + kw.pop("sources", []),
                         isPartOf=pid, entities=ents, performers=people,
                         relations=[{"type": "isPartOf", "target": pid}] + kw.pop("relations", []), **common, **kw)
        attempts.append(finalize(rec))
        return rec

    no_ctrl = {"positive": {"kind": "none"}, "negative": {"kind": "none"}}

    # --- synthesis attempts (built first so the screen's refuted predictions can point at them) ----------------
    def synthesis_finding(fid, target, rows, failure_modes, question):
        phases = sorted({r["phase"] for r in rows})
        f = {
            "id": fid, "question": question,
            "target": {"label": f"aluminosilicate {target}", "type": "material", "identifier": f"iza:{target}"},
            "outcomeClass": "negative-not-achievable", "informativeness": "uninformative",
            "failureModes": failure_modes,
            "effect": {"metric": f"syntheses yielding aluminosilicate {target}", "value": 0, "n": len(rows), "direction": "none",
                       "note": f"phases observed: {', '.join(phases)}"},
            "controls": {"positive": {"kind": "none", "note": "no OSDA known to crystallise a zeolite under this protocol was run alongside, so an amorphous product cannot be separated from a protocol failure"},
                         "negative": {"kind": "none", "note": "no OSDA-free gel was run; the pure-silica entries vary the aluminium content and are conditions, not controls"}},
            "replicates": {"note": f"{len(rows)} phase determinations across {len({(r['table'], r['entry']) for r in rows})} gel compositions; two sampling times per entry; number of autoclaves per entry not stated"},
            "conditions": {"osda": rows[0]["osda_name"], "tables": sorted({r["table"] for r in rows}),
                           "siAl": sorted({r["si_al"] for r in rows}), "temperaturesC": sorted({r["temperature_c"] for r in rows}),
                           "timesDays": sorted({r["time_days"] for r in rows}), "phasesObserved": phases,
                           "inorganicCations": sorted({r["inorganic_cation"] for r in rows})},
            "evidence": [_row_evidence(r) for r in rows],
        }
        apply_informativeness(f)
        return f

    def stability_finding(fid, code, outcome, metric, value, locator, note):
        o = osdas[code]
        f = {"id": fid, "question": f"Did {o['name']} ({code}) survive the hydrothermal conditions intact?",
             "target": {"label": f"{o['name']} ({code})", "type": "compound", "identifier": OSDA_IDS[code]},
             "outcomeClass": outcome, "informativeness": "not-applicable",
             "effect": {"metric": metric, "value": value, "direction": "not-applicable", "note": o["stability"]},
             "controls": dict(no_ctrl, negative={"kind": "background", "label": "NMR spectrum of the as-made OSDA salt", "expected": "intact cation resonances", "observed": "intact", "passed": True}),
             "evidence": [{"label": "NMR of recovered mother liquors", "source": PUB_DOI[4:], "locator": locator, "quote": o["stability"][:300]}],
             "note": note}
        apply_informativeness(f)
        return f

    stf_rows = [r for r in syntheses if r["table"] == "S18"]
    m_rows = [r for r in syntheses if r["table"] == "S20"]
    m2_rows = [r for r in syntheses if r["table"] in ("S21", "S22")]

    f_stf = synthesis_finding("stf-not-formed", "STF", stf_rows, ["phase-not-formed", "decomposition"],
                              "Does 6-ethyl-1-methyl-5-azaspiro[4.5]decan-5-ium hydroxide crystallise aluminosilicate STF from an aluminosilicate gel in hydroxide media?")
    f_stf_osda = stability_finding("osda-degraded", "QHGWEBIGEQBZPY", "positive", "OSDA degradation in the mother liquor", "original resonances lost after 30 and 50 days",
                                   "SI Figure S9", "The degradation is the authors' explanation for the failed structure direction; it is recorded as a positive observation, not as a control.")
    rec_stf = attempt("acs-zeolite-stf-synthesis",
                      "Hydrothermal synthesis targeting aluminosilicate STF with the shortlisted spirocyclic OSDA gives only amorphous solids",
                      "Does the computationally shortlisted OSDA QHGWEBIGEQBZPY crystallise aluminosilicate STF in hydroxide media across Si/Al, temperature and time?",
                      "A powder X-ray diffraction pattern matching STF.", f_stf["outcomeClass"], [f_stf, f_stf_osda],
                      [synth_stage("hydrothermal syntheses targeting STF (SI Table S18)", stf_rows), stage_xrd], "wet-lab",
                      outcomeSummary="Eight gel compositions from pure silica to Si/Al 10, at 150 to 200 °C for 14 to 50 days, all gave amorphous solids. The OSDA was a mixture of stereoisomers and degraded during synthesis.",
                      confidence={"level": "low", "basis": "no positive-control synthesis; OSDA purity and stability compromised"},
                      cost={"wetLabRuns": len(stf_rows), "wallClockDays": max(r["time_days"] for r in stf_rows), "note": "16 phase determinations over 8 gel compositions", "source": "SI Table S18"},
                      provenanceNotes=[f"OSDA purity: {osdas['QHGWEBIGEQBZPY']['purity']}", f"Elemental analysis: {osdas['QHGWEBIGEQBZPY']['elementalAnalysis']}"])
    f_m = synthesis_finding("ifr-not-formed", "IFR", m_rows, ["phase-not-formed", "decomposition"],
                            "Does N-benzyl-N,N,2-trimethylpropan-2-aminium hydroxide crystallise aluminosilicate IFR from an aluminosilicate gel in hydroxide media without inorganic cations?")
    f_m_osda = stability_finding("osda-degraded", "QG001780m", "positive", "OSDA degradation in the mother liquor", "intact cation progressively lost after 29 and 40 days",
                                 "SI Figure S11", "The authors' explanation for the failed structure direction.")
    rec_m = attempt("acs-zeolite-ifr-synthesis-qg001780m",
                    "Hydrothermal synthesis targeting aluminosilicate IFR with QG001780m gives only amorphous solids",
                    "Does the designed OSDA QG001780m crystallise aluminosilicate IFR in hydroxide media without inorganic cations?",
                    "A powder X-ray diffraction pattern matching IFR.", f_m["outcomeClass"], [f_m, f_m_osda],
                    [synth_stage("hydrothermal syntheses targeting IFR without inorganic cations (SI Table S20)", m_rows), stage_xrd], "wet-lab",
                    outcomeSummary="Six gel compositions from pure silica to Si/Al 10, at 175 to 200 °C for 14 to 42 days, all gave amorphous solids. The OSDA degraded during synthesis.",
                    confidence={"level": "low", "basis": "no positive-control synthesis; OSDA degraded"},
                    cost={"wetLabRuns": len(m_rows), "wallClockDays": max(r["time_days"] for r in m_rows), "note": "12 phase determinations over 6 gel compositions", "source": "SI Table S20"},
                    provenanceNotes=[f"Source inconsistency: {osdas['QG001780m']['inconsistency']}"])

    f_m2 = synthesis_finding("ifr-not-formed", "IFR", m2_rows, ["phase-not-formed", "impurity-phase"],
                             "Does N-benzyl-N,N-dimethylpropan-2-aminium crystallise aluminosilicate IFR under SSZ-42-type (Na+) or MCM-58-type (K+) hydroxide conditions?")
    f_m2["conditions"]["mtwRankInPrediction"] = osdas["QG001780m2"]["mtwRank"]
    f_m2_osda = stability_finding("osda-intact", "QG001780m2", "positive", "OSDA degradation after 1 to 4 days in Na+ or K+ gels", "about 3 percent",
                                  "SI Figures S13 and S15", "Unlike the other two OSDAs this one survived, so degradation does not explain the absence of IFR here.")
    rec_m2 = attempt("acs-zeolite-ifr-synthesis-qg001780m2",
                     "Hydrothermal synthesis targeting aluminosilicate IFR with QG001780m2 gives amorphous solids, MOR, ZSM-12 or dense phases",
                     "Does the designed OSDA QG001780m2 crystallise aluminosilicate IFR under SSZ-42-type or MCM-58-type hydroxide conditions, with or without Na+ or K+?",
                     "A powder X-ray diffraction pattern matching IFR.", f_m2["outcomeClass"], [f_m2, f_m2_osda],
                     [synth_stage("hydrothermal syntheses targeting IFR in SSZ-42-type and MCM-58-type gels (SI Tables S21, S22)", m2_rows,
                                  "; for these series aluminium metal or aluminium sulfate, fumed or colloidal silica, NaOH or KOH, rotation at 60 rpm"), stage_xrd], "wet-lab",
                     outcomeSummary="Fourteen gel compositions with Si/Al 10 to 100, with or without Na+ or K+, at 150 to 175 °C for 7 to 21 days gave amorphous solids, mordenite, ZSM-12 (MTW, ranked 13th in the prediction) or dense phases; never IFR.",
                     confidence={"level": "low", "basis": "no positive-control synthesis; the OSDA survived, so the absence of IFR is not explained by degradation"},
                     cost={"wetLabRuns": len(m2_rows), "wallClockDays": max(r["time_days"] for r in m2_rows), "note": "14 phase determinations over 14 gel compositions; done at POSTECH", "source": "SI Tables S21, S22"},
                     provenanceNotes=[hyd["table2Note"]])

    # --- the computational screen, with its predictions recorded as refuted by the syntheses --------------------
    def classifier_finding(fid, model, label, sens, spec, n, note, locator):
        f = {"id": fid, "question": f"How well does {label} separate STF-directing from non-STF OSDAs?",
             "target": {"label": f"{label} ({model})", "type": "software"},
             "outcomeClass": "partial", "informativeness": "not-applicable",
             "effect": {"metric": "sensitivity for STF-directing OSDAs, training set", "value": sens, "unit": "%", "n": n, "direction": "not-applicable",
                        "comparedTo": f"specificity {spec} % for non-STF OSDAs, training set", "note": note},
             "controls": no_ctrl,
             "conditions": {"descriptors": ml["descriptors"]},
             "evidence": [{"label": f"classification matrix for {model}", "source": PUB_DOI[4:], "locator": locator,
                           "values": {m["dataset"] + "/" + m["class"]: {k: m[k] for k in ("accuracy_pct", "classified_stf", "classified_non_stf", "n")}
                                      for m in models if m["model"] == model}}]}
        apply_informativeness(f)
        return f

    f_c1 = classifier_finding("classifier-model-1", "Model 1", "linear discriminant analysis on volume and Ic", 92, 58, 453,
                              "a volume filter of 175 to 208 A3 raises specificity to 81 % (train) and 79 % (test) without changing sensitivity", "SI Tables S7 and S8")
    f_c2 = classifier_finding("classifier-model-2", "Model 2", "multilayer perceptron 8-3-2", 21, 99, 368,
                              "recognised none of the 8 STF OSDAs in the external set of 171; the authors call it overly strict for a small set and suited to screening millions", "SI Tables S9 and S10")
    f_c3 = classifier_finding("classifier-model-3", "Model 3", "multilayer perceptron 8-5-2 trained on chemically similar inactives", 42, 74, 63,
                              "validation set 75 % (4 STF) and 80 % (10 non-STF); external set of 547 inactives 80 % correct (436)", "SI Tables S11 and S12")

    f_land = {"id": "esyn-landscape", "question": "For how many of the 78 OSDAs taken from OSDB (36 active for STF, 42 inactive-close) is aluminosilicate STF the lowest-synthesis-energy phase?",
              "target": {"label": "aluminosilicate STF", "type": "material", "identifier": "iza:STF"},
              "outcomeClass": "positive", "informativeness": "not-applicable",
              "effect": {"metric": "OSDAs for which STF is the most stable phase by E_syn", "value": 0, "n": 78, "direction": "none",
                         "comparedTo": "AEI most stable for 19, CHA for 38, BEC for 17, BEA for 4", "note": scr["loadingExplanation"]},
              "controls": no_ctrl,
              "conditions": {"competingPhases": scr["competingPhasesStf"], "medium": "hydroxide, aluminosilicate"},
              "evidence": [{"label": "Results 4.2.1.1, OSDAs in Papers", "source": PUB_DOI[4:], "locator": "section 4.2.1.1",
                            "values": {"mostStable": scr["esynMostStableAmongInPapers"], "n": 78}, "quote": scr["stfNeverMostStable"]}],
              "note": "A computational result the authors treat as the explanation for why STF and IFR are hard to obtain as aluminosilicates; it is not itself a failed attempt."}
    apply_informativeness(f_land)

    def candidates_finding(fid, target, value, n, note, locators):
        f = {"id": fid, "question": f"Which screened or designed OSDAs place aluminosilicate {target} among the top three phases by synthesis energy?",
             "target": {"label": f"aluminosilicate {target}", "type": "material", "identifier": f"iza:{target}"},
             "outcomeClass": "partial", "informativeness": "not-applicable",
             "effect": {"metric": f"OSDAs with {target} ranked in the top three phases", "value": value, "n": n, "direction": "not-applicable", "note": note},
             "controls": no_ctrl,
             "evidence": [{"label": loc, "source": PUB_DOI[4:], "locator": loc,
                           "values": {"candidates": [c["sda_name"] for c in candidates if c["target"] == target and c["source"] == loc]}} for loc in locators]}
        apply_informativeness(f)
        return f

    f_stfc = candidates_finding("stf-candidates", "STF", scr["stfCandidatesFromPapers"] + scr["stfCandidatesFromMl"], None,
                                f"{scr['stfCandidatesFromPapers']} from OSDB 'in papers' ({scr['stfCandidatesFromPapersSplit']}) and {scr['stfCandidatesFromMl']} from the machine-learning screen of 580 unpublished OSDAs; STF is never ranked first",
                                ["SI Table S14", "SI Table S15"])
    f_ifrc = candidates_finding("ifr-candidates", "IFR", scr["ifrTop3"] + scr["ifrShoeboxTop3"], scr["ifrShoeboxMatches"] + scr["ifrEvaluatedByEsyn"],
                                f"{scr['ifrShoeboxTop3']} of {scr['ifrShoeboxMatches']} shoebox-matched OSDB entries and {scr['ifrTop3']} of {scr['ifrEvaluatedByEsyn']} designed candidates; IFR is never ranked first",
                                ["SI Table S16", "SI Table S17"])
    f_denovo = {"id": "de-novo-stf", "question": "Does de novo design or virtual combinatorial chemistry produce an OSDA with STF among its top three phases by synthesis energy?",
                "target": {"label": "aluminosilicate STF", "type": "material", "identifier": "iza:STF"},
                "outcomeClass": "negative-not-achievable", "informativeness": "uninformative",
                "effect": {"metric": "designed OSDAs near the Pareto front with STF in the top three phases", "value": 0, "n": scr["deNovoNearPareto"], "direction": "none",
                           "note": f"{scr['deNovoDesignedForStf']} OSDAs were designed; {scr['deNovoNearPareto']} within 0.2 kJ per mol Si of the Pareto front were ranked by E_syn"},
                "controls": {"positive": {"kind": "none", "note": "the design run was not shown to rediscover a known STF-directing OSDA"},
                             "negative": {"kind": "none"}},
                "conditions": {"competingPhases": 19},
                "evidence": [{"label": "Results 4.3, Design and Search of OSDAs for STF and IFR", "source": PUB_DOI[4:], "locator": "section 4.3",
                              "values": {"designed": scr["deNovoDesignedForStf"], "nearPareto": scr["deNovoNearPareto"], "top3": 0}}]}
    apply_informativeness(f_denovo)

    def prediction_finding(code, rec, synth_finding):
        o = osdas[code]
        f = {"id": f"prediction-{code.lower()}",
             "question": f"Did the synthesis-energy prediction for {o['name']} ({code}), {' > '.join(o['prediction'])}, match the phase obtained?",
             "target": {"label": f"{o['name']} ({code})", "type": "compound", "identifier": OSDA_IDS[code]},
             "outcomeClass": "refuted", "informativeness": "not-applicable",
             "failureModes": ["model-did-not-generalize"],
             "effect": {"metric": "predicted phases obtained", "value": 0, "n": synth_finding["effect"]["n"], "direction": "none",
                        "comparedTo": f"prediction {', '.join(o['prediction'])}", "note": synth_finding["effect"]["note"]},
             "controls": dict(no_ctrl, positive={"kind": "none", "note": "judged on the refuting syntheses, which themselves lack a positive control; see provenanceNotes"}),
             "conditions": {"predictedPhases": o["prediction"], "observedPhases": synth_finding["conditions"]["phasesObserved"],
                            **({"mtwRankInPrediction": o["mtwRank"]} if code == "QG001780m2" else {})},
             "evidence": [{"label": "Table 2: OSDAs synthesized and results", "source": PUB_DOI[4:], "locator": "Table 2 (image in the XML, transcribed)",
                           "values": {"prediction": o["prediction"], "obtained": synth_finding["conditions"]["phasesObserved"]}},
                          {"label": "Conclusions", "source": PUB_DOI[4:], "locator": "Conclusions", "quote": res["verdict"]}],
             "relatedFindings": [f"{rec['slug']}#{synth_finding['id']}"],
             "note": "The refuting experiment is itself an uninformative negative for the synthesis target: the OSDA degraded, so what is refuted is the pipeline's prediction of the outcome, not the thermodynamic ranking as such."}
        apply_informativeness(f)
        return f

    f_p1 = prediction_finding("QHGWEBIGEQBZPY", rec_stf, f_stf)
    f_p2 = prediction_finding("QG001780m", rec_m, f_m)
    f_p3 = prediction_finding("QG001780m2", rec_m2, f_m2)

    screened = [{"label": f"{c['sda_name']} ({c['origin']})", "type": "compound", "decision": "included" if c["synthesized"] else "excluded",
                 "reason": "selected-for-testing" if c["synthesized"] else "not-selected-for-testing",
                 "score": {"method": f"rank of {c['target']} among competing phases by synthesis energy", "value": float(c["rank_of_target"]), "rank": c["rank_of_target"]},
                 "source": c["source"], "note": f"target {c['target']}; competing phases {c['competing_phase_1']}, {c['competing_phase_2']}; {c['activity_for_target']} for the target in pure-silica form"}
                for c in candidates]

    attempt("acs-zeolite-osda-screen",
            "Synthesis-energy, machine-learning and de novo screen of more than 10,000 OSDAs predicts CHA and AEI everywhere and shortlists three OSDAs whose predictions the syntheses refute",
            "Which OSDAs are predicted to crystallise aluminosilicate STF or IFR in hydroxide media, and did the predictions for the three synthesised OSDAs hold?",
            "An OSDA for which STF or IFR is among the most stable phases by synthesis energy, and a hydrothermal outcome matching the prediction.",
            "refuted", [f_land, f_stfc, f_ifrc, f_denovo, f_c1, f_c2, f_c3, f_p1, f_p2, f_p3],
            [stage_screen, stage_design, stage_ml, stage_rank], "computational",
            outcomeSummary="No OSDA makes STF or IFR the most stable aluminosilicate phase; 13 STF and 5 IFR candidates have the target in the top three. For the three synthesised, the predicted CHA, AEI, STF or IFR never formed, which the authors call a failure of the predictions.",
            confidence={"level": "medium", "basis": "the ranking is consistent across 1,190 database OSDAs and thousands of designed ones, but its experimental test was confounded by OSDA degradation"},
            screened=screened,
            screenedSummary={"osdbTotal": scr["osdbTotal"], "osdbInPapers": scr["osdbInPapers"], "osdbNotInPapers": scr["osdbNotInPapers"],
                             "activeForStf": scr["activeForStf"], "inactiveCloseToPareto": scr["inactiveCloseToPareto"],
                             "designedForStf": scr["deNovoDesignedForStf"], "generatedForIfr": scr["ifrGenerated"], "ifrPassedFilters": scr["ifrPassedFilters"],
                             "shortlisted": len(candidates), "synthesised": 3},
            cost={"note": "computational; no compute cost reported", "source": "Computational Methods"},
            relations=[{"type": "informs", "target": r["@id"]} for r in (rec_stf, rec_m, rec_m2)],
            provenanceNotes=[f"The authors' own total is '{scr['totalsStated']}'; screenedSummary carries the per-source counts the article states.",
                             "Predictions are recorded as refuted on the authors' own verdict in the Conclusions. The refuting syntheses are uninformative negatives for their targets (no positive control), and two of the three OSDAs degraded, so the refutation is of the pipeline's outcome prediction under the conditions actually run.",
                             "Table 2 is an image in the PMC XML; the predicted-phase order and outcomes were transcribed from the figure file cm5c01751_0007.jpg."])

    path["hasPart"] = [a["@id"] for a in attempts]
    check_valid(path)
    return [path] + attempts
