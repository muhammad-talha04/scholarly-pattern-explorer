"""Export a SMALL, shareable snapshot of the latest results for GitHub.

The raw data (1 GB JSONL, 200 MB DuckDB) must never go to GitHub: GitHub
rejects files over 100 MB, and the data is rebuildable anyway. What people
want to see is the RESULT, so this script writes only small files:

  docs/
    LATEST.md                          human-readable weekly report
    data/summary.json                  headline numbers + timestamp
    data/emerging_patterns.csv         topic pairs growing the most
    data/declining_patterns.csv        topic pairs fading the most
    data/latest_window_patterns.csv    strongest patterns in the newest window
    data/top_collaborators.csv         most connected authors, newest window
    data/link_metrics.csv              AUC / AP of each link-prediction model
    data/predicted_collaborations.csv  top predicted author pairs
    charts/papers_per_year.png
    charts/pattern_lifecycles.png
    charts/coauthor_network.png
    charts/link_model_auc.png

It also refreshes the block between these two markers in README.md, if present:
  <!-- SNAPSHOT:START -->
  <!-- SNAPSHOT:END -->

Run:  python export_snapshot.py --db data/openalex.duckdb --out docs
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # draw to files; no window needed
import matplotlib.pyplot as plt
import pandas as pd

import analytics as A
from dbconn import DB


def table_exists(db: DB, name: str) -> bool:
    try:
        db.df(f"SELECT 1 FROM {name} LIMIT 1")
        return True
    except Exception:                                          # noqa: BLE001
        return False


def emerging_declining(db: DB, top: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Same logic as mine_windows.emerging_report, returned instead of printed."""
    df = db.df("""
        WITH ranked AS (
            SELECT itemset, window_start, support,
                   ROW_NUMBER() OVER (PARTITION BY itemset ORDER BY window_start)      AS rn_first,
                   ROW_NUMBER() OVER (PARTITION BY itemset ORDER BY window_start DESC) AS rn_last
            FROM patterns WHERE k >= 2
        )
        SELECT f.itemset,
               f.window_start AS first_window, ROUND(f.support, 4) AS first_support,
               l.window_start AS last_window,  ROUND(l.support, 4) AS last_support,
               ROUND(l.support - f.support, 4) AS change
        FROM ranked f JOIN ranked l
          ON l.itemset = f.itemset AND f.rn_first = 1 AND l.rn_last = 1
        ORDER BY change DESC
    """)
    if df.empty:
        return df, df
    return df.head(top).reset_index(drop=True), df.tail(top).iloc[::-1].reset_index(drop=True)


def top_collaborators(edges: pd.DataFrame, top: int) -> pd.DataFrame:
    if edges.empty:
        return pd.DataFrame(columns=["author", "collaborators", "joint_papers"])
    long = pd.concat([
        edges.rename(columns={"author_a": "author", "author_b": "other"}),
        edges.rename(columns={"author_b": "author", "author_a": "other"}),
    ])
    return (long.groupby("author")
                .agg(collaborators=("other", "nunique"), joint_papers=("papers", "sum"))
                .sort_values(["collaborators", "joint_papers"], ascending=False)
                .head(top).reset_index())


def chart_papers_per_year(db: DB, path: Path) -> None:
    df = db.df("SELECT pub_year, COUNT(*) AS papers FROM works GROUP BY pub_year ORDER BY pub_year")
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(df.pub_year, df.papers, color="#4C72B0")
    ax.set_title("Papers per publication year")
    ax.set_xlabel("year"); ax.set_ylabel("papers")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def chart_lifecycles(db: DB, itemsets: list[str], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    if itemsets:
        ts = A.pattern_timeseries(db, itemsets)
        # pattern_timeseries returns long format: window_start, itemset, support
        for name, g in ts.groupby("itemset"):
            ax.plot(g.window_start, g.support, marker="o", ms=3, label=A.short_label(name))
        ax.legend(fontsize=7, loc="upper left", frameon=False)
    ax.set_title("Lifecycles of the fastest-growing topic pairs")
    ax.set_xlabel("window start year"); ax.set_ylabel("support")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def chart_network(edges: pd.DataFrame, title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 8))
    comp = A.largest_component(edges)
    pos, pairs = A.layout_graph(comp)
    for a, b in pairs:
        ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]], color="#bbbbbb", lw=0.6, zorder=1)
    if pos:
        degree = pd.concat([comp.author_a, comp.author_b]).value_counts()
        xs = [pos[n][0] for n in pos]; ys = [pos[n][1] for n in pos]
        sizes = [15 + 12 * degree.get(n, 1) for n in pos]
        ax.scatter(xs, ys, s=sizes, color="#DD8452", zorder=2)
        for n in degree.head(8).index:
            ax.annotate(n, pos[n], fontsize=7, zorder=3)
    ax.set_title(title); ax.axis("off")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def chart_link_metrics(metrics: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    if not metrics.empty:
        m = metrics.sort_values("auc")
        ax.barh(m.model, m.auc, color="#55A868")
        ax.set_xlim(0.5, 1.0)
    ax.set_title("Link prediction: AUC by model (0.5 = coin flip)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def md_table(df: pd.DataFrame, n: int = 10) -> str:
    if df.empty:
        return "_no rows_"
    d = df.head(n).astype(str)
    lines = ["| " + " | ".join(d.columns) + " |", "|" + "---|" * len(d.columns)]
    lines += ["| " + " | ".join(r) + " |" for r in d.itertuples(index=False, name=None)]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/openalex.duckdb")
    ap.add_argument("--out", default="docs")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--no-names", action="store_true",
                    help="publish OpenAlex author IDs instead of names")
    ap.add_argument("--readme", default="README.md")
    args = ap.parse_args()

    out = Path(args.out)
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "charts").mkdir(parents=True, exist_ok=True)

    db = DB(args.db)
    lo, hi = A.year_range(db)
    counts = A.corpus_summary(db).iloc[0].to_dict()
    wins = A.windows(db)
    latest = int(wins.window_start.max()) if not wins.empty else lo
    latest_end = int(wins.window_end.max()) if not wins.empty else hi

    emerging, declining = emerging_declining(db, args.top)
    latest_patterns = A.patterns_for_window(db, latest, min_k=2, limit=args.top)
    edges = A.coauthor_edges(db, latest, latest_end, min_papers=2, limit=600)
    collab = top_collaborators(edges, args.top)

    metrics = db.df("SELECT * FROM link_metrics ORDER BY auc DESC") \
        if table_exists(db, "link_metrics") else pd.DataFrame(columns=["model", "auc", "ap"])
    preds = pd.DataFrame(columns=["author_a", "author_b", "score"])
    if table_exists(db, "link_predictions"):
        if args.no_names:
            preds = db.df("SELECT author_a, author_b, ROUND(score, 3) AS score "
                          "FROM link_predictions ORDER BY score DESC LIMIT 100")
        else:
            preds = db.df("""
                SELECT a1.display_name AS author_a, a2.display_name AS author_b,
                       ROUND(p.score, 3) AS score
                FROM link_predictions p
                JOIN authors a1 ON a1.author_id = p.author_a
                JOIN authors a2 ON a2.author_id = p.author_b
                ORDER BY p.score DESC LIMIT 100
            """)
    if args.no_names:
        collab["author"] = "hidden"

    # ---- data files ----
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    summary = {
        "generated_at": stamp,
        "year_range": [lo, hi],
        "latest_window": [latest, latest_end],
        **{k: int(v) for k, v in counts.items()},
    }
    (out / "data" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    emerging.to_csv(out / "data" / "emerging_patterns.csv", index=False)
    declining.to_csv(out / "data" / "declining_patterns.csv", index=False)
    latest_patterns.to_csv(out / "data" / "latest_window_patterns.csv", index=False)
    collab.to_csv(out / "data" / "top_collaborators.csv", index=False)
    metrics.to_csv(out / "data" / "link_metrics.csv", index=False)
    preds.to_csv(out / "data" / "predicted_collaborations.csv", index=False)

    # ---- charts ----
    chart_papers_per_year(db, out / "charts" / "papers_per_year.png")
    chart_lifecycles(db, emerging.itemset.head(6).tolist() if not emerging.empty else [],
                     out / "charts" / "pattern_lifecycles.png")
    net_edges = edges.copy()
    if args.no_names:
        net_edges[["author_a", "author_b"]] = net_edges[["author_a", "author_b"]].apply(
            lambda c: c.map(lambda s: f"a{abs(hash(s)) % 10**6}"))
    chart_network(net_edges, f"Co-authorship network, {latest}-{latest_end} (largest group)",
                  out / "charts" / "coauthor_network.png")
    chart_link_metrics(metrics, out / "charts" / "link_model_auc.png")
    db.close()

    # ---- report ----
    report = f"""# Weekly snapshot

_Generated {stamp}. Corpus: {summary['works']:,} papers, {summary['authors']:,} authors,
{summary['topics']:,} topics, publication years {lo}-{hi}._

![papers per year](charts/papers_per_year.png)

## Emerging topic pairs
{md_table(emerging)}

![lifecycles](charts/pattern_lifecycles.png)

## Declining topic pairs
{md_table(declining)}

## Strongest patterns in {latest}-{latest_end}
{md_table(latest_patterns)}

## Collaboration network, {latest}-{latest_end}
{md_table(collab)}

![network](charts/coauthor_network.png)

## Link prediction
{md_table(metrics)}

![auc](charts/link_model_auc.png)

Top predicted collaborations: [data/predicted_collaborations.csv](data/predicted_collaborations.csv)
"""
    (out / "LATEST.md").write_text(report, encoding="utf-8")

    # ---- README block ----
    readme = Path(args.readme)
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        block = (f"<!-- SNAPSHOT:START -->\n"
                 f"**Last automatic update:** {stamp} · {summary['works']:,} papers · "
                 f"[full weekly report]({args.out}/LATEST.md)\n\n"
                 f"![pattern lifecycles]({args.out}/charts/pattern_lifecycles.png)\n"
                 f"<!-- SNAPSHOT:END -->")
        new = re.sub(r"<!-- SNAPSHOT:START -->.*?<!-- SNAPSHOT:END -->", block,
                     text, flags=re.S)
        if new != text:
            readme.write_text(new, encoding="utf-8")
            print(f"updated snapshot block in {readme}")

    print(f"snapshot written to {out}/")


if __name__ == "__main__":
    main()
