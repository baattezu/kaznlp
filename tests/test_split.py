import pytest

from kaznlp.split import temporal_split


def make_records(n):
    return [{"id": i, "date": f"2026-09-{i + 1:02d}"} for i in range(n)]


def test_sizes_follow_ratios():
    parts = temporal_split(make_records(20))
    assert [len(parts[k]) for k in ("train", "val", "test")] == [14, 3, 3]


def test_split_is_chronological_even_if_input_is_shuffled():
    records = list(reversed(make_records(20)))
    parts = temporal_split(records)
    assert max(r["date"] for r in parts["train"]) < min(r["date"] for r in parts["val"])
    assert max(r["date"] for r in parts["val"]) < min(r["date"] for r in parts["test"])


def test_records_with_same_date_stay_together():
    records = [{"date": "2026-09-01"}] * 3 + [{"date": "2026-09-02"}] * 3
    parts = temporal_split(records, ratios=(0.5, 0.25, 0.25))
    assert len(parts["train"]) == 3
    assert {r["date"] for r in parts["train"]} == {"2026-09-01"}


def test_datetime_with_time_part():
    records = [{"date": "2026-09-01T10:00:00"}, {"date": "2026-09-01T09:00:00"}]
    parts = temporal_split(records, ratios=(0.5, 0.5, 0.0))
    assert parts["train"][0]["date"] == "2026-09-01T09:00:00"


@pytest.mark.parametrize("ratios", [(0.5, 0.5, 0.5), (0.7, 0.3), (1.2, -0.1, -0.1)])
def test_bad_ratios(ratios):
    with pytest.raises(ValueError):
        temporal_split(make_records(5), ratios=ratios)
