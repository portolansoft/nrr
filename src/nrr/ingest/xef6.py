"""Converter for Koch, Hoß, Schnakenburg, Karttunen and Kraus 2026, 'Failed Attempts at Oxidation of XeF6: Synthesis
and Characterization of [Xe2F11][RuF6]' (Inorg. Chem. 65, 15126-15135, doi:10.1021/acs.inorgchem.6c02072, CC BY 4.0;
full text from Europe PMC, PMC13343514).

A classic synthetic dead end: RuF6 and XeF6 at every ratio and temperature tried evolve F2 and give only xenon(VI)
salts. The by-product [Xe2F11][RuF6] is new and fully characterised (CCDC 2477117), and the explanation offered is
thermodynamic reasoning rather than a control experiment. Conditions are given in prose, not a table, so each is a
finding with its paragraph as locator, and no run count is reported anywhere.
"""
from __future__ import annotations

from pathlib import Path

from nrr.ingest.common import (
    check_valid, data_pointer, entity, finalize, new_record, performer, read_csv, read_json, read_yaml, source,
)
from nrr.rules import apply_informativeness

STUDY = "acs-xef6"
PUB_DOI = "doi:10.1021/acs.inorgchem.6c02072"
PMCID = "PMC13343514"
SI_FILE = "ic6c02072_si_001.pdf"
CCDC = "2477117"
TARGET = {"label": "xenon(VIII) fluoride species: [XeF7]+ salt or XeF8", "type": "compound", "identifier": "compound:xef7-cation-or-xef8"}


def _float(v):
    return float(v) if v not in (None, "") else None


def parse_conditions(path: Path) -> list[dict]:
    rows = read_csv(path)
    for r in rows:
        for k in ("ruf6_mg", "ruf6_mmol", "xef6_mg", "xef6_mmol", "ahf_ml"):
            r[k] = _float(r[k])
    return rows


def _compound(resolver, name, label=None, role=None, **extra):
    hit = resolver.compound(name) or {}
    ident = hit.get("identifier") or f"compound:{name.lower().replace(' ', '-')}"
    return entity(ident, "compound", label or name, scheme="PubChem" if hit.get("identifier") else None, role=role,
                  note=None if hit.get("identifier") else "identifier not resolved", **extra)


def build_xef6_records(root: Path, resolver) -> list[dict]:
    cur, raw = root / "curated" / "xef6", root / "raw" / "xef6"
    facts = read_yaml(cur / "pub_facts.yaml")
    conds = parse_conditions(cur / "conditions.csv")
    fetched = read_json(raw / "europepmc" / "record.json")["fetched"]
    pub, tgt, obs, nc, th = facts["publication"], facts["target"], facts["observations"], facts["newCompound"], facts["thermodynamics"]

    org_hit = resolver.organization(facts["operator"]["name"]) or {}
    operator = {"name": facts["operator"]["name"], "type": "Organization"}
    if org_hit.get("identifier"):
        operator["identifier"] = org_hit["identifier"]
    aalto = resolver.organization("Aalto University") or {}

    si_meta = fetched["files"][f"si/{SI_FILE}"]
    si_pointer = data_pointer(SI_FILE, repository="Europe PMC", accession=PMCID, url=fetched["supplementaryFiles"],
                              checksum="sha256:" + si_meta["sha256"], size=si_meta["size"], format="application/pdf",
                              role="Supporting Information: crystallographic details, powder patterns and vibrational spectra of both salts, computational details, FIA coordinates")
    ccdc_src = source("data-deposit", f"ccdc:{CCDC}", label=f"CCDC {CCDC}: crystal structure of [Xe2F11][RuF6]", url=nc["ccdcUrl"],
                      note="joint Cambridge Crystallographic Data Centre and FIZ Karlsruhe Access Structures service; the only machine-readable deposit of the four ACS studies",
                      data=[data_pointer(f"CCDC {CCDC}", repository="CCDC Access Structures", accession=CCDC, url=nc["ccdcUrl"], format="CIF", role="single-crystal structure at 100 K")])
    sources_common = [
        source("source-publication", PUB_DOI, resolver, label=pub["title"], url=pub["url"], license=pub["license"], note=pub["licenseStatement"]),
        source("supplementary", f"pmc:{PMCID}/{SI_FILE}", resolver, label="Supporting Information (PDF)", url=fetched["supplementaryFiles"],
               license=pub["license"], data=[si_pointer], note=pub["dataAvailability"]),
        ccdc_src,
    ]
    dead_end_sources = [source("prior-art", f"doi:{d}", resolver, label=f"earlier Xe(VIII) attempt with {de['oxidant']}", note=de["outcome"])
                        for de in facts["priorDeadEnds"] for d in de["dois"]]
    pa = facts["priorArt"]
    prior = [
        source("prior-art", f"doi:{pa['xef5ruf6Structure']}", resolver, label="Bartlett et al. 1973: crystal structures of [XeF][RuF6] and [XeF5][RuF6]"),
        source("prior-art", f"doi:{pa['ruf6Redox']}", resolver, label="Burns and O'Donnell 1980: oxidation-reduction reactions of RuF6"),
        source("comparator", f"doi:{pa['xe2f11Au'][0]}", resolver, label="Leary, Zalkin, Bartlett 1973: [Xe2F11][AuF6] structure"),
        source("comparator", f"doi:{pa['xe2f11Au'][1]}", resolver, label="Leary, Zalkin, Bartlett 1974: [Xe2F11][AuF6] and the Raman spectrum of [Xe2F11]+"),
        source("reference", f"doi:{pa['mf6Affinities']}", resolver, label="Craciun et al. 2010: electron and fluoride affinities of second-row MF6"),
        source("reference", f"doi:{pa['clf6brf6']}", resolver, label="Schroer and Christe 2001: [ClF6]+ and [BrF6]+ salts"),
        source("reference", f"doi:{pa['xef5MixedCation']}", resolver, label="Mazej and Goreshnik 2017: mixed-cation [XeF5]+ salts"),
        source("reference", f"doi:{pa['xef5Salts2023']}", resolver, label="Mazej and Goreshnik 2023: xenon(VI) salts including XeF5RuF6"),
        source("reference", f"doi:{pa['oxidizerScale']}", resolver, label="Christe and Dixon 1992: quantitative scale for oxidative fluorinators"),
        source("reference", f"doi:{pa['ahfSolvent']}", resolver, label="Zemva 1998: anhydrous HF as a solvent for high oxidation states"),
    ]

    # --- entities -------------------------------------------------------------------------------
    ents = [
        _compound(resolver, "xenon hexafluoride", "xenon hexafluoride (XeF6)", role="substrate to be oxidised"),
        _compound(resolver, "ruthenium hexafluoride", "ruthenium hexafluoride (RuF6)", role="oxidiser"),
        _compound(resolver, "hydrogen fluoride", "anhydrous hydrogen fluoride (aHF)", role="solvent"),
        _compound(resolver, "fluorine", "fluorine (F2)", role="evolved by-product, detected with KI"),
        _compound(resolver, "potassium iodide", "potassium iodide (KI)", role="F2 detection reagent"),
        _compound(resolver, "ruthenium pentafluoride", "ruthenium pentafluoride (RuF5)", role="reduction product with excess RuF6"),
        entity(TARGET["identifier"], "compound", TARGET["label"], role="target, never observed", note="hypothetical; no registry identifier"),
        entity(f"ccdc:{CCDC}", "compound", nc["formula"], scheme="CCDC", url=nc["ccdcUrl"], role="new compound obtained instead of the target",
               extra={"spaceGroup": nc["spaceGroup"], "structureType": nc["structureType"]}),
        entity("compound:xef5-ruf6", "compound", "[XeF5][RuF6], known xenon(VI) salt", role="product of the equimolar reaction", note="structure reported by Bartlett et al. 1973"),
        entity("compound:xef5-oligofluoridoruthenate", "compound", "[XeF5][RunF5n+1] (n = 1, 2, 3, ...)", role="products with excess RuF6, not quantified"),
        entity("assay:scxrd", "assay", "single-crystal X-ray diffraction, Bruker D8 Quest, Mo Kalpha, 100 K", role="structure determination"),
        entity("assay:raman-ir", "assay", "Raman (532 nm, sealed quartz capillary) and ATR IR spectroscopy in an argon glovebox", role="product identification; the only probe for [XeF7]+"),
        entity(org_hit.get("identifier", "org:university-of-bonn"), "organization", facts["operator"]["name"], note=facts["operator"]["note"]),
        entity(aalto.get("identifier", "org:aalto-university"), "organization", "Aalto University", note="quantum-chemical calculations"),
    ] + [entity(f"software:{sw['name'].split(' ')[0].lower()}", "software", sw["name"], role=sw["role"], extra={"version": sw["version"]} if sw.get("version") else None)
         for sw in facts["software"]]
    people = [performer(c["name"], "person", "writing", affiliation=c["affiliation"], identifier=f"https://orcid.org/{c['orcid']}" if c.get("orcid") else None,
                        note="listed author; the article carries no author-contribution statement") for c in facts["contributors"]]

    applicability = {
        "reaction": "RuF6 with XeF6, neat or in anhydrous HF, RuF6:XeF6 from excess XeF6 through 1:1 and 2:1 to excess RuF6",
        "temperatures": "thawed from 77 K to room temperature, and -78 degrees C",
        "vessels": "PFA or FEP reaction vessels on a fluorine-passivated Monel Schlenk line",
        "productProbes": "single-crystal and powder X-ray diffraction, Raman and IR; [XeF7]+ sought by its predicted Raman bands at 588, 647 and 503 cm-1",
        "runCount": "not reported for any condition",
        "note": "the authors restrict their conclusion to 'the conditions investigated by us so far'",
    }
    common = dict(operator=operator, sourceLicense="CC BY 4.0", domainTags=["chemistry"],
                  aiUseDeclaration={"statement": facts["aiUse"]["statement"]})
    cost = {"note": "number of reactions per condition is not reported; amounts of 30 to 120 mg per reaction; no monetary cost reported", "source": "Experimental Section"}
    no_ctrl = {"positive": {"kind": "none"}, "negative": {"kind": "none"}}
    pos_note = ("no reaction known to give a Xe(VIII) product was run alongside, and the oxidising power of RuF6 toward BrF5 is cited from earlier work rather than re-demonstrated; "
                "the immediate decolorisation of RuF6 shows the oxidiser was consumed, not that the target could have been seen. "
                f"The only detection criterion for [XeF7]+ is its predicted Raman bands at 588, 647 and 503 cm-1 ({obs['xef7Bands']}); no detection limit is stated")

    # --- path ----------------------------------------------------------------------------------------
    screened = [{"label": de["oxidant"], "type": "compound", "decision": "excluded", "reason": "prior-art-found", "note": de["outcome"],
                 "references": [f"doi:{d}" for d in de["dois"]], "source": "Introduction"} for de in facts["priorDeadEnds"]]
    screened.append({"label": "RuF6", "type": "compound", "identifier": next(e["id"] for e in ents if e["label"].startswith("ruthenium hexafluoride")),
                     "decision": "included", "reason": "selected-for-testing", "note": tgt["rationale"], "source": "Introduction"})
    path = new_record(
        "path", STUDY, "acs-xef6-path",
        "RuF6 does not oxidise XeF6 to xenon(VIII); F2 is evolved and only xenon(VI) salts form, one of them new",
        question="Can RuF6, a strong one-electron oxidiser of low Lewis acidity, oxidise XeF6 to a xenon(VIII) fluoride species such as a [XeF7]+ salt or XeF8?",
        hypothesis=f"{facts['purpose']} {tgt['rationale']}",
        successCriteria="Isolation or spectroscopic identification of a xenon(VIII) fluoride species, for example [XeF7]+ by its predicted Raman bands or by single-crystal X-ray diffraction.",
        pathType="mixed", outcomeClass="negative-not-achievable",
        outcomeSummary=f"At every ratio and temperature tried, F2 evolved and only xenon(VI) salts formed: the new [Xe2F11][RuF6] with excess XeF6, the known [XeF5][RuF6] at 1:1, and [XeF5]+ oligofluoridoruthenates with excess RuF6. {th['verdict']}",
        confidence={"level": "low", "basis": "no positive control, no run counts, no detection limit for [XeF7]+, and the authors themselves say the conditions may not be right yet"},
        nextSteps=facts["nextSteps"], openQuestions=facts["openQuestions"],
        untriedBranches=[{"description": s, "status": "proposed-by-authors", "source": "Why does RuF6 fail to oxidize XeF6; Conclusions"} for s in facts["nextSteps"]]
                       + [{"description": "A solvent other than anhydrous HF, or a Lewis acid additive, given that aHF raises the oxidising power of F2 toward NF3 only with AsF5 or SbF5 present.", "status": "inferred-by-ingest", "source": "The choice of solvent aHF and comparison of the reactivity of oxidizers"}],
        invalidators=["isolation of any [XeF7]+ salt or of XeF8 from RuF6 and XeF6 under conditions not tried here, for example lower temperature, a different solvent or a Lewis acid additive",
                      "a demonstration that [XeF7]+ forms transiently and decomposes, which would change the finding from 'not formed' to 'formed and lost'"],
        applicabilityConditions=applicability, cost=cost,
        sources=sources_common + dead_end_sources + prior, performers=people, entities=ents, screened=screened,
        screenedSummary={"oxidisersPreviouslyTriedForXeVIII": 3, "oxidisersTriedHere": 1},
        governance={"humanSubjectData": "none", "biosecurityTier": "none"},
        provenanceNotes=[
            "Reaction conditions are described in prose, not tabulated. Each condition is a finding with its Results and Discussion paragraph as locator; the two preparations in the Experimental Section give masses for the excess-XeF6 and equimolar reactions only. No run count is reported for any condition.",
            "The positive finding, a new fully characterised compound, is an attempt of its own derived from the failed oxidation (relation wasDerivedFrom), so the path stays a negative for its stated target while the by-product is queryable as a positive with its CCDC deposit.",
            "The explanation is thermodynamic reasoning (fluoride ion affinities, lattice energies, known instability of [XeF7]+ to F2 loss), recorded as a computational attempt of class partial, because the authors conclude it does not rule the target out and no redox potentials exist for anhydrous HF.",
            "The article has no author-contribution statement; every author is recorded with the role 'writing' only.",
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

    # --- attempt 1: the oxidation attempts, one finding per prose condition ------------------------------------
    cond_findings = []
    for c in conds:
        f = {"id": f"condition-{c['condition']}",
             "question": f"Does RuF6 oxidise XeF6 to a xenon(VIII) species at RuF6:XeF6 {c['ratio_ruf6_xef6']}, {c['solvent']}, {c['temperature']}?",
             "target": TARGET,
             "outcomeClass": "negative-not-achievable", "informativeness": "uninformative",
             "failureModes": ["decomposition"],
             "effect": {"metric": "xenon oxidation state of the isolated product", "value": c["xe_oxidation_state"], "direction": "none",
                        "comparedTo": "VIII sought", "note": f"F2 evolved: {c['f2_evolved']}; product: {c['xe_product']}"},
             "controls": {"positive": {"kind": "none", "note": pos_note},
                          "negative": {"kind": "none", "note": "no XeF6-only or RuF6-only control under the same conditions is described; RuF6 alone is known to lose F2 slowly, which the authors argue is too slow to matter"}},
             "replicates": {"note": "no run count is reported for this or any condition"},
             "conditions": {k: v for k, v in {"ratioRuF6toXeF6": c["ratio_ruf6_xef6"], "solvent": c["solvent"], "temperature": c["temperature"],
                                               "ruf6Mmol": c["ruf6_mmol"], "xef6Mmol": c["xef6_mmol"], "ahfMl": c["ahf_ml"],
                                               "product": c["xe_product"], "rutheniumProduct": c["ru_product"], "evidenceForProduct": c["evidence"]}.items() if v is not None},
             "evidence": [{"label": c["locator"].split(";")[0], "source": PUB_DOI[4:], "locator": c["locator"],
                           "values": {k: v for k, v in c.items() if k not in ("locator", "condition") and v not in (None, "")}}],
             "note": "'decomposition' records the authors' hypothesis that any [XeF7]+ formed decomposes by F2 loss too fast to be observed; whether it forms at all is an open question of the record."}
        apply_informativeness(f)
        cond_findings.append(f)
    f_f2 = {"id": "f2-evolved",
            "question": "Is the gas evolved on mixing RuF6 and XeF6 fluorine?",
            "target": {"label": "fluorine (F2)", "type": "compound", "identifier": next(e["id"] for e in ents if e["label"].startswith("fluorine"))},
            "outcomeClass": "positive", "informativeness": "not-applicable",
            "effect": {"metric": "F2 detection by KI", "value": "detected in every reaction", "direction": "not-applicable"},
            "controls": dict(no_ctrl, negative={"kind": "background", "label": "other fluorinating agents present are not volatile at -196 degrees C", "expected": "no I2 from anything but F2", "observed": "KI turned brown", "passed": True}),
            "conditions": {"method": "gas phase pumped through KI powder at -196 degrees C", "f2VapourPressureMbar": 370},
            "evidence": [{"label": "Results and Discussion, paragraph 2", "source": PUB_DOI[4:], "locator": "Results and Discussion, paragraph 2", "quote": obs["f2Detection"][:400]}]}
    apply_informativeness(f_f2)
    stage_rxn = {"stage": "experiment", "label": "RuF6 with XeF6, neat or in anhydrous HF, condensed at 77 K and thawed; room temperature and -78 degrees C",
                 "performedBy": people, "method": "fluorine-passivated Monel Schlenk line; RuF6 and XeF6 made by literature procedures; PFA or FEP vessels; volatiles removed in vacuum; products by powder XRD, Raman and IR",
                 "conditions": {"ratios": [c["ratio_ruf6_xef6"] for c in conds], "temperatures": sorted({c["temperature"] for c in conds}), "solvents": sorted({c["solvent"] for c in conds})},
                 "replicates": {"note": "not reported"},
                 "note": obs["volatility"]}
    rec_rxn = attempt("acs-xef6-oxidation-attempts",
                      "RuF6 and XeF6 at five ratio and temperature conditions evolve F2 and give only xenon(VI) salts",
                      "Under which of the ratios and temperatures tried does RuF6 oxidise XeF6 beyond xenon(VI)?",
                      "A product containing xenon(VIII), seen by its predicted Raman bands or by X-ray diffraction.",
                      cond_findings[0]["outcomeClass"], cond_findings + [f_f2], [stage_rxn], "wet-lab",
                      outcomeSummary=f"Excess XeF6 (neat or in aHF): [Xe2F11][RuF6] and F2. Equimolar: [XeF5][RuF6] and F2. Excess RuF6: F2, RuF5 and [XeF5]+ oligofluoridoruthenates, not quantified. At -78 degrees C the same products, more slowly. {obs['xef7Bands']}.",
                      confidence={"level": "low", "basis": "no positive control, no run counts, no detection limit; the authors say the conditions may not be right yet"},
                      provenanceNotes=["The rule remaps every condition to inconclusive-no-positive-control, and the authors agree in substance: 'it may be that our reaction conditions are not right, yet'. This is the first study in the corpus where the rule's verdict and the authors' own hedge coincide word for word."])

    # --- attempt 2: the new compound ------------------------------------------------------------------------------
    f_xs = {"id": "crystal-structure",
            "question": "What is the crystal structure of the colourless product from RuF6 with excess XeF6?",
            "target": {"label": nc["formula"], "type": "compound", "identifier": f"ccdc:{CCDC}"},
            "outcomeClass": "positive", "informativeness": "not-applicable",
            "effect": {"metric": "R(F) for I >= 2 sigma(I)", "value": nc["rF"], "direction": "not-applicable", "note": f"wR(F2) {nc['wR2']}; {nc['reflections']} reflections, {nc['uniqueReflections']} unique, {nc['parameters']} parameters, no restraints"},
            "controls": no_ctrl,
            "conditions": {"spaceGroup": nc["spaceGroup"], "a": nc["a"], "b": nc["b"], "c": nc["c"], "beta": nc["beta"], "volume": nc["volume"], "z": nc["z"], "temperatureK": nc["temperatureK"],
                           "radiation": "Mo Kalpha 0.71073 A", "crystals": nc["crystals"], "structureType": nc["structureType"]},
            "evidence": [{"label": "Table 1", "source": PUB_DOI[4:], "locator": "Table 1; Experimental Section, Single-Crystal X-Ray Diffraction",
                          "values": {k: nc[k] for k in ("spaceGroup", "a", "b", "c", "beta", "volume", "z", "temperatureK", "rF", "wR2")},
                          "data": ccdc_src["data"]}]}
    f_geo = {"id": "cation-geometry",
             "question": "How does the [Xe2F11]+ cation in the ruthenium salt compare with the Au, Sb and V salts?",
             "target": {"label": nc["formula"], "type": "compound", "identifier": f"ccdc:{CCDC}"},
             "outcomeClass": "positive", "informativeness": "not-applicable",
             "effect": {"metric": "Xe-F-Xe angle", "value": nc["xeFxeAngle"], "unit": "degrees", "direction": "not-applicable",
                        "comparedTo": "169.2(2) (Au), 166.2(2) (Sb), 166.5(4) (V); 140.3(6) in [Xe2F11]2[NiF6]",
                        "note": f"averaged Xe-mu-F {nc['xeMuFBond']} A; Ru-F {nc['ruFRange']}; Xe...F anion contacts {nc['xeFAnionContacts']}"},
             "controls": no_ctrl,
             "evidence": [{"label": "Figures 1 to 3 and text", "source": PUB_DOI[4:], "locator": "Characterization of [Xe2F11][RuF6], paragraphs 2 and 3; Figures 1 to 3"}]}
    f_vib = {"id": "vibrational-spectra",
             "question": "Do the Raman and IR spectra of the product match the calculated spectrum of [Xe2F11][RuF6]?",
             "target": {"label": nc["formula"], "type": "compound", "identifier": f"ccdc:{CCDC}"},
             "outcomeClass": "positive", "informativeness": "not-applicable",
             "effect": {"metric": "agreement of observed and DFT-PBE0/TZVP band positions", "value": "good overall agreement", "direction": "not-applicable", "note": nc["vibrational"]},
             "controls": dict(no_ctrl, positive={"kind": "known-positive-task", "label": "periodic DFT of the refined structure, lattice parameters within 2.7 percent of experiment, confirmed minimum by harmonic frequencies", "expected": "band positions near observed", "observed": "good overall agreement", "passed": True}),
             "conditions": {"raman": "532 nm, room temperature, flame-sealed quartz capillary", "ir": "ATR diamond, 4 cm-1, argon glovebox", "calculation": th["software"]},
             "evidence": [{"label": "Figure 4 and Table 2", "source": PUB_DOI[4:], "locator": "Figure 4; Table 2; SI Figures S2 and S3"}]}
    for f in (f_xs, f_geo, f_vib):
        apply_informativeness(f)
    stage_char = {"stage": "instrument-capture", "label": "single-crystal and powder X-ray diffraction, Raman and IR of [Xe2F11][RuF6]", "performedBy": people,
                  "instrument": ["Bruker D8 Quest with PHOTON III C14 detector", "Stoe StadiMP powder diffractometer, Cu Kalpha1", "Monovista CRS+ confocal Raman microscope", "Bruker alpha FT-IR, ATR diamond"],
                  "software": [{"name": "APEX5"}, {"name": "SHELXT"}, {"name": "SHELXL"}, {"name": "Diamond"}],
                  "outputs": ccdc_src["data"]}
    attempt("acs-xef6-xe2f11-ruf6",
            "[Xe2F11][RuF6], a new xenon(VI) salt, characterised by single-crystal X-ray diffraction (CCDC 2477117), Raman, IR and periodic DFT",
            "What is the colourless product of RuF6 with excess XeF6, and how does it relate to the known [Xe2F11][MF6] salts?",
            "A refined crystal structure and vibrational spectra assigned against calculation.",
            "positive", [f_xs, f_geo, f_vib], [stage_char], "wet-lab",
            outcomeSummary=f"{nc['formula']} crystallises in {nc['spaceGroup']}, a = {nc['a']}, b = {nc['b']}, c = {nc['c']} A, beta = {nc['beta']} degrees, V = {nc['volume']} A3, Z = {nc['z']} at {nc['temperatureK']} K, isotypic with the V and Sb salts; one-dimensional strands along a.",
            confidence={"level": "high", "basis": "R(F) 0.0176 with no restraints; powder pattern matches; spectra match calculation"},
            cost={"note": "30 mg RuF6 and 100 mg XeF6 for the preparation; run count not reported", "source": "Experimental Section"},
            relations=[{"type": "wasDerivedFrom", "target": rec_rxn["@id"], "note": "the compound is the product of the failed oxidation with excess XeF6"}],
            provenanceNotes=["A positive record hanging off a negative path. The by-product is queryable by its CCDC id and by the framework of related salts it is compared with; the path's headline stays negative for its stated target."])

    # --- attempt 3: thermodynamic explanation ---------------------------------------------------------------------
    def thermo(fid, question, metric, value, unit, note, locator, comparedTo=None, outcome="positive"):
        f = {"id": fid, "question": question, "target": TARGET if "xef7" in fid else {"label": "RuF6 + XeF6 reaction energetics in aHF", "type": "process"},
             "outcomeClass": outcome, "informativeness": "not-applicable",
             "effect": {"metric": metric, "value": value, "unit": unit, "direction": "not-applicable", "note": note, **({"comparedTo": comparedTo} if comparedTo else {})},
             "controls": no_ctrl,
             "conditions": {"method": th["fia"].split(":")[0], "solventModel": "CPCM, epsilon(HF) = 84, where marked CP"},
             "evidence": [{"label": locator, "source": PUB_DOI[4:], "locator": locator}]}
        apply_informativeness(f)
        return f
    f_feas = thermo("xef7-ruf6-feasible", "Would a [XeF7][RuF6] salt be thermodynamically feasible from XeF8 and RuF5?",
                    "estimated formation energy of solid [XeF7][RuF6], solvent-corrected", -572, "kJ/mol",
                    "-138 kJ/mol without the solvent model; lattice energy -489 kJ/mol from Bartlett's volume formula with the IF7 volume for the cation; the authors: 'this indicates that [XeF7][RuF6] would be a feasible compound'",
                    "Estimations of the Lattice Energies; equations 11, 12, 14, 15", comparedTo="-611 (CP) / -368 kJ/mol for the observed [XeF5][RuF6]")
    f_unst = thermo("xef7-unstable-to-f2", "Is the free [XeF7]+ cation stable to loss of F2?",
                    "instability of [XeF7]+ with respect to F2 loss at 0 K (Grant et al. 2010)", 191, "kJ/mol",
                    "XeF8 likewise unstable by about 93 kJ/mol; packing into a solid with a suitable anion may stabilise the cation",
                    "Further Thermodynamic Considerations", comparedTo="XeF8: 93 kJ/mol")
    f_fia = thermo("fluoride-ion-affinities", "What are the fluoride ion affinities of the species involved, with and without an HF solvent model?",
                   "FIA of [XeF7]+, solvent-corrected", -379, "kJ/mol", th["fia"], "Consideration of Fluoride Ion Affinities (FIAs); equations 10 to 12",
                   comparedTo="[XeF5]+ -367 (CP); RuF5 -462 (CP)")
    f_why = {"id": "why-it-fails",
             "question": "Why does RuF6 fail to oxidise XeF6, at least under these conditions?",
             "target": TARGET, "outcomeClass": "partial", "informativeness": "not-applicable",
             "effect": {"metric": "explanation reached", "value": "none decisive", "direction": "not-applicable",
                        "note": f"{th['redoxPotentials']}; {th['ruf6Stability'] if 'ruf6Stability' in th else obs['ruf6Stability']}; {th['conclusionHypothesis']}"},
             "controls": no_ctrl,
             "evidence": [{"label": "Why does RuF6 fail to oxidize XeF6", "source": PUB_DOI[4:], "locator": "section 'Why does RuF6 fail to oxidize XeF6 (at least not under these conditions)?', final paragraphs", "quote": th["verdict"]}],
             "note": "The thermodynamics do not rule the target out; the authors' working hypothesis is kinetic, that [XeF7]+ decomposes too fast."}
    apply_informativeness(f_why)
    stage_calc = {"stage": "computation", "label": "FIAs at CCSD(T)/def2-QZVPP on PW6B95 geometries with and without CPCM(HF); lattice energies by Bartlett's volume formula",
                  "performedBy": people, "software": [{"name": "ORCA", "version": "6.1.1"}, {"name": "CRYSTAL23"}], "method": th["fia"], "note": th["software"]}
    attempt("acs-xef6-thermodynamics",
            "Thermodynamic estimates say a [XeF7][RuF6] salt may be stable, so the failure is not explained",
            "Do fluoride ion affinities, reaction enthalpies and lattice energies explain why no xenon(VIII) product forms?",
            "An energetic argument that rules the target out or identifies the barrier.",
            "partial", [f_feas, f_unst, f_fia, f_why], [stage_calc], "computational",
            outcomeSummary=f"{th['formationEnergies']} {th['instability']} {th['redoxPotentials']}",
            confidence={"level": "medium", "basis": "the lattice energy of the putative salt rests on an estimated cation volume; solvent-corrected and uncorrected values differ in sign for the reaction enthalpies"},
            cost={"note": "CSC Finland compute; amount not reported", "source": "Acknowledgments"},
            relations=[{"type": "informs", "target": rec_rxn["@id"]}])

    path["hasPart"] = [a["@id"] for a in attempts]
    check_valid(path)
    return [path] + attempts
