"""Converter for Cheveralls et al. 2026, 'Leave-one-batch-out cross-validation reveals strong batch effects
in Raman spectroscopy of yeast cultures' (The Stacks, doi:10.57844/arcadia-xdmk-yq0w).

This study is in the corpus because its controls are not reagents. The positive control is a different
prediction task on the same spectra and pipeline that is known to carry signal (species rather than strain).
The negative control is adversarial: a classifier trained to predict which plate a spectrum came from, a label
that should be unpredictable because the plates are end-to-end replicates. Both controls are computational,
and the same data and model produce a strong result or a weak one depending only on the validation scheme.
"""
from __future__ import annotations

from pathlib import Path

from nrr.ingest.common import (
    check_valid, data_pointer, entity, finalize, new_record, performer, read_csv, read_json, read_yaml, source,
)
from nrr.rules import apply_informativeness

STUDY = "arcadia-raman"
PUB_DOI = "doi:10.57844/arcadia-xdmk-yq0w"
CODE_DOI = "doi:10.5281/zenodo.19226627"


def parse_strains(path: Path) -> list[dict]:
    return read_csv(path)


def parse_results(path: Path) -> dict[tuple[str, str, str], dict]:
    """Model performance keyed by (task, cross-validation strategy, dataset)."""
    out = {}
    for r in read_csv(path):
        r["mcc_median"] = float(r["mcc_median"])
        r["mcc_min"] = float(r["mcc_min"]) if r["mcc_min"] else None
        r["mcc_max"] = float(r["mcc_max"]) if r["mcc_max"] else None
        out[(r["task"], r["cv_strategy"], r["dataset"])] = r
    return out


def build_raman_records(root: Path, resolver) -> list[dict]:
    cur = root / "curated" / "raman"
    raw = root / "raman" if False else root / "raw" / "raman"
    facts = read_yaml(cur / "pub_facts.yaml")
    strains = parse_strains(cur / "strains.csv")
    results = parse_results(cur / "results.csv")
    zen = read_json(raw / "zenodo" / "record_19226627.json")

    pub, design, an, res = facts["publication"], facts["design"], facts["analysis"], facts["results"]
    spec, proc, bc, leak = facts["spectroscopy"], facts["processing"], facts["batchCorrection"], facts["leakageCaveat"]
    operator = {"name": facts["operator"]["name"], "identifier": facts["operator"]["ror"], "type": "Organization"}

    code_files = [data_pointer(f["key"], repository="Zenodo", accession="10.5281/zenodo.19226627",
                               url=f["links"]["self"], checksum=f["checksum"], size=f["size"],
                               role="code and processed spectra archive") for f in zen["files"]]
    sources_common = [
        source("source-publication", PUB_DOI, resolver, label=pub["title"], url=pub["url"], license=pub["license"]),
        source("code-repository", CODE_DOI, resolver, label=zen["metadata"]["title"], url=pub["codeRepo"],
               license=pub["codeLicense"], note=f"version {pub['codeVersion']}; {pub['licenceNote']}", data=code_files),
    ]
    prior = [source("prior-art", f"doi:{d}", resolver, label=k)
             for k, d in facts["priorArt"].items()]
    related = [source("reference", f"doi:{p['doi']}", resolver, label=p["relation"], url=f"https://thestacks.org/publications/{p['slug']}")
               for p in facts["relatedArcadiaPubs"]]

    def taxon(name):
        hit = resolver.cache.get(f"taxon:{name}")
        return hit["identifier"] if hit and hit.get("identifier") else None

    sc, sp = taxon("Saccharomyces cerevisiae") or "NCBITaxon:4932", taxon("Schizosaccharomyces pombe") or "NCBITaxon:4896"
    ents = [
        entity(sc, "organism", "Saccharomyces cerevisiae", scheme="NCBI Taxonomy"),
        entity(sp, "organism", "Schizosaccharomyces pombe", scheme="NCBI Taxonomy"),
        entity("ror:052zd4v68", "organization", "Arcadia Science", url=facts["operator"]["ror"]),
        entity("instrument:wasatch-wp-785x", "instrument", spec["instrument"], role="Raman spectrometer",
               extra={"laserPower": spec["laserPower"], "integrationTime": spec["integrationTime"]}),
        entity("assay:spontaneous-raman-spectroscopy", "assay",
               "spontaneous Raman spectroscopy of desiccated cell pellets, 785 nm excitation",
               note="no exact ontology term was resolved for spontaneous Raman spectroscopy of biological samples"),
    ]
    for s in strains:
        ents.append(entity(f"strain:{s['strain_or_gene_id']}", "strain",
                           f"{s['species']} {s['strain_or_gene_id']}" + (f" ({s['genotype']})" if s["genotype"] else ""),
                           scheme=s["source_collection"], role="classification target",
                           extra={k: v for k, v in {"genotype": s["genotype"], "description": s["description"],
                                                    "taxon": s["taxon"], "humanOrtholog": s["human_ortholog"]}.items() if v}))
    for hg, sym in {s["human_ortholog_gene"]: s["human_ortholog"] for s in strains if s["human_ortholog_gene"]}.items():
        ents.append(entity(hg, "gene", f"{sym} (human ortholog of a mutated yeast gene in this panel)", scheme="HGNC"))
    for sw in facts["software"]:
        ents.append(entity(sw.get("rrid") or f"software:{sw['name']}", "software", sw["name"], role=sw["role"]))

    people = [performer(c["name"], "person", role, affiliation="Arcadia Science")
              for c in facts["contributors"] for role in c["roles"]]
    ai_tools = [performer(t["name"], "llm", "software" if "code" in t["purpose"] else "review" if "review" in t["purpose"] else "figure-generation",
                          provider=t["provider"], version=t.get("version"), note=t["purpose"])
                for t in facts["aiUse"]["tools"]]
    analysts = [p for p in people if p["role"] in ("formal-analysis", "software", "methodology")]

    applicability = {
        "organisms": [sc, sp], "strains": [s["strain_or_gene_id"] for s in strains],
        "strainDiversity": "three standard lab strains and six knockout strains within two species; the authors note the strains may be too genetically similar to produce detectable spectral differences",
        "assay": "spontaneous Raman spectroscopy, 785 nm excitation, desiccated wet cell pellets on stainless steel",
        "samplePreparation": facts["culture"]["mounting"],
        "spectraPerStrain": design["spectraPerStrainAfterQc"], "spectraTotal": design["spectraTotalAfterQc"],
        "replicates": design["replicates"], "processing": "; ".join(proc["steps"]),
        "models": an["models"], "metric": an["metric"],
        "note": "conclusions are specific to this sample-preparation protocol; desiccation is inherently variable and likely contributes to the plate-level batch effect",
    }
    common = dict(operator=operator, sourceLicense="CC BY 4.0 (pub); MIT (code and data archive)",
                  aiUseDeclaration={"statement": facts["aiUse"]["statement"],
                                    "tools": [{"name": t["name"], "provider": t["provider"],
                                               **({"version": t["version"]} if t.get("version") else {}),
                                               "purpose": t["purpose"]} for t in facts["aiUse"]["tools"]]})
    base_cost = {"note": f"{design['spectraPerStrainAcquired']} spectra acquired per strain across three plates, {design['spectraTotalAfterQc']} retained after quality control; no monetary or compute cost is reported",
                 "source": "The approach, Experimental design"}

    processing_stage = {
        "stage": "computation", "label": "spectral processing pipeline",
        "performedBy": analysts, "method": "; ".join(proc["steps"]),
        "software": [{"name": "ramanspy"}, {"name": "Python", "identifier": "RRID:SCR_008394"}],
        "inputs": [data_pointer("raw spectra, 5 x 5 grid per well on three plates", note=design["grid"])],
        "note": "the consensus background spectrum is averaged across all three plates deliberately, to avoid injecting per-plate differences as additional batch effects",
    }

    def model_stage(label, method):
        return {"stage": "analysis", "label": label, "performedBy": analysts, "method": method,
                "software": [{"name": "scikit-learn", "identifier": "RRID:SCR_002577"}],
                "parameters": {"models": an["models"], "metric": an["metric"]},
                "outputs": code_files}

    # --- path -----------------------------------------------------------------------------------
    path = new_record(
        "path", STUDY, "arcadia-raman-path",
        "Can Raman spectra distinguish yeast strains and species, and do batch effects confound the answer?",
        question="Can spontaneous Raman spectra be used to classify yeast strain and species identity, and to what extent do experimental batch effects confound such predictions?",
        hypothesis=facts["purpose"],
        successCriteria="Classification accuracy above chance under a cross-validation scheme that holds out whole experimental replicates, with an adversarial control showing that the model is not reading batch identity.",
        pathType="mixed", outcomeClass="partial",
        outcomeSummary="Species identity is recoverable from the spectra (median MCC 0.97 under leave-one-plate-out cross-validation). Strain identity is not: it appears recoverable under standard cross-validation (0.79) but collapses when whole plates are held out (0.32), and an adversarial classifier predicts plate identity almost perfectly, showing that batch effects dominate.",
        confidence={"level": "medium", "basis": "the batch effect is demonstrated directly by an adversarial task and is robust to classifier and batch-correction method; the strain negative rests on 248 spectra across nine closely related strains and is explicitly flagged by the authors as possibly not generalising"},
        nextSteps=facts["recommendations"],
        openQuestions=["How much of the residual strain-level signal loss is stochastic sample-level batch effect and how much is genuine absence of strain-specific Raman signatures?"],
        untriedBranches=[{"description": r, "status": "proposed-by-authors", "source": "Conclusions and recommendations"} for r in facts["recommendations"]]
        + [{"description": "Repeat the strain task on a panel with greater genetic diversity; the authors state the negative result may not generalise to more divergent strains.",
            "status": "proposed-by-authors", "source": "Limitations and caveats"},
           {"description": "Repeat with a sample-preparation protocol that avoids desiccation, which the authors identify as a likely source of the plate-level batch effect.",
            "status": "proposed-by-authors", "source": "Limitations and caveats"}],
        invalidators=["a strain panel with greater genetic diversity in which strain identity survives leave-one-replicate-out cross-validation",
                      "a sample-preparation protocol whose adversarial plate-prediction control is clean without correction",
                      "a batch-correction scheme applied within each training fold, which would make the corrected estimates valid for unseen plates"],
        applicabilityConditions=applicability, cost=base_cost,
        sources=sources_common + prior + related, performers=people + ai_tools, entities=ents,
        governance={"humanSubjectData": "none", "biosecurityTier": "none"},
        provenanceNotes=[
            pub["statusNote"],
            pub["licenceNote"],
            f"Self-declared analysis limitation carried on the corrected findings: {leak['statement']} {leak['consequence']}",
            "Only random-forest numbers are given numerically in the text. Figure 8 reports every combination of model and batch-correction method, and the authors state the medians were not meaningfully different; those combinations are recorded as a robustness finding rather than as separate measured values.",
            facts["aiUse"]["note"],
        ],
        hasPart=[], **common)
    finalize(path, check=False)
    pid = path["@id"]
    attempts: list[dict] = []

    def attempt(slug, title, question, success, outcome, findings, stages, **kw):
        rec = new_record("attempt", STUDY, slug, title, attemptType="computational", pathType="computation", question=question,
                         successCriteria=success, outcomeClass=outcome, findings=findings, stages=stages,
                         applicabilityConditions=applicability, cost=base_cost, sources=sources_common,
                         isPartOf=pid, entities=ents, performers=analysts + ai_tools,
                         relations=[{"type": "isPartOf", "target": pid}] + kw.pop("relations", []), **common, **kw)
        attempts.append(finalize(rec))
        return rec

    def effect(row, note=None):
        e = {"metric": an["metric"], "value": row["mcc_median"],
             "comparedTo": "chance, which is MCC 0 for this metric; perfect prediction is MCC 1",
             "n": 3, "test": "median across cross-validation folds", "direction": "not-applicable"}
        if row["mcc_min"] is not None:
            e["range"] = [row["mcc_min"], row["mcc_max"]]
        if note:
            e["note"] = note
        return e

    def conditions(row):
        return {"task": f"predict {row['task']} identity", "crossValidation": row["cv_strategy"],
                "dataset": row["dataset"], "model": row["model"],
                "spectra": design["spectraTotalAfterQc"], "plates": 3,
                "batchCorrection": bc["lmm"] if row["dataset"] == "lmm-corrected" else "none"}

    def ev(row, label=None):
        return [{"label": label or row["source"], "source": PUB_DOI[4:], "locator": row["source"].split(";")[-1].strip(),
                 "values": {"mccMedian": row["mcc_median"], "mccRange": [row["mcc_min"], row["mcc_max"]] if row["mcc_min"] is not None else None,
                            "task": row["task"], "crossValidation": row["cv_strategy"], "dataset": row["dataset"]},
                 "data": code_files}]

    r_std = results[("strain", "standard-5-fold", "uncorrected")]
    r_lopo = results[("strain", "leave-one-plate-out", "uncorrected")]
    r_lopo_c = results[("strain", "leave-one-plate-out", "lmm-corrected")]
    r_plate = results[("plate", "leave-one-strain-out", "uncorrected")]
    r_plate_c = results[("plate", "leave-one-strain-out", "lmm-corrected")]
    r_sp = results[("species", "leave-one-plate-out", "uncorrected")]
    r_sp_c = results[("species", "leave-one-plate-out", "lmm-corrected")]

    # --- attempt 1: species classification (runs first because it is the positive control) --------
    def species_finding(fid, row, corrected):
        f = {"id": fid,
             "question": f"Can species identity (S. cerevisiae versus S. pombe) be predicted from Raman spectra under leave-one-plate-out cross-validation{' after batch correction' if corrected else ''}?",
             "target": {"label": "yeast species identity from Raman spectra", "type": "other"},
             "outcomeClass": "positive", "informativeness": "not-applicable",
             "effect": effect(row, note=res["speciesEvidence"]),
             "controls": {"positive": {"kind": "none", "note": "this task is itself the positive control for the strain task"},
                          "negative": {"kind": "adversarial-label", "label": "predicting plate identity",
                                       "expected": "chance performance, because plates are end-to-end replicates",
                                       "observed": f"MCC {r_plate_c['mcc_median'] if corrected else r_plate['mcc_median']}",
                                       "passed": bool(corrected),
                                       "note": "species classification succeeds even while the plate-level batch effect is present, which is why it is read as genuine biological signal"}},
             "conditions": conditions(row),
             "replicates": {"biological": 3, "note": "three end-to-end replicate plates, held out one at a time"},
             "evidence": ev(row),
             "note": "the most important random forest features align with wavenumbers where the mean species spectra visibly differ"}
        apply_informativeness(f)
        return f

    rec_species = attempt(
        "arcadia-raman-species-classification",
        "Species identity is recoverable from Raman spectra and survives holding out whole replicates",
        "Can Raman spectra distinguish S. cerevisiae from S. pombe under cross-validation that holds out whole experimental replicates?",
        "Classification well above chance under leave-one-plate-out cross-validation, with feature importances that correspond to visible spectral differences.",
        "positive", [species_finding("species-lopo", r_sp, False), species_finding("species-lopo-corrected", r_sp_c, True)],
        [processing_stage, model_stage("species classification", an["cvLopo"])],
        outcomeSummary=res["speciesLopo"],
        confidence={"level": "high", "basis": "near-perfect under replicate-held-out cross-validation, robust to batch correction, and supported by interpretable feature importances"},
        provenanceNotes=["This attempt supplies the positive control used by the strain attempt: it shows the spectra and the pipeline can recover a real biological distinction."])

    # --- attempt 2: adversarial batch-effect detection --------------------------------------------
    def plate_finding(fid, row, corrected):
        f = {"id": fid,
             "question": f"Can plate identity be predicted from the spectra{' after batch correction' if corrected else ''}, given that the three plates are end-to-end replicates with no true biological difference?",
             "target": {"label": "plate identity, a biologically meaningless label", "type": "other"},
             "outcomeClass": "positive", "informativeness": "not-applicable",
             "effect": effect(row, note="a high value here is a bad outcome for the experiment: it means the spectra carry a confound the model can exploit" if not corrected else "after correction the adversarial classifier performs near chance, confirming the plate-level effect was removed"),
             "controls": {"positive": {"kind": "known-positive-task", "label": "species classification on the same spectra",
                                       "expected": "recoverable biological signal", "observed": f"MCC {r_sp['mcc_median']}", "passed": True},
                          "negative": {"kind": "none", "note": "this task is itself the negative control for the other tasks in the study"}},
             "conditions": conditions(row),
             "replicates": {"biological": 3, "note": "leave-one-strain-out cross-validation, inverting the prediction and cross-validation dimensions"},
             "evidence": ev(row),
             "note": facts["adversarialTest"]["rationale"]}
        apply_informativeness(f)
        return f

    rec_batch = attempt(
        "arcadia-raman-batch-effect",
        "An adversarial task shows plate identity is almost perfectly predictable, confirming a strong batch effect",
        "Do the Raman spectra carry a plate-level experimental batch effect strong enough for a classifier to exploit?",
        "A classifier trained to predict plate identity should perform at chance if no batch effect exists; performance above chance demonstrates one.",
        "positive", [plate_finding("plate-loso", r_plate, False), plate_finding("plate-loso-corrected", r_plate_c, True)],
        [processing_stage, model_stage("adversarial plate-identity classification", an["cvLoso"]),
         {"stage": "computation", "label": "batch correction", "performedBy": analysts,
          "method": f"{bc['lmm']}. Alternative: {bc['combat']}",
          "note": f"{bc['noFixedEffect']} {bc['lmmAssumptions']}"}],
        outcomeSummary=f"{res['plateLoso']} After correction: {res['plateLosoCorrected']}",
        confidence={"level": "high", "basis": "plates are end-to-end replicates, so any predictability is by construction a batch effect; the result reverses cleanly after correction"},
        relations=[{"type": "comparedWith", "target": rec_species["@id"], "note": "species signal survives the batch effect that destroys the strain signal"}],
        provenanceNotes=["This attempt supplies the negative control used by the strain attempt. The authors recommend adversarial prediction of meaningless labels as general practice."])

    # --- attempt 3: strain classification (the finding the study is named for) ---------------------
    pos_ctrl = lambda corrected: {
        "kind": "known-positive-task", "label": "species classification on the same spectra and pipeline",
        "expected": "recoverable biological signal if the spectra and pipeline work",
        "observed": f"MCC {(r_sp_c if corrected else r_sp)['mcc_median']} under leave-one-plate-out cross-validation",
        "passed": True, "source": "Figure 6"}
    neg_ctrl = lambda corrected: {
        "kind": "adversarial-label", "label": "predicting plate identity, which should be unpredictable",
        "expected": "chance performance (MCC 0), because the three plates are end-to-end replicates",
        "observed": f"MCC {(r_plate_c if corrected else r_plate)['mcc_median']}",
        "passed": bool(corrected),
        "note": ("the adversarial classifier performs near chance after correction, so the control is clean" if corrected
                 else "the adversarial classifier predicts plate identity almost perfectly, so the control is not clean and any strain result is confounded"),
        "source": "Figure 4"}

    f_std = {
        "id": "strain-standard-cv",
        "question": "Can strain identity be predicted from Raman spectra under standard five-fold cross-validation?",
        "target": {"label": "yeast strain identity from Raman spectra", "type": "other"},
        "outcomeClass": "refuted", "informativeness": "not-applicable",
        "failureModes": ["confounded", "train-test-leakage"],
        "effect": effect(r_std, note="this is the number the study refutes: each fold contains spectra from all three plates, so the model can read batch-specific features and use them to predict strain"),
        "controls": {"positive": {"kind": "none", "note": "no control was run at this stage; the adversarial and species tasks came later and are what refute this result"},
                     "negative": {"kind": "none", "note": "the absence of an adversarial control is precisely what allowed this result to look strong"}},
        "conditions": conditions(r_std),
        "replicates": {"biological": 3, "note": "spectra from all three plates are mixed across folds, which is the flaw"},
        "evidence": ev(r_std) + [{"label": "Refuting analysis in the same study", "source": PUB_DOI[4:],
                                  "locator": "Figures 3 and 4", "quote": res["strainLopoExplanation"][:400]}],
        "relatedFindings": ["arcadia-raman-strain-classification#strain-lopo",
                            "arcadia-raman-batch-effect#plate-loso"],
        "note": "Recorded as refuted rather than positive: the study shows this measurement reflects experimental batch rather than strain biology.",
    }
    apply_informativeness(f_std)

    f_lopo = {
        "id": "strain-lopo",
        "question": "Can strain identity be predicted from Raman spectra when whole experimental replicates are held out?",
        "target": {"label": "yeast strain identity from Raman spectra", "type": "other"},
        "outcomeClass": "negative-no-effect", "informativeness": "uninformative",
        "failureModes": ["batch-effect", "confounded"],
        "effect": effect(r_lopo, note=res["strainLopo"]),
        "controls": {"positive": pos_ctrl(False), "negative": neg_ctrl(False)},
        "conditions": conditions(r_lopo),
        "replicates": {"biological": 3, "note": "each fold holds out one whole plate"},
        "evidence": ev(r_lopo),
        "relatedFindings": ["arcadia-raman-strain-classification#strain-standard-cv"],
        "note": "The drop from 0.79 to 0.32 is the study's central observation. Because the adversarial control is not clean at this stage, the low value cannot yet be read as an absence of strain signal.",
    }
    apply_informativeness(f_lopo)

    f_lopo_c = {
        "id": "strain-lopo-corrected",
        "question": "Can strain identity be predicted from Raman spectra after the plate-level batch effect has been removed?",
        "target": {"label": "yeast strain identity from Raman spectra", "type": "other"},
        "outcomeClass": "negative-no-effect", "informativeness": "uninformative",
        "failureModes": ["train-test-leakage", "signal-below-noise"],
        "effect": effect(r_lopo_c, note=res["strainLopoCorrectedExplanation"]),
        "controls": {"positive": pos_ctrl(True), "negative": neg_ctrl(True)},
        "conditions": dict(conditions(r_lopo_c), leakage=leak["statement"], intendedReading=leak["intendedReading"]),
        "replicates": {"biological": 3},
        "evidence": ev(r_lopo_c) + [{"label": "Limitations and caveats: self-declared train-test leakage",
                                     "source": PUB_DOI[4:], "locator": "Limitations and caveats",
                                     "quote": leak["consequence"][:400]},
                                    {"label": "Limitations and caveats: sample size and strain similarity",
                                     "source": PUB_DOI[4:], "locator": "Limitations and caveats",
                                     "values": {"limitations": facts["limitations"]}}],
        "note": "Both controls now behave. What is missing is a detection limit: the authors state the dataset is small and the strains may be too similar to produce detectable differences, but give no bound on the strain difference the design could have resolved.",
    }
    apply_informativeness(f_lopo_c)

    f_robust = {
        "id": "strain-robustness",
        "question": "Do these conclusions depend on the choice of classifier or batch-correction method?",
        "target": {"label": "robustness of the conclusions to model and batch-correction choice", "type": "other"},
        "outcomeClass": "positive", "informativeness": "not-applicable",
        "effect": {"metric": "median MCC across every combination of dataset, model and task",
                   "value": "not meaningfully different between random forest and support vector machine, or between the linear mixed model and ComBat",
                   "direction": "not-applicable", "comparedTo": "the random-forest and linear-mixed-model results reported numerically",
                   "note": "Figure 8 reports all combinations; the pub gives no numeric values for the support vector machine or ComBat runs"},
        "controls": {"positive": pos_ctrl(True), "negative": neg_ctrl(True)},
        "conditions": {"models": "random forest and support vector machine (RBF, C = 100)",
                       "batchCorrection": "none, linear mixed model, and ComBat",
                       "tasks": "strain, species and plate prediction"},
        "evidence": [{"label": "Results: Results aren't sensitive to model type or batch correction method",
                      "source": PUB_DOI[4:], "locator": "Figure 8", "quote": an["robustness"]}],
    }
    apply_informativeness(f_robust)

    attempt("arcadia-raman-strain-classification",
            "Strain identity appears predictable from Raman spectra until whole replicates are held out, and then it is not",
            "Can Raman spectra distinguish nine yeast strains, and does the answer depend on the cross-validation scheme?",
            "Strain classification above chance under leave-one-plate-out cross-validation, with a clean adversarial control showing the model is not reading plate identity.",
            "inconclusive-controls-failed", [f_std, f_lopo, f_lopo_c, f_robust],
            [processing_stage, model_stage("strain classification under two cross-validation schemes", f"{an['cvStandard']} and {an['cvLopo']}")],
            outcomeSummary=f"{res['strainStandardCv']} {res['strainLopo']} After batch correction: {res['strainLopoCorrected']}",
            confidence={"level": "medium", "basis": "the collapse under replicate-held-out cross-validation is robust to model and correction method, but the residual negative rests on 248 spectra across nine closely related strains with no stated detection limit"},
            invalidators=["a more genetically diverse strain panel in which strain identity survives leave-one-plate-out cross-validation",
                          "batch correction applied within each training fold, which would make the corrected estimate valid for unseen plates"],
            relations=[{"type": "wasDerivedFrom", "target": rec_batch["@id"], "note": "the adversarial plate task is the negative control for these findings"},
                       {"type": "wasDerivedFrom", "target": rec_species["@id"], "note": "the species task is the positive control for these findings"}],
            provenanceNotes=[
                "The same spectra and the same random forest give median MCC 0.79 under standard cross-validation and 0.32 under leave-one-plate-out cross-validation. The claim's sign depends on the validation scheme alone, which is why the analysis configuration is recorded in every finding's conditions.",
                "The standard cross-validation result is recorded as refuted rather than positive, and the informativeness rule deliberately does not apply its control requirement to a refutation.",
                f"Authors' self-declared limitation carried on the corrected finding: {leak['consequence']}",
            ])

    path["hasPart"] = [a["@id"] for a in attempts]
    check_valid(path)
    return [path] + attempts
