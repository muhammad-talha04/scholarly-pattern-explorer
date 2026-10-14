"""
STEP 4b: the visualizer - a dark research dashboard over one database.

Run it:   streamlit run app.py      then open http://localhost:8501

What you can do
---------------
  Sidebar  : pick a DATASET (every .duckdb file in data/) and a COUNTRY
             (All countries, or any country from a scrollable, searchable list)
  Views    : World · Raw data · Mined patterns · Lifecycles · Co-authorship ·
             Link prediction

Rules this file keeps
---------------------
  * NO SQL here. Every query lives in analytics.py (testable from the CLI).
  * Look & feel live in ui_style.py and .streamlit/config.toml.

Why it no longer hangs when you switch views
--------------------------------------------
  1. The database is opened READ-ONLY and every query uses its own cursor.
     One DuckDB connection shared between Streamlit threads was the main
     cause of freezes.
  2. Every query AND the slow network layout are cached (cache key includes
     dataset + country + window), so revisiting a view is instant.
  3. Only the selected view runs its queries, and the controls inside a view
     live in st.fragment blocks, so moving one of them reruns only that block.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analytics as A
import countries as C
import ui_style as U
from dbconn import DB

st.set_page_config(page_title="Scholarly Pattern Explorer", page_icon=":material/hub:",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(U.CSS, unsafe_allow_html=True)

DATA_DIR = Path("data")
DATASET_NAMES = {           # friendly names for known files; others use the file name
    "openalex": "AI · global (cited 20+)",
    "canada": "CS · Canada (cited 10+)",
    "sample": "Synthetic demo data",
}
VIEWS = [":material/public: World",
         ":material/bar_chart: Raw data",
         ":material/auto_awesome: Mined patterns",
         ":material/timeline: Lifecycles",
         ":material/hub: Co-authorship",
         ":material/psychology: Link prediction"]
ALL = "__ALL__"


# ------------------------------------------------------------ data access ----

@st.cache_resource(show_spinner=False)
def get_db(path: str) -> DB:
    """One read-only connection per database file, shared by all sessions."""
    return DB(path, read_only=True)


@st.cache_data(show_spinner=False, ttl=3600, max_entries=1000)
def _run(_db, db_key: str, fn_name: str, args: tuple, kwargs: tuple):
    """Run analytics.<fn_name>(db, *args, **kwargs) once and remember it.
    `db_key` (the file path + modified time) joins the cache key so switching
    datasets, or rebuilding one, never shows stale numbers."""
    return getattr(A, fn_name)(_db, *args, **dict(kwargs))


def list_datasets() -> list[Path]:
    files = sorted(DATA_DIR.glob("*.duckdb"), key=lambda p: (p.stem != "openalex", p.stem))
    return [f for f in files if not f.stem.startswith(("ci", "_"))]


def dataset_label(p: Path) -> str:
    size = p.stat().st_size / 1e6
    return f"{DATASET_NAMES.get(p.stem, p.stem.replace('_', ' ').title())}  ·  {size:,.0f} MB"


# ---------------------------------------------------------------- sidebar ----

with st.sidebar:
    st.markdown(U.brand(), unsafe_allow_html=True)

    datasets = list_datasets()
    if not datasets:
        st.error("No .duckdb files in data/. Run build_db.py first.")
        st.stop()
    st.markdown(U.side_label("Dataset"), unsafe_allow_html=True)
    ds = st.selectbox("Dataset", datasets, format_func=dataset_label,
                      label_visibility="collapsed")
    db_path = str(ds)
    db_key = f"{db_path}:{ds.stat().st_mtime_ns}"


def q(fn_name: str, *args, **kwargs):
    """Cached analytics call. Same signature as the analytics function."""
    return _run(db, db_key, fn_name, args, tuple(sorted(kwargs.items())))


try:
    db = get_db(db_path)
    clist = q("country_list")
except Exception as exc:                                   # noqa: BLE001
    st.error(f"Could not open {db_path}: {exc}")
    st.info("If the weekly job is rebuilding this database right now, wait for it "
            "to finish and refresh. Otherwise run: python build_db.py")
    st.stop()

with st.sidebar:
    st.markdown(U.side_label("Country"), unsafe_allow_html=True)
    options = [ALL] + clist["country"].tolist()
    papers_by_c = dict(zip(clist["country"], clist["papers"]))
    mined_by_c = dict(zip(clist["country"], clist["mined"]))

    def country_fmt(code: str) -> str:
        if code == ALL:
            return "🌍  All countries"
        star = "" if mined_by_c.get(code) else "  ·  no patterns"
        return f"{C.label(code)}  ·  {int(papers_by_c.get(code, 0)):,} papers{star}"

    picked = st.selectbox("Country", options, format_func=country_fmt,
                          label_visibility="collapsed",
                          help="Scroll or start typing a country name. A paper "
                               "counts for a country when any author had an "
                               "institution there.")
    country = None if picked == ALL else picked
    if clist.empty:
        st.caption(f"Countries not available for this dataset yet. Run  \n"
                   f"`python mine_countries.py --db {db_path}`")

win = q("windows", country)
if win.empty:
    # A country with too few papers has no mined windows: fall back to the
    # whole-corpus windows so the raw data, map and network still work.
    win = q("windows")
    patterns_ok = False
else:
    patterns_ok = True
if win.empty:
    st.warning("No mined patterns in this database yet. Run: python mine_windows.py")
    st.stop()

labels = [f"{int(r.window_start)}–{int(r.window_end)}" for r in win.itertuples()]
with st.sidebar:
    st.markdown(U.side_label("Time window"), unsafe_allow_html=True)
    choice = st.select_slider("Three-year window", options=labels, value=labels[-1],
                              label_visibility="collapsed")
    with st.expander(":material/tune: Thresholds"):
        min_k = st.slider("Minimum topics per pattern", 1, 4, 2)
        min_lift = st.slider("Minimum lift for rules", 1.0, 5.0, 1.1, 0.1)
        min_papers = st.slider("Minimum shared papers (network)", 1, 6, 2)
    with st.expander(":material/help: Reading the numbers"):
        st.caption("**Support**: share of papers in the window containing every "
                   "topic of a pattern.  \n**Lift > 1**: two topics attract each "
                   "other more than their popularity explains.  \n**Country**: "
                   "papers with at least one author at an institution there.")

y0, y1 = (int(v) for v in choice.split("–"))
row = win[win.window_start == y0].iloc[0]
summary = q("corpus_summary", country).iloc[0]
scope_name = "All countries" if not country else C.name(country)

# ------------------------------------------------------------------- hero ----

st.markdown(U.hero(
    "Scholarly Pattern Explorer",
    "Which combinations of research topics are emerging — and which is the field abandoning?",
    [("Dataset", DATASET_NAMES.get(ds.stem, ds.stem)),
     ("Scope", f"{'🌍' if not country else C.flag(country)} {scope_name}"),
     ("Window", choice)],
), unsafe_allow_html=True)

st.markdown(U.kpis([
    ("Papers in window", f"{int(row.papers):,}" if patterns_ok else "—", choice),
    ("Patterns in window", f"{int(row.itemsets):,}" if patterns_ok else "—", "FP-Growth itemsets"),
    ("Papers", f"{int(summary.works):,}", scope_name),
    ("Authors", f"{int(summary.authors):,}", scope_name),
    ("Topics", f"{int(summary.topics):,}", "OpenAlex topics"),
    ("Countries", f"{len(clist):,}", "in this dataset"),
]), unsafe_allow_html=True)

view = st.segmented_control("View", VIEWS, default=VIEWS[1], label_visibility="collapsed",
                            key="view")
if view is None:
    view = VIEWS[1]


def chart(fig, filename: str) -> None:
    st.plotly_chart(fig, width="stretch", config={
        "displaylogo": False,
        "toImageButtonOptions": {"filename": filename, "format": "png", "scale": 2},
    })


def need_patterns() -> bool:
    if patterns_ok:
        return True
    n = int(papers_by_c.get(country, 0))
    st.info(f"No mined patterns for {scope_name} ({n:,} papers). Countries need at "
            f"least 300 papers to be mined reliably; smaller ones would only produce "
            f"noise. The World, Raw data and Co-authorship views still work.",
            icon=":material/info:")
    return False


def scope_text() -> str:
    return f"{choice} · {scope_name}"


# ------------------------------------------------------------------- views ----

if view == VIEWS[0]:                                                     # World
    cp = q("country_papers", y0, y1)
    if cp.empty:
        st.info("Country data is missing for this dataset. Run: "
                f"python mine_countries.py --db {db_path}")
    else:
        cp = cp.assign(iso3=cp.country.map(C.iso3), name=cp.country.map(C.name))
        with st.container(border=True):
            st.markdown(U.section("Where the research comes from",
                                  f"{choice} · papers with at least one author in each country"),
                        unsafe_allow_html=True)
            fig = px.choropleth(cp[cp.iso3 != ""], locations="iso3", color="papers",
                                hover_name="name", color_continuous_scale=U.AURORA,
                                projection="natural earth")
            fig.update_geos(bgcolor="rgba(0,0,0,0)", showframe=False,
                            showcoastlines=False, landcolor="#1A2440",
                            showland=True, showocean=True, oceancolor=U.PANEL,
                            lakecolor=U.PANEL, countrycolor="#2A3756")
            if country and C.iso3(country):
                fig.add_trace(go.Choropleth(
                    locations=[C.iso3(country)], z=[1], showscale=False,
                    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                    marker_line_color="#F472B6", marker_line_width=2.5, hoverinfo="skip"))
            chart(U.styled(fig, 520), "world_map")

        left, right = st.columns(2, gap="medium")
        with left, st.container(border=True):
            top = cp.head(15).iloc[::-1]
            st.markdown(U.section("Top 15 countries", f"{choice} · papers per country"),
                        unsafe_allow_html=True)
            fig = px.bar(top, x="papers", y=top.country.map(C.label), orientation="h",
                         color="papers", color_continuous_scale=U.AURORA)
            fig.update_layout(coloraxis_showscale=False, yaxis_title=None)
            chart(U.styled(fig, 480), "top_countries")
        with right, st.container(border=True):
            if country:
                partners = q("collaboration_partners", country, y0, y1, 15)
                st.markdown(U.section(f"{C.flag(country)} {scope_name}'s closest partners",
                                      f"{choice} · papers co-written with each country"),
                            unsafe_allow_html=True)
                if partners.empty:
                    st.info("No international co-authored papers in this window.")
                else:
                    p = partners.iloc[::-1]
                    fig = px.bar(p, x="papers", y=p.partner.map(C.label), orientation="h",
                                 color_discrete_sequence=[U.VIOLET])
                    fig.update_layout(yaxis_title=None)
                    chart(U.styled(fig, 480), f"partners_{country}")
            else:
                pairs = q("top_country_pairs", y0, y1, 15)
                st.markdown(U.section("Strongest international collaborations",
                                      f"{choice} · papers co-written by both countries"),
                            unsafe_allow_html=True)
                if pairs.empty:
                    st.info("No international co-authored papers in this window.")
                else:
                    pairs = pairs.assign(pair=pairs.country_a.map(C.label) + "  ↔  "
                                         + pairs.country_b.map(C.label)).iloc[::-1]
                    fig = px.bar(pairs, x="papers", y="pair", orientation="h",
                                 color_discrete_sequence=[U.VIOLET])
                    fig.update_layout(yaxis_title=None)
                    chart(U.styled(fig, 480), "country_pairs")

        with st.container(border=True):
            share = q("international_share", country)
            ppy = q("papers_per_year", country)
            st.markdown(U.section("Output and international collaboration over time",
                                  f"{scope_name} · bars = papers per year, line = share "
                                  "of papers with authors from 2+ countries"),
                        unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_bar(x=ppy.year, y=ppy.papers, name="papers",
                        marker=dict(color=U.TEAL, opacity=.55))
            fig.add_scatter(x=share.year, y=share.share, name="international share",
                            yaxis="y2", mode="lines+markers",
                            line=dict(color=U.PINK, width=3), marker=dict(size=5))
            fig.update_layout(yaxis2=dict(overlaying="y", side="right", tickformat=".0%",
                                          gridcolor="rgba(0,0,0,0)", showgrid=False),
                              legend=dict(orientation="h", y=1.08, x=0))
            chart(U.styled(fig, 380), f"output_{country or 'all'}")

elif view == VIEWS[1]:                                                  # Raw data
    with st.container(border=True):
        dist = q("topic_distribution", y0, y1, 20, country)
        st.markdown(U.section("Most frequent research topics",
                              f"{scope_text()} · top 20 topics by number of papers"),
                    unsafe_allow_html=True)
        if dist.empty:
            st.info("No papers in this window for this scope.")
        else:
            fig = px.bar(dist, x="papers", y="topic", orientation="h", color="papers",
                         color_continuous_scale=U.AURORA)
            fig.update_yaxes(categoryorder="total ascending", title=None)
            fig.update_layout(coloraxis_showscale=False)
            chart(U.styled(fig, 600), "tab1_topic_distribution")
            st.markdown(U.note("This is the raw data, before any mining: what the corpus "
                               "is about, not which topics travel together."),
                        unsafe_allow_html=True)

    with st.container(border=True):
        mat = q("cooccurrence_matrix", y0, y1, 12, country)
        st.markdown(U.section("Which topics appear together",
                              f"{scope_text()} · papers containing both topics"),
                    unsafe_allow_html=True)
        if mat.empty:
            st.info("Not enough data in this window to build a co-occurrence table.")
        else:
            fig = px.imshow(mat, aspect="auto", color_continuous_scale=U.SEQUENTIAL)
            fig.update_xaxes(title=None, tickangle=-35)
            fig.update_yaxes(title=None)
            chart(U.styled(fig, 620), "tab1_cooccurrence_heatmap")

elif view == VIEWS[2]:                                            # Mined patterns
    if need_patterns():
        pat = q("patterns_for_window", y0, min_k, 40, country)
        if pat.empty:
            st.info("No patterns at this size. Lower the minimum topics per pattern.")
        else:
            with st.container(border=True):
                st.markdown(U.section("Frequent topic combinations (FP-Growth)",
                                      f"{scope_text()} · support = share of papers "
                                      "containing every topic listed"),
                            unsafe_allow_html=True)
                left, right = st.columns([3, 2], gap="medium")
                with left:
                    top = pat.head(20).assign(label=lambda d: d.itemset.map(A.short_label))
                    fig = px.bar(top, x="support", y="label", orientation="h",
                                 color="support", color_continuous_scale=U.AURORA,
                                 hover_data={"itemset": True, "label": False})
                    fig.update_yaxes(categoryorder="total ascending", title=None)
                    fig.update_layout(coloraxis_showscale=False)
                    chart(U.styled(fig, 620), "tab2_frequent_itemsets")
                with right:
                    st.dataframe(
                        pat, hide_index=True, height=560, width="stretch",
                        column_order=("itemset", "k", "support_count", "support"),
                        column_config={
                            "itemset": st.column_config.TextColumn("pattern", width="medium"),
                            "k": st.column_config.NumberColumn("topics", width="small"),
                            "support_count": st.column_config.NumberColumn("papers", format="%d"),
                            "support": st.column_config.ProgressColumn(
                                "support", format="%.3f", min_value=0.0,
                                max_value=float(pat["support"].max())),
                        })
                    st.download_button("Download patterns (CSV)",
                                       pat.to_csv(index=False).encode("utf-8"),
                                       file_name=f"patterns_{country or 'all'}_{y0}_{y1}.csv",
                                       mime="text/csv", icon=":material/download:",
                                       width="stretch")

        emerging, declining = q("emerging_declining", 10, country)
        if not emerging.empty:
            e_col, d_col = st.columns(2, gap="medium")
            for col, df, title, color in ((e_col, emerging, "Emerging combinations", U.TEAL),
                                          (d_col, declining, "Fading combinations", U.PINK)):
                with col, st.container(border=True):
                    st.markdown(U.section(title, f"{scope_name} · change in support, "
                                                 "first → last window"),
                                unsafe_allow_html=True)
                    d = df.assign(label=df.itemset.map(A.short_label)).iloc[::-1]
                    fig = px.bar(d, x="change", y="label", orientation="h",
                                 color_discrete_sequence=[color],
                                 hover_data={"first_window": True, "last_window": True,
                                             "label": False})
                    fig.update_yaxes(title=None)
                    chart(U.styled(fig, 420), title.lower().replace(" ", "_"))

        rules = q("top_rules", y0, min_lift, 25, country)
        with st.container(border=True):
            st.markdown(U.section("Association rules",
                                  f"{scope_text()} · lift above 1 = real attraction"),
                        unsafe_allow_html=True)
            if rules.empty:
                st.info("No rules above this lift. Lower the slider in Thresholds.")
            else:
                fig = px.scatter(rules, x="confidence", y="lift", size="support",
                                 color="lift", color_continuous_scale=U.AURORA,
                                 hover_data=["antecedent", "consequent"])
                chart(U.styled(fig, 440), "tab2_association_rules")
                st.dataframe(rules, hide_index=True, width="stretch", column_config={
                    "antecedent": st.column_config.TextColumn("if a paper covers", width="medium"),
                    "consequent": st.column_config.TextColumn("it also covers", width="medium"),
                    "support": st.column_config.NumberColumn(format="%.4f"),
                    "confidence": st.column_config.NumberColumn(format="%.2f"),
                    "lift": st.column_config.NumberColumn(format="%.1f"),
                })

elif view == VIEWS[3]:                                                # Lifecycles
    if need_patterns():
        @st.fragment
        def lifecycles():
            opts_df = q("patterns_for_window", y0, max(min_k, 2), 60, country)
            options = opts_df["itemset"].tolist() if not opts_df.empty else []
            with st.container(border=True):
                st.markdown(U.section("Pattern lifecycles",
                                      f"{scope_name} · support across sliding windows; "
                                      "a line leaving the floor is a combination being born"),
                            unsafe_allow_html=True)
                picked_p = st.multiselect("Patterns to track", options, default=options[:5],
                                          format_func=A.short_label,
                                          key=f"life_{db_key}_{country}_{y0}")
                ts = q("pattern_timeseries", tuple(picked_p), country)
                if ts.empty:
                    st.info("Pick at least one pattern above.")
                    return
                ts = ts.assign(pattern=ts["itemset"].map(A.short_label))
                fig = px.line(ts, x="window_start", y="support", color="pattern",
                              markers=True, color_discrete_sequence=U.CATEGORICAL,
                              labels={"window_start": "window start year"})
                fig.update_traces(line=dict(width=3), marker=dict(size=6))
                fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.15,
                                              x=0, title=None, font=dict(size=11)))
                fig.update_xaxes(dtick=2)
                chart(U.styled(fig, 620), f"tab3_lifecycles_{country or 'all'}")
        lifecycles()

elif view == VIEWS[4]:                                             # Co-authorship
    @st.fragment
    def coauthorship():
        opts_df = q("patterns_for_window", y0, max(min_k, 2), 60, country) if patterns_ok \
            else pd.DataFrame(columns=["itemset"])
        choices = ["(every paper in this window)"] + opts_df["itemset"].tolist()
        with st.container(border=True):
            st.markdown(U.section("Co-authorship network",
                                  "who writes together — scoped to the window, country "
                                  "and (optionally) one mined pattern"),
                        unsafe_allow_html=True)
            c1, c2, c3 = st.columns([3, 1, 1])
            focus = c1.selectbox("Papers behind one pattern", choices,
                                 index=1 if len(choices) > 1 else 0,
                                 format_func=lambda s: s if s.startswith("(") else A.short_label(s))
            only_big = c2.toggle("Largest community", value=True)
            local_only = c3.toggle("Only local authors", value=False,
                                   disabled=not country)
            itemset = None if focus.startswith("(") else focus
            with st.spinner("Laying out the network…"):
                net = q("network", y0, y1, 1 if itemset else min_papers, 800, itemset,
                        country, bool(local_only and country), only_big)
            edges, pos, pairs = net["edges"], net["pos"], net["pairs"]
            degree, home = net["degree"], net["home"]
            if edges.empty:
                st.info("No co-author pairs here. Lower the minimum shared papers, "
                        "or pick another pattern.")
                return

            ex, ey = [], []
            for a, b in pairs:
                if a in pos and b in pos:
                    ex += [pos[a][0], pos[b][0], None]
                    ey += [pos[a][1], pos[b][1], None]
            names = list(pos)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", hoverinfo="skip",
                                     line=dict(width=0.6, color="rgba(148,163,184,0.25)")))
            hover = [f"<b>{n}</b><br>{C.label(home.get(n))}<br>{degree.get(n, 0)} collaborators"
                     for n in names]
            if country:
                colors = [U.TEAL if home.get(n) == country else U.VIOLET for n in names]
                marker = dict(color=colors)
            else:
                marker = dict(color=[degree.get(n, 0) for n in names],
                              colorscale=U.AURORA, showscale=True,
                              colorbar=dict(title="collaborators", thickness=10, outlinewidth=0))
            marker.update(size=[7 + 2.2 * degree.get(n, 0) ** 0.5 for n in names],
                          line=dict(width=0.6, color="#0A0F1E"))
            fig.add_trace(go.Scatter(x=[pos[n][0] for n in names], y=[pos[n][1] for n in names],
                                     mode="markers", text=hover, hoverinfo="text", marker=marker))
            fig.update_layout(showlegend=False, xaxis=dict(visible=False),
                              yaxis=dict(visible=False))
            chart(U.styled(fig, 680), f"tab4_network_{country or 'all'}")

            n_auth = len(names)
            cap = f"{n_auth:,} authors · {len(edges):,} collaboration links"
            if country:
                local = sum(1 for n in names if home.get(n) == country)
                cap += f" · 🟢 teal = based in {scope_name} ({local:,}), 🟣 violet = international partners"
            st.caption(cap)

            top = (pd.DataFrame({"author": list(degree), "collaborators": list(degree.values())})
                   .assign(country=lambda d: d.author.map(lambda n: C.label(home.get(n))))
                   .sort_values("collaborators", ascending=False).head(12))
            st.dataframe(top, hide_index=True, width="stretch", column_config={
                "collaborators": st.column_config.ProgressColumn(
                    "distinct collaborators", format="%d", min_value=0,
                    max_value=int(top["collaborators"].max())),
            })
    coauthorship()

elif view == VIEWS[5]:                                           # Link prediction
    metrics = q("link_metrics")
    if metrics.empty:
        st.info("No link-prediction results in this dataset. Run: "
                f"python linkpred.py --db {db_path}")
    else:
        left, right = st.columns([2, 3], gap="medium")
        with left, st.container(border=True):
            st.markdown(U.section("Model performance",
                                  "trained up to the split year, tested on later "
                                  "collaborations · 0.5 = coin flip"),
                        unsafe_allow_html=True)
            m = metrics.melt(id_vars="model", value_vars=["auc", "ap"],
                             var_name="metric", value_name="score")
            fig = px.bar(m, x="score", y="model", color="metric", barmode="group",
                         orientation="h", color_discrete_sequence=[U.TEAL, U.VIOLET])
            fig.update_xaxes(range=[0.5, 1.0])
            fig.update_yaxes(categoryorder="total ascending", title=None)
            chart(U.styled(fig, 460), "link_metrics")
            best = metrics.iloc[0]
            st.markdown(U.note(f"Best model: {best.model} (AUC {best.auc:.3f}). Models are "
                               "trained on the whole dataset; the country filter only "
                               "narrows the predictions shown."), unsafe_allow_html=True)

        with right:
            @st.fragment
            def predictions():
                with st.container(border=True):
                    st.markdown(U.section("Predicted future collaborations",
                                          f"{scope_name} · pairs who have not yet "
                                          "written together, highest score first"),
                                unsafe_allow_html=True)
                    preds = q("link_predictions", country, 300)
                    if preds.empty:
                        st.info("No predictions involve this country.")
                        return
                    names = sorted(set(preds.author_a) | set(preds.author_b))
                    who = st.selectbox("Focus on one author", ["(everyone)"] + names)
                    if who != "(everyone)":
                        preds = preds[(preds.author_a == who) | (preds.author_b == who)]
                    show = preds.assign(country_a=preds.country_a.map(C.label),
                                        country_b=preds.country_b.map(C.label))
                    st.dataframe(show.head(100), hide_index=True, height=470, width="stretch",
                                 column_config={
                                     "author_a": "author", "country_a": "country",
                                     "author_b": "likely partner", "country_b": "country ",
                                     "score": st.column_config.ProgressColumn(
                                         "score", format="%.2f", min_value=0.0,
                                         max_value=float(preds.score.max() or 1)),
                                 })
            predictions()

st.markdown("<div class='foot'>Data: OpenAlex (CC0) · patterns mined with a hand-written "
            "FP-Growth · countries from author institutions</div>", unsafe_allow_html=True)
