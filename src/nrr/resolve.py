"""Identifier resolution with a JSON cache.

Converters and tests run offline against `curated/identifiers.json`; `scripts/resolve_ids.py`
runs once online to populate it. Sources: PubChem PUG REST (compounds), UniProt (proteins),
OLS4 (ontology terms), Cellosaurus, HGNC, ROR, SciCrunch RRID resolver, Crossref and DataCite
(DOI status). Every online answer is stored with the date it was fetched.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

# Spellings as they appear in the papers' tables -> canonical lower-case query names.
ALIASES: dict[str, str] = {
    "dimethyl fumerate": "dimethyl fumarate",
    "roflumist": "roflumilast",
    "trehelose": "trehalose",
    "b-ionone": "beta-ionone",
    "β-ionone": "beta-ionone",
    "mfge-8": "mfge8",
    "mfg-e8": "mfge8",
    "isothiocyanate": "sulforaphane",
    "l-sulforaphane": "sulforaphane",
    "jasplak": "jasplakinolide",
    "tubastatina": "tubastatin a",
    "dpn": "diarylpropionitrile",
    "aicar and tudca": "aicar + tudca",
    "sim + res": "simvastatin + resveratrol",
    "bms-777607": "bms777607",
    "neca": "5'-n-ethylcarboxamidoadenosine",
    "tauroursodeoxycholic acid (tudca)": "tauroursodeoxycholic acid",
    "tudca": "tauroursodeoxycholic acid",
    "4-pba": "4-phenylbutyric acid",
    "ga max efficiency": "geneart max efficiency transformation reagent for algae",
    "geneart": "geneart max efficiency transformation reagent for algae",
    "m-n": "m-n medium (no enzyme)",
    "m−n": "m-n medium (no enzyme)",
}

# Names that PubChem may resolve to the wrong record; the expected molecular formula guards them.
EXPECTED_FORMULA: dict[str, str] = {
    "g-1": "C21H18BrNO3",
    "rgd": "C12H22N6O6",
    "740 y-p": None,  # peptide, no single-formula guard
}

_PAREN = re.compile(r"\s*\((?:[^()]*;[^()]*|a gift from[^()]*|[^()]*cat\.?\s*no[^()]*)\)\s*", re.I)


def normalize(name: str) -> str:
    n = _PAREN.sub(" ", name).strip().lower()
    n = re.sub(r"\s+", " ", n)
    return ALIASES.get(n, n)


def citation_key(text: str) -> str:
    """Stable cache key for a free-text citation: lower-case, spacing normalised, first 80 characters."""
    t = re.sub(r"\s+([.,;:])", r"\1", text.lower())
    t = re.sub(r"\s+", " ", t).strip()
    return "citation:" + t[:80]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Resolver:
    def __init__(self, cache_path: Path | str, online: bool = False, pause: float = 0.25):
        self.cache_path = Path(cache_path)
        self.online = online
        self.pause = pause
        self.misses: list[str] = []
        self.cache: dict = json.loads(self.cache_path.read_text(encoding="utf-8")) if self.cache_path.exists() else {}
        self._session = None

    # -- infrastructure -------------------------------------------------------------------
    def _get(self, key: str, fetch):
        if key in self.cache:
            return self.cache[key]
        if not self.online:
            self.misses.append(key)
            return None
        try:
            value = fetch()
        except Exception as exc:  # transport errors are reported but not cached, so a later run retries
            print(f"resolve error for {key}: {str(exc)[:120]}")
            self.misses.append(key)
            return None
        if value is not None:
            value = dict(value, fetchedAt=_now())
        self.cache[key] = value
        time.sleep(self.pause)
        return value

    def _http(self, url: str, **kw):
        import requests  # imported lazily so offline use has no dependency at import time
        if self._session is None:
            self._session = requests.Session()
            self._session.headers["User-Agent"] = "portolan-nrr-pilot/0.2 (contact@portolansoft.com)"
        for attempt in range(4):
            r = self._session.get(url, timeout=30, **kw)
            if r.status_code in (429, 503) and attempt < 3:
                time.sleep(2 * (attempt + 1) ** 2)
                continue
            r.raise_for_status()
            return r
        raise RuntimeError("unreachable")

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8")

    # -- resolvers ------------------------------------------------------------------------
    def compound(self, name: str) -> dict | None:
        q = normalize(name)
        def fetch():
            from urllib.parse import quote
            # two light calls (name -> CID, CID -> properties) are throttled less than one heavy name query
            r = self._http(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(q)}/cids/JSON")
            cids = r.json().get("IdentifierList", {}).get("CID", [])
            if not cids:
                return {"unresolved": True}
            time.sleep(self.pause)
            r = self._http(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cids[0]}/property/MolecularFormula,InChIKey,IUPACName,Title/JSON")
            props = r.json()["PropertyTable"]["Properties"][0]
            expected = EXPECTED_FORMULA.get(q)
            if expected and props.get("MolecularFormula") != expected:
                return {"unresolved": True, "reason": f"PubChem formula {props.get('MolecularFormula')} != expected {expected}"}
            return {"identifier": f"pubchem:CID{props['CID']}", "label": props.get("Title", q), "formula": props.get("MolecularFormula"),
                    "inchikey": props.get("InChIKey"), "iupac": props.get("IUPACName"), "source": "PubChem PUG REST name lookup"}
        return self._get(f"compound:{q}", fetch)

    def protein(self, gene: str, taxon: int = 9606) -> dict | None:
        q = gene.upper()
        def fetch():
            r = self._http("https://rest.uniprot.org/uniprotkb/search", params={"query": f"gene_exact:{q} AND organism_id:{taxon} AND reviewed:true", "fields": "accession,protein_name,gene_primary", "format": "json"})
            res = r.json()["results"]
            if not res:
                return {"unresolved": True}
            e = res[0]
            return {"identifier": f"uniprot:{e['primaryAccession']}", "label": e["proteinDescription"]["recommendedName"]["fullName"]["value"], "gene": q, "source": "UniProt REST"}
        return self._get(f"protein:{q}:{taxon}", fetch)

    def ontology(self, label: str, ontologies: tuple[str, ...] = ("obi", "mondo", "cl", "go")) -> dict | None:
        q = label.strip().lower()
        def fetch():
            r = self._http("https://www.ebi.ac.uk/ols4/api/search", params={"q": label, "ontology": ",".join(ontologies), "exact": "true", "rows": 5})
            docs = r.json()["response"]["docs"]
            docs = [d for d in docs if d.get("ontology_name") in ontologies and d.get("obo_id")]
            if not docs:
                return {"unresolved": True}
            d = docs[0]
            return {"identifier": d["obo_id"], "label": d["label"], "ontology": d["ontology_name"], "source": "OLS4 exact search"}
        return self._get(f"ontology:{q}", fetch)

    def cell_line(self, name: str) -> dict | None:
        q = name.strip()
        def fetch():
            r = self._http("https://api.cellosaurus.org/search/cell-line", params={"q": q, "fields": "id,ac,ox", "format": "json"})
            lines = r.json()["Cellosaurus"]["cell-line-list"]
            for cl in lines:
                names = [n["value"] for n in cl.get("name-list", [])]
                if q in names:
                    ac = [a["value"] for a in cl["accession-list"] if a["type"] == "primary"][0]
                    return {"identifier": f"RRID:{ac}", "label": q, "taxon": [f"NCBITaxon:{s['accession']}" for s in cl.get("species-list", [])], "source": "Cellosaurus API"}
            return {"unresolved": True}
        return self._get(f"cellline:{q}", fetch)

    def gene(self, symbol: str) -> dict | None:
        q = symbol.upper()
        def fetch():
            r = self._http(f"https://rest.genenames.org/fetch/symbol/{q}", headers={"Accept": "application/json"})
            docs = r.json()["response"]["docs"]
            if not docs:
                return {"unresolved": True}
            d = docs[0]
            return {"identifier": d["hgnc_id"], "label": d["symbol"], "name": d.get("name"), "ensembl": d.get("ensembl_gene_id"), "entrez": d.get("entrez_id"), "uniprot": d.get("uniprot_ids"), "source": "HGNC REST"}
        return self._get(f"gene:{q}", fetch)

    def taxon(self, name: str) -> dict | None:
        """NCBI Taxonomy id for a scientific name (esearch); cache key and value match the hand-entered taxon entries."""
        q = name.strip()
        def fetch():
            r = self._http("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params={"db": "taxonomy", "term": q, "retmode": "json"})
            ids = r.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return {"unresolved": True}
            return {"identifier": f"NCBITaxon:{ids[0]}", "label": q, "source": "NCBI Taxonomy esearch"}
        return self._get(f"taxon:{q}", fetch)

    def organization(self, name: str) -> dict | None:
        q = name.strip()
        def fetch():
            r = self._http("https://api.ror.org/v2/organizations", params={"query": q})
            for it in r.json().get("items", []):
                names = [n["value"] for n in it.get("names", [])]
                if any(q.lower() in n.lower() for n in names):
                    display = [n["value"] for n in it["names"] if "ror_display" in n.get("types", [])]
                    return {"identifier": it["id"], "label": display[0] if display else names[0], "source": "ROR v2 API"}
            return {"unresolved": True}
        return self._get(f"org:{q.lower()}", fetch)

    def rrid(self, rrid: str) -> dict | None:
        q = rrid.replace("RRID:", "")
        def fetch():
            r = self._http(f"https://scicrunch.org/resolver/RRID:{q}.json")
            hits = r.json().get("hits", {}).get("hits", [])
            if not hits:
                return {"unresolved": True}
            item = hits[0]["_source"].get("item", {})
            return {"identifier": f"RRID:{q}", "label": item.get("name"), "source": "SciCrunch resolver"}
        return self._get(f"rrid:{q}", fetch)

    def citation_doi(self, citation: str) -> dict | None:
        """Resolve a free-text citation to a DOI with Crossref's bibliographic search, guarded by
        first-author and year agreement. Returns None when unresolved or offline-miss."""
        key = citation_key(citation)
        def fetch():
            r = self._http("https://api.crossref.org/works", params={"query.bibliographic": citation[:300], "rows": 3})
            items = r.json()["message"]["items"]
            years = set(re.findall(r"\((\d{4})\)", citation))
            low = citation.lower()
            for it in items:
                fam = ((it.get("author") or [{}])[0].get("family") or "").lower()
                iy = str((it.get("issued", {}).get("date-parts") or [[None]])[0][0])
                if fam and fam in low and (not years or iy in years):
                    return {"doi": it["DOI"].lower(), "title": (it.get("title") or [""])[0][:200], "score": it.get("score"), "source": "Crossref query.bibliographic"}
            return {"unresolved": True}
        val = self._get(key, fetch)
        if not val or val.get("unresolved") or "error" in val:
            return None
        return val

    def doi_status(self, doi: str) -> dict:
        d = doi.lower().replace("https://doi.org/", "").replace("doi:", "")
        def fetch():
            try:
                r = self._http(f"https://api.crossref.org/works/{d}")
                m = r.json()["message"]
                updates = m.get("update-to") or []
                integrity = "none"
                for u in updates:
                    t = (u.get("type") or "").lower()
                    if "retract" in t:
                        integrity = "retracted"
                    elif "concern" in t:
                        integrity = "expression-of-concern"
                    elif "correct" in t or "errat" in t:
                        integrity = "corrected"
                version = "VoR" if m.get("type") == "journal-article" else "preprint" if m.get("type") == "posted-content" else "unknown"
                return {"version": version, "integrity": integrity, "assertedBy": "crossref-relation", "checkedAt": _now(),
                        "title": (m.get("title") or [""])[0][:200], "type": m.get("type"), "container": (m.get("container-title") or [""])[0],
                        "publishedOnline": m.get("published-online", {}).get("date-parts", [[None]])[0]}
            except Exception:
                r = self._http(f"https://api.datacite.org/dois/{d}")
                a = r.json()["data"]["attributes"]
                rtg = (a.get("types") or {}).get("resourceTypeGeneral")
                return {"version": "dataset" if rtg == "Dataset" else "v1", "integrity": "none", "assertedBy": "datacite",
                        "checkedAt": _now(), "title": (a.get("titles") or [{}])[0].get("title", "")[:200], "type": rtg,
                        "publisher": a.get("publisher"), "state": a.get("state")}
        val = self._get(f"doi:{d}", fetch)
        if val is None or "error" in val:
            return {"version": "unknown", "integrity": "unknown", "assertedBy": "not-checked", "checkedAt": _now(), "note": "offline or lookup failed"}
        return val
