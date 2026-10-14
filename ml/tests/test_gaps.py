import json

from ml.gaps import counts_from_works, find_gaps, load_inputs

LAST = 2025


def synthetic():
    return {
        # small but doubling every year -> gap
        "Quantum Machine Learning": {2022: 6, 2023: 12, 2024: 24, 2025: 48},
        # large and flat -> not a gap
        "Natural Language Processing": {2022: 900, 2023: 910, 2024: 905, 2025: 915},
        # large and growing slowly
        "Machine Learning in Healthcare": {2022: 400, 2023: 440, 2024: 480, 2025: 520},
        # one-off spike in 2024 -> damped
        "Spiky Topic": {2022: 10, 2023: 10, 2024: 80, 2025: 10},
        # too few papers -> ignored
        "Tiny Topic": {2022: 1, 2023: 2, 2024: 4, 2025: 8},
    }


def test_gap_detected_and_ranked_first():
    gaps = find_gaps(synthetic(), {"Quantum Machine Learning": [["CA", 3.5], ["PK", 2.0]]},
                     last_year=LAST)
    assert gaps and gaps[0]["topic"] == "Quantum Machine Learning"
    g = gaps[0]
    assert g["growth_rate"] > 0.5 and g["paper_count"] == 90
    assert g["top_countries"] == ["CA", "PK"]
    assert (g["window_start"], g["window_end"]) == (2022, 2025)


def test_steady_large_topic_not_flagged():
    topics = {g["topic"] for g in find_gaps(synthetic(), last_year=LAST)}
    assert "Natural Language Processing" not in topics
    assert "Machine Learning in Healthcare" not in topics


def test_one_off_spike_damped():
    gaps = find_gaps(synthetic(), last_year=LAST)
    assert "Spiky Topic" not in {g["topic"] for g in gaps}


def test_min_counts_filter_noise():
    assert "Tiny Topic" not in {g["topic"] for g in find_gaps(synthetic(), last_year=LAST)}


def test_incomplete_current_year_ignored():
    data = synthetic()
    data["Quantum Machine Learning"][2026] = 1   # partial year must not count
    assert find_gaps(data, last_year=LAST)[0]["topic"] == "Quantum Machine Learning"


def test_string_years_from_json():
    data = {t: {str(y): n for y, n in v.items()} for t, v in synthetic().items()}
    assert find_gaps(data, last_year=LAST)[0]["topic"] == "Quantum Machine Learning"


def _works():
    rows, i = [], 0
    for year, n in {2022: 6, 2023: 12, 2024: 24, 2025: 48}.items():
        for _ in range(n):
            i += 1
            rows.append({"id": f"W{i}", "title": "q", "year": year, "topics": ["QML"],
                         "countries": ["CA", "PK"] if i % 2 else ["CA"]})
    for year in (2022, 2023, 2024, 2025):
        for _ in range(300):
            i += 1
            rows.append({"id": f"W{i}", "title": "n", "year": year, "topics": ["NLP"],
                         "countries": ["US"]})
    return rows


def test_counts_from_works_fractional():
    tyc, top = counts_from_works(_works())
    assert tyc["QML"] == {2022: 6, 2023: 12, 2024: 24, 2025: 48}
    assert top["QML"][0][0] == "CA"
    assert abs(sum(v for _, v in top["QML"]) - 90) < 1e-6   # each paper weighs 1


def test_load_prefers_snapshot(tmp_path):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps({"topic_year_counts": synthetic(),
                                "topic_top_countries": {"Quantum Machine Learning": [["PK", 9]]}}))
    works = tmp_path / "works_v2.jsonl"
    works.write_text("\n".join(json.dumps(r) for r in _works()))
    tyc, top, src = load_inputs(snap, works)
    assert src == "snapshot" and find_gaps(tyc, top, last_year=LAST)[0]["top_countries"] == ["PK"]


def test_load_falls_back_to_works(tmp_path):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps({"countries": []}))    # today's snapshot: no topic_year_counts
    works = tmp_path / "works_v2.jsonl"
    works.write_text("\n".join(json.dumps(r) for r in _works()))
    tyc, top, src = load_inputs(snap, works)
    assert src == "works"
    gaps = find_gaps(tyc, top, last_year=LAST)
    assert [g["topic"] for g in gaps] == ["QML"] and gaps[0]["top_countries"][0] == "CA"
