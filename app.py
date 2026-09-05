"""
STEP 4b: the visualizer. Four linked views over one database.

Run it:      streamlit run app.py
Then open the http://localhost:8501 link it prints.

This file contains NO SQL. Every query lives in analytics.py, which has its own
command-line self-test. Keep it that way: UI code is hard to test, query code is
easy to test.

  Raw data        what the corpus actually contains
  Mined patterns  what FP-Growth found in the selected window
  Lifecycles      the support of one pattern across every window
  Co-authorship   the research community behind those papers

Those four are chosen with a segmented control rather than st.tabs. Tabs look
tidier but Streamlit computes the contents of every tab on every rerun, so a
tabbed version of this app runs four sets of queries to show you one. Here only
the selected view touches the database.

The look comes from .streamlit/config.toml, not from CSS injected into the page.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analytics as A
from dbconn import DB

st.set_page_config(page_title="Scholarly pattern explorer",
                   page_icon=":material/insights:", layout="wide")

# One palette for the whole app, matching .streamlit/config.toml. Plotly fixes
# a trace's colour when the figure is built, so these have to be passed in at
# creation time; setting them on the layout afterwards recolours nothing.
INK = "#232A31"
ACCENT = "#1B5E5A"
GRID = "#E7E1D6"
# The exact backgroundColor from .streamlit/config.toml. Giving the figure this
# colour rather than leaving it transparent is deliberate. On screen the two are
# indistinguishable, because the chart sits on this very colour anyway - but a
# transparent PNG takes the background of whatever page it is dropped into, so
# the same chart in a GitHub README becomes dark ink on a dark page for anyone
# reading in dark mode. An opaque figure exports looking the way it looked here.
PAPER = "#FBFAF7"
CATEGORICAL = ["#1B5E5A", "#C2703D", "#3D5A80", "#7A6A9B",
               "#8C7B2F", "#A2555A", "#4E7A5C", "#6E7C87"]
SEQUENTIAL = ["#F7F3EC", "#C6DAD6", "#7FADA7", "#3B837B", "#12433F"]

VIEWS = [":material/bar_chart: Raw data",
         ":material/insights: Mined patterns",
         ":material/timeline: Lifecycles",
         ":material/hub: Co-authorship"]

def styled(fig, height: int = 520):
    """
    Make a figure look like part of this app instead of part of Plotly.

    The two background lines are the important ones: the figure is filled with
    the page colour and the plotting area is left clear, so the chart reads as a
    region of the page rather than a white rectangle pasted onto it - and it
    still exports as a self-contained image (see PAPER above).
    """
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor=PAPER,
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, 'Segoe UI', sans-serif", size=13, color=INK),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=GRID, font_size=12),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        coloraxis_colorbar=dict(outlinewidth=0, thickness=12),
        height=height,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     title_font_size=12, tickfont_size=11, automargin=True)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     title_font_size=12, tickfont_size=11, automargin=True)
    return fig


def titled(fig, heading: str, sub: str = ""):
    """
    Put the heading inside the figure rather than above it.

    A page heading is Streamlit text, so it is absent from an exported image and
    the file cannot explain itself. Titling the figure means the PNG can be
    dropped straight into a paper or a README and still make sense.
    """
    text = f"<b>{heading}</b>"
    if sub:
        text += f"<br><span style='font-size:12px;color:#6B7A85'>{sub}</span>"
    fig.update_layout(
        title=dict(text=text, x=0, xanchor="left",
                   font=dict(size=17, family="Georgia, serif")),
        # Only the top margin is set. Left and bottom are left alone so that
        # `automargin` can grow them to fit long topic names instead of clipping.
        margin=dict(t=78 if sub else 56),
    )
    return fig


def chart(fig, filename: str) -> None:
    """
    Draw a figure and give its PNG export a real name.

    The camera icon in the chart toolbar otherwise saves everything as
    `newplot.png`, so six downloads arrive indistinguishable from each other.
    scale=2 exports at twice screen resolution, which survives being printed.
    """
    st.plotly_chart(fig, width="stretch", config={
        "displaylogo": False,
        "toImageButtonOptions": {"filename": filename, "format": "png", "scale": 2},
    })


@st.cache_resource
def get_db(path: str) -> DB:
    """One connection per database file, shared by every user of the app."""
    return DB(path)


@st.cache_data(show_spinner=False, ttl=1800, max_entries=300)
def _run(_db, db_key: str, fn_name: str, *args):
    """
    Run analytics.<fn_name>(db, *args) once and remember the answer.

    WHY `db_key` EXISTS
    -------------------
    Streamlit deliberately ignores any argument whose name starts with an
    underscore when it builds the cache key - that is how you pass an unhashable
    object like a database connection. But it also means that swapping the
    database file in the sidebar would NOT invalidate the cache: you would see
    numbers from the previous database sitting next to numbers from the new one.
    So the file path is passed in as an ordinary argument purely to join the key.
    It is never used inside the function.
    """
    return getattr(A, fn_name)(_db, *args)


with st.sidebar:
    st.markdown("#### :material/database: Data source")
    db_path = st.text_input("Database file", "data/openalex.duckdb",
                            help="Any file produced by build_db.py")


def cached(_db, fn_name: str, *args):
    """Same call signature everywhere; the db path silently joins the cache key."""
    return _run(_db, db_path, fn_name, *args)


try:
    db = get_db(db_path)
    win = cached(db, "windows")
except Exception as exc:                                  # noqa: BLE001
    st.error(f"Could not open the database: {exc}", icon=":material/error:")
    st.info("Run:  python make_sample_data.py && python build_db.py && python mine_windows.py")
    st.stop()

if win.empty:
    st.warning("No mined patterns in this database yet. Run:  python mine_windows.py",
               icon=":material/warning:")
    st.stop()

labels = [f"{int(r.window_start)}-{int(r.window_end)}" for r in win.itertuples()]

with st.sidebar:
    st.markdown("#### :material/date_range: Window")
    choice = st.select_slider("Three-year window", options=labels, value=labels[-1],
                              help="Windows overlap and step by one year")

    st.markdown("#### :material/tune: Thresholds")
    min_k = st.slider("Minimum topics per pattern", 1, 4, 2)
    min_lift = st.slider("Minimum lift for rules", 1.0, 5.0, 1.1, 0.1)
    min_papers = st.slider("Minimum shared papers in the network", 1, 6, 2)

    st.markdown("#### :material/help: Reading the numbers")
    st.caption(
        "**Support** is the share of papers in the window containing every topic "
        "of a pattern. **Lift** above 1 means two topics attract each other more "
        "than their individual popularity explains."
    )

y0, y1 = (int(v) for v in choice.split("-"))
row = win[win.window_start == y0].iloc[0]
summary = cached(db, "corpus_summary").iloc[0]

st.title("Scholarly pattern explorer")
st.caption("Which combinations of research topics are emerging, "
           "and which is the field abandoning?")

with st.container(horizontal=True):
    st.metric("Papers in window", f"{int(row.papers):,}", border=True)
    st.metric("Patterns in window", f"{int(row.itemsets):,}", border=True)
    st.metric("Papers in corpus", f"{int(summary.works):,}", border=True)
    st.metric("Topics", f"{int(summary.topics):,}", border=True)
    st.metric("Authors", f"{int(summary.authors):,}", border=True)
    st.metric("Windows mined", f"{len(win):,}", border=True)

view = st.segmented_control("View", VIEWS, default=VIEWS[0],
                            label_visibility="collapsed")
if view is None:            # a segmented control can be cleared by clicking again
    view = VIEWS[0]


def pattern_options() -> list[str]:
    """Patterns of at least two topics in this window, for the two pickers."""
    df = cached(db, "patterns_for_window", y0, max(min_k, 2), 60)
    return df["itemset"].tolist() if not df.empty else []

if view == VIEWS[0]:
    with st.container(border=True):
        dist = cached(db, "topic_distribution", y0, y1, 20)
        chart(
            titled(
                styled(px.bar(dist, x="papers", y="topic", color="field",
                              orientation="h", color_discrete_sequence=CATEGORICAL)
                       .update_yaxes(categoryorder="total ascending"), 580),
                "Most frequent research topics",
                f"{choice} - top 20 topics by number of papers",
            ),
            "tab1_topic_distribution",
        )
        st.caption("This is the raw data, before any mining. It tells you what the "
                   "corpus is about, and nothing about which topics travel together.")

    with st.container(border=True):
        mat = cached(db, "cooccurrence_matrix", y0, y1, 12)
        if mat.empty:
            st.info("Not enough data in this window to build a co-occurrence table.",
                    icon=":material/info:")
        else:
            chart(
                titled(
                    styled(px.imshow(mat, aspect="auto",
                                     color_continuous_scale=SEQUENTIAL), 580),
                    "Which topics appear together",
                    f"{choice} - papers containing both topics (self-join counts)",
                ),
                "tab1_cooccurrence_heatmap",
            )
            st.caption("A self-join on the bridge table counts every pair. It is the "
                       "honest baseline the miner has to beat: pairs of popular topics "
                       "look strong here even when neither attracts the other.")

elif view == VIEWS[1]:
    pat = cached(db, "patterns_for_window", y0, min_k, 40)
    if pat.empty:
        st.info("No patterns at this size. Lower the minimum topics per pattern, "
                "or re-mine with a lower --min-support.", icon=":material/info:")
    else:
        with st.container(border=True):
            left, right = st.columns([3, 2], gap="medium")
            with left:
                chart(
                    titled(
                        styled(px.bar(pat.head(20), x="support", y="itemset",
                                      orientation="h",
                                      color_discrete_sequence=[ACCENT])
                               .update_yaxes(categoryorder="total ascending",
                                             title=None), 640),
                        "Frequent topic combinations found by FP-Growth",
                        f"{choice} - support is the share of papers containing "
                        "every topic listed",
                    ),
                    "tab2_frequent_itemsets",
                )
            with right:
                st.dataframe(
                    pat, hide_index=True, height=600, width="stretch",
                    column_order=("itemset", "k", "support_count", "support"),
                    column_config={
                        "itemset": st.column_config.TextColumn("pattern", width="large"),
                        "k": st.column_config.NumberColumn("topics", width="small"),
                        "support_count": st.column_config.NumberColumn("papers",
                                                                       format="%d"),
                        "support": st.column_config.ProgressColumn(
                            "support", format="%.3f", min_value=0.0,
                            max_value=float(pat["support"].max())),
                    },
                )
                st.download_button(
                    "Download these patterns as CSV",
                    pat.to_csv(index=False).encode("utf-8"),
                    file_name=f"patterns_{y0}_{y1}.csv", mime="text/csv",
                    icon=":material/download:", width="stretch",
                )

    rules = cached(db, "top_rules", y0, min_lift, 25)
    with st.container(border=True):
        if rules.empty:
            st.info("No rules above this lift. Lower the slider.", icon=":material/info:")
        else:
            chart(
                titled(
                    styled(px.scatter(rules, x="confidence", y="lift", size="support",
                                      color="lift", color_continuous_scale=SEQUENTIAL,
                                      hover_data=["antecedent", "consequent"]), 470),
                    "Association rules",
                    f"{choice} - lift above 1 means a real attraction, "
                    "not just two individually popular topics",
                ),
                "tab2_association_rules",
            )
            st.dataframe(
                rules, hide_index=True, width="stretch",
                column_config={
                    "antecedent": st.column_config.TextColumn("if a paper covers",
                                                              width="medium"),
                    "consequent": st.column_config.TextColumn("it also covers",
                                                              width="medium"),
                    "support": st.column_config.NumberColumn(format="%.4f"),
                    "confidence": st.column_config.NumberColumn(format="%.2f"),
                    "lift": st.column_config.NumberColumn(format="%.1f"),
                },
            )

elif view == VIEWS[2]:
    options = pattern_options()
    with st.container(border=True):
        picked = st.multiselect("Patterns to track", options, default=options[:5],
                                format_func=A.short_label,
                                help="Each one is followed across every window")
        ts = cached(db, "pattern_timeseries", tuple(picked))
        if ts.empty:
            st.info("Pick at least one pattern above.", icon=":material/info:")
        else:
            ts = ts.assign(pattern=ts["itemset"].map(A.short_label))
            fig = styled(px.line(ts, x="window_start", y="support", color="pattern",
                                 markers=True, color_discrete_sequence=CATEGORICAL,
                                 labels={"window_start": "window start year",
                                         "support": "support"}), 660)
            # Long topic names destroy a legend down the side, so put it underneath.
            fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.18,
                                          x=0, title=None, font=dict(size=10)))
            fig.update_xaxes(dtick=2)
            titled(fig, "Pattern lifecycles: support across sliding windows",
                   "support is 0 where the pattern was not frequent, so a line "
                   "leaving the floor is a research combination being born")
            chart(fig, "tab3_pattern_lifecycles")
            st.caption("This is the reason for storing mining results in the database. "
                       "Every window was answered once, so 25 windows of history cost "
                       "one query rather than 25 mining runs.")

elif view == VIEWS[3]:
    options = pattern_options()
    choices = ["(every paper in this window)"] + options
    with st.container(border=True):
        controls = st.container(horizontal=True)
        with controls:
            focus = st.selectbox(
                "Build the network from the papers behind one pattern",
                choices, index=1 if len(choices) > 1 else 0,
                format_func=lambda s: s if s.startswith("(") else A.short_label(s),
            )
            only_big = st.checkbox("Largest community only", value=True,
                                   help="Hides the two-person islands a raw "
                                        "top-N query always returns")
        itemset = None if focus.startswith("(") else focus

        # Inside a single pattern there are few papers, so demanding two shared
        # papers would empty the graph; one shared paper is already meaningful.
        edges = cached(db, "coauthor_edges", y0, y1,
                       1 if itemset else min_papers, 800, itemset)
        if only_big:
            edges = A.largest_component(edges)

        if edges.empty:
            st.info("No co-author pairs here. Lower the minimum shared papers, "
                    "or pick another pattern.", icon=":material/info:")
        else:
            pos, pairs = A.layout_graph(edges)
            ex, ey = [], []
            for a, b in pairs:
                if a in pos and b in pos:
                    ex += [pos[a][0], pos[b][0], None]
                    ey += [pos[a][1], pos[b][1], None]

            degree: dict[str, int] = {}
            for a, b in pairs:
                degree[a] = degree.get(a, 0) + 1
                degree[b] = degree.get(b, 0) + 1
            names = list(pos)

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", hoverinfo="skip",
                                     line=dict(width=0.7, color="#CFC7B8")))
            fig.add_trace(go.Scatter(
                x=[pos[n][0] for n in names], y=[pos[n][1] for n in names],
                mode="markers",
                text=[f"{n}<br>{degree.get(n, 0)} collaborators" for n in names],
                hoverinfo="text",
                marker=dict(size=[7 + 1.7 * degree.get(n, 0) ** 0.5 for n in names],
                            color=[degree.get(n, 0) for n in names],
                            colorscale="Viridis", showscale=True,
                            line=dict(width=0.5, color="#FBFAF7"),
                            colorbar=dict(title="collaborators", thickness=12,
                                          outlinewidth=0)),
            ))
            styled(fig, 660)
            fig.update_layout(showlegend=False,
                              xaxis=dict(visible=False), yaxis=dict(visible=False))
            n_authors = len(set(edges.author_a) | set(edges.author_b))
            titled(fig, "Co-authorship network",
                   f"{choice} - "
                   + (f"papers containing '{A.short_label(itemset)}'" if itemset
                      else "every paper in the window")
                   + f"; {n_authors:,} authors, {len(edges):,} collaboration links")
            chart(fig, "tab4_coauthor_network")

            top = (pd.DataFrame({"author": list(degree),
                                 "collaborators": list(degree.values())})
                   .sort_values("collaborators", ascending=False).head(10))
            st.markdown("**Most connected authors here**")
            st.dataframe(
                top, hide_index=True, width="stretch",
                column_config={
                    "collaborators": st.column_config.ProgressColumn(
                        "distinct collaborators", format="%d", min_value=0,
                        max_value=int(top["collaborators"].max())),
                },
            )
            st.caption("Nothing in this pipeline reads an affiliation. If these names "
                       "turn out to work in the same laboratory, support counts alone "
                       "found it.")

st.divider()
st.caption("Data from OpenAlex (CC0). Patterns mined by fpgrowth.py, "
           "stored in the same database, and never recomputed in the browser.")






