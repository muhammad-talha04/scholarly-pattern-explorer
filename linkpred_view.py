"""Streamlit view for Link Prediction results.

Renders model performance metrics and an interactive explorer for
predicted future collaborations.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from linkgraph import resolve_schema

def render_link_prediction(con):
    # The 'con' passed here is the DB wrapper. 
    # We need the actual connection object inside it.
    db_conn = con.con if hasattr(con, 'con') else con

    st.header("🤝 Future Collaboration Predictor")
    st.markdown(
        "This view uses Graph Machine Learning to predict which authors are likely "
        "to collaborate in the future based on their current network position "
        "and shared research topics."
    )

    # 1. Metrics Table
    st.subheader("Model Performance")
    try:
        metrics_df = db_conn.execute("SELECT * FROM link_metrics").df()
        if not metrics_df.empty:
            # Highlight the best model
            best_model = metrics_df.loc[metrics_df['auc'].idxmax(), 'model']
            st.dataframe(metrics_df, use_container_width=True)
            st.info(f"🏆 **Best Model:** {best_model} (Highest AUC)")
        else:
            st.warning("No metrics found. Please run `linkpred.py` first.")
    except Exception as e:
        st.error(f"Could not load metrics: {e}")

    st.divider()

    # 2. Top Predictions Explorer
    st.subheader("Predicted Future Links")

    try:
        preds_df = db_conn.execute("SELECT * FROM link_predictions").df()
        if not preds_df.empty:
            # Use schema resolution to find the authors table
            S = resolve_schema(db_conn)

            # Let's do a join to get names
            query = f"""
                SELECT p.author_a, a1.{S.authors_name} as name_a,
                       p.author_b, a2.{S.authors_name} as name_b,
                       p.score, p.model
                FROM link_predictions p
                JOIN {S.authors} a1 ON p.author_a = a1.{S.authors_id}
                JOIN {S.authors} a2 ON p.author_b = a2.{S.authors_id}
                ORDER BY p.score DESC
            """
            named_preds = db_conn.execute(query).df()

            col1, col2 = st.columns([1, 3])
            with col1:
                seed_author = st.selectbox(
                    "Filter by Author",
                    ["All"] + sorted(named_preds['name_a'].unique().tolist() + named_preds['name_b'].unique().tolist())
                )

            with col2:
                if seed_author == "All":
                    display_df = named_preds.head(20)
                else:
                    display_df = named_preds[
                        (named_preds['name_a'] == seed_author) | (named_preds['name_b'] == seed_author)
                    ].head(20)

                st.table(display_df[['name_a', 'name_b', 'score']])
        else:
            st.warning("No predictions found. Please run `linkpred.py` first.")
    except Exception as e:
        st.error(f"Could not load predictions: {e}")