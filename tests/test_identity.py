from nrr.identity import canonical_json, content_address


def test_key_order_does_not_change_address():
    a = {"b": 1, "a": [1, 2, {"z": 1, "y": 2}]}
    b = {"a": [1, 2, {"y": 2, "z": 1}], "b": 1}
    assert content_address(a) == content_address(b)


def test_value_change_changes_address():
    assert content_address({"a": 1}) != content_address({"a": 2})


def test_address_ignores_identity_fields():
    base = {"question": "q"}
    with_id = {"question": "q", "@id": "urn:x", "contentAddress": "abc", "dateCreated": "2026-01-01T00:00:00Z"}
    assert content_address(base) == content_address(with_id)


def test_address_ignores_registry_derived_has_part():
    assert content_address({"q": 1, "hasPart": ["a"]}) == content_address({"q": 1, "hasPart": ["a", "b"]})


def test_address_format():
    addr = content_address({"a": 1})
    assert addr.startswith("urn:portolan:nrr:sha256:")
    assert len(addr.split(":")[-1]) == 64


def test_canonical_json_is_compact_and_sorted():
    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'
