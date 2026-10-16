"""Post-deploy acceptance checks for the council fixes (william, 2026-10-16).

Runs against the live API (stdlib only), so it is not part of CI. Run it after every
deploy or data reload:

    python eval/acceptance.py [--api https://scholarly-pattern-explorer.onrender.com]

Exit code 0 means every check passed. Today (hash embedder, 14,159-paper front-loaded
corpus) the growth and search-quality checks are EXPECTED to fail. They should pass once
the even monthly re-sample and the bge-small switch land; that is the merge/release gate.
"""
import argparse, json, re, sys, time, urllib.parse, urllib.request

SUBFIELD_FILTER = "type:article,primary_topic.subfield.id:subfields/1702"  # same as pipeline/ingest.py
ROUTES = ["health", "stats", "countries", "countries/collaborations", "patterns",
          "patterns?trend=gap", "patterns?trend=emerging", "runs", "galaxy?limit=600",
          "search?q=learning"]
CANCER = re.compile(r"cancer|tumou?r|oncolog|carcinoma|malignan|neoplas|lesion|metasta", re.I)


def get(url, timeout=60):
    t = time.time()
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, json.load(r), time.time() - t


def search(api, q):
    _, d, dt = get(f"{api}/search?q={urllib.parse.quote(q)}")
    return d.get("results", []), dt


def openalex_count(start, end):
    url = ("https://api.openalex.org/works?per_page=1&filter="
           f"from_publication_date:{start},to_publication_date:{end},{SUBFIELD_FILTER}")
    return get(url)[1]["meta"]["count"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://scholarly-pattern-explorer.onrender.com")
    ap.add_argument("--growth-tolerance-pp", type=float, default=5.0)
    a = ap.parse_args()
    api = a.api.rstrip("/") + "/api/v1"
    results = []

    def check(name, ok, detail):
        results.append(ok)
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    try:  # Render free tier cold-starts in ~50 s; warm it before timing anything
        get(f"{api}/health", timeout=120)
    except Exception as e:
        check("warm-up /health", False, repr(e)); return 1

    # 1. Every route answers 200 within 10 s once warm (council S4: no 200 s hangs)
    for r in ROUTES:
        try:
            st, _, dt = get(f"{api}/{r}", timeout=30)
            check(f"route /{r}", st == 200 and dt < 10, f"HTTP {st} in {dt:.1f}s")
        except Exception as e:
            check(f"route /{r}", False, repr(e))

    # 2. Growth (council C1/C2 + kill criterion 11.6)
    countries = get(f"{api}/countries")[1]
    shown = [c for c in countries if c.get("growth_pct") is not None]
    small = [c["code"] for c in shown
             if min(c.get("growth_cur_count") or 0, c.get("growth_prev_count") or 0) < 30]
    check("growth: 30-paper minimum in both periods", not small,
          f"{len(shown)} countries show growth; below minimum: {small or 'none'}")
    steep = [c["code"] for c in shown if c["growth_pct"] < -50]
    check("growth: kill criterion (most countries not in steep decline)",
          bool(shown) and len(steep) * 2 < len(shown),
          f"{len(steep)} of {len(shown)} shown countries below -50%")
    if shown:
        start, end = shown[0]["growth_window_start"], shown[0]["growth_window_end"]
        cur = sum(c.get("growth_cur_count") or 0 for c in countries)
        prev = sum(c.get("growth_prev_count") or 0 for c in countries)
        ours = (cur / prev - 1) * 100 if prev else float("nan")
        p_start, p_end = f"{int(start[:4]) - 1}{start[4:]}", f"{int(end[:4]) - 1}{end[4:]}"
        oa = (openalex_count(start, end) / openalex_count(p_start, p_end) - 1) * 100
        check("growth: corpus YTD growth matches OpenAlex",
              abs(ours - oa) <= a.growth_tolerance_pp,
              f"ours {ours:+.1f}% vs OpenAlex {oa:+.1f}% ({start}..{end} vs same months last year)")

    # 3. Search quality (council S1/S2; queries from eval-embedder set)
    hits, _ = search(api, "teaching computers to spot tumours in medical scans")
    n = sum(bool(CANCER.search(h.get("title", ""))) for h in hits[:5])
    check("search: paraphrase 'tumours in medical scans' top-5 mostly on topic", n >= 3,
          f"{n}/5 cancer/tumour titles; #1 = {hits[0]['title'][:70] if hits else 'none'}")
    for q in ["dark matter detection", "coral reef bleaching"]:
        hits, _ = search(api, q)
        check(f"search: out-of-corpus '{q}' shows no close matches", not hits,
              f"{len(hits)} results returned")

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
