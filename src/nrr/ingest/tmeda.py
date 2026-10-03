"""Converter for Macleod, Bage, Meyer and Thomas 2024, 'Hidden Boron Catalysis: A Cautionary Tale on TMEDA
Inhibition' (Org. Lett. 26, 9564-9567, doi:10.1021/acs.orglett.4c03591, CC BY 4.0; full text from Europe PMC,
PMC11555781).

A negative about a control method. Trapping with TMEDA is the field's standard test for whether a hydroboration
'catalyst' is really decomposing HBpin to BH3; kinetics here show the TMEDA.(BH3)2 adduct is labile above 60 °C, so
the test passes reactions that are in fact BH3-catalysed. The chemistry analogue of the Raman batch-effects record,
where the validation scheme was the problem: the record has to say 'this negative control is unreliable under these
conditions' and connect that to the literature that relied on it.
"""
from __future__ import annotations

from pathlib import Path

from nrr.ingest.common import (
    check_valid, data_pointer, entity, finalize, new_record, performer, read_csv, read_json, read_yaml, source,
)
from nrr.rules import apply_informativeness

STUDY = "acs-tmeda"
PUB_DOI = "doi:10.1021/acs.orglett.4c03591"
PMCID = "PMC11555781"
SI_FILE = "ol4c03591_si_001.pdf"
TEST_ID = "assay:tmeda-inhibition-test"
TEST_LABEL = "TMEDA inhibition test for hidden BH3 catalysis in HBpin hydroboration"
SENSITIVITY = "inhibition is defined as less than 5 % product by 1H and 11B NMR against a 1,3,5-trimethoxybenzene internal standard; yields are the average of two runs"


def _num(v):
    try:
        return float(v) if "." in v else int(v)
    except (ValueError, TypeError):
        return v


def parse_kinetics(path: Path) -> list[dict]:
    rows = read_csv(path)
    for r in rows:
        r["temperature_c"] = int(r["temperature_c"])
        r["bh3_mol_pct"] = int(r["bh3_mol_pct"])
        r["initial_rate_mm_s"] = float(r["initial_rate_mm_s"])
        r["yield_pct"] = _num(r["yield_pct"])
    return rows


def parse_amine_screen(path: Path) -> list[dict]:
    rows = read_csv(path)
    for r in rows:
        r["temperature_c"] = int(r["temperature_c"])
        r["inhibited"] = r["result"].startswith("inhibition")
    return rows


def parse_loading(path: Path) -> list[dict]:
    rows = read_csv(path)
    for r in rows:
        r["temperature_c"] = int(r["temperature_c"])
        r["tmeda_equiv"] = float(r["tmeda_equiv"])
    return rows


def _compound(resolver, name: str, label: str | None = None, role: str | None = None, **extra) -> dict:
    hit = resolver.compound(name) or {}
    ident = hit.get("identifier") or f"compound:{name.lower().replace(' ', '-')}"
    return entity(ident, "compound", label or name, scheme="PubChem" if hit.get("identifier") else None, role=role,
                  note=None if hit.get("identifier") else "identifier not resolved", **extra)


def build_tmeda_records(root: Path, resolver) -> list[dict]:
    cur, raw = root / "curated" / "tmeda", root / "raw" / "tmeda"
    facts = read_yaml(cur / "pub_facts.yaml")
    kinetics = parse_kinetics(cur / "kinetics.csv")
    screen = parse_amine_screen(cur / "amine_screen.csv")
    loading = parse_loading(cur / "loading.csv")
    si_refs = read_csv(cur / "si_references.csv")
    fetched = read_json(raw / "europepmc" / "record.json")["fetched"]

    pub, meth, res, lit = facts["publication"], facts["method"], facts["results"], facts["literatureSurvey"]
    limit = res["temperatureLimit"]
    org_hit = resolver.organization(facts["operator"]["name"]) or {}
    operator = {"name": facts["operator"]["name"], "type": "Organization"}
    if org_hit.get("identifier"):
        operator["identifier"] = org_hit["identifier"]

    si_meta = fetched["files"][f"si/{SI_FILE}"]
    si_pointer = data_pointer(SI_FILE, repository="Europe PMC", accession=PMCID, url=fetched["supplementaryFiles"],
                              checksum="sha256:" + si_meta["sha256"], size=si_meta["size"], format="application/pdf",
                              role="Supporting Information: procedures, reaction monitoring, loading tables S1 and S2, amine table S3, literature analysis S4")
    sources_common = [
        source("source-publication", PUB_DOI, resolver, label=pub["title"], url=pub["url"], license=pub["license"], note=pub["licenseStatement"]),
        source("supplementary", f"pmc:{PMCID}/{SI_FILE}", resolver, label="Supporting Information (PDF)", url=fetched["supplementaryFiles"],
               license=pub["license"], data=[si_pointer], note=pub["dataAvailability"]),
    ]
    pa = facts["priorArt"]
    prior = [
        source("prior-art", f"doi:{pa['tmedaTestIntroduced']}", resolver, label="Bage et al. 2020: the TMEDA trapping and inhibition test introduced, demonstrated up to 60 °C"),
        source("prior-art", f"doi:{pa['nucleophilePromotedDecomposition']}", resolver, label="Bage et al. 2020: nucleophile-promoted decomposition of HBpin to BH3"),
        source("prior-art", f"doi:{pa['brownAdductAt110C']}", resolver, label="Brown and Murray 1984: TMEDA.(BH3)2 used as a hydroboration reagent at 110 °C"),
        source("reference", f"doi:{pa['catecholboraneDegradation']}", resolver, label="Westcott et al. 1993: nucleophile-promoted degradation of catecholborane"),
        source("reference", f"doi:{pa['trojanHorse']}", resolver, label="Burgess and Jaspars 1993: 'beware of the Trojan horse'"),
        source("reference", f"doi:{pa['boraneCatalysedHydroboration']}", resolver, label="borane-catalysed hydroboration of alkynes and alkenes"),
        source("reference", f"doi:{pa['alkyneHydroborationKinetics']}", resolver, label="kinetics of alkyne hydroboration; why yields of 2 do not reach 100 %"),
    ]
    example_refs = []
    for r in si_refs:
        hit = resolver.citation_doi(r["citation"]) or {}
        ident = f"doi:{hit['doi']}" if hit.get("doi") else f"citation:{r['citation'][:80]}"
        example_refs.append(source("reference", ident, resolver, label=r["citation"][:160],
                                   note=f"SI reference {r['si_ref']}: cited as an example of a publication using TMEDA reaction inhibition as the detection method for hidden boron catalysis; whether its test was run above 60 °C is not stated per paper"
                                        + ("" if hit.get("doi") else "; DOI not resolved")))

    # --- entities -------------------------------------------------------------------------------
    ents = [
        entity(TEST_ID, "assay", TEST_LABEL, role="the control method under test",
               note="a lack of inhibition on adding TMEDA has been read as evidence of true, non-boron catalysis"),
        _compound(resolver, "N,N,N',N'-tetramethylethylenediamine", "N,N,N',N'-tetramethylethylenediamine (TMEDA)", role="BH3 trap"),
        entity("compound:tmeda-bis-borane", "compound", "TMEDA.(BH3)2 adduct", role="the trapped species, tested as a catalyst", note="11B NMR -10.6 ppm (q, J = 98 Hz); no registry identifier given"),
        _compound(resolver, "pinacolborane", "pinacolborane (HBpin)", role="hydroboration reagent"),
        _compound(resolver, "borane", "borane (BH3)", role="the hidden catalyst"),
        _compound(resolver, "borane dimethyl sulfide", "borane dimethyl sulfide (Me2S.BH3)", role="positive-control BH3 source"),
        _compound(resolver, "phenylacetylene", "phenylacetylene (1)", role="alkyne substrate"),
        _compound(resolver, "4-tert-butylstyrene", "4-tert-butylstyrene (3)", role="alkene substrate"),
        _compound(resolver, "1,4-diazabicyclo[2.2.2]octane", "DABCO (amine of 5a)", role="alternative trap"),
        _compound(resolver, "N,N,N',N'',N''-pentamethyldiethylenetriamine", "PMDTA (amine of 5b)", role="alternative trap"),
        _compound(resolver, "N-methylmorpholine", "N-methylmorpholine (amine of 5c)", role="alternative trap"),
        _compound(resolver, "N,N-diisopropylethylamine", "N,N-diisopropylethylamine, DIPEA (amine of 5d)", role="alternative trap"),
        _compound(resolver, "triethylamine", "triethylamine", role="alternative trap; also the stabiliser in commercial HBpin"),
        _compound(resolver, "trimethylamine", "trimethylamine", role="alternative trap"),
        _compound(resolver, "lithium tert-butoxide", "lithium tert-butoxide (LiOtBu)", role="nucleophile used to generate hidden BH3 catalysis on purpose"),
        _compound(resolver, "1,3,5-trimethoxybenzene", "1,3,5-trimethoxybenzene", role="NMR internal standard"),
        _compound(resolver, "toluene", "toluene", role="solvent"),
        _compound(resolver, "diglyme", "diglyme", role="coordinating co-solvent in the repeat kinetics (SI Figure S2)"),
        entity(org_hit.get("identifier", "org:university-of-edinburgh"), "organization", facts["operator"]["name"], note=facts["operator"]["note"]),
    ]
    people = [performer(c["name"], "person", "writing", affiliation=facts["operator"]["name"],
                        note="listed author; the article carries no author-contribution statement") for c in facts["contributors"]]

    applicability = {
        "reaction": "hydroboration of terminal alkynes and alkenes with pinacolborane in toluene (and diglyme), BH3 at 20 mol %",
        "tmedaInhibitionTestValidUpToC": limit,
        "falseNegativesFromC": 80,
        "hbpinThermalDecompositionFromC": 80,
        "tmedaLoading": "one-to-one TMEDA to 'catalyst' for the headline; 0.5 to 1.0 eq extends inhibition but not completely",
        "temperatures": "external heating-block temperatures; room temperature about 18 °C",
        "substratesNotCovered": "carbonyl compounds, for which the TMEDA test is not compatible (SI Section S4)",
        "note": "the limit is about the TMEDA.(BH3)2 adduct's lability, so it applies to any catalysed HBpin hydroboration that uses TMEDA inhibition as its evidence of true catalysis",
    }
    common = dict(operator=operator, sourceLicense="CC BY 4.0", domainTags=["chemistry"],
                  aiUseDeclaration={"statement": facts["aiUse"]["statement"]})
    cost = {"note": "bench-scale NMR kinetics; runs are the average of two; no monetary cost reported", "source": "SI Section S3"}

    no_ctrl = {"positive": {"kind": "none"}, "negative": {"kind": "none"}}
    pos_ctrl = {"kind": "designated", "label": "Me2S.BH3 as free-BH3 source, 20 mol % BH3",
                "expected": "fast BH3-catalysed hydroboration", "observed": "9.6 mM/s, 87 % of 2 in 40 min at 60 °C (alkyne); 1.8 mM/s, >95 % of 4 in 7 h (alkene)",
                "passed": True, "note": meth["controlRationale"], "source": "Schemes 2 and 3"}
    bg_ctrl = {"kind": "background", "label": "HBpin and substrate with no BH3 source",
               "expected": "no product", "observed": "no reaction at room temperature; HBpin alone gives product only at 80 °C and above",
               "passed": True, "note": "clean to 70 °C; at 80 °C and above HBpin decomposes to BH3 thermally, so the background is not clean there", "source": "SI S3.6 and Table 1 control row"}

    # --- attempt 1: adduct kinetics ---------------------------------------------------------------------------
    k_findings = []
    for r in [k for k in kinetics if k["bh3_source"] == "TMEDA.(BH3)2"]:
        ctrl = next(k for k in kinetics if k["bh3_source"] == "Me2S.BH3" and k["substrate"] == r["substrate"])
        inert = r["temperature_c"] <= limit
        f = {"id": f"{r['substrate']}-{r['temperature_c']}",
             "question": f"Does the TMEDA.(BH3)2 adduct catalyse the hydroboration of {r['substrate_label']} with HBpin at {r['temperature_c']} °C?",
             "target": {"label": "TMEDA.(BH3)2 adduct", "type": "compound", "identifier": "compound:tmeda-bis-borane"},
             "outcomeClass": "negative-no-effect" if inert else "positive",
             "informativeness": "informative" if inert else "not-applicable",
             "effect": {"metric": "initial rate of boronic ester formation", "value": r["initial_rate_mm_s"], "unit": "mM/s",
                        "direction": "none" if inert else "increase",
                        "comparedTo": f"{ctrl['initial_rate_mm_s']} mM/s and {ctrl['yield_pct']} % in {ctrl['yield_time']} for the Me2S.BH3 control at {ctrl['temperature_c']} °C",
                        "note": f"{r['yield_pct']} % of product after {r['yield_time']}"},
             "controls": {"positive": pos_ctrl, "negative": bg_ctrl},
             "sensitivity": SENSITIVITY,
             "replicates": {"technical": 2, "note": "yields are the average of two runs (SI S3.2)"},
             "conditions": {"temperatureC": r["temperature_c"], "bh3MolPct": r["bh3_mol_pct"], "solvent": r["solvent"], "yieldPct": r["yield_pct"], "yieldTime": r["yield_time"],
                            "substrate": r["substrate_label"]},
             "evidence": [{"label": r["source"].split(":")[0], "source": PUB_DOI[4:], "locator": r["source"].split(":")[0],
                           "values": {"initialRate_mM_s": r["initial_rate_mm_s"], "yieldPct": r["yield_pct"], "yieldTime": r["yield_time"]},
                           "quote": r["source"].split(": ", 1)[1].strip("'")[:300]}],
             "note": ("not sufficiently labile to meaningfully catalyse the reaction" if inert else "sufficiently labile to release catalytically active BH3")}
        apply_informativeness(f)
        k_findings.append(f)

    f_test = {"id": "tmeda-test-false-negative-above-60",
              "question": "Does a lack of inhibition by TMEDA demonstrate true, non-boron catalysis at the temperatures the test is used at?",
              "target": {"label": TEST_LABEL, "type": "assay", "identifier": TEST_ID},
              "outcomeClass": "refuted", "informativeness": "not-applicable",
              "failureModes": ["reagent-nonspecific"],
              "effect": {"metric": "temperature above which the trapped adduct catalyses hydroboration", "value": limit, "unit": "°C", "direction": "not-applicable",
                         "note": "50 % product at 80 °C and 94 % at 100 °C for the alkyne, complete conversion at 80 and 100 °C for the alkene, with the adduct as the only BH3 source"},
              "controls": {"positive": pos_ctrl, "negative": bg_ctrl},
              "sensitivity": SENSITIVITY,
              "conditions": {"validUpToC": limit, "falseNegativeFromC": 80, "literatureUseAboveLimitPct": lit["tmedaAbove60C"]["percentOfTmeda"]},
              "evidence": [{"label": "Abstract", "source": PUB_DOI[4:], "locator": "Abstract", "quote": res["headline"]},
                           {"label": "Conclusion", "source": PUB_DOI[4:], "locator": "final paragraph", "quote": res["conclusion"][:600]}],
              "relatedFindings": [f"acs-tmeda-adduct-kinetics#{f['id']}" for f in k_findings if f["conditions"]["temperatureC"] > limit],
              "note": "What is refuted is the inference 'no inhibition, therefore true catalysis' above 60 °C, not the existence of hidden catalysis. The record keeps the test valid at or below 60 °C."}
    apply_informativeness(f_test)

    f_demo = {"id": "hidden-catalysis-demonstration",
              "question": "Does TMEDA added to a deliberately hidden BH3-catalysed reaction inhibit it at 60 °C, and does the inhibition survive heating to 100 °C?",
              "target": {"label": TEST_LABEL, "type": "assay", "identifier": TEST_ID},
              "outcomeClass": "positive", "informativeness": "not-applicable",
              "effect": {"metric": "inhibition on adding 0.1 eq TMEDA at 60 °C", "value": "complete, lost at 100 °C", "direction": "not-applicable"},
              "controls": dict(no_ctrl, positive={"kind": "internal-positive", "label": "LiOtBu 10 mol % generating BH3 from HBpin", "expected": "hydroboration proceeds", "observed": "product forming over 90 min at 60 °C", "passed": True}),
              "conditions": {"nucleophile": "LiOtBu 10 mol %", "tmedaEquiv": 0.1, "tmedaAddedAtMin": 90, "heatedTo100AtMin": 180},
              "evidence": [{"label": "SI S3.4 and Figure S4", "source": PUB_DOI[4:], "locator": "SI Section S3.4, Figure S4", "quote": meth["hiddenCatalysisDemonstration"][:400]}]}
    apply_informativeness(f_demo)

    f_hbpin = {"id": "hbpin-thermal-decomposition",
               "question": "At what temperature does pinacolborane alone decompose to BH3?",
               "target": {"label": "pinacolborane (HBpin)", "type": "compound", "identifier": next(e["id"] for e in ents if e["label"].startswith("pinacolborane"))},
               "outcomeClass": "positive", "informativeness": "not-applicable",
               "effect": {"metric": "lowest temperature at which Et3N.BH3 is observed by 11B NMR after 20 h", "value": 80, "unit": "°C", "direction": "not-applicable"},
               "controls": dict(no_ctrl, negative={"kind": "background", "label": "distilled HBpin with Et3N at room temperature, 60 and 70 °C for 20 h", "expected": "no BH3", "observed": "no decomposition", "passed": True}),
               "conditions": {"bh3ObservedFromC": 80, "otherDecompositionFromC": 90, "duration": "20 h"},
               "evidence": [{"label": "SI S3.5 and Figure S5", "source": PUB_DOI[4:], "locator": "SI Section S3.5, Figure S5", "quote": meth["hbpinStability"][:400]}],
               "note": "This is why the background control of the amine screen fails at 80 °C, and why the authors say any HBpin hydroboration at or above 80 °C is inherently susceptible to hidden BH3 catalysis."}
    apply_informativeness(f_hbpin)

    stage_kin = {"stage": "experiment", "label": "NMR reaction monitoring of HBpin hydroboration catalysed by Me2S.BH3 or TMEDA.(BH3)2",
                 "performedBy": people, "method": f"{meth['conditions']}; {meth['monitoring']}", "instrument": ["Bruker Avance III 400 and 500 MHz, PRO 500 MHz, Avance I 600 MHz NMR spectrometers"],
                 "conditions": {"temperaturesC": [60, 80, 100], "solvents": ["toluene", "diglyme"]},
                 "replicates": {"runsAveraged": 2}, "note": meth["adductSynthesis"]}

    # --- path (finalised before attempts, as elsewhere) --------------------------------------------------------
    path = new_record(
        "path", STUDY, "acs-tmeda-path",
        "Is TMEDA inhibition a reliable test for hidden BH3 catalysis, and is any amine a better trap?",
        question=facts["purpose"],
        hypothesis="If the TMEDA.(BH3)2 adduct is labile at the temperatures hydroboration catalysis is run at, TMEDA will fail to inhibit BH3-catalysed hydroboration there and a lack of inhibition cannot be read as true catalysis.",
        successCriteria="A temperature range over which TMEDA (or another amine) completely inhibits BH3-catalysed HBpin hydroboration, defined as less than 5 % product by NMR, with the adduct shown not to catalyse on its own.",
        pathType="experiment", outcomeClass="partial",
        outcomeSummary=f"{res['headline']} {res['recommendation']}",
        confidence={"level": "high", "basis": "the free-BH3 positive control and the no-catalyst background are both run at every temperature; the inhibition threshold is defined; two substrates agree; the loading and literature analyses are consistent with the kinetics"},
        nextSteps=facts["nextSteps"], openQuestions=facts["openQuestions"],
        untriedBranches=[{"description": s, "status": "proposed-by-authors", "source": "final paragraph"} for s in facts["nextSteps"]]
                       + [{"description": "Re-test the published 'true catalysis' claims whose only evidence was TMEDA inhibition above 60 °C, at or below 60 °C or by direct 11B NMR observation of the adduct.", "status": "inferred-by-ingest", "source": "SI Section S4 counts"}],
        invalidators=["an amine or other trap shown to sequester BH3 completely at 80 °C and above under hydroboration conditions",
                      "a demonstration that TMEDA.(BH3)2 does not release catalytically active BH3 above 60 °C in a solvent or at a loading not tested here"],
        applicabilityConditions=applicability, cost=cost,
        sources=sources_common + prior, performers=people, entities=ents,
        governance={"humanSubjectData": "none", "biosecurityTier": "none"},
        provenanceNotes=[
            "The headline negative here is about a method, not a reaction: the record makes the TMEDA inhibition test itself an entity of type assay and the target of a refuted finding, with the valid temperature range in the finding's conditions and in applicabilityConditions.",
            f"Main-text Table 1 is an image in the PMC XML; its colour grid (green: less than 5 % product; pink: product observed) was transcribed cell by cell from the figure file ol4c03591_0004.jpg into curated/tmeda/amine_screen.csv. SI Table S3 repeats it without the colours in the text extraction.",
            "The article has no author-contribution statement; every author is recorded with the role 'writing' only.",
            "Rates and yields are read from the text accompanying Schemes 2 and 3 and from SI Tables S1 and S2; yields in SI Schemes S3 and S4 are in images and were not transcribed.",
        ],
        hasPart=[], **common)
    finalize(path, check=False)
    pid = path["@id"]
    attempts: list[dict] = []

    def attempt(slug, title, question, success, outcome, findings, stages, attempt_type, **kw):
        rec = new_record("attempt", STUDY, slug, title, attemptType=attempt_type,
                         pathType="literature" if attempt_type == "evidence-synthesis" else "experiment",
                         question=question, successCriteria=success, outcomeClass=outcome, findings=findings, stages=stages,
                         applicabilityConditions=applicability, cost=kw.pop("cost", cost), sources=sources_common + kw.pop("sources", []),
                         isPartOf=pid, entities=ents, performers=people,
                         relations=[{"type": "isPartOf", "target": pid}] + kw.pop("relations", []), **common, **kw)
        attempts.append(finalize(rec))
        return rec

    attempt("acs-tmeda-adduct-kinetics",
            "TMEDA.(BH3)2 is inert at 60 °C but catalyses HBpin hydroboration at 80 and 100 °C, so the TMEDA inhibition test gives false negatives above 60 °C",
            "Over what temperature range does the TMEDA.(BH3)2 adduct remain inert as a hydroboration catalyst, compared with free BH3 and with no catalyst?",
            "Adduct-catalysed rate indistinguishable from the no-catalyst background and far below the Me2S.BH3 control, with less than 5 % product.",
            "refuted", k_findings + [f_test, f_demo, f_hbpin], [stage_kin], "wet-lab",
            outcomeSummary="Alkyne: 0.3 mM/s and 4 % at 60 °C against 9.6 mM/s and 87 % for free BH3; 50 % at 80 °C and 94 % at 100 °C. Alkene: 0.02 mM/s and 3 % at 60 °C against 1.8 mM/s and >95 %; complete at 80 and 100 °C. HBpin alone decomposes to BH3 from 80 °C.",
            confidence={"level": "high", "basis": "designated free-BH3 control and no-catalyst background at every temperature; threshold defined; two substrates"},
            provenanceNotes=["Attempt headline is 'refuted' because the finding the authors built the paper around is the refutation of the inference 'no inhibition means true catalysis' above 60 °C; the six kinetic findings carry the data, two of them informative negatives at 60 °C."])

    # --- attempt 2: amine screen ----------------------------------------------------------------------------------
    by_code: dict[str, list[dict]] = {}
    for r in screen:
        by_code.setdefault(r["code"], []).append(r)
    screen_bg = dict(bg_ctrl, observed="no product at 18, 60 and 70 °C; product at 80 °C",
                     note="the no-amine-borane control row is clean to 70 °C and not clean at 80 °C, because HBpin decomposes to BH3 thermally from 80 °C; the 80 °C column therefore cannot distinguish a failed trap from background catalysis",
                     source="Table 1 control row")
    amine_findings = []
    for code, rows in by_code.items():
        if code == "control":
            continue
        rows = sorted(rows, key=lambda r: r["temperature_c"])
        inhib_temps = [r["temperature_c"] for r in rows if r["inhibited"]]
        up_to = max(inhib_temps) if inhib_temps else None
        if up_to is None:
            outcome, note = "negative-no-effect", "product formed even at room temperature: this amine-borane releases catalytically active BH3 and does not act as a trap"
        else:
            outcome, note = "partial", f"inhibits to {up_to} °C, the same limit as TMEDA; not an improvement"
        f = {"id": f"amine-{code}",
             "question": f"Does {rows[0]['amine_borane']} inhibit BH3-catalysed hydroboration of phenylacetylene with HBpin, and to what temperature?",
             "target": {"label": f"{rows[0]['amine_borane']} ({code})", "type": "compound",
                        "identifier": next((e["id"] for e in ents if code != "control" and f"({code})" in e["label"]), None)},
             "outcomeClass": outcome, "informativeness": "informative" if outcome.startswith("negative") else "not-applicable",
             "effect": {"metric": "highest temperature with less than 5 % product", "value": up_to if up_to is not None else "none, product at 18 °C", "unit": "°C", "direction": "not-applicable",
                        "comparedTo": "TMEDA: inhibition demonstrated to 60 °C"},
             "controls": {"positive": {"kind": "internal-positive", "label": "DABCO.(BH3)2 (5a) and PMDTA.(BH3)3 (5b) inhibit to 60 °C in the same grid",
                                       "expected": "inhibition at low temperature", "observed": "less than 5 % product at 18 and 60 °C", "passed": True},
                          "negative": screen_bg},
             "sensitivity": SENSITIVITY,
             "conditions": {"inhibitsUpToC": up_to, "temperaturesTestedC": [r["temperature_c"] for r in rows], "amineBoraneMmol": 0.1, "substrate": "phenylacetylene 1.0 mmol", "hbpinMmol": 1.5, "solvent": "toluene 0.20 mL"},
             "evidence": [{"label": f"Table 1 row {code}", "source": PUB_DOI[4:], "locator": r["source"], "values": {"temperatureC": r["temperature_c"], "result": r["result"]}} for r in rows],
             "note": note}
        if f["target"]["identifier"] is None:
            del f["target"]["identifier"]
        apply_informativeness(f)
        amine_findings.append(f)
    f_better = {"id": "better-trap",
                "question": "Is any of the six amines tested a better in situ BH3 trap than TMEDA for the inhibition test?",
                "target": {"label": TEST_LABEL, "type": "assay", "identifier": TEST_ID},
                "outcomeClass": "negative-not-achievable", "informativeness": "informative",
                "effect": {"metric": "amines inhibiting above 60 °C", "value": 0, "n": 6, "direction": "none",
                           "note": "5a and 5b match TMEDA (inhibition to 60 °C); 5c, 5d, Et3N.BH3 and Me3N.BH3 give product at room temperature"},
                "controls": {"positive": {"kind": "internal-positive", "label": "5a and 5b inhibit to 60 °C", "expected": "inhibition detectable", "observed": "detected", "passed": True},
                             "negative": screen_bg},
                "sensitivity": SENSITIVITY,
                "conditions": {"aminesTested": [rows[0]["amine_borane"] for code, rows in by_code.items() if code != "control"], "temperaturesTestedC": [18, 60, 70, 80]},
                "evidence": [{"label": "Table 1 and text", "source": PUB_DOI[4:], "locator": "Table 1; paragraph 'In an attempt to find a better inhibitor'", "quote": res["amines"]}]}
    apply_informativeness(f_better)
    stage_screen = {"stage": "experiment", "label": "amine-borane adducts as BH3 sources in HBpin hydroboration of phenylacetylene, 1 h each at 18, 60, 70 and 80 °C",
                    "performedBy": people, "method": meth["amineScreen"], "instrument": ["NMR spectrometer (1H and 11B)"],
                    "conditions": {"temperaturesC": [18, 60, 70, 80], "readout": "less than 5 % product (green) or product observed (pink)"}}
    attempt("acs-tmeda-amine-screen",
            "No amine tested is a better BH3 trap than TMEDA: two match its 60 °C limit, four release BH3 at room temperature",
            "Is any of six alternative amine-borane adducts inert to a higher temperature than TMEDA.(BH3)2 in HBpin hydroboration?",
            "An amine-borane with less than 5 % product at 70 °C or above where the no-amine background is still clean.",
            "negative-not-achievable", amine_findings + [f_better], [stage_screen], "wet-lab",
            outcomeSummary=res["amines"],
            confidence={"level": "high", "basis": "internal positives (5a, 5b) and a clean background to 70 °C in the same grid; threshold defined"},
            provenanceNotes=["Table 1 is a colour grid read from the figure image; each cell is one evidence item with its row and column as locator. No per-cell yields are given in the article."])

    # --- attempt 3: higher TMEDA loading ----------------------------------------------------------------------------
    def loading_finding(sub, label):
        rows = [r for r in loading if r["substrate"] == sub]
        hot = [r for r in rows if r["temperature_c"] == 100 and r["tmeda_equiv"] > 0]
        last = max(hot, key=lambda r: r["tmeda_equiv"])
        complete = sub == "alkyne"
        f = {"id": f"loading-{sub}",
             "question": f"Does a higher loading of TMEDA relative to the 'catalyst' restore complete inhibition of hidden BH3 catalysis in the hydroboration of {label} at 80 and 100 °C?",
             "target": {"label": TEST_LABEL, "type": "assay", "identifier": TEST_ID},
             "outcomeClass": "partial", "informativeness": "not-applicable",
             "effect": {"metric": f"product at 100 °C with {last['tmeda_equiv']} eq TMEDA", "value": _num(last["yield_pct"]) if not isinstance(_num(last["yield_pct"]), str) else last["yield_pct"], "unit": "%", "direction": "decrease",
                        "comparedTo": f"{rows[0]['yield_pct']} % with no TMEDA at 80 °C", "note": "increased inhibition with loading but, for the alkene, not complete; false negatives remain possible"},
             "controls": {"positive": {"kind": "internal-positive", "label": "no TMEDA, LiOtBu 10 mol %", "expected": "hidden BH3 catalysis proceeds", "observed": ">95 % product at 80 °C", "passed": True},
                          "negative": bg_ctrl},
             "sensitivity": SENSITIVITY,
             "conditions": {"tmedaEquiv": last["tmeda_equiv"], "nucleophile": "LiOtBu 10 mol %", "temperaturesC": sorted({r["temperature_c"] for r in rows}),
                            "completeInhibitionAt": "0.5 eq TMEDA at 80 and 100 °C" if complete else "none of 0.5, 0.75 or 1.0 eq at 100 °C"},
             "evidence": [{"label": r["source"], "source": PUB_DOI[4:], "locator": r["source"], "values": {"tmedaEquiv": r["tmeda_equiv"], "temperatureC": r["temperature_c"], "yieldPct": r["yield_pct"]}} for r in rows],
             "note": "SI S3.3.1 also shows that an extra 0.4 eq TMEDA with the adduct achieves inhibition at 80 °C but not at 100 °C (Schemes S3 and S4, yields in images)."}
        apply_informativeness(f)
        return f
    stage_load = {"stage": "experiment", "label": "hidden BH3 catalysis generated with LiOtBu, inhibited with 0.1 to 1.0 eq TMEDA at 80 and 100 °C",
                  "performedBy": people, "method": "HBpin 3.0 mmol, LiOtBu 10 mol %, TMEDA 0.1 to 1 eq, substrate 2.0 mmol, toluene; yields by 1H NMR, average of two runs (SI S3.3.2)",
                  "conditions": {"temperaturesC": [80, 100], "tmedaEquiv": sorted({r["tmeda_equiv"] for r in loading})}}
    attempt("acs-tmeda-loading",
            "Higher TMEDA loading improves but does not complete inhibition of hidden BH3 catalysis above 60 °C",
            "Can a higher TMEDA to 'catalyst' ratio rescue the inhibition test at 80 and 100 °C?",
            "Less than 5 % product at 80 and 100 °C with a loading that would be practical in a test reaction.",
            "partial", [loading_finding("alkyne", "phenylacetylene"), loading_finding("alkene", "4-tert-butylstyrene")], [stage_load], "wet-lab",
            outcomeSummary="Alkyne: 0.5 eq TMEDA gives less than 5 % product at 80 and 100 °C. Alkene: 70 % at 0.5 eq and 80 °C; 11, 9 and 7 % at 0.5, 0.75 and 1.0 eq at 100 °C. The authors conclude false negatives remain possible.",
            confidence={"level": "medium", "basis": "two runs per entry; the authors note BH3 generated in situ is far below the nominal catalyst concentration, so the loading needed in a real test is uncertain"})

    # --- attempt 4: literature survey -----------------------------------------------------------------------------------
    f_uptake = {"id": "uptake",
                "question": "How many catalysed-HBpin-hydroboration publications test for hidden boron catalysis, before and after the TMEDA method was introduced in May 2020?",
                "target": {"label": "catalysed hydroboration literature with HBpin, 2010 to September 2024", "type": "other"},
                "outcomeClass": "positive", "informativeness": "not-applicable",
                "effect": {"metric": "publications testing for hidden boron catalysis after May 2020", "value": lit["afterTmedaMethod"]["testedForHiddenCatalysis"], "n": lit["afterTmedaMethod"]["publications"],
                           "unit": "publications", "direction": "increase",
                           "comparedTo": f"{lit['beforeTmedaMethod']['testedForHiddenCatalysis']} of {lit['beforeTmedaMethod']['publications']} ({lit['beforeTmedaMethod']['percent']} %) before May 2020",
                           "note": f"{lit['afterTmedaMethod']['percent']} % after; {lit['usedTmedaInhibition']['publications']} of the {lit['afterTmedaMethod']['testedForHiddenCatalysis']} used TMEDA inhibition"},
                "controls": no_ctrl,
                "conditions": {"database": lit["database"], "accessed": lit["accessed"], "window": lit["window"], "searchTerms": lit["searchTerms"]},
                "evidence": [{"label": "SI Section S4 and Figure S6", "source": PUB_DOI[4:], "locator": "SI Section S4",
                              "values": {"publications": lit["publications"], "before": lit["beforeTmedaMethod"], "after": lit["afterTmedaMethod"], "tmeda": lit["usedTmedaInhibition"]}}]}
    f_hot = {"id": "tests-above-60",
             "question": "How many published uses of the TMEDA inhibition test were run above 60 °C, where this study shows the test gives false negatives?",
             "target": {"label": TEST_LABEL, "type": "assay", "identifier": TEST_ID},
             "outcomeClass": "positive", "informativeness": "not-applicable",
             "effect": {"metric": "TMEDA inhibition tests run above 60 °C", "value": lit["tmedaAbove60C"]["publications"], "n": lit["usedTmedaInhibition"]["publications"], "unit": "publications", "direction": "not-applicable",
                        "note": f"{lit['tmedaAbove60C']['percentOfTmeda']} %; a further {lit['tmedaOnCarbonyls']['publications']} ({lit['tmedaOnCarbonyls']['percentOfTmeda']} %) applied the test to carbonyl substrates, which are not compatible with it"},
             "controls": no_ctrl,
             "conditions": {"temperatureLimitC": limit},
             "evidence": [{"label": "SI Section S4", "source": PUB_DOI[4:], "locator": "SI Section S4",
                           "values": {"above60": lit["tmedaAbove60C"], "carbonyls": lit["tmedaOnCarbonyls"]}}],
             "relatedFindings": ["acs-tmeda-adduct-kinetics#tmeda-test-false-negative-above-60"],
             "note": "These are the published negatives the kinetics invalidate as evidence of true catalysis. The SI gives references 9 to 27 as examples of papers using the test but does not say which of them ran it hot, so they are attached as references here, not as per-paper refutations."}
    for f in (f_uptake, f_hot):
        apply_informativeness(f)
    stage_lit = {"stage": "literature-search", "label": "all catalysed hydroboration publications with HBpin, January 2010 to September 2024",
                 "performedBy": people,
                 "sourcesSearched": [{"name": lit["database"], "platform": "CAS SciFinder-n", "kind": "abstracting database", "coverage": lit["window"], "url": "https://scifinder-n.cas.org/"}],
                 "queries": [{"text": ", ".join(lit["searchTerms"]), "date": lit["accessed"], "recordsFound": lit["publications"], "verbatim": True}],
                 "recordsFound": lit["publications"], "method": "spreadsheet classification of each publication by whether and how it tested for hidden boron catalysis",
                 "note": lit["source"]}
    attempt("acs-tmeda-literature-survey",
            "Of 633 catalysed HBpin hydroboration papers since 2010, 24 used TMEDA inhibition and 15 of those ran it above 60 °C",
            "How widely is the TMEDA inhibition test used, and how often above the temperature at which it is now shown to fail?",
            "A count of publications using the test, split by whether the test temperature exceeded 60 °C.",
            "positive", [f_uptake, f_hot], [stage_lit], "evidence-synthesis",
            outcomeSummary=f"{lit['publications']} publications; {lit['beforeTmedaMethod']['percent']} % tested for hidden catalysis before May 2020 and {lit['afterTmedaMethod']['percent']} % after; {lit['usedTmedaInhibition']['publications']} used TMEDA inhibition, {lit['tmedaAbove60C']['publications']} of them above 60 °C and {lit['tmedaOnCarbonyls']['publications']} on carbonyl substrates.",
            confidence={"level": "medium", "basis": "single-database search with stated terms; classification by the authors; the per-paper spreadsheet is not deposited"},
            sources=example_refs,
            screenedSummary={"publications": lit["publications"], "beforeMay2020": lit["beforeTmedaMethod"]["publications"], "afterMay2020": lit["afterTmedaMethod"]["publications"],
                             "testedBefore": lit["beforeTmedaMethod"]["testedForHiddenCatalysis"], "testedAfter": lit["afterTmedaMethod"]["testedForHiddenCatalysis"],
                             "usedTmedaInhibition": lit["usedTmedaInhibition"]["publications"], "tmedaAbove60C": lit["tmedaAbove60C"]["publications"], "tmedaOnCarbonyls": lit["tmedaOnCarbonyls"]["publications"],
                             "exampleReferencesListed": len(si_refs)},
            cost={"papersProcessed": lit["publications"], "note": "manual classification; effort not reported", "source": "SI Section S4"},
            provenanceNotes=[lit["exampleReferences"] + " The ingest therefore does not assert per paper that its negative was invalidated; the count of 15 is the authors' aggregate.",
                             "The per-paper spreadsheet behind Figure S6 is not deposited."])

    path["hasPart"] = [a["@id"] for a in attempts]
    check_valid(path)
    return [path] + attempts
