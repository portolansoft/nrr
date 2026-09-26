"""Converter for Kolb, Reitman, Lane et al. 2024, 'Label-free neuroimaging in mice captures sensory activity
in response to tactile stimuli and acute pain' (The Stacks, doi:10.57844/arcadia-b963-15ac) and its Zenodo deposits.

The study images the mouse cortex without labels while delivering three stimuli: vibration (touch), capsaicin
(acute pain) and histamine (itch). Touch and pain produced clear signals; itch did not, and the project was iced.
The itch arm is the reason this study is in the corpus: its positive control passed and its negative control did
not stay clean, which is the one clause of the informativeness rule no earlier record had exercised.
"""
from __future__ import annotations

from pathlib import Path

from nrr.ingest.common import (
    check_valid, data_pointer, entity, finalize, new_record, performer, read_csv, read_json, read_yaml, source,
)
from nrr.rules import apply_informativeness

STUDY = "arcadia-neuroimaging"
PUB_DOI = "doi:10.57844/arcadia-b963-15ac"
DATA_DOI = "doi:10.5281/zenodo.11585535"
CODE_DOI = "doi:10.5281/zenodo.12770054"

# Reporting fields the pub does not address. Stating their absence is the informative act.
REPORTING = {
    "blinding": "not stated; trials were acquired and analysed by the same team without a stated blinding step",
    "randomization": "not stated; one animal per trial, stimuli delivered in a fixed order within a session",
    "preregistration": "none",
    "reportingGuideline": "none cited; ARRIVE 2.0 items including sample-size justification, randomization and blinding are not reported",
}


def parse_trials(path: Path) -> list[dict]:
    """One row per imaging trial, transcribed from the figure legends (Data IDs and conditions)."""
    rows = read_csv(path)
    for r in rows:
        r["imaging_minutes"] = int(r["imaging_minutes"])
        r["isoflurane_percent"] = float(r["isoflurane_percent"]) if r["isoflurane_percent"] else None
        r["finding_id"] = r["trial_id"].removesuffix("-vehicle").removesuffix("-drug")
    return rows


def build_neuroimaging_records(root: Path, resolver) -> list[dict]:
    cur = root / "curated" / "neuroimaging"
    raw = root / "raw" / "neuroimaging"
    facts = read_yaml(cur / "pub_facts.yaml")
    trials = parse_trials(cur / "trials.csv")
    zen = read_json(raw / "zenodo" / "record_11585535.json")
    code_zen = read_json(raw / "zenodo" / "record_12770054.json")

    pub, animals, instr, surg = facts["publication"], facts["animals"], facts["instrument"], facts["surgery"]
    tp, ip, an, res = facts["tactileProtocol"], facts["injectionProtocol"], facts["analysis"], facts["results"]
    operator = {"name": facts["operator"]["name"], "identifier": facts["operator"]["ror"], "type": "Organization"}

    # --- data pointers: each figure Data ID is an instrument run inside a checksummed session zip -----
    zfiles = {f["key"]: f for f in zen["files"]}
    by_date = {k.removeprefix("pub-data-raw-").removesuffix(".zip"): f for k, f in zfiles.items() if "raw" in k}

    def run_pointer(trial: dict) -> dict:
        f = by_date[trial["session_date"]]
        return data_pointer(
            f"{trial['modality']} {trial['arm']} run, {trial['site']} ({trial['figure']})",
            repository="Zenodo", accession="10.5281/zenodo.11585535", url=f["links"]["self"],
            runId=trial["data_id"], checksum=f["checksum"], size=f["size"], format="zip of raw imaging frames",
            role="raw instrument run", note=f"session {trial['session_date']}; {trial['imaging_minutes']} min at 10 fps")

    all_files = [data_pointer(f["key"], repository="Zenodo", accession="10.5281/zenodo.11585535",
                              url=f["links"]["self"], checksum=f["checksum"], size=f["size"],
                              role="processed imaging data" if "processed" in f["key"] else "raw imaging session")
                 for f in zen["files"]]

    sources_common = [
        source("source-publication", PUB_DOI, resolver, label=pub["title"], url=pub["url"], license=pub["license"]),
        source("data-deposit", DATA_DOI, resolver, label=zen["metadata"]["title"],
               license="CC BY 4.0", note="80.9 GB across six files; raw sessions are split by date", data=all_files),
        source("code-repository", CODE_DOI, resolver, label=code_zen["metadata"]["title"],
               url=pub["codeRepo"], license="CC BY 4.0", note=f"version {pub['codeVersion']}"),
    ]
    prior = [source("prior-art" if k in ("flavoproteinImaging", "itchFewerNeurons", "itchInS1") else "reference",
                    f"doi:{d}", resolver, label=k)
             for k, v in facts["priorArt"].items() for d in (v if isinstance(v, list) else [v])]

    # --- shared entities ------------------------------------------------------------------------
    def onto(label):
        hit = resolver.ontology(label)
        return hit["identifier"] if hit and hit.get("identifier") else None

    def compound(label):
        hit = resolver.compound(label)
        return hit["identifier"] if hit and hit.get("identifier") else None

    ents = [
        entity(animals["taxon"], "organism", animals["species"], scheme="NCBI Taxonomy"),
        entity(animals["strainRrid"], "strain", f"{animals['strain']} ({animals['genotype']}, {animals['sex']})",
               scheme="IMSR / RRID", role="experimental animal", extra={"supplier": animals["strainSupplier"]}),
        entity(onto("primary somatosensory cortex") or "UBERON:0008933", "anatomicalStructure",
               "primary somatosensory cortex (S1)", scheme="UBERON", role="expected response region"),
        entity(onto("cerebral cortex") or "UBERON:0000956", "anatomicalStructure", "cerebral cortex",
               scheme="UBERON", role="imaged field"),
        entity(onto("sensory perception of touch") or "GO:0050975", "process", "sensory perception of touch", scheme="GO"),
        entity(onto("sensory perception of pain") or "GO:0019233", "process", "sensory perception of pain", scheme="GO"),
        entity(onto("response to histamine") or "GO:0034776", "process", "response to histamine", scheme="GO"),
        entity(onto("fluorescence microscopy assay") or "CHMO:0000087", "assay",
               "flavoprotein autofluorescence widefield imaging", scheme="CHMO",
               note="no exact OBI term for label-free flavoprotein autofluorescence imaging; the nearest exact match is the CHMO fluorescence microscopy term"),
        entity("instrument:uwfm-arcadia", "instrument", instr["name"], role="imaging instrument",
               extra={"basedOn": instr["basedOn"], "modifications": instr["modifications"],
                      "fieldOfView": instr["fieldOfView"], "frameRate": instr["frameRate"], "cost": instr["cost"]}),
        entity("ror:052zd4v68", "organization", "Arcadia Science", url=facts["operator"]["ror"]),
        entity("organization:cradl", "organization",
               "Charles River Accelerator and Development Lab (CRADL), South San Francisco, CA",
               role="IACUC of record for the animal work"),
        entity(f"github:{pub['codeRepo'].split('github.com/')[1]}", "software",
               "Arcadia-Science/2024-sensory-neuroimaging", url=pub["codeRepo"], extra={"version": pub["codeVersion"]}),
    ]
    for label, role in [("capsaicin", "algogen (acute pain stimulus)"), ("histamine dihydrochloride", "pruritogen (itch stimulus)"),
                        ("isoflurane", "anaesthetic"), ("lidocaine", "local anaesthetic"), ("ethanol", "vehicle component")]:
        cid = compound(label)
        if cid:
            ents.append(entity(cid, "compound", label, scheme="PubChem", role=role))

    people = [performer(c["name"], "person", role, affiliation="Arcadia Science")
              for c in facts["contributors"] for role in c["roles"]]
    ai_tools = [performer(t["name"], "llm", "software", provider=t["provider"], note=t["purpose"])
                for t in facts["aiUse"]["tools"]]
    experimenters = [p for p in people if p["role"] in ("investigation", "methodology", "formal-analysis")]

    applicability = {
        "organism": animals["taxon"], "species": animals["species"], "strain": animals["strain"],
        "strainIdentifier": animals["strainRrid"], "genotype": animals["genotype"], "sex": animals["sex"],
        "animalsInStudy": animals["totalAnimals"], "animalsPerTrial": animals["perTrialN"],
        "anesthesia": surg["anesthesia"], "preparation": surg["preparation"], "invasiveness": surg["invasiveness"],
        "instrument": instr["name"], "readout": "flavoprotein autofluorescence, dF/F over a region of interest",
        "imaging": f"{instr['frameRate']}, {instr['fieldOfView']}",
        "analysis": "; ".join(an["steps"]),
        "statistics": an["statistics"],
    }
    common = dict(operator=operator, pathType="experiment", sourceLicense="CC BY 4.0",
                  aiUseDeclaration={"statement": facts["aiUse"]["statement"],
                                    "tools": [{"name": t["name"], "provider": t["provider"], "purpose": t["purpose"]} for t in facts["aiUse"]["tools"]]})
    governance = {"humanSubjectData": "none",
                  "biosecurityTier": "none",
                  "complianceIds": [animals["iacuc"]]}
    base_cost = {"wetLabRuns": len(trials), "humanExperimenters": 2,
                 "note": f"13 imaging trials across {animals['totalAnimals']} mice. The pub reports the imaging system cost ({instr['cost']}) as capital, not as the cost of this study; no per-study cost is given.",
                 "source": "Methods, Microscope and sensory stimulation hardware"}

    # --- path ------------------------------------------------------------------------------------
    path = new_record(
        "path", STUDY, "arcadia-neuroimaging-path",
        "Label-free flavoprotein imaging of the mouse cortex as a behaviour-independent assay for touch, pain and itch (iced)",
        question="Can label-free, through-skull flavoprotein autofluorescence imaging of the mouse cortex measure brain responses to touch, capsaicin-induced pain and histamine-induced itch, as an alternative to mouse behavioural assays?",
        hypothesis=facts["purpose"],
        successCriteria="A localized, reproducible cortical signal for each of the three stimuli, distinguishable from its vehicle or unstimulated control, in anaesthetized mice.",
        outcomeClass="partial",
        outcomeSummary="Touch produced localized contralateral somatosensory signals and capsaicin produced widespread oscillatory cortical activation absent in vehicle trials; histamine produced activation indistinguishable from saline and inconsistent between trials, so the itch application was iced.",
        confidence={"level": "low", "basis": "one mouse per trial, five mice in total, no statistics, no detection limit and no blinding reported; the pub is framed as a demonstration rather than a powered study"},
        abandonmentReasons=facts["icebox"]["reasons"],
        nextSteps=facts["nextSteps"],
        openQuestions=facts["openQuestions"],
        untriedBranches=[{"description": s, "status": "proposed-by-authors", "source": "Next steps"} for s in facts["nextSteps"]]
        + [{"description": "Imaging session 2024-03-06 is deposited on Zenodo (20.2 GB, the largest single raw session) but is not cited by any figure or result in the pub; no analysis of it is reported.",
            "status": "data-deposited-not-analysed",
            "source": "Zenodo file manifest compared against the session dates cited in the figure legends",
            "dataAvailable": [data_pointer(by_date["2024-03-06"]["key"], repository="Zenodo",
                                           accession="10.5281/zenodo.11585535", url=by_date["2024-03-06"]["links"]["self"],
                                           checksum=by_date["2024-03-06"]["checksum"], size=by_date["2024-03-06"]["size"],
                                           role="raw imaging session, uncited")]}],
        invalidators=["a repeat of the itch experiment with a sensitive genetically encoded calcium indicator that resolves a histamine-specific signal",
                      "the same experiment in non-anaesthetized animals, since anaesthesia suppresses cortical activity",
                      "an injection-artifact control that separates needle and handling responses from the pruritogen response"],
        applicabilityConditions=applicability, cost=base_cost,
        sources=sources_common + prior, performers=people + ai_tools, entities=ents,
        governance=governance,
        provenanceNotes=[
            f"Icebox statement: {facts['icebox']['statement']}",
            "Mouse identity per trial is not given in the pub. Trials are grouped into animals here from the authors' 'same mouse as in B/C' statements and shared session dates; those groupings are inferred, not stated.",
            "The pub says vehicle trials were imaged for 10 minutes, while the figure legends and the deposited file names say 15 minutes. The trial table follows the file names.",
            "Figure 3D is described as the same mouse as Figure 3C, but its Data IDs carry an earlier session date (2024-03-18) than 3C (2024-03-19). Recorded as printed.",
            "No statistical test, power analysis or detection limit appears anywhere in the pub; effect values are therefore qualitative or single-trial.",
        ],
        hasPart=[], **common)
    finalize(path, check=False)
    pid = path["@id"]
    attempts: list[dict] = []

    def attempt(slug, title, question, success, outcome, findings, stages, **kw):
        rec = new_record("attempt", STUDY, slug, title, attemptType="wet-lab", question=question,
                         successCriteria=success, outcomeClass=outcome, findings=findings, stages=stages,
                         applicabilityConditions=applicability, cost=base_cost, sources=sources_common,
                         isPartOf=pid, entities=ents, performers=experimenters, governance=governance,
                         relations=[{"type": "isPartOf", "target": pid}] + kw.pop("relations", []), **common, **kw)
        attempts.append(finalize(rec))
        return rec

    def trial(tid):
        return next(t for t in trials if t["trial_id"] == tid)

    def evidence_for(fig, *tids, extra_label=None):
        ts = [trial(t) for t in tids]
        return [{"label": extra_label or f"Figure {fig}", "source": PUB_DOI[4:], "locator": f"Figure {fig}",
                 "values": {t["arm"]: t["observed"] for t in ts},
                 "data": [run_pointer(t) for t in ts]}]

    # --- attempt 1: tactile stimulation (the assay validation, and the per-session gate) ----------
    tactile_stage = {
        "stage": "experiment", "label": "vibrating tactile stimulation of a single limb",
        "performedBy": experimenters, "protocol": tp["sequence"],
        "instrument": [instr["name"]],
        "conditions": {"stimulator": tp["stimulator"], "expectation": tp["expectation"], "anesthesia": surg["anesthesia"]},
        "protocolAdaptations": tp["adaptations"],
        "note": f"{tp['adaptationStatement']} {tp['gateStatement']} A trial was therefore repeated with adjusted settings until a signal appeared, which means the tactile result is a tuned positive rather than a first-pass one.",
    }
    analysis_stage = {
        "stage": "analysis", "label": "imaging analysis pipeline",
        "performedBy": [p for p in people if p["role"] == "software"] or experimenters,
        "method": "; ".join(an["steps"]),
        "software": [{"name": "Arcadia-Science/2024-sensory-neuroimaging", "version": pub["codeVersion"], "url": pub["codeRepo"]},
                     {"name": "scikit-image", "identifier": "RRID:SCR_021142"}],
        "note": an["normalisationCaveat"],
    }
    f_tactile = []
    for t in (trial("tactile-rhl"), trial("tactile-lhl"), trial("tactile-rfl")):
        f = {
            "id": t["finding_id"],
            "question": f"Does vibrating stimulation of the {t['site']} produce a localized autofluorescence increase in the expected contralateral somatosensory area?",
            "target": {"label": f"{t['site']} vibrotactile stimulation", "type": "process",
                       "identifier": onto("sensory perception of touch") or "GO:0050975"},
            "outcomeClass": "positive", "informativeness": "not-applicable",
            "effect": {"metric": "peak dF/F above pre-stimulus baseline, stimulus-triggered average over 50 stimulations",
                       "value": "1-3%", "unit": "%", "n": 1, "direction": "increase",
                       "comparedTo": "pre-stimulus baseline in the same trial",
                       "significant": "no statistical test reported",
                       "note": f"expected region {t['expected_region']}; observed {t['observed']}; the 1-3% range is reported for tactile trials as a whole and is consistent with previous flavoprotein imaging (refs 9-10)"},
            "controls": {
                "positive": {"kind": "none", "note": "no designated positive control; the prior expectation of S1 activation comes from the literature (refs 19-20), which is not a control run in this experiment"},
                "negative": {"kind": "within-subject", "label": "ipsilateral hemisphere and unstimulated periods of the same trial",
                             "expected": "no localized somatosensory response", "observed": "response confined to the contralateral somatosensory area",
                             "passed": True, "note": "somatotopic specificity is the control: stimulating the opposite limb moved the response to the opposite hemisphere"}},
            "replicates": {"biological": 1, "technical": 50, "note": "one mouse per trial; 50 stimulation repeats averaged within the trial"},
            "conditions": {"stimulus": t["stimulus"], "site": t["site"], "isofluranePercent": t["isoflurane_percent"],
                           "imagingMinutes": t["imaging_minutes"], "mouse": t["mouse"] + " (inferred, see provenance notes)"},
            "evidence": evidence_for(t["figure"], t["trial_id"]),
            **REPORTING,
        }
        apply_informativeness(f)
        f_tactile.append(f)
    rec_tactile = attempt(
        "arcadia-neuroimaging-tactile",
        "Vibrotactile stimulation produces localized contralateral somatosensory autofluorescence (assay validation)",
        "Can the ultra-widefield microscope reproduce known somatotopic cortical responses to tactile stimulation, and thereby qualify a session for chemical stimuli?",
        "A localized autofluorescence increase in the somatosensory area contralateral to the stimulated limb, at the anatomically expected position.",
        "positive", f_tactile, [tactile_stage, analysis_stage],
        outcomeSummary="Contralateral, somatotopically appropriate responses for right hindlimb, left hindlimb and right forelimb stimulation; a 1-3% increase in autofluorescence above baseline after averaging 50 stimulations.",
        confidence={"level": "medium", "basis": "three trials, consistent with known anatomy and with published flavoprotein imaging, but each n = 1 and obtained after per-trial tuning"},
        provenanceNotes=["The troubleshooting loop in this stage means the tactile signal was tuned into existence per session. This does not undermine the positive result, but it is why the tactile response is recorded as an internal positive control for later trials rather than as an independent one."])

    # --- attempt 2: capsaicin ---------------------------------------------------------------------
    def gate_control():
        return {"kind": "internal-positive", "label": "tactile response confirmed in the same session before injection",
                "expected": "localized contralateral somatosensory response", "observed": "confirmed; the authors proceeded to chemical stimuli only after seeing it",
                "passed": True, "source": "Methods, Injection experiments: 'Once we observed a brain response to a tactile stimulus, we proceeded with chemical stimuli.'"}

    caps_stage = {
        "stage": "experiment", "label": "intradermal capsaicin and paired vehicle injection during imaging",
        "performedBy": experimenters,
        "protocol": f"{ip['route']}; {ip['timing']}; {ip['marking']}",
        "instrument": [instr["name"]],
        "conditions": {"dose": ip["capsaicinDose"], "vehicle": ip["capsaicinVehicle"], "control": ip["capsaicinControl"]},
        "note": "each capsaicin trial is paired with a vehicle trial in the same mouse",
    }
    f_caps = []
    for fid, fig, veh, drug, site in [("capsaicin-lhl", "3B", "capsaicin-lhl-vehicle", "capsaicin-lhl-drug", "left hindlimb"),
                                      ("capsaicin-rhl", "3C", "capsaicin-rhl-vehicle", "capsaicin-rhl-drug", "right hindlimb"),
                                      ("capsaicin-nape", "3D", "capsaicin-nape-vehicle", "capsaicin-nape-drug", "nape of the neck")]:
        td = trial(drug)
        f = {
            "id": fid,
            "question": f"Does intradermal capsaicin in the {site} produce cortical activity distinguishable from its paired vehicle injection?",
            "target": {"label": "capsaicin", "identifier": compound("capsaicin"), "type": "compound"},
            "outcomeClass": "positive", "informativeness": "not-applicable",
            "effect": {"metric": "whole-brain dF/F after injection versus paired vehicle trial",
                       "value": td["observed"], "n": 1, "direction": "increase",
                       "comparedTo": f"paired vehicle injection in the same mouse ({trial(veh)['observed']})",
                       "significant": "no statistical test reported",
                       "note": "activation is described qualitatively; the pub reports no effect size or test for injection trials"},
            "controls": {"positive": gate_control(),
                         "negative": {"kind": "vehicle", "label": ip["capsaicinControl"], "expected": "no widespread cortical activation",
                                      "observed": trial(veh)["observed"], "passed": True}},
            "replicates": {"biological": 1, "note": "one mouse per condition; no repeat trials"},
            "conditions": {"dose": ip["capsaicinDose"], "route": ip["route"], "site": site,
                           "isofluranePercent": td["isoflurane_percent"], "imagingMinutes": td["imaging_minutes"],
                           "mouse": td["mouse"] + " (inferred, see provenance notes)"},
            "evidence": evidence_for(fig, veh, drug),
            **REPORTING,
        }
        if fid == "capsaicin-rhl":
            f["failureModes"] = ["confounded"]
            f["note"] = res["capsaicinConfound"]
        if fid == "capsaicin-nape":
            f["note"] = "Region of interest restricted to the responsive somatosensory area rather than the whole brain, in both vehicle and capsaicin trials."
        apply_informativeness(f)
        f_caps.append(f)
    rec_caps = attempt(
        "arcadia-neuroimaging-capsaicin",
        "Intradermal capsaicin produces widespread oscillatory cortical activation absent from paired vehicle trials",
        "Does capsaicin-induced acute pain produce cortical autofluorescence activity that the microscope can detect against a paired vehicle control?",
        "Cortical activation after capsaicin injection that is clearly absent after the paired vehicle injection in the same mouse.",
        "positive", f_caps, [caps_stage, analysis_stage],
        outcomeSummary=res["capsaicin"],
        confidence={"level": "medium", "basis": "consistent across three injection sites with paired vehicle controls, but n = 1 per condition, no statistics, and an order effect the authors flag"},
        relations=[{"type": "wasDerivedFrom", "target": rec_tactile["@id"], "note": "the tactile response gated entry to these trials"}],
        provenanceNotes=[f"Order confound flagged by the authors: {res['capsaicinConfound']}",
                         "Effect values are the authors' qualitative descriptions; no numeric dF/F is tabulated for injection trials."])

    # --- attempt 3: histamine (the record this study was chosen for) ------------------------------
    hist_stage = {
        "stage": "experiment", "label": "intradermal histamine and paired saline injection during imaging",
        "performedBy": experimenters,
        "protocol": f"{ip['route']}; {ip['timing']}; {ip['marking']}",
        "instrument": [instr["name"]],
        "conditions": {"dose": ip["histamineDose"], "control": ip["histamineControl"]},
        "note": "each histamine trial is paired with a saline trial in the same mouse and limb",
    }
    hist_cid = compound("histamine dihydrochloride")

    def hist_controls(veh_trial):
        return {"positive": gate_control(),
                "negative": {"kind": "vehicle", "label": ip["histamineControl"],
                             "expected": "no widespread cortical activation",
                             "observed": veh_trial["observed"],
                             "passed": False,
                             "note": "the saline control produced widespread bilateral activation of a magnitude similar to histamine, so the control does not establish a clean baseline and the assay cannot separate the pruritogen from the injection itself"}}

    f_hist = []
    for fid, fig, veh, drug, site in [("histamine-lhl", "4B", "histamine-lhl-vehicle", "histamine-lhl-drug", "left hindlimb"),
                                      ("histamine-rhl", "4C", "histamine-rhl-vehicle", "histamine-rhl-drug", "right hindlimb")]:
        td, tv = trial(drug), trial(veh)
        f = {
            "id": fid,
            "question": f"Does intradermal histamine in the {site} produce cortical activity distinguishable from its paired saline injection?",
            "target": {"label": "histamine dihydrochloride", "identifier": hist_cid, "type": "compound"},
            "outcomeClass": "negative-no-effect", "informativeness": "uninformative",
            "failureModes": ["no-differential-signal", "irreproducible-across-trials"],
            "effect": {"metric": "whole-brain dF/F after injection versus paired saline trial",
                       "value": td["observed"], "n": 1, "direction": "none",
                       "comparedTo": f"paired saline injection in the same mouse ({tv['observed']})",
                       "significant": "no statistical test reported",
                       "note": "both saline and histamine produced widespread bilateral activation of similar magnitude"},
            "controls": hist_controls(tv),
            "replicates": {"biological": 1, "note": "one mouse; patterns inconsistent between trials"},
            "conditions": {"dose": ip["histamineDose"], "route": ip["route"], "site": site,
                           "imagingMinutes": td["imaging_minutes"], "mouse": td["mouse"] + " (inferred, see provenance notes)"},
            "evidence": evidence_for(fig, veh, drug),
            **REPORTING,
        }
        apply_informativeness(f)
        f_hist.append(f)

    overall = {
        "id": "histamine-overall",
        "question": "Does histamine-induced itch produce cortical activity detectable by label-free flavoprotein autofluorescence imaging in anaesthetized mice?",
        "target": {"label": "histamine-induced itch, cortical response", "identifier": hist_cid, "type": "compound"},
        "outcomeClass": "negative-no-effect", "informativeness": "uninformative",
        "failureModes": ["no-differential-signal", "irreproducible-across-trials", "signal-below-noise"],
        "effect": {"metric": "consistency and localisation of cortical activation across histamine trials",
                   "value": "no consistent or localized activation; magnitude similar to saline control", "n": 2,
                   "direction": "none", "comparedTo": "paired saline injections in the same mouse",
                   "significant": "no statistical test reported",
                   "note": res["histamine"]},
        "controls": hist_controls(trial("histamine-lhl-vehicle")),
        "replicates": {"biological": 1, "technical": 2, "note": "two limbs in one mouse; the authors describe the patterns as inconsistent between trials"},
        "conditions": {"dose": ip["histamineDose"], "route": ip["route"], "anesthesia": surg["anesthesia"]},
        "evidence": [{"label": "Results, Brain activity in response to capsaicin-induced pain and histamine-induced itch",
                      "source": PUB_DOI[4:], "locator": "Figure 4",
                      "quote": "the activity patterns were inconsistent between trials, the magnitude of the activation was similar to saline control, and the activation didn't seem to be localized to a particular brain area"},
                     {"label": "Icebox statement", "source": PUB_DOI[4:],
                      "quote": facts["icebox"]["statement"][:400]},
                     {"label": "Authors' mechanistic hypothesis for the absence", "source": PUB_DOI[4:],
                      "locator": "Next steps", "quote": res["itchHypothesis"][:400]}],
        "relatedFindings": ["arcadia-neuroimaging-histamine#histamine-lhl", "arcadia-neuroimaging-histamine#histamine-rhl"],
        "nearestPriorResult": "doi:10.5607/en22029",
        "note": res["histamineInterpretation"],
        **REPORTING,
    }
    apply_informativeness(overall)
    f_hist.append(overall)

    attempt("arcadia-neuroimaging-histamine",
            "Histamine-induced itch produces no cortical signal separable from saline injection (iced for a technical gap)",
            "Does intradermal histamine produce cortical autofluorescence activity distinguishable from a saline injection in anaesthetized mice?",
            "Cortical activation after histamine injection that is consistent between trials, localized, and larger than the paired saline injection.",
            "inconclusive-controls-failed", f_hist, [hist_stage, analysis_stage],
            outcomeSummary="Histamine and saline both produced widespread bilateral activation of similar magnitude, inconsistent between trials and not localized. The positive control passed; the negative control did not stay clean, so the experiment cannot say whether an itch signal exists.",
            confidence={"level": "low", "basis": "two trials in one mouse, no detection limit, and a vehicle control that produced the same response as the treatment"},
            invalidators=["a sensitive calcium indicator such as GCaMP resolving a histamine-specific signal",
                          "an injection-artifact control that separates needle and handling responses from the pruritogen response",
                          "the same experiment in non-anaesthetized animals"],
            relations=[{"type": "wasDerivedFrom", "target": rec_tactile["@id"], "note": "the tactile response gated entry to these trials"},
                       {"type": "comparedWith", "target": rec_caps["@id"], "note": "the same method and animals detected capsaicin-induced pain"}],
            provenanceNotes=["This is the record the study was selected for: the positive control passed and the negative control did not stay clean, which is the clause of the informativeness rule that no earlier record in the corpus had exercised.",
                             "Encoding judgement 1: the saline control is recorded as not passing. The pub does not use that language; it says the magnitude of histamine activation 'was similar to saline control'. Treating a vehicle that reproduces the treatment response as a control that did not stay clean is this ingest's reading, and it is what drives the outcome class.",
                             "Encoding judgement 2: the positive control is recorded as passing on the strength of the stated gate ('Once we observed a brain response to a tactile stimulus, we proceeded with chemical stimuli'). The pub does not report a tactile confirmation for each individual injection session, so the per-session pass is inferred from the protocol rather than observed per trial.",
                             "The pub states no detection limit, power analysis or significance test, so the finding is uninformative on two counts, not one.",
                             "The authors' own hypothesis for the absence (too few itch-responsive cortical neurons to exceed noise) is recorded as evidence, not as a conclusion."])

    path["hasPart"] = [a["@id"] for a in attempts]
    check_valid(path)
    return [path] + attempts
