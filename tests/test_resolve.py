import json

import pytest

from nrr.resolve import ALIASES, Resolver, citation_key, normalize


@pytest.fixture
def cache(tmp_path):
    p = tmp_path / "identifiers.json"
    p.write_text(json.dumps({
        "compound:ripasudil": {"identifier": "pubchem:CID9863672", "label": "ripasudil", "inchikey": "QSKQVZWVLOIIEV-NSHDSACASA-N"},
        "doi:10.1038/s41586-026-10652-y": {"version": "VoR", "integrity": "none", "assertedBy": "crossref-relation", "checkedAt": "2026-09-25T00:00:00Z"},
    }))
    return p


def test_offline_hit_returns_cached_entry(cache):
    r = Resolver(cache, online=False)
    assert r.compound("Ripasudil")["identifier"] == "pubchem:CID9863672"


def test_offline_miss_returns_none_and_is_recorded(cache):
    r = Resolver(cache, online=False)
    assert r.compound("unobtainium") is None
    assert "compound:unobtainium" in r.misses


def test_doi_status_offline_uses_cache(cache):
    r = Resolver(cache, online=False)
    assert r.doi_status("10.1038/s41586-026-10652-y")["integrity"] == "none"


def test_doi_status_offline_miss_is_unknown(cache):
    r = Resolver(cache, online=False)
    st = r.doi_status("10.9999/nope")
    assert st["version"] == "unknown" and st["integrity"] == "unknown"


def test_aliases_normalise_table_spellings():
    assert normalize("Dimethyl fumerate") == "dimethyl fumarate"
    assert normalize("Roflumist") == "roflumilast"
    assert normalize("trehelose") == "trehalose"
    assert normalize("B-Ionone") == "beta-ionone"
    assert normalize("MFGE-8") == "mfge8"
    assert "isothiocyanate" in ALIASES


def test_normalize_strips_vendor_parentheticals():
    assert normalize("Y-27632 (Cayman Chemical Company; Cat. No. 10005583)") == "y-27632"


def test_citation_doi_offline_uses_cache(tmp_path):
    p = tmp_path / "identifiers.json"
    key = citation_key("Sun, C.-C., Chiu, H.-T., Lin, Y .-F., Lee, K.-Y . & Pang, J.-H. S. Y-27632, a ROCK Inhibitor, Promoted ...")
    assert key.startswith("citation:sun, c.-c., chiu, h.-t., lin, y.-f.")
    p.write_text(json.dumps({key: {"doi": "10.1371/journal.pone.0144571", "score": 0.9}}))
    r = Resolver(p, online=False)
    assert r.citation_doi("Sun, C.-C., Chiu, H.-T., Lin, Y .-F., Lee, K.-Y . & Pang, J.-H. S. Y-27632, a ROCK Inhibitor, Promoted ...")["doi"] == "10.1371/journal.pone.0144571"
    assert r.citation_doi("Nobody. Nothing. Nowhere 1, 1 (1900).") is None
