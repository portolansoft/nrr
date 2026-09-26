from nrr.ingest.common import INGEST_DATE, status_at_check
from nrr.resolve import Resolver


def test_offline_status_miss_uses_ingest_date_not_wall_clock(tmp_path):
    p = tmp_path / "ids.json"
    p.write_text("{}")
    st = status_at_check(Resolver(p, online=False), "10.9999/never-resolved")
    assert st["checkedAt"] == INGEST_DATE
    assert st["assertedBy"] == "not-checked"
