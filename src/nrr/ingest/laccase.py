"""Converter for Steffens, Antell, Cook, Rao, Britt, Sedlak and Alvarez-Cohen 2023, 'An Artifact of Perfluoroalkyl
Acid (PFAA) Removal Attributed to Sorption Processes in a Laccase Mediator System' (Environ. Sci. Technol. Lett. 10,
337-342, doi:10.1021/acs.estlett.3c00173, CC BY 4.0; full text from Europe PMC, PMC10100556).

A failure to replicate reported PFOA and PFOS degradation by a laccase mediator system, with the apparent loss traced to
sorption on the enzyme by mass balance. The positive control is a different substrate (carbamazepine) rather than a
different reagent, which is the case the research note wanted the rule to see.
"""
from __future__ import annotations

from pathlib import Path

from nrr.ingest.common import (
    check_valid, data_pointer, entity, finalize, new_record, performer, read_csv, read_json, read_yaml, source,
)
from nrr.rules import apply_informativeness

STUDY = "acs-laccase"
PUB_DOI = "doi:10.1021/acs.estlett.3c00173"
PMCID = "PMC10100556"
SI_FILE = "ez3c00173_si_001.pdf"
TAXA = {"Trametes versicolor": "white-rot fungus; source of TvL, the laccase used in every TvL experiment",
        "Agaricus bisporus": "source of the second commercial laccase in the mediator screen",
        "Pleurotus ostreatus": "source of the laccase in the prior reports; no longer commercially available"}
MEDIATORS = [("1-hydroxybenzotriazole", "1-hydroxybenzotriazole (HBT)"), ("N-hydroxyphthalimide", "N-hydroxyphthalimide (HPI)"),
             ("violuric acid", "violuric acid"), ("TEMPO", "TEMPO"), ("2-azaadamantane N-oxyl", "AZADO (2-azaadamantane N-oxyl)")]


def parse_mass_balance(path: Path) -> dict[tuple[str, str, str], tuple[float, float]]:
    out = {}
    for r in read_csv(path):
        out[(r["analyte"], r["treatment"], r["measure"])] = (int(r["mass_recovered_pct"]), float(r["error_pct"]))
    return out


def parse_experiments(path: Path) -> dict[str, dict]:
    out = {}
    for r in read_csv(path):
        r["replicates"] = int(r["replicates"]) if r["replicates"] else None
        out[r["experiment"]] = r
    return out


def _compound(resolver, name, label=None, role=None, **extra):
    hit = resolver.compound(name) or {}
    ident = hit.get("identifier") or f"compound:{name.lower().replace(' ', '-')}"
    return entity(ident, "compound", label or name, scheme="PubChem" if hit.get("identifier") else None, role=role,
                  note=None if hit.get("identifier") else "identifier not resolved", **extra)


def build_laccase_records(root: Path, resolver) -> list[dict]:
    cur, raw = root / "curated" / "laccase", root / "raw" / "laccase"
    facts = read_yaml(cur / "pub_facts.yaml")
    mb = parse_mass_balance(cur / "mass_balance.csv")
    ex = parse_experiments(cur / "experiments.csv")
    mb_rows = read_csv(cur / "mass_balance.csv")
    fetched = read_json(raw / "europepmc" / "record.json")["fetched"]
    pub, prior_r, meth, res, sens = facts["publication"], facts["priorReports"], facts["method"], facts["results"], facts["sensitivity"]

    org_hit = resolver.organization(facts["operator"]["name"]) or {}
    operator = {"name": facts["operator"]["name"], "type": "Organization"}
    if org_hit.get("identifier"):
        operator["identifier"] = org_hit["identifier"]

    si_meta = fetched["files"][f"si/{SI_FILE}"]
    si_pointer = data_pointer(SI_FILE, repository="Europe PMC", accession=PMCID, url=fetched["supplementaryFiles"],
                              checksum="sha256:" + si_meta["sha256"], size=si_meta["size"], format="application/pdf",
                              role="Supporting Information: protocols (Text S1 to S5), Tables S1 to S3, Figures S1 to S8")
    sources_common = [
        source("source-publication", PUB_DOI, resolver, label=pub["title"], url=pub["url"], license=pub["license"], note=pub["licenseStatement"]),
        source("supplementary", f"pmc:{PMCID}/{SI_FILE}", resolver, label="Supporting Information (PDF)", url=fetched["supplementaryFiles"],
               license=pub["license"], data=[si_pointer], note=pub["dataAvailability"]),
    ]
    prior = [
        source("prior-art", f"doi:{prior_r['pfoa']['doi']}", resolver, label=prior_r["pfoa"]["label"], note=prior_r["pfoa"]["claim"]),
        source("prior-art", f"doi:{prior_r['pfos']['doi']}", resolver, label=prior_r["pfos"]["label"], note=prior_r["pfos"]["claim"]),
        source("comparator", f"doi:{prior_r['cbz']['doi']}", resolver, label=prior_r["cbz"]["label"], note=prior_r["cbz"]["claim"]),
        source("reference", f"doi:{prior_r['btnoEpr']['doi']}", resolver, label=prior_r["btnoEpr"]["label"]),
        source("reference", f"doi:{prior_r['proteinsAsSorbents']['doi']}", resolver, label=prior_r["proteinsAsSorbents"]["label"]),
        source("reference", f"doi:{prior_r['pfaaAlbumin']['doi']}", resolver, label=prior_r["pfaaAlbumin"]["label"]),
    ]

    # --- entities -------------------------------------------------------------------------------
    pfoa = _compound(resolver, "perfluorooctanoic acid", "perfluorooctanoic acid (PFOA)", role="target substrate")
    pfos = _compound(resolver, "perfluorooctanesulfonic acid", "perfluorooctanesulfonic acid (PFOS)", role="target substrate")
    cbz = _compound(resolver, "carbamazepine", "carbamazepine (CBZ)", role="positive-control substrate")
    ents = [pfoa, pfos, cbz] + [_compound(resolver, n, lab, role="nitroxyl mediator") for n, lab in MEDIATORS] + [
        entity("protein:trametes-versicolor-laccase", "protein", "Trametes versicolor laccase (TvL), MilliporeSigma", role="enzyme under test",
               note="commercial preparation; no UniProt accession is given in the article"),
        entity("protein:agaricus-bisporus-laccase", "protein", "Agaricus bisporus laccase, MilliporeSigma", role="enzyme in the mediator screen"),
        entity("protein:native-white-rot-laccase", "protein", "native white rot fungal laccase, Creative Enzymes", role="enzyme in the mediator screen", note="species not stated"),
        _compound(resolver, "copper(II) sulfate", "copper(II) sulfate, 10 mM, pH 5", role="reaction matrix"),
        _compound(resolver, "sodium malonate", "sodium malonate buffer, 50 mM, pH 4.5", role="reaction matrix"),
        _compound(resolver, "2,6-dimethoxyphenol", "2,6-dimethoxyphenol (DMP)", role="laccase activity assay substrate"),
        _compound(resolver, "methanol", "basic methanol (0.5 % NH4OH)", role="quench and extraction solvent"),
        entity("assay:lc-msms-pfas", "assay", "LC-MS/MS isotope-dilution quantification of PFAS", role="analytical method", note=meth["analysis"]),
        entity("assay:epr-btno", "assay", "X-band CW EPR of the benzotriazole-N-oxyl (BTNO) radical", role="mediator radical check", note=meth["epr"]),
        entity("assay:dmp-activity", "assay", "DMP laccase activity assay", role="enzyme activity check", note=meth["activityAssay"]),
        entity(org_hit.get("identifier", "org:uc-berkeley"), "organization", facts["operator"]["name"], note=facts["operator"]["note"]),
    ]
    for name, role in TAXA.items():
        hit = resolver.taxon(name) or {}
        ents.append(entity(hit.get("identifier", f"taxon:{name.lower().replace(' ', '-')}"), "organism", name, scheme="NCBI Taxonomy" if hit.get("identifier") else None,
                           role=role, note=None if hit.get("identifier") else "taxon not resolved"))
    people = [performer(c["name"], "person", "writing", affiliation=c["affiliation"], identifier=f"https://orcid.org/{c['orcid']}" if c.get("orcid") else None,
                        note="listed author; the article carries no author-contribution statement") for c in facts["contributors"]]

    applicability = {
        "system": "laccase mediator systems with nitroxyl (N-OH or N-oxyl) mediators in aerated batch reactors at 30 °C",
        "enzymes": "Trametes versicolor laccase (MilliporeSigma) for the TvL experiments; Agaricus bisporus and a native white-rot laccase in the screen; the Pleurotus ostreatus laccase of the prior reports was not available",
        "substrateConcentrations": "1 uM (screen and two-week experiment) and 0.1 uM (96 h and 24 h experiments)",
        "matrices": "10 mM CuSO4 pH 5 or 50 mM sodium malonate pH 4.5",
        "duration": "24 h to 28 days with repeated enzyme and mediator dosing",
        "analysis": meth["analysis"],
        "note": "the negative is about detectable degradation under these conditions; sorption to the enzyme is shown to mimic up to about 60 % apparent removal when only the aqueous phase is sampled",
    }
    common = dict(operator=operator, sourceLicense="CC BY 4.0", domainTags=["chemistry"],
                  aiUseDeclaration={"statement": facts["aiUse"]["statement"]})
    cost = {"wetLabDays": 28, "note": "batch reactors in triplicate; the longest experiment 28 days; no monetary cost reported", "source": "Materials and Methods; SI"}
    no_ctrl = {"positive": {"kind": "none"}, "negative": {"kind": "none"}}
    SENS = f"{sens['statement']}. {sens['ingestReading']}"

    pos_cbz = {"kind": "designated", "label": "carbamazepine (CBZ) as surrogate substrate with TvL and HBT",
               "expected": "transformation", "observed": "about 35 % removal in 120 h, p < 0.001", "passed": True,
               "note": "a different substrate run in a separate reactor set with the same enzyme, mediator and buffer, not an arm of the same experiment; it shows the enzyme-mediator system was oxidatively active",
               "source": "Results paragraph 2; SI Figure S3"}

    def stage(label, exp_id, extra=None):
        e = ex[exp_id]
        st = {"stage": "experiment", "label": label, "performedBy": people,
              "method": f"{meth['reactors']}; {meth['quench']}; {meth['analysis']}",
              "conditions": {"substrate": e["substrate"], "substrateConcentrationUm": e["substrate_conc_um"], "enzyme": e["enzyme"], "enzymeUnitsPerMl": e["enzyme_units_per_ml"],
                             "mediator": e["mediator"], "mediatorConcentration": e["mediator_conc"], "matrix": e["matrix"], "dosing": e["dosing"], "duration": e["duration"]},
              "replicates": {"reactors": e["replicates"]} if e["replicates"] else {},
              "instrument": ["New Brunswick Excella E25 shaker incubator", "Agilent Triple Quad 6460A LC-MS/MS"]}
        if extra:
            st.update(extra)
        return st

    # --- path -------------------------------------------------------------------------------------
    path = new_record(
        "path", STUDY, "acs-laccase-path",
        "Laccase mediator systems do not detectably degrade PFOA or PFOS; the reported loss is sorption to the enzyme",
        question="Can a laccase mediator system be optimised to degrade perfluorooctanoic acid (PFOA) and perfluorooctanesulfonic acid (PFOS), as two earlier reports of modest losses suggested?",
        hypothesis=facts["purpose"],
        successCriteria="A statistically significant decrease in PFOA or PFOS mass, not only aqueous concentration, relative to untreated and enzyme-only controls, under conditions where the same enzyme and mediator transform a surrogate substrate.",
        pathType="experiment", outcomeClass="negative-not-replicated",
        outcomeSummary=f"{res['headline']} {res['conclusion']}",
        confidence={"level": "high", "basis": "surrogate-substrate positive control passed, radical formation confirmed by EPR, enzyme activity confirmed, triplicate reactors, and a full mass balance including vessel and protein extraction that accounts for the apparent loss"},
        nextSteps=facts["nextSteps"], openQuestions=facts["openQuestions"],
        untriedBranches=[{"description": s, "status": "proposed-by-authors", "source": "Environmental Implications"} for s in facts["nextSteps"]]
                       + [{"description": "Repeat the prior reports' conditions with a Pleurotus ostreatus laccase, with full mass balance, if a source of that enzyme can be found.", "status": "inferred-by-ingest", "source": "Results paragraph 1"}],
        invalidators=["a mass-balanced demonstration of PFOA or PFOS transformation products by any laccase mediator system",
                      "a Pleurotus ostreatus laccase preparation shown to degrade PFAAs with vessel and protein extraction accounted for"],
        applicabilityConditions=applicability, cost=cost,
        sources=sources_common + prior, performers=people, entities=ents,
        relations=[{"type": "contradicts", "target": f"doi:{prior_r['pfoa']['doi']}", "note": "PFOA removal >20 % at 10 days not replicated with TvL/HBT"},
                   {"type": "contradicts", "target": f"doi:{prior_r['pfos']['doi']}", "note": "PFOS removal not replicated with two commercial laccases and five mediators over 28 days"}],
        governance={"humanSubjectData": "none", "biosecurityTier": "none"},
        provenanceNotes=[
            "The positive control is a surrogate substrate (carbamazepine) run in a separate reactor set with the same enzyme, mediator and buffer, not an arm of the PFAA experiments. The ingest counts it as a designated positive control for the TvL/HBT findings and says so in each control's note; it does not count for the mediator screen, which used two other laccases.",
            sens["ingestReading"],
            "SI Tables S2 and S3 are images in the PDF; every cell was transcribed into curated/laccase/mass_balance.csv with the row and column as locator. The main text rounds them (82 % recovered becomes '18 +/- 2 % apparent loss').",
            "The article has no author-contribution statement; every author is recorded with the role 'writing' only.",
            "TvL/HBT against PFOS was tested only in the 0.1 uM 96 h and 24 h experiments; the two-week dosing experiment was PFOA only.",
        ],
        hasPart=[], **common)
    finalize(path, check=False)
    pid = path["@id"]
    attempts: list[dict] = []

    def attempt(slug, title, question, success, outcome, findings, stages, **kw):
        rec = new_record("attempt", STUDY, slug, title, attemptType="wet-lab", pathType="experiment",
                         question=question, successCriteria=success, outcomeClass=outcome, findings=findings, stages=stages,
                         applicabilityConditions=applicability, cost=kw.pop("cost", cost), sources=sources_common + kw.pop("sources", []),
                         isPartOf=pid, entities=ents, performers=people,
                         relations=[{"type": "isPartOf", "target": pid}] + kw.pop("relations", []), **common, **kw)
        attempts.append(finalize(rec))
        return rec

    # --- attempt 1: mediator screen ----------------------------------------------------------------------
    def screen_finding(exp_id, enzyme_label, p):
        e = ex[exp_id]
        f = {"id": exp_id,
             "question": f"Does {enzyme_label} with any of five nitroxyl mediators remove PFOS over 28 days?",
             "target": {"label": "PFOS", "type": "compound", "identifier": pfos["id"]},
             "outcomeClass": "negative-no-effect", "informativeness": "uninformative",
             "effect": {"metric": "PFOS concentration relative to the no-mediator control after evaporation correction", "value": "no significant difference", "n": 3,
                        "direction": "none", "test": "two-tailed t test", "pValue": p, "significant": False,
                        "comparedTo": "enzyme-only (no-mediator) reactors; the prior report expected >20 % removal at 20 days and >30 % at 30 days"},
             "controls": {"positive": {"kind": "none", "note": "no surrogate substrate was run with these two laccases; the carbamazepine control used Trametes versicolor laccase in a separate experiment"},
                          "negative": {"kind": "no-treatment", "label": "untreated reactor (no enzyme, no mediator) and enzyme-only reactors", "expected": "no loss",
                                       "observed": "concentrations rose through evaporation from filter caps and were used to correct all treatments (Text S4)", "passed": True,
                                       "note": "clean in the sense of no unexplained loss; the evaporation correction is derived from this control"}},
             "sensitivity": SENS,
             "replicates": {"biological": 3, "note": "triplicate reactors; 10 mL in 30 mL polypropylene flasks"},
             "conditions": {"enzyme": e["enzyme"], "enzymeUnitsPerMl": 1, "mediators": [lab for _, lab in MEDIATORS], "mediatorConcentration": "20 uM", "substrateConcentrationUm": 1,
                            "matrix": e["matrix"], "dosing": e["dosing"], "duration": e["duration"]},
             "evidence": [{"label": e["source"], "source": PUB_DOI[4:], "locator": e["source"], "values": {"pValue": p, "replicates": 3}, "quote": res["screen"]}],
             "nearestPriorResult": f"{prior_r['pfos']['label']}: {prior_r['pfos']['claim']}"}
        apply_informativeness(f)
        return f
    f_wr = screen_finding("screen-white-rot", "a native white-rot laccase (Creative Enzymes)", 0.58)
    f_ab = screen_finding("screen-agaricus", "Agaricus bisporus laccase (Sigma)", 0.24)
    screened = [{"label": lab, "type": "compound", "identifier": next(e["id"] for e in ents if e["label"] == lab), "decision": "included", "reason": "selected-for-testing",
                 "note": "nitroxyl mediator screened with both laccases against 1 uM PFOS (SI Figure S1)"} for _, lab in MEDIATORS]
    attempt("acs-laccase-mediator-screen",
            "Two commercial laccases with five nitroxyl mediators do not remove PFOS over 28 days",
            "Does any of five nitroxyl mediators with a high-redox commercial laccase remove PFOS within the 20 to 30 days the prior report needed?",
            "A significant decrease in PFOS concentration relative to the enzyme-only control by day 28.",
            f_wr["outcomeClass"], [f_wr, f_ab], [stage("28-day PFOS screen, two laccases by five mediators, weekly dosing", "screen-white-rot")],
            outcomeSummary=f"{res['screen']} p = 0.58 (white rot) and 0.24 (Agaricus bisporus).",
            confidence={"level": "medium", "basis": "no positive control with these enzymes; evaporation correction needed"},
            screened=screened, screenedSummary={"laccases": 2, "mediators": 5, "days": 28},
            provenanceNotes=["The rule remaps this to inconclusive-no-positive-control: the surrogate-substrate control was run with a different enzyme. The authors moved to TvL after this screen because the P. ostreatus laccase of the prior reports was unavailable."])

    # --- attempt 2: system checks -------------------------------------------------------------------------
    f_cbz = {"id": "cbz-transformed",
             "question": "Does the TvL/HBT system transform the surrogate substrate carbamazepine under literature conditions?",
             "target": {"label": "carbamazepine (CBZ)", "type": "compound", "identifier": cbz["id"]},
             "outcomeClass": "positive", "informativeness": "not-applicable",
             "effect": {"metric": "CBZ removal after three doses over 120 h", "value": 35, "unit": "%", "n": 3, "direction": "decrease", "test": "two-tailed t test", "pValue": "< 0.001", "significant": True,
                        "comparedTo": "untreated, TvL-only and HBT-only reactors"},
             "controls": dict(no_ctrl, negative={"kind": "no-treatment", "label": "untreated, TvL only, HBT only", "expected": "no removal", "observed": "no comparable removal", "passed": True}),
             "conditions": {"enzymeUnitsPerMl": 2, "mediatorConcentration": "1 mM", "matrix": "50 mM sodium malonate pH 4.5", "doses": 3, "duration": "120 h"},
             "evidence": [{"label": "Results paragraph 2; SI Figure S3", "source": PUB_DOI[4:], "locator": "Results paragraph 2; SI Figure S3", "quote": res["cbz"]}],
             "note": "This is the positive control for the TvL/HBT PFAA findings: the same enzyme and mediator in the same buffer are oxidatively active on a persistent, hydrophobic contaminant."}
    f_act = {"id": "activity-retained",
             "question": "Does TvL retain activity in the CuSO4 solution used for PFAA reactors, compared with acetate buffer?",
             "target": {"label": "Trametes versicolor laccase (TvL)", "type": "protein", "identifier": "protein:trametes-versicolor-laccase"},
             "outcomeClass": "positive", "informativeness": "not-applicable",
             "effect": {"metric": "laccase activity profile by DMP assay", "value": "similar in 5 mM CuSO4 and 0.1 M sodium acetate; none in 5 mM FeSO4", "direction": "not-applicable"},
             "controls": no_ctrl,
             "conditions": {"assay": "DMP oxidation at 468 nm, triplicate", "matrices": ["5 mM CuSO4", "0.1 M sodium acetate", "5 mM FeSO4"]},
             "evidence": [{"label": "SI Text S5, Figure S5", "source": PUB_DOI[4:], "locator": "Results paragraph 3; SI Text S5, Figure S5"}],
             "note": "Activity declined over 6 to 8 h in the presence of HBT (SI Figure S8), which is why the 96 h experiment was dosed twice daily."}
    f_epr = {"id": "btno-radical",
             "question": "Does the TvL/HBT/CuSO4 system generate the benzotriazole-N-oxyl (BTNO) radical proposed to oxidise contaminants?",
             "target": {"label": "benzotriazole-N-oxyl radical from HBT", "type": "compound"},
             "outcomeClass": "positive", "informativeness": "not-applicable",
             "effect": {"metric": "EPR detection of BTNO", "value": "detected in both routes", "direction": "not-applicable",
                        "note": "hyperfine structure resolved at room temperature in CH3CN (Ce(IV) oxidation) and not resolved in the frozen aqueous laccase sample at 50 K, attributed to anisotropic line broadening"},
             "controls": dict(no_ctrl, positive={"kind": "designated", "label": "BTNO generated chemically by Ce(IV) ammonium nitrate in CH3CN", "expected": "literature hyperfine pattern", "observed": "g = 2.0069, three 1H and three 14N couplings matching Galli et al. 2004", "passed": True}),
             "conditions": {"g": 2.0069, "frequencyGHz": 9.4, "aqueousSample": "1 mM HBT, 12 mg/mL TvL, 10 uM CuSO4 at 50 K", "chemicalSample": "20 mM Ce(IV) and 20 mM HBT in CH3CN, room temperature"},
             "evidence": [{"label": "SI Text S3, Figures S6 and S7", "source": PUB_DOI[4:], "locator": "Results paragraph 3; SI Text S3, Figures S6 and S7"}]}
    for f in (f_cbz, f_act, f_epr):
        apply_informativeness(f)
    attempt("acs-laccase-system-checks",
            "The TvL/HBT system is active: carbamazepine is transformed, the BTNO radical forms, and enzyme activity is retained in the PFAA matrix",
            "Are the enzyme, the mediator radical and the reaction matrix each functioning, so that a PFAA negative would be a property of the chemistry rather than of a dead system?",
            "Significant CBZ removal, EPR detection of BTNO, and retained laccase activity in CuSO4.",
            "positive", [f_cbz, f_act, f_epr],
            [stage("carbamazepine transformation with TvL and HBT", "cbz-positive-control"),
             {"stage": "experiment", "label": "EPR and activity checks", "performedBy": people, "method": f"{meth['epr']}; {meth['activityAssay']}",
              "instrument": ["Bruker Biospin EleXsys E500 X-band EPR spectrometer (CalEPR Center, UC Davis)", "Shimadzu UV-vis plate reader"]}],
            outcomeSummary="About 35 % CBZ removal (p < 0.001); BTNO radical detected by EPR in the laccase system; TvL activity retained in CuSO4 and acetate.",
            confidence={"level": "high", "basis": "each check has its own comparator or chemical standard"})

    # --- attempt 3: PFAA degradation attempts ------------------------------------------------------------------
    e2 = ex["pfoa-two-weeks"]
    f_pfoa2w = {"id": "pfoa-two-weeks",
                "question": "Does TvL with HBT, dosed six times over two weeks, remove 1 uM PFOA?",
                "target": {"label": "PFOA", "type": "compound", "identifier": pfoa["id"]},
                "outcomeClass": "negative-not-replicated", "informativeness": "informative",
                "effect": {"metric": "PFOA concentration relative to untreated control after two weeks", "value": "no significant removal", "n": 3, "direction": "none",
                           "test": "two-tailed t test", "pValue": 0.29, "significant": False, "comparedTo": "untreated control; the prior report claimed >20 % removal after 10 days"},
                "controls": {"positive": pos_cbz,
                             "negative": {"kind": "no-treatment", "label": "untreated control reactors", "expected": "no loss", "observed": "no loss beyond error", "passed": True, "source": "SI Figure S4"}},
                "sensitivity": SENS,
                "replicates": {"biological": 3, "note": "triplicate reactors"},
                "conditions": {"enzymeUnitsPerMl": 1, "mediatorConcentration": "1 mM", "doses": 6, "dosingInterval": "every 2 to 3 days", "duration": "2 weeks", "matrix": e2["matrix"], "substrateConcentrationUm": 1},
                "evidence": [{"label": e2["source"], "source": PUB_DOI[4:], "locator": e2["source"], "values": {"pValue": 0.29, "doses": 6}, "quote": res["pfoaTwoWeeks"]}],
                "nearestPriorResult": f"{prior_r['pfoa']['label']}: {prior_r['pfoa']['claim']}"}
    apply_informativeness(f_pfoa2w)

    def apparent_loss(analyte_ent, code, drop, recovered, err, partner):
        f = {"id": f"{code}-96h-apparent-loss",
             "question": f"Is the fall in measured {analyte_ent['label'].split(' (')[-1].rstrip(')')} concentration after 24 h of TvL/HBT dosing a transformation?",
             "target": {"label": analyte_ent["label"], "type": "compound", "identifier": analyte_ent["id"]},
             "outcomeClass": "refuted", "informativeness": "not-applicable",
             "failureModes": ["measurement-artifact"],
             "effect": {"metric": "decrease in aqueous concentration at 24 h", "value": drop, "unit": "%", "n": 3, "direction": "decrease",
                        "comparedTo": f"{recovered} +/- {err} % of the mass recovered when the reactor was extracted with basic methanol at 96 h",
                        "note": "the concentration fall is real; its reading as degradation is what is refuted"},
             "controls": {"positive": pos_cbz, "negative": {"kind": "no-treatment", "label": "untreated and enzyme-only reactors", "expected": "no loss", "observed": "over-recovery on extraction, attributed to fast sorption to the vessel before the first aliquot", "passed": True}},
             "sensitivity": SENS,
             "replicates": {"biological": 3},
             "conditions": {"substrateConcentrationUm": 0.1, "enzymeUnitsPerMl": 1, "mediatorConcentration": "1 mM", "dosing": "twice daily", "duration": "96 h", "matrix": "10 mM CuSO4"},
             "evidence": [{"label": "Figure 1", "source": PUB_DOI[4:], "locator": "Results paragraphs 4 and 5; Figure 1", "values": {"decreaseAt24hPct": drop, "massRecoveredPct": recovered, "sd": err},
                           "quote": res["massBalance96h"]}],
             "relatedFindings": [f"acs-laccase-sorption#{partner}"],
             "note": "Judged on the refuting analysis: the mass balance. Sampling only the aqueous phase would have reported this as up to about 60 % removal."}
        apply_informativeness(f)
        return f
    f_pfoa_art = apparent_loss(pfoa, "pfoa", 64, 99, 14, "pfoa-partition")
    f_pfos_art = apparent_loss(pfos, "pfos", 67, 111, 11, "pfos-partition")
    attempt("acs-laccase-pfaa-degradation",
            "TvL with HBT does not remove PFOA over two weeks; the 64 to 67 % concentration fall at 0.1 uM is recovered in full on extraction",
            "Does Trametes versicolor laccase with HBT degrade PFOA or PFOS under conditions where it transforms carbamazepine?",
            "A significant loss of PFAA mass relative to untreated control, confirmed by extraction of the whole reactor.",
            "negative-not-replicated", [f_pfoa2w, f_pfoa_art, f_pfos_art],
            [stage("two-week PFOA dosing with TvL and HBT", "pfoa-two-weeks"), stage("0.1 uM PFOA and PFOS, twice-daily dosing, 96 h, whole-reactor extraction", "pfaa-96h")],
            outcomeSummary=f"{res['pfoaTwoWeeks']} At 0.1 uM, {res['apparentLoss24h']}, but {res['massBalance96h']}",
            confidence={"level": "high", "basis": "surrogate positive control passed; untreated controls; triplicates; full mass recovery"},
            provenanceNotes=["The two refuted findings and the informative negative sit in one attempt because they are the same question asked at two concentrations; the apparent loss at 0.1 uM is what a less careful study would have published."])

    # --- attempt 4: sorption partition -------------------------------------------------------------------------
    def partition(analyte_ent, code, label):
        sub, sub_e = mb[(code, "TvL + HBT", "subsample (24 hours)")]
        tvl_sub, tvl_e = mb[(code, "TvL", "subsample (24 hours)")]
        dsol, dsol_e = mb[(code, "TvL + HBT", "delta solution")]
        dsol_t, dsol_te = mb[(code, "TvL", "delta solution")]
        rows = [r for r in mb_rows if r["analyte"] == code]
        f = {"id": f"{code.lower()}-partition",
             "question": f"Where does the {label} mass that disappears from solution in TvL/HBT reactors go: protein, vessel or transformation?",
             "target": {"label": analyte_ent["label"], "type": "compound", "identifier": analyte_ent["id"]},
             "outcomeClass": "positive", "informativeness": "not-applicable",
             "effect": {"metric": "apparent loss from the 24 h subsample relative to total extracted mass, TvL + HBT", "value": 100 - sub, "unit": "%", "sd": sub_e, "n": 3, "direction": "not-applicable",
                        "comparedTo": f"{100 - tvl_sub} +/- {tvl_e} % with TvL only; delta solution (mass lost from solution between 0 and 24 h, attributed to protein sorption) {dsol} +/- {dsol_e} % with TvL + HBT and {dsol_t} +/- {dsol_te} % with TvL only",
                        "note": "delta solution gives a complete mass balance within error against the solution extract (Figure 2)"},
             "controls": dict(no_ctrl, negative={"kind": "no-treatment", "label": "enzyme-free control reactors", "expected": "no loss to protein", "observed": f"delta solution {mb[(code, 'control', 'delta solution')][0]} +/- {mb[(code, 'control', 'delta solution')][1]} %", "passed": True}),
             "replicates": {"biological": 3},
             "conditions": {"substrateConcentrationUm": 0.1, "enzymeMg": 60, "enzymeUnitsPerMl": 2, "mediatorConcentration": "2 mM", "duration": "24 h", "matrix": "10 mM CuSO4",
                            "tvlOnlyLossPct": 100 - tvl_sub, "extraction": meth["extraction"]},
             "evidence": [{"label": f"{r['treatment']} / {r['measure']}", "source": PUB_DOI[4:], "locator": r["source"],
                           "values": {"massRecoveredPct": int(r["mass_recovered_pct"]), "errorPct": float(r["error_pct"])}} for r in rows],
             "note": res["mechanism"] if code == "PFOA" else res["partition"]}
        apply_informativeness(f)
        return f
    f_pp = partition(pfoa, "PFOA", "PFOA")
    f_sp = partition(pfos, "PFOS", "PFOS")
    ctrl_r, ctrl_e = mb[("PFOS", "control", "reactor extract")]
    f_reactor = {"id": "pfos-reactor-sorption",
                 "question": "Does PFOS sorb to the glass reactor, and does the presence of enzyme change how much?",
                 "target": {"label": pfos["label"], "type": "compound", "identifier": pfos["id"]},
                 "outcomeClass": "positive", "informativeness": "not-applicable",
                 "effect": {"metric": "PFOS mass recovered from the emptied reactor, enzyme-free control", "value": ctrl_r, "unit": "%", "sd": ctrl_e, "n": 3, "direction": "not-applicable",
                            "comparedTo": f"{mb[('PFOS', 'TvL + HBT', 'reactor extract')][0]} +/- {mb[('PFOS', 'TvL + HBT', 'reactor extract')][1]} % with TvL + HBT and {mb[('PFOS', 'TvL', 'reactor extract')][0]} +/- {mb[('PFOS', 'TvL', 'reactor extract')][1]} % with TvL only",
                            "note": "sorption to the protein is more favourable than to the glass"},
                 "controls": no_ctrl,
                 "evidence": [{"label": "SI Table S3 reactor extract rows", "source": PUB_DOI[4:], "locator": "SI Table S3 (image on page S8), Reactor extract rows; Figure 2b", "quote": res["reactorSorption"]}]}
    apply_informativeness(f_reactor)
    attempt("acs-laccase-sorption",
            "The apparent PFOA and PFOS loss is sorption to the laccase, 18 +/- 2 % and 34 +/- 4 %, with a complete mass balance",
            "How much PFOA and PFOS sorbs to the enzyme and to the reactor in 24 h, and does the mediator change it?",
            "Separate extraction of the enzyme solution and the emptied vessel accounting for the total mass within error.",
            "positive", [f_pp, f_sp, f_reactor], [stage("24 h partition experiment with separate extraction of enzyme solution and reactor", "sorption-24h", {"protocol": meth["extraction"]})],
            outcomeSummary=f"{res['partition']} {res['reactorSorption']} {res['mechanism']}",
            confidence={"level": "high", "basis": "triplicates, both phases extracted, mass balance closes within error"},
            relations=[{"type": "informs", "target": attempts[-1]["@id"], "note": "explains the apparent loss recorded as refuted in the degradation attempt"}],
            provenanceNotes=["All 24 cells of SI Tables S2 and S3 were transcribed from the images; the main text's '18 +/- 2 %' is 100 minus the 82 % subsample recovery with its 1.7 % error rounded."])

    path["hasPart"] = [a["@id"] for a in attempts]
    check_valid(path)
    return [path] + attempts
