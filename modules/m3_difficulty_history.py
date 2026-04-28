"""M3 - Difficulty History (in progress).

Plot the long-term evolution of the Bitcoin mining difficulty.

Adjustment-event markers (every 2016 blocks) and the actual-vs-target
block-time ratio per period will be added in the next iteration of M3.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from api.blockchain_client import get_difficulty_history


@st.cache_data(ttl=3600, show_spinner=False)  # difficulty changes only every ~2 weeks
def _load_history(timespan: str) -> pd.DataFrame:
    values = get_difficulty_history(timespan)
    df = pd.DataFrame(values)
    if df.empty:
        return df
    df["x"] = pd.to_datetime(df["x"], unit="s")
    return df.rename(columns={"x": "Date", "y": "Difficulty"})


def render() -> None:
    """Render the M3 panel."""
    st.header("M3 — Difficulty History")
    st.caption(
        "Long-term evolution of the Bitcoin mining difficulty. "
        "Source: blockchain.info /charts/difficulty."
    )

    timespan = st.selectbox(
        "Time window",
        options=["1year", "2years", "5years", "all"],
        index=1,
        key="m3_timespan",
    )

    try:
        df = _load_history(timespan)
    except Exception as exc:
        st.error(f"Error loading difficulty history: {exc}")
        return

    if df.empty:
        st.warning("No data available for that window.")
        return

    fig = px.line(
        df,
        x="Date",
        y="Difficulty",
        title=f"Bitcoin mining difficulty — {timespan}",
    )
    fig.update_yaxes(title="Difficulty (dimensionless)")
    fig.update_xaxes(title="Date")
    st.plotly_chart(fig, use_container_width=True)

    st.info(
        "**In progress** — the next iteration of M3 will mark each "
        "difficulty adjustment event (every 2016 blocks) and plot the ratio "
        "between actual block time and the 600-second target per period, "
        "as required by the project brief."
    )