"""Converter for Caddell et al. 2026, 'Evaluation of Alcalase pretreatment for Chlamydomonas reinhardtii
CRISPR knock-in' (The Stacks, doi:10.57844/arcadia-pdu7-q2zz) and its Zenodo deposit."""
from __future__ import annotations

import csv
from pathlib import Path

from nrr.ingest.common import (
    check_valid, data_pointer, entity, finalize, new_record, performer, read_csv, read_json, read_yaml, source,
)
from nrr.rules import apply_informativeness

STUDY = "arcadia-alcalase"
PUB_DOI = "doi:10.57844/arcadia-pdu7-q2zz"
DATA_DOI = "doi:10.5281/zenodo.22238548"


# ---- parsers ------------------------------------------------------------------------------

def parse_wall_permeability(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.reader(f):
            if len(r) < 7 or r[0] == "Tube ID" or not r[1].strip():  # header rows and blank separator rows
                continue
            rows.append({
                "tube": r[0], "culture": r[1], "treatment": r[2], "triton": r[3] == "plus",
                "od1": float(r[4]), "od2": float(r[5]), "efficiency_percent": float(r[6].rstrip("%")),
            })
    return rows


def parse_colony_index(path: Path) -> dict:
    rows = read_csv(path)
    seq = [r for r in rows if r["Amplicon Sequencing Result"].strip()]
    edited = [r for r in seq if "no edit detected" not in r["Amplicon Sequencing Result"] and "WT sequence" not in r["Amplicon Sequencing Result"]]
    return {
        "colonies": len(rows),
        "sequenced": len(seq),
        "edited": len(edited),
        "pcr_band_yes": sum(1 for r in rows if r["ColonyPCR_band"].strip() == "y"),
        "pcr_band_no": sum(1 for r in rows if r["ColonyPCR_band"].strip() == "n"),
        "pcr_na": sum(1 for r in rows if r["ColonyPCR_band"].strip() == "na"),
        "by_treatment": _count(rows, "Treatment"),
        "by_guide": _count(rows, "Guide RNA"),
        "by_morphology": _count(rows, "Morphology"),
        "regreened": sum(1 for r in rows if r.get("Green culture in 96_deepwell (TAP) at 2 weeks (5/11/26)", "").strip() == "Y"),
    }


def _count(rows, key):
    out: dict[str, int] = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return dict(sorted(out.items()))


def rule_of_three(n: int) -> float:
    """Upper 95% bound (percent) on a rate when 0 events are seen in n trials."""
    return 300.0 / n


# ---- record construction ----------------------------------------------------------------

def build_alcalase_records(root: Path, resolver) -> list[dict]:
    cur = root / "curated" / "alcalase"
    raw = root / "raw" / "alcalase"
    facts = read_yaml(cur / "pub_facts.yaml")
    text = read_yaml(cur / "text_facts.yaml")
    guides = read_csv(cur / "guides.csv")
    counts = read_csv(cur / "colony_counts.csv")
    geno = read_csv(cur / "genotyping_summary.csv")
    zen = read_json(raw / "zenodo" / "record_22238548.json")
    wall = parse_wall_permeability(raw / "zenodo" / "wall_permeability_data.csv")
    idx = parse_colony_index(raw / "zenodo" / "Chlamydomonas_CRISPR-HDR_plate_colony_image_index.csv")

    pub = facts["publication"]
    operator = {"name": facts["operator"]["name"], "identifier": facts["operator"]["ror"], "type": "Organization"}

    zen_files = [data_pointer(f["key"], repository="Zenodo", accession="10.5281/zenodo.22238548", url=f["links"]["self"],
                              checksum=f["checksum"], size=f["size"], role="raw-data") for f in zen["files"]]
    sources_common = [
        source("source-publication", PUB_DOI, resolver, label=pub["title"], url=pub["url"], license=pub["license"]),
        source("data-deposit", DATA_DOI, resolver, label=zen["metadata"]["title"], license="CC BY 4.0", data=zen_files),
    ]
    prior_art = [source(r["role"] if r["role"] in ("prior-art", "protocol") else "reference", f"doi:{r['doi']}", resolver, label=r["cite"])
                 for r in facts["references"] if r.get("doi")]

    org = facts["organism"]
    ent_common = [
        entity(org["taxon"], "organism", org["species"], scheme="NCBI Taxonomy"),
        entity("chlamycollection:CC-124", "strain", "CC-124 wild type", scheme=org["strainSource"], role="host strain"),
        entity("ror:052zd4v68", "organization", "Arcadia Science", url=facts["operator"]["ror"]),
    ]
    for g in guides:
        ent_common.append(entity(f"phytozome:{g['locus_id']}", "locus", f"{g['gene']} ({g['alias']})", scheme="Phytozome C. reinhardtii v5.6",
                                 role="CRISPR target", extra={"guide": g["guide"], "protospacer": g["protospacer"], "pam": g["pam"], "azimuth": g["azimuth_score"]}))
    for rg in facts["reagents"]:
        ent_common.append(entity(f"catalog:{rg['vendor']}:{rg['catalog']}" if rg.get("catalog") else f"reagent:{rg['label']}", "reagent", rg["label"],
                                 role=rg["role"], extra={"vendor": rg.get("vendor")}))
    nat = resolver.compound("nourseothricin")
    if nat and nat.get("identifier"):
        ent_common.append(entity(nat["identifier"], "compound", "nourseothricin (NAT)", role="selection antibiotic", scheme="PubChem"))
    for sw in facts["software"]:
        ent_common.append(entity(sw.get("rrid") or f"software:{sw['name']}", "software", sw["name"], extra={"version": sw.get("version")}))

    people = [performer(c["name"], "person", role, affiliation="Arcadia Science", identifier=(f"https://orcid.org/{c['orcid']}" if c.get("orcid") else None))
              for c in facts["contributors"] for role in c["roles"]]
    ai_tools = [performer(t["name"], "llm", "copy-editing" if "copy" in t["purpose"] or "wording" in t["purpose"] else "review" if "review" in t["purpose"] else "literature-search" if "literature" in t["purpose"] else "figure-generation",
                          provider=t.get("provider"), version=t.get("version"), note=t["purpose"]) for t in facts["aiUse"]["tools"]]

    applicability = {
        "organism": org["taxon"], "strain": org["strain"], "cellWall": "intact (cell-walled strain)",
        "synchronization": facts["protocol"]["synchronization"],
        "cultureFormats": ["flask (liquid TAP, mid-log)", "plate (TAP agar lawn)"],
        "alcalase": facts["protocol"]["alcalase"], "comparator": facts["protocol"]["geneart"],
        "delivery": facts["protocol"]["electroporation"], "cargo": facts["protocol"]["rnp"] + "; " + facts["protocol"]["donor"],
        "selection": facts["protocol"]["selection"], "loci": [g["locus_id"] for g in guides],
        "replicates": "n = 1 per condition; one experimenter; one batch of each key reagent",
        "dates": {"transformation": facts["timeline"]["transformationImageDate"], "genotyping": facts["timeline"]["colonyPcrDate"]},
    }
    common = dict(operator=operator, pathType="experiment", sourceLicense="CC BY 4.0",
                  aiUseDeclaration={"statement": facts["aiUse"]["statement"], "tools": [{"name": t["name"], "provider": t["provider"], "version": t["version"], "purpose": t["purpose"]} for t in facts["aiUse"]["tools"]]})
    base_cost = {"wallClockDays": facts["timeline"]["workflowDays"], "humanExperimenters": 1, "wetLabRuns": 1,
                 "note": "single unreplicated experiment; USD not reported", "source": facts["timeline"]["workflowDaysSource"]}

    # ---- path -------------------------------------------------------------------------
    path = new_record("path", STUDY, "arcadia-alcalase-path",
                      "Alcalase pretreatment for CRISPR-Cas9 HDR knock-in in cell-walled Chlamydomonas reinhardtii (iced project)",
                      question="Can Alcalase, an off-the-shelf serine endopeptidase, replace in-house autolysin to permeabilise the C. reinhardtii cell wall for Cas9 RNP plus HDR-donor electroporation and yield targeted knock-ins?",
                      hypothesis=facts["purpose"],
                      successCriteria="NAT-resistant colonies well above the no-donor background after Alcalase pretreatment, and on-target HDR insertion (~2 kb amplicon or sequence-confirmed edit) detectable among them at a rate usable for high-throughput screens.",
                      outcomeClass="abandoned",
                      outcomeSummary="Alcalase digested walls but killed most cells before electroporation, gave near-background NAT resistance, and neither reagent yielded any on-target editing among 191 colonies screened; the project was iced (#TechnicalGap, #StrategicMisalignment).",
                      confidence={"level": "medium", "basis": "one attempt, one reagent batch, one experimenter; authors state Alcalase is not ruled out under gentler conditions"},
                      abandonmentReasons=facts["icebox"]["reasons"],
                      nextSteps=facts["nextSteps"],
                      untriedBranches=[{"description": s, "status": "proposed-by-authors", "source": "Next steps"} for s in facts["nextSteps"]],
                      openQuestions=facts["openQuestions"],
                      invalidators=["a milder Alcalase regime (lower dose, shorter time, osmotic support) that preserves viability",
                                    "a positive editing control showing the guides, donor and selection work in a known-working delivery system",
                                    "replication with independent reagent batches and experimenters"],
                      applicabilityConditions=applicability,
                      cost=base_cost,
                      sources=sources_common + prior_art,
                      performers=people + ai_tools,
                      entities=ent_common,
                      provenanceNotes=[
                          "Encoded from the published text, tables and the Zenodo CSVs; imaging and gel raw files are pointed to, not parsed.",
                          f"Icebox statement: {facts['icebox']['statement']}",
                          f"Authors' caveat: {facts['caveats']}",
                      ],
                      governance={"humanSubjectData": "none", "biosecurityTier": "none (model alga, no select agents)"},
                      hasPart=[],
                      **common)
    finalize(path, check=False)
    pid = path["@id"]

    attempts: list[dict] = []

    def attempt(slug, title, question, success, outcome, findings, extra_entities=(), stages=None, **kw):
        relations = [{"type": "isPartOf", "target": pid}] + kw.pop("relations", [])
        rec = new_record("attempt", STUDY, slug, title, attemptType="wet-lab", question=question, successCriteria=success,
                         outcomeClass=outcome, findings=findings, applicabilityConditions=applicability, cost=base_cost,
                         sources=sources_common, isPartOf=pid, entities=ent_common + list(extra_entities),
                         performers=[p for p in people if p["role"] in ("investigation", "formal-analysis", "experimental-design")],
                         stages=stages or [], relations=relations, **common, **kw)
        attempts.append(finalize(rec))
        return rec

    vehicle_ctrl = {"kind": "no-treatment", "label": "M-N medium, no enzyme (same wash procedure)", "observed": "6-7% pigment leakage", "passed": True,
                    "source": "Table (wall_permeability_data.csv); Figure 3"}

    # ---- 1. wall permeability -----------------------------------------------------
    leak = {(r["culture"], r["treatment"]): r["efficiency_percent"] for r in wall if r["triton"]}
    f_leak = [{
        "id": f"leak-{trt.lower()}-{cul}",
        "question": f"Does {trt} treatment permeabilise the cell wall of {cul}-grown CC-124 cells (detergent-induced pigment leakage)?",
        "target": {"label": f"{trt} pretreatment ({cul} culture)", "type": "reagent"},
        # The authors' claim is about Alcalase; GeneArt (non-enzymatic) is the comparator and is recorded as partial.
        "outcomeClass": "positive" if trt == "Alcalase" else "partial",
        "informativeness": "not-applicable",
        "effect": {"metric": "OD662 released after Triton X-100 / OD662 before, percent", "value": leak[(cul, trt)], "unit": "%", "n": 1,
                   "direction": "increase", "comparedTo": f"M-N no-enzyme control {leak[(cul, 'M-N')]}%", "note": "n = 1 (same culture used for transformations)"},
        "controls": {"positive": {"kind": "none", "note": "no reference wall-less strain was run"}, "negative": vehicle_ctrl},
        "replicates": {"biological": 1, "note": "single measurement per condition"},
        "evidence": [{"label": "wall_permeability_data.csv (Zenodo)", "source": "10.5281/zenodo.22238548", "locator": "wall_permeability_data.csv",
                      "values": {"od1": next(r["od1"] for r in wall if r["culture"] == cul and r["treatment"] == trt and r["triton"]),
                                 "od2": next(r["od2"] for r in wall if r["culture"] == cul and r["treatment"] == trt and r["triton"]),
                                 "efficiencyPercent": leak[(cul, trt)]}},
                     {"label": "Results, 'Alcalase reduced viability and NAT resistance'", "source": PUB_DOI[4:], "locator": "Figure 3",
                      "quote": "Pigmentation release was approximately 22% for Alcalase, 11% for GeneArt washing, and 6% for the M−N control"}],
        "conditions": {"treatment": facts["protocol"]["alcalase"] if trt == "Alcalase" else facts["protocol"]["geneart"], "culture": cul},
    } for cul in ("flask", "plate") for trt in ("Alcalase", "GeneArt")]
    for f in f_leak:
        apply_informativeness(f)
    attempt("arcadia-alcalase-wall-permeability",
            "Alcalase increases C. reinhardtii cell-wall permeability (OD-based leakage assay)",
            "Does a 1 h Alcalase (1:10) treatment permeabilise the cell wall of synchronised CC-124 cells more than GeneArt washing or no enzyme?",
            "Pigment leakage after Triton X-100 clearly above the no-enzyme control.",
            "positive", f_leak,
            stages=[{"stage": "experiment", "label": "cell wall leakage assay", "performedBy": [people[1]], "method": facts["protocol"]["leakageAssay"],
                     "instrument": ["NanoDrop OneC spectrophotometer"], "outputs": [zen_files[-1]]}],
            outcomeSummary="Alcalase 22-23% leakage vs GeneArt 11% vs no enzyme 6-7% (n = 1 each).",
            confidence={"level": "low", "basis": "single measurement per condition"})

    # ---- 2. viability -------------------------------------------------------------
    def cnt(trt, cul, guide, ep, medium):
        r = next(r for r in counts if r["treatment"] == trt and r["culture"] == cul and r["guide"] == guide and r["electroporation"] == ep and r["medium"] == medium)
        return r["colonies"]
    surv = text["viability"]["electroporationSurvival"]
    f_via = []
    for cul in ("flask", "plate"):
        alc = int(cnt("Alcalase", cul, "none", "no", "TAP")); ga = cnt("GeneArt", cul, "none", "no", "TAP")
        f_via.append({
            "id": f"viability-{cul}",
            "question": f"Do {cul}-grown CC-124 cells survive Alcalase pretreatment (1:10, 1 h) as well as GeneArt washing?",
            "target": {"label": f"Alcalase pretreatment ({cul} culture)", "type": "reagent"},
            "outcomeClass": "negative-not-achievable", "informativeness": "informative",
            "failureModes": ["toxicity"],
            "effect": {"metric": "colonies on TAP (100x dilution, no electroporation)", "value": alc, "n": 1, "direction": "decrease",
                       "comparedTo": f"GeneArt: {ga} (> ~1,200 colonies, counting ceiling)", "note": ">= 10-fold fewer colonies; equal starting cell numbers by OD750"},
            "controls": {"positive": {"kind": "internal-positive", "label": "GeneArt-washed cells (same culture)", "expected": "dense growth", "observed": "too many to count (> ~1,200)", "passed": True},
                         "negative": {"kind": "no-treatment", "label": "M-N no-enzyme control", "observed": "not plated for counting (leakage assay only)", "passed": True, "note": "viability baseline is the GeneArt arm, which retained dense growth"}},
            "sensitivity": "colony-count assay resolves at least a 10-fold difference (35-68 colonies vs > 1,200); n = 1 per condition",
            "replicates": {"biological": 1},
            "evidence": [{"label": "Table 4 (control plates, no RNP/no donor, non-electroporated)", "source": PUB_DOI[4:], "locator": "Table 4; Figure 4",
                          "values": {"alcalase": alc, "geneart": ga}, "data": [d for d in zen_files if d["label"].startswith("colony counting")]}],
            "conditions": {"culture": cul, "electroporationSurvivalPercent": surv[f"{cul}_percent"], "electroporationSurvivalMethod": surv["method"]},
        })
    for f in f_via:
        apply_informativeness(f)
    attempt("arcadia-alcalase-viability",
            "Alcalase pretreatment (1:10, 1 h) cuts CC-124 viability at least ten-fold independent of electroporation",
            "Is Alcalase pretreatment under these conditions tolerated by cell-walled CC-124 cells?",
            "Colony yield on TAP comparable to GeneArt-washed cells from the same starting density.",
            "negative-not-achievable", f_via,
            stages=[{"stage": "experiment", "label": "viability by colony counting", "performedBy": [people[1]], "method": facts["protocol"]["colonyCounting"],
                     "instrument": ["Epson V700 flatbed scanner"], "software": [{"name": "Fiji", "version": "2.16.0/1.54p", "identifier": "RRID:SCR_002285"}]}],
            outcomeSummary="35 (flask) and 68 (plate) colonies after Alcalase vs > 1,200 after GeneArt; Alcalase survivors tolerated electroporation at 69% (flask) vs 38% (plate).",
            invalidators=["lower Alcalase dose or shorter digestion with osmotic support that restores colony yield"],
            confidence={"level": "medium", "basis": "large effect (>= 10-fold) but n = 1 and one reagent batch"})

    # ---- 3. transformation (NAT resistance) ----------------------------------------
    bg = text["transformation"]["background"]
    f_tr = []
    for trt in ("Alcalase", "GeneArt"):
        per_guide = {g["guide"]: {cul: int(cnt(trt, cul, g["guide"], "yes", "TAP+NAT")) for cul in ("flask", "plate")} for g in guides}
        vals = [v for d in per_guide.values() for v in d.values()]
        bgv = bg["alcalase" if trt == "Alcalase" else "geneart"]
        above = sum(1 for g in per_guide.values() for cul, v in g.items() if v > 2 * max(bgv))
        neg = trt == "Alcalase"
        f = {
            "id": f"natr-{trt.lower()}",
            "question": f"Does electroporation of Cas9 RNP plus linear NAT HDR donor into {trt}-treated CC-124 cells yield NAT-resistant colonies above the no-donor background?",
            "target": {"label": f"{trt} pretreatment + electroporation (RNP + NAT donor)", "type": "reagent"},
            "outcomeClass": "negative-not-achievable" if neg else "positive",
            "informativeness": "informative",
            "failureModes": ["transformation-failed", "toxicity"] if neg else [],
            "effect": {"metric": "NAT-resistant colonies per plate (TAP + 7.5 ug/mL NAT), 8 guide x culture conditions", "value": f"{min(vals)}-{max(vals)}", "n": 8,
                       "direction": "none" if neg else "increase", "comparedTo": f"no-RNP/no-donor background {bgv} (flask, plate)",
                       "perReplicate": vals, "note": f"{above} of 8 conditions above twice the background"},
            "controls": {"positive": {"kind": "internal-positive", "label": "GeneArt-treated cells, same RNP and donor", "expected": "many NAT-resistant colonies", "observed": "121-1,094 per plate", "passed": True}
                         if neg else {"kind": "none", "note": "no independently validated transformation positive control; GeneArt is the reference arm"},
                         "negative": {"kind": "background", "label": "no RNP, no donor, electroporated, plated on TAP + NAT", "observed": f"{bgv[0]} and {bgv[1]} colonies", "passed": True, "note": "selection escape rare"}},
            "sensitivity": "background of 0-4 colonies per plate; a delivery efficiency giving >= 10 NAT-resistant colonies above background would have been detected",
            "replicates": {"biological": 1, "note": "one plate per guide x culture condition"},
            "evidence": [{"label": "Table 4 (TAP + NAT plates)", "source": PUB_DOI[4:], "locator": "Table 4; Figure 5", "values": {"perGuide": per_guide, "background": bgv},
                          "data": [d for d in zen_files if d["label"].startswith("colony counting")]}],
            "conditions": {"pretreatment": trt, "delivery": facts["protocol"]["electroporation"], "cargo": "4 uL RNP (5 uM) + 1 ug linear donor"},
            "note": text["transformation"]["interpretation"] if neg else "NAT resistance most likely reflects random (NHEJ) donor integration; no on-target events found (see hdr-knockin)",
        }
        apply_informativeness(f)
        f_tr.append(f)
    attempt("arcadia-alcalase-transformation",
            "Alcalase-treated CC-124 cells yield near-background NAT-resistant colonies after Cas9 RNP + donor electroporation; GeneArt-treated cells yield hundreds",
            "Can Alcalase pretreatment deliver Cas9 RNP and a linear NAT donor into cell-walled CC-124 at a frequency that yields NAT-resistant colonies?",
            "NAT-resistant colony counts well above the no-donor background in most guide x culture conditions.",
            "negative-not-achievable", f_tr,
            stages=[{"stage": "experiment", "label": "RNP + donor electroporation and NAT selection", "performedBy": [people[1]], "method": facts["protocol"]["electroporation"] + "; " + facts["protocol"]["selection"],
                     "instrument": ["Gene Pulser Xcell electroporator (Bio-Rad)"], "conditions": {"rnp": facts["protocol"]["rnp"], "donor": facts["protocol"]["donor"]}}],
            outcomeSummary=text["transformation"]["alcalase_cfu_range"] + "; " + text["transformation"]["alcalase_at_background"] + "; GeneArt " + text["transformation"]["geneart_cfu_range"],
            invalidators=["a donor-only, no-RNP control to quantify random integration", "Alcalase conditions that preserve viability (see viability record)"],
            confidence={"level": "medium", "basis": "consistent across 8 conditions and both culture formats, but n = 1 each"},
            relations=[{"type": "wasDerivedFrom", "target": attempts[1]["@id"], "note": "viability loss precedes and confounds delivery"}])

    # ---- 4. HDR knock-in ------------------------------------------------------------
    tot = next(g for g in geno if g["colony_morphology"] == "total")
    f_hdr = [{
        "id": "hdr-ontarget",
        "question": "Among NAT-resistant colonies from either pretreatment, did Cas9 RNP plus a 50 bp-homology-arm linear donor produce on-target HDR insertion or indels at CpSRP43, CpSRP54 or SRTA exon 1?",
        "target": {"label": "on-target HDR knock-in at Cre04.g231026 / Cre11.g479750 / Cre10.g462200", "type": "process"},
        "outcomeClass": "inconclusive-no-positive-control", "informativeness": "uninformative",
        "failureModes": ["low-editing-efficiency"],
        "effect": {"metric": "colonies with ~2 kb HDR amplicon or sequence-confirmed edit", "value": 0, "n": int(tot["pcr_screened"]), "direction": "none",
                   "comparedTo": "wild-type ~0.5 kb amplicon", "note": f"{tot['pcr_positive']}/{tot['pcr_screened']} wild-type-size amplicons, rest no band; 0/{tot['amplicon_sequenced']} edits by Nanopore amplicon sequencing (10 per guide)"},
        "controls": {"positive": {"kind": "none", "note": "no guide/donor/selection combination previously shown to edit in this delivery system; authors list restoring such a control as a next step"},
                     "negative": {"kind": "background", "label": "no RNP, no donor", "observed": "0-4 NAT-resistant colonies", "passed": True}},
        "sensitivity": f"0 of {tot['amplicon_sequenced']} sequenced colonies edited: an on-target rate above {rule_of_three(int(tot['amplicon_sequenced'])):.1f}% among NAT-resistant colonies would have been detected with 95% probability (rule of three, derived by portolan-ingest); PCR screen of {tot['pcr_screened']} colonies bounds the ~2 kb insert rate below {rule_of_three(int(tot['pcr_screened'])):.1f}%",
        "replicates": {"biological": 1, "note": "201 colonies picked, 10 excluded for evaporation"},
        "evidence": [{"label": "Table 5", "source": PUB_DOI[4:], "locator": "Table 5", "values": {r["colony_morphology"]: {"pcrPositive": int(r["pcr_positive"]), "screened": int(r["pcr_screened"]), "sequenced": int(r["amplicon_sequenced"])} for r in geno}},
                     {"label": "Per-colony index (Zenodo)", "source": "10.5281/zenodo.22238548", "locator": "Chlamydomonas_CRISPR-HDR_plate_colony_image_index.csv",
                      "values": {"rows": idx["colonies"], "pcrBandYes": idx["pcr_band_yes"], "sequenced": idx["sequenced"], "editsDetected": idx["edited"], "byTreatment": idx["by_treatment"], "byGuide": idx["by_guide"]},
                      "derivedBy": "portolan-ingest", "method": "row counts over the index CSV",
                      "data": [d for d in zen_files if d["label"] in ("Chlamydomonas_CRISPR-HDR_plate_colony_image_index.csv", "amplicon sequencing results.zip", "colony PCR gel images.zip", "HDR donor plasmid maps.zip")]}],
        "conditions": {"guides": [g["guide"] for g in guides], "homologyArms": "50 bp", "donor": "1,589 bp linear NAT cassette", "genotyping": facts["protocol"]["colonyPcr"], "sequencing": facts["protocol"]["ampliconSequencing"]},
        "note": text["genotyping"]["interpretation"],
    }]
    for f in f_hdr:
        apply_informativeness(f)
    attempt("arcadia-alcalase-hdr-knockin",
            "No on-target HDR insertion or indels detected at three loci among 191 NAT-resistant colonies (0/40 sequenced), under either pretreatment",
            "Does Cas9 RNP plus a 50 bp-arm linear donor produce on-target knock-in in cell-walled CC-124 after Alcalase or GeneArt pretreatment?",
            "A ~2 kb amplicon or a sequence-confirmed edit at the target locus in at least one NAT-resistant colony.",
            "inconclusive-no-positive-control", f_hdr,
            stages=[{"stage": "genotyping", "label": "colony PCR and amplicon sequencing", "performedBy": [people[1], performer("Angstrom Innovation", "service", "sequencing-service", note="Oxford Nanopore amplicon sequencing")],
                     "method": facts["protocol"]["colonyPcr"], "software": [{"name": "Geneious Prime", "version": "2026.0.2", "identifier": "RRID:SCR_010519"}]}],
            outcomeSummary="0 of 191 colonies by PCR and 0 of 40 by sequencing showed on-target editing; delivery failure cannot be separated from editing or repair failure.",
            invalidators=["a positive editing control (validated guide, donor and selection)", "a donor-only, no-RNP control", "co-targeting an endogenous selectable marker to enrich edited cells"],
            confidence={"level": "medium", "basis": "clean genotyping of 191 colonies, but no positive control for editing; authors call it a practical caution, not an evaluation of any component"})

    # ---- 5. visual screen -----------------------------------------------------------
    vs = text["visualScreen"]
    f_vs = [{
        "id": "visual-screen",
        "question": "Can pale-green colony colour serve as a visual proxy for CpSRP43/CpSRP54 (TLA) knockouts among NAT-resistant colonies?",
        "target": {"label": "colony colour as TLA-knockout readout", "type": "assay"},
        "outcomeClass": "negative-not-achievable", "informativeness": "informative",
        "failureModes": ["phenotype-nonspecific", "selection-escape"],
        "effect": {"metric": "white colonies regaining green pigmentation off selection", "value": vs["reversion"]["percent"], "unit": "%", "n": vs["reversion"]["whiteColoniesTransferred"],
                   "direction": "not-applicable", "note": f"{vs['reversion']['regainedGreen']}/{vs['reversion']['whiteColoniesTransferred']}; medium colonies {vs['reversion']['mediumPercent']}% vs small {vs['reversion']['smallPercent']}%"},
        "controls": {"positive": {"kind": "internal-positive", "label": "SRTA-targeting transformations (no TLA phenotype expected)", "expected": "green colonies only", "observed": "same range of pale-green and white colonies as TLA-targeting plates", "passed": True,
                                  "note": "the comparison that shows the readout is not target-specific"},
                     "negative": {"kind": "no-treatment", "label": "colonies transferred to selection-free TAP", "observed": "33% of white colonies re-greened", "passed": True}},
        "sensitivity": "96 white colonies followed; phenotype categories large/medium/small and green/pale-green/white scored by eye and scanner",
        "evidence": [{"label": "Results, 'Colony phenotype was too variable to screen for TLA knockouts'", "source": PUB_DOI[4:], "locator": "Figure 6", "values": vs["reversion"],
                      "data": [d for d in zen_files if d["label"] in ("deepwell plates.zip", "colony selection.zip")]}],
        "note": vs["interpretation"],
    }]
    for f in f_vs:
        apply_informativeness(f)
    attempt("arcadia-alcalase-visual-screen",
            "Colony colour cannot serve as a visual screen for TLA knockouts under NAT selection",
            "Is the pale-green TLA phenotype usable as a first-pass visual readout of editing efficiency?",
            "Pale-green colonies confined to TLA-targeting transformations.",
            "negative-not-achievable", f_vs,
            outcomeSummary="Pale-green and white colonies appeared on all plates regardless of target; a third of white colonies re-greened off selection.",
            confidence={"level": "medium", "basis": "consistent across all conditions but confounded by selection and transformation stress"})

    # ---- 6. culture format ----------------------------------------------------------
    f_cf = [{
        "id": "culture-format",
        "question": "Do flask-grown (liquid, mid-log) and plate-grown (agar lawn) synchronised cultures differ in suitability for Alcalase/GeneArt pretreatment and knock-in?",
        "target": {"label": "flask vs plate starting culture", "type": "other"},
        "outcomeClass": "inconclusive", "informativeness": "uninformative",
        "effect": {"metric": "electroporation survival, Alcalase-treated (electroporated/non-electroporated colony ratio)", "value": f"{surv['flask_percent']}% vs {surv['plate_percent']}%", "n": 1,
                   "direction": "not-applicable", "note": "both formats gave NAT-resistant colonies with GeneArt; no on-target events under either"},
        "controls": {"positive": {"kind": "none", "note": "no knock-in positive control, so the formats cannot be compared on the primary endpoint"},
                     "negative": {"kind": "background", "label": "no RNP, no donor", "observed": "0-4 colonies", "passed": True}},
        "evidence": [{"label": "Table 4; Key takeaways", "source": PUB_DOI[4:], "locator": "Table 4", "values": {"alcalaseSurvival": surv, "geneartNatPerGuide": {g["guide"]: {cul: int(cnt("GeneArt", cul, g["guide"], "yes", "TAP+NAT")) for cul in ("flask", "plate")} for g in guides}}}],
        "note": text["cultureFormat"]["interpretation"],
    }]
    for f in f_cf:
        apply_informativeness(f)
    attempt("arcadia-alcalase-culture-format",
            "Flask- versus plate-grown starting cultures: no conclusion for knock-in; Alcalase survivors from flask tolerated electroporation better",
            "Does the starting culture format (flask vs plate) change wall permeabilisation, viability or knock-in outcome?",
            "A consistent difference in NAT-resistant or edited colonies between formats.",
            "inconclusive", f_cf,
            outcomeSummary=text["cultureFormat"]["interpretation"],
            confidence={"level": "low", "basis": "secondary variable; primary endpoint had no events"})

    path["hasPart"] = [a["@id"] for a in attempts]
    check_valid(path)
    return [path] + attempts
