from pipeline.country_stats import tally, specialized_topics


def _w(i, cs, topics):
    return {"id": f"W{i}", "year": 2025, "countries": cs, "topics": topics}


def _corpus():
    ws, i = [], 0
    # Big country A: mostly "AI", some "Quantum". Small country B: specialises in "Seismology".
    for _ in range(60):
        ws.append(_w(i, ["AA"], ["AI"])); i += 1
    for _ in range(20):
        ws.append(_w(i, ["AA"], ["Quantum"])); i += 1
    for _ in range(15):
        ws.append(_w(i, ["BB"], ["AI"])); i += 1
    for _ in range(12):
        ws.append(_w(i, ["BB"], ["Seismology"])); i += 1
    for _ in range(3):
        ws.append(_w(i, ["BB"], ["Rare"])); i += 1
    return ws


def test_lq_ranks_specialty_above_dominant_topic():
    t = tally(_corpus())
    b = specialized_topics(t, "BB")
    assert b[0]["name"] == "Seismology"
    assert b[0]["lq"] > 1 > next(x["lq"] for x in b if x["name"] == "AI")


def test_min_count_filters_tiny_topics():
    t = tally(_corpus())
    assert "Rare" not in [x["name"] for x in specialized_topics(t, "BB")]


def test_unknown_country_is_empty():
    assert specialized_topics(tally(_corpus()), "ZZ") == []
