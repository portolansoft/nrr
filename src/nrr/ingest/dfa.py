"""Converter for Morin, Patton et al. 2024, 'A structurally divergent actin conserved in fungi has no
association with specific traits' (The Stacks, doi:10.57844/arcadia-9768-f6c5).

Encoded as a test of whether the data model has converged. This study shares almost nothing structurally with
the four already in the corpus: there is no experiment, the unit of observation is a species rather than a cell
or an animal, the evidence is evolutionary model selection over a phylogeny, and the negative takes the form
'no association with any of six traits'.
"""
from __future__ import annotations

from pathlib import Path

from nrr.ingest.common import (
    check_valid, data_pointer, entity, finalize, new_record, performer, read_csv, read_json, read_yaml, source,
)
from nrr.rules import apply_informativeness

STUDY = "arcadia-dfa"
PUB_DOI = "doi:10.57844/arcadia-9768-f6c5"
DATA_DOI = "doi:10.5281/zenodo.10211653"
CODE_DOI = "doi:10.5281/zenodo.10779267"


def parse_traits(path: Path) -> dict[str, dict]:
    out = {}
    for r in read_csv(path):
        r["n_species"] = int(r["n_species"])
        for k in ("best_aic", "correlated_aic", "p_value_slope", "p_value_intercept"):
            r[k] = float(r[k]) if r[k] else None
        out[r["trait"]] = r
    return out


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-")


def build_dfa_records(root: Path, resolver) -> list[dict]:
    cur, raw = root / "curated" / "dfa", root / "raw" / "dfa"
    facts = read_yaml(cur / "pub_facts.yaml")
    traits = parse_traits(cur / "traits.csv")
    zdata = read_json(raw / "zenodo" / "record_10211653.json")
    zcode = read_json(raw / "zenodo" / "record_10779267.json")

    pub, tgt, pc = facts["publication"], facts["target"], facts["proteinCartographyRun"]
    ws, tc, st, res = facts["workingSet"], facts["traitCuration"], facts["statistics"], facts["results"]
    operator = {"name": facts["operator"]["name"], "identifier": facts["operator"]["ror"], "type": "Organization"}

    data_files = [data_pointer(f["key"], repository="Zenodo", accession="10.5281/zenodo.10211653",
                               url=f["links"]["self"], checksum=f["checksum"], size=f["size"],
                               role="ProteinCartography inputs and outputs") for f in zdata["files"]]
    code_files = [data_pointer(f["key"], repository="Zenodo", accession="10.5281/zenodo.10779267",
                               url=f["links"]["self"], checksum=f["checksum"], size=f["size"],
                               role="analysis code, divergent actin lists, species and trait tables") for f in zcode["files"]]

    sources_common = [
        source("source-publication", PUB_DOI, resolver, label=pub["title"], url=pub["url"], license=pub["license"]),
        source("data-deposit", DATA_DOI, resolver, label=zdata["metadata"]["title"], license="CC BY 4.0", data=data_files),
        source("code-repository", CODE_DOI, resolver, label=zcode["metadata"]["title"], url=pub["codeRepo"],
               license="CC BY 4.0", data=code_files),
    ]
    prior = [source("prior-art" if k in ("proteinCartography", "actinCaseStudy") else "reference",
                    f"doi:{d}", resolver, label=k) for k, d in facts["priorArt"].items()]
    db_sources = [source("reference", f"doi:{d['doi']}", resolver, label=f"{d['name']}: {d['role']}", url=d.get("url"))
                  for d in facts["databases"] if d.get("doi")]

    searched = [{"name": d["name"], "kind": "reference database", "url": d.get("url") or f"https://doi.org/{d['doi']}",
                 "coverage": d["role"]} for d in facts["databases"]]

    # --- entities -------------------------------------------------------------------------------
    ents = [
        entity("NCBITaxon:4751", "organism", "Fungi (kingdom)", scheme="NCBI Taxonomy", role="taxonomic scope"),
        entity("uniprot:P60709", "protein", "human cytoplasmic beta-actin (ACTB)", scheme="UniProt",
               role="seed protein for the original ProteinCartography run"),
        entity("protein-family:divergent-fungal-actin", "protein", "divergent fungal actin (DFA)",
               role="the protein family whose function is in question", note=tgt["description"]),
        entity("ror:052zd4v68", "organization", "Arcadia Science", url=facts["operator"]["ror"]),
    ]
    for acc in tgt["representatives"]:
        ents.append(entity(f"uniprot:{acc}", "protein", f"divergent fungal actin representative {acc}",
                           scheme="UniProt", role="ProteinCartography search input"))
    for t, row in traits.items():
        ents.append(entity(f"trait:{_slug(t)}", "phenotype", t, scheme="Fun Fun",
                           role="candidate predictor of DFA presence",
                           extra={"dataType": row["data_type"], "speciesWithData": row["n_species"],
                                  **({"categories": row["categories"]} if row["categories"] else {})}))
    for sw in facts["software"]:
        ents.append(entity(f"software:{sw['name']}", "software", sw["name"], role=sw["role"],
                           extra={k: v for k, v in {"version": sw.get("version"), "doi": sw.get("doi")}.items() if v}))
    for db in facts["databases"]:
        ents.append(entity(f"database:{_slug(db['name'])}", "dataset", db["name"], role=db["role"],
                           url=db.get("url"), extra={"doi": db["doi"]} if db.get("doi") else None))

    people = [performer(c["name"], "person", role, affiliation="Arcadia Science")
              for c in facts["contributors"] for role in c["roles"]]
    ai_tools = [performer(t["name"], "llm", "software", provider=t["provider"], note=t["purpose"])
                for t in facts["aiUse"]["tools"]]
    analysts = [p for p in people if p["role"] in ("formal-analysis", "methodology", "investigation", "data-curation")]

    applicability = {
        "taxonomicScope": "Fungi (NCBITaxon:4751)",
        "proteinFamily": "structurally divergent fungal actins, defined as ProteinCartography clusters LC04, LC11 and LC14",
        "absenceDefinition": ws["absenceRule"] + " " + ws["absenceRuleCaveat"],
        "workingSetSpecies": ws["size"], "speciesWithDfa": ws["withDfa"], "speciesWithoutDfa": ws["withoutDfa"],
        "speciesAnalysed": tc["finalSet"],
        "traitsTested": list(traits),
        "traitSource": f"{tc['database']}: {tc['databaseNote']}",
        "phylogeny": ws["phylogenySource"],
        "unitOfObservation": "species, not independent observations; phylogenetic non-independence is modelled explicitly",
        "statistics": f"{st['discreteApproach']} {st['continuousApproach']}",
        "note": "conclusions are bounded by which traits had usable public data, not by which traits are biologically plausible",
    }
    common = dict(operator=operator, sourceLicense="CC BY 4.0",
                  aiUseDeclaration={"statement": facts["aiUse"]["statement"],
                                    "tools": [{"name": t["name"], "provider": t["provider"], "purpose": t["purpose"]} for t in facts["aiUse"]["tools"]]})
    base_cost = {"note": f"computational study; {ws['size']} species in the working set, {tc['finalSet']} analysed; no monetary or compute cost is reported",
                 "source": "The approach"}

    pc_stage = {
        "stage": "computation", "label": "ProteinCartography structure search and clustering",
        "performedBy": analysts, "method": f"{pc['mode']}; {pc['parameters']}; {pc['clusteringMethod']}; similarity by {pc['similarityMetric']}",
        "software": [{"name": "ProteinCartography", "version": pc["version"]}, {"name": "MMseqs2", "version": "14.7e284"},
                     {"name": "Foldseek"}, {"name": "BLAST+"}],
        "parameters": {"hits": pc["hits"], "clusters": pc["clusters"], "averageCompactness": pc["averageCompactness"],
                       "wellDefinedClusters": pc["wellDefinedClusters"], "compactnessThreshold": pc["compactnessThreshold"]},
        "sourcesSearched": [s for s in searched if s["name"] in ("AlphaFold Protein Structure Database", "UniProtKB", "NCBI Taxonomy")],
        "outputs": data_files,
    }
    curation_stage = {
        "stage": "computation", "label": "working-set definition and trait curation",
        "performedBy": analysts,
        "method": f"{ws['absenceRule']}. {tc['selectionCriterion']}. {tc['removedInconsistent']}. {tc['removedNoPhylogeny']}.",
        "sourcesSearched": searched,
        "parameters": {"withAnyTrait": tc["withAnyTrait"], "finalSet": tc["finalSet"],
                       "thresholdSensitivityCheck": ws["sensitivityCheck"]},
        "protocolAdaptations": [ws["sensitivityCheck"], st["categoryRule"]] + st["recoding"],
        "note": "category levels were redefined after seeing the data, to keep at least four species per level",
    }
    model_stage = {
        "stage": "analysis", "label": "evolutionary model selection and phylogeny-corrected regression",
        "performedBy": analysts, "method": f"{st['discreteApproach']} {st['discreteModels']} {st['continuousApproach']}",
        "software": [{"name": "corHMM", "version": "2.8"}, {"name": "phyr", "version": "1.1.2"}],
        "outputs": code_files,
        "note": st["multipleTesting"],
    }

    # --- path -----------------------------------------------------------------------------------
    path = new_record(
        "path", STUDY, "arcadia-dfa-path",
        "Phylogenetic trait mapping to find the function of a divergent fungal actin (iced)",
        question="Can phylogenetic trait mapping reveal the function of a structurally divergent actin isoform conserved across fungi, by finding a species-level trait that predicts its presence or absence?",
        hypothesis=facts["purpose"],
        successCriteria="At least one fungal trait whose evolutionary history is better explained by a model correlated with divergent actin presence than by an independent model, or a continuous trait whose slope on divergent actin presence differs significantly from zero.",
        pathType="computation", outcomeClass="partial",
        outcomeSummary="The divergent actin was mapped across 853 fungal species and found to be evolutionarily labile, unlike canonical actin. None of six curated traits predicted its presence, so its function remains unknown and the project was iced for lack of usable trait data.",
        confidence={"level": "low", "basis": "no positive control on the trait-mapping method, an average of 34 species per trait, six traits chosen for data availability rather than biological relevance, and an absence criterion the authors expect to produce false negatives"},
        abandonmentReasons=facts["icebox"]["reasons"],
        nextSteps=facts["nextSteps"],
        openQuestions=["What function do divergent fungal actins perform, given conserved ATP-binding residues but poorly conserved polymerization residues?",
                       "Would a trait panel chosen for biological relevance rather than data availability recover an association?"],
        untriedBranches=[{"description": s, "status": "proposed-by-authors", "source": "Next steps"} for s in facts["nextSteps"]],
        invalidators=["a trait panel with better coverage in which an association is recovered",
                      "a positive control showing the method recovers a known protein-trait association at comparable sample sizes",
                      "a knockout of the divergent actin in a tractable species producing a characterised phenotype"],
        applicabilityConditions=applicability, cost=base_cost,
        sources=sources_common + prior + db_sources, performers=people + ai_tools, entities=ents,
        governance={"humanSubjectData": "none", "biosecurityTier": "none"},
        provenanceNotes=[
            f"Icebox statement: {facts['icebox']['statement']} {facts['icebox']['note']}",
            f"Absence is inferred, not observed: {ws['absenceRule']} {ws['absenceRuleCaveat']}",
            f"Trait categories were recoded after inspecting the data to keep at least four species per level, which is recorded as a protocol adaptation rather than as a pre-specified design.",
            st["multipleTesting"],
            f"Part of the Arcadia platform effort '{pub['platformEffort']}'.",
        ],
        hasPart=[], **common)
    finalize(path, check=False)
    pid = path["@id"]
    attempts: list[dict] = []

    def attempt(slug, title, question, success, outcome, findings, stages, **kw):
        rec = new_record("attempt", STUDY, slug, title, attemptType="computational", pathType="computation",
                         question=question, successCriteria=success, outcomeClass=outcome, findings=findings,
                         stages=stages, applicabilityConditions=applicability, cost=base_cost,
                         sources=sources_common, isPartOf=pid, entities=ents, performers=analysts,
                         relations=[{"type": "isPartOf", "target": pid}] + kw.pop("relations", []), **common, **kw)
        attempts.append(finalize(rec))
        return rec

    no_ctrl = {"positive": {"kind": "none"}, "negative": {"kind": "none"}}

    # --- attempt 1: expand the divergent actin set ------------------------------------------------
    f_ext = {
        "id": "extended-set",
        "question": "How many structurally similar divergent actins exist beyond the original cluster, and in how many strains?",
        "target": {"label": "divergent fungal actin protein family", "type": "protein",
                   "identifier": "protein-family:divergent-fungal-actin"},
        "outcomeClass": "positive", "informativeness": "not-applicable",
        "effect": {"metric": "divergent actin proteins in the extended set", "value": 436, "n": 412,
                   "direction": "increase", "comparedTo": "the original cluster of 292 sequences",
                   "note": f"{pc['inputClusters']}; {pc['extendedSet']}"},
        "controls": dict(no_ctrl, positive={"kind": "none", "note": "cluster compactness is used as a quality measure rather than a control"}),
        "conditions": {"proteinCartographyVersion": pc["version"], "hits": pc["hits"], "clusters": pc["clusters"],
                       "averageCompactness": pc["averageCompactness"], "compactnessContext": pc["compactnessContext"]},
        "evidence": [{"label": "The results: ProteinCartography identifies clusters of divergent actins",
                      "source": PUB_DOI[4:], "locator": "Figure 3",
                      "values": {"hits": pc["hits"], "clusters": pc["clusters"], "wellDefined": pc["wellDefinedClusters"],
                                 "extendedSet": 436, "strains": 412}, "data": data_files}],
    }
    f_fungal = {
        "id": "fungal-specificity",
        "question": "Is the extended set of divergent actins still overwhelmingly fungal?",
        "target": {"label": "kingdom distribution of the divergent actin family", "type": "protein",
                   "identifier": "protein-family:divergent-fungal-actin"},
        "outcomeClass": "positive", "informativeness": "not-applicable",
        "effect": {"metric": "share of the extended set found in fungal species", "value": "more than 93%", "unit": "%",
                   "direction": "not-applicable", "comparedTo": "Metazoa, the next most represented kingdom, at 2%",
                   "note": pc["fungalSet"]},
        "controls": no_ctrl,
        "conditions": {"kingdomAssignment": "NCBI Taxonomy, with manual curation to clade level where UniProt reports no kingdom"},
        "evidence": [{"label": "The results: The extended set still contains mainly fungal proteins",
                      "source": PUB_DOI[4:], "locator": "Figure 4A", "values": {"fungalPercent": 93, "metazoaPercent": 2}}],
    }
    f_single = {
        "id": "single-copy",
        "question": "Do fungal species that carry a divergent actin carry more than one?",
        "target": {"label": "divergent actin copy number per species", "type": "protein",
                   "identifier": "protein-family:divergent-fungal-actin"},
        "outcomeClass": "positive", "informativeness": "not-applicable",
        "effect": {"metric": "share of divergent-actin-carrying species with exactly one copy", "value": "at least 95%",
                   "unit": "%", "direction": "not-applicable",
                   "note": pc["multipleHits"]},
        "controls": no_ctrl,
        "conditions": {"verification": "tBLASTn against genomes for strains with multiple hits"},
        "evidence": [{"label": "The approach: Taxonomic analysis of the extended set", "source": PUB_DOI[4:],
                      "values": {"strainsWithMultipleHits": 16}}],
        "note": "For half the multi-hit strains the duplicates were the same sequence annotated by different groups; for the rest tBLASTn could not resolve discrete loci, which the authors attribute to genome quality.",
    }
    for f in (f_ext, f_fungal, f_single):
        apply_informativeness(f)
    rec_expand = attempt(
        "arcadia-dfa-cluster-expansion",
        "ProteinCartography expands the divergent fungal actin set to 436 proteins across 412 strains",
        "Which proteins are structurally similar to the six representative divergent fungal actins, and in which organisms do they occur?",
        "A well-defined structural cluster containing the input proteins, large enough to support a species-level comparative analysis.",
        "positive", [f_ext, f_fungal, f_single], [pc_stage],
        outcomeSummary=f"{pc['extendedSet']} {pc['fungalFraction']}",
        confidence={"level": "medium", "basis": "average cluster compactness 0.6 sits mid-range against 25 previous runs; cluster membership is the definition of the protein family rather than an independently validated boundary"},
        provenanceNotes=["The protein family is defined operationally as membership of ProteinCartography clusters LC04, LC11 and LC14. There is no sequence-motif or experimental definition, so the family boundary is a clustering decision."])

    # --- attempt 2: distribution across the kingdom -----------------------------------------------
    f_dist = {
        "id": "distribution-labile",
        "question": "Is the divergent fungal actin evolutionarily conserved across the fungal kingdom, or labile?",
        "target": {"label": "divergent actin presence across fungal orders", "type": "protein",
                   "identifier": "protein-family:divergent-fungal-actin"},
        "outcomeClass": "positive", "informativeness": "not-applicable",
        "effect": {"metric": "fraction of species carrying a divergent actin, per fungal order",
                   "value": "variable across and within orders, neither zero nor one for many orders",
                   "n": ws["size"], "direction": "not-applicable",
                   "comparedTo": "canonical actin, which is highly conserved across the kingdom",
                   "note": res["distribution"]},
        "controls": dict(no_ctrl, positive={"kind": "known-positive-task",
                                            "label": "canonical actin, known to be highly conserved across eukaryotes",
                                            "expected": "near-uniform presence", "observed": "conserved, in contrast to the divergent actin",
                                            "passed": True,
                                            "note": "a contrast rather than a control run through the same pipeline; recorded because it is the comparison the authors rely on to call the divergent actin labile"}),
        "replicates": {"biological": ws["size"], "note": f"{ws['size']} species across 8 phyla; order recovered for 783 of them"},
        "conditions": {"phylogeny": ws["phylogenySource"], "orders": 85, "phyla": ws["phyla"]},
        "evidence": [{"label": "The results: The distribution of DFAs across species is highly variable",
                      "source": PUB_DOI[4:], "locator": "Figure 4B",
                      "values": {"workingSet": ws["size"], "withDfa": ws["withDfa"], "withoutDfa": ws["withoutDfa"],
                                 "phyla": ws["phyla"]}}],
        "note": f"Carries its own caveat: {ws['absenceRuleCaveat']} {res['distributionCaveat']}",
    }
    apply_informativeness(f_dist)
    rec_dist = attempt(
        "arcadia-dfa-distribution",
        "The divergent fungal actin is evolutionarily labile across the fungal kingdom",
        "How is the divergent fungal actin distributed across fungal orders, and does that distribution suggest a conserved or an adaptive role?",
        "A distribution pattern that distinguishes a conserved trait from a labile one across the fungal phylogeny.",
        "positive", [f_dist], [pc_stage, curation_stage],
        outcomeSummary=res["distribution"],
        confidence={"level": "low", "basis": "lability is inferred partly from inferred absences, and the authors note that overestimating absence would overestimate lability"},
        relations=[{"type": "wasDerivedFrom", "target": rec_expand["@id"]}],
        provenanceNotes=[f"Absence of the protein is inferred from a protein-count threshold, not observed: {ws['absenceRule']}"])

    # --- attempt 3: trait association (the negative the pub is named for) --------------------------
    def trait_finding(name, row):
        discrete = row["data_type"] == "discrete"
        eff = {"metric": ("Akaike information criterion of the best independent-evolution model" if discrete
                          else "slope of the trait on divergent actin presence, phylogeny-corrected logistic regression"),
               "n": row["n_species"], "direction": "none",
               "test": ("model selection by Akaike information criterion across four fitted models, two discrete-time Markov and two hidden Markov"
                        if discrete else "phylogeny-corrected generalized linear mixed model, pglmm_compare"),
               "significant": False}
        if discrete:
            eff["value"] = row["best_aic"]
            eff["comparedTo"] = f"best correlated-evolution model, AIC {row['correlated_aic']}; the independent model wins by {round(row['correlated_aic'] - row['best_aic'], 2)}"
            eff["note"] = "a lower AIC is a better fit, so the independent model being lowest means the trait and the protein show no shared evolutionary trajectory"
        else:
            eff["value"] = row["p_value_slope"]
            eff["pValue"] = row["p_value_slope"]
            eff["comparedTo"] = "a slope of zero, meaning the trait does not change the probability of divergent actin presence"
            eff["note"] = f"intercept p-value {row['p_value_intercept']}; no multiple-comparison correction is reported across traits"
        f = {
            "id": f"trait-{_slug(name)}",
            "question": f"Does {name} predict the presence or absence of a divergent fungal actin across species?",
            "target": {"label": name, "type": "phenotype", "identifier": f"trait:{_slug(name)}"},
            "outcomeClass": "negative-no-association", "informativeness": "uninformative",
            "failureModes": ["insufficient-data"],
            "effect": eff,
            "controls": {"positive": {"kind": "none",
                                      "note": "no protein family with a known association to this trait was run through the same pipeline, so a null result cannot be separated from a method unable to detect an association at this sample size"},
                         "negative": {"kind": "none",
                                      "note": "no permuted or shuffled trait assignment was tested"}},
            "replicates": {"biological": row["n_species"],
                           "note": f"{row['n_species']} species with usable data for this trait; species are not independent observations and phylogeny is modelled explicitly"},
            "statistics": st["discreteApproach"] if discrete else st["continuousApproach"],
            "conditions": {"dataType": row["data_type"], "categories": row["categories"] or "continuous",
                           "traitSource": tc["database"], "speciesAnalysed": tc["finalSet"],
                           "recoding": "; ".join(st["recoding"]) if discrete else "none"},
            "evidence": [{"label": row["source"], "source": PUB_DOI[4:], "locator": row["source"],
                          "values": {k: v for k, v in row.items() if v not in (None, "")}, "data": code_files}],
            "note": row["conclusion"],
        }
        apply_informativeness(f)
        return f

    f_traits = [trait_finding(n, r) for n, r in traits.items()]
    f_overall = {
        "id": "trait-overall",
        "question": "Does any of the six curated fungal traits predict the presence or absence of a divergent fungal actin?",
        "target": {"label": "divergent fungal actin function, inferred from trait association", "type": "protein",
                   "identifier": "protein-family:divergent-fungal-actin"},
        "outcomeClass": "negative-no-association", "informativeness": "uninformative",
        "failureModes": ["insufficient-data", "association-already-known"] if False else ["insufficient-data"],
        "effect": {"metric": "traits showing a correlated evolutionary trajectory with divergent actin presence",
                   "value": 0, "n": len(traits), "direction": "none", "significant": False,
                   "comparedTo": "six traits tested: four discrete by AIC model selection, two continuous by phylogeny-corrected regression",
                   "note": res["traitAssociation"]},
        "controls": {"positive": {"kind": "none", "note": st["positiveControl"]},
                     "negative": {"kind": "none", "note": "no permutation or shuffled-label control was run"}},
        "replicates": {"biological": tc["finalSet"],
                       "note": f"{tc['finalSet']} species in total, an average of 34 species per trait out of 36,253 fungi with at least one structure in UniProt"},
        "statistics": f"{st['discreteApproach']} {st['continuousApproach']} {st['multipleTesting']}",
        "conditions": {"traits": list(traits), "speciesAnalysed": tc["finalSet"],
                       "absenceDefinition": ws["absenceRule"]},
        "evidence": [{"label": "The results: None of the six tested fungal traits correlate with DFA status",
                      "source": PUB_DOI[4:], "locator": "Tables 2 and 3",
                      "values": {n: {"n": r["n_species"], "bestModel": r["best_model"],
                                     "aic": r["best_aic"], "pValue": r["p_value_slope"]} for n, r in traits.items()}},
                     {"label": "Limitations", "source": PUB_DOI[4:], "locator": "Limitations",
                      "values": {"stated": facts["limitations"]}},
                     {"label": "Key takeaways", "source": PUB_DOI[4:],
                      "quote": facts["keyTakeaways"][1][:300]}],
        "relatedFindings": [f"arcadia-dfa-trait-association#trait-{_slug(n)}" for n in traits],
        "note": "The authors attribute the null to trait coverage and to errors in calling divergent actin absent. The record adds that no positive control on the method was run, so the null cannot be separated from a method that would not have detected an association at these sample sizes.",
    }
    apply_informativeness(f_overall)

    attempt("arcadia-dfa-trait-association",
            "None of six curated fungal traits predicts the presence of a divergent fungal actin",
            "Does any curated species-level fungal trait predict the presence or absence of the divergent fungal actin, which would suggest a function for it?",
            "A trait whose evolutionary history is better explained by a model correlated with divergent actin presence, or a continuous trait with a slope significantly different from zero.",
            "inconclusive-no-positive-control", f_traits + [f_overall],
            [curation_stage, model_stage],
            outcomeSummary=res["traitAssociation"],
            confidence={"level": "low", "basis": "an average of 34 species per trait, traits chosen for data availability, no positive control on the method, and an absence criterion expected to produce false negatives"},
            invalidators=["a trait panel chosen for biological relevance with usable coverage",
                          "a positive control demonstrating the pipeline recovers a known protein-trait association at comparable sample sizes",
                          "a DFA-absence call based on genome assemblies rather than a UniProt protein-count threshold"],
            relations=[{"type": "wasDerivedFrom", "target": rec_dist["@id"], "note": "lability motivated the search for an adaptive trait association"},
                       {"type": "wasDerivedFrom", "target": rec_expand["@id"]}],
            provenanceNotes=[
                "Each trait is recorded as its own finding and the aggregate claim as a seventh, so a naive count of negatives for this study would be seven rather than one.",
                f"Every per-trait finding is uninformative for the same reason, so the class negative-no-association never survives into the record even though it is the pub's own framing.",
                st["multipleTesting"],
                f"Sample sizes per trait range from 10 to 71 species: {', '.join(f'{n} {r['n_species']}' for n, r in traits.items())}.",
            ])

    path["hasPart"] = [a["@id"] for a in attempts]
    check_valid(path)
    return [path] + attempts
