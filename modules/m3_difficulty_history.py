"""M3 - Difficulty History.

Long-term evolution of the Bitcoin mining difficulty, with one marker per
difficulty-adjustment event (every 2016 blocks) and the ratio between the
actual mean block time per period and the protocol's 600-second target.

The mempool.space `/api/v1/mining/hashrate/<period>` endpoint already
returns one entry per real difficulty adjustment, so each point on the
top chart corresponds to a 2016-block retarget. The bottom chart turns
the time gap between consecutive points into the actual-vs-target ratio
required by the project brief.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from api.blockchain_client import get_difficulty_history

TARGET_BLOCK_TIME_S = 600          # Bitcoin protocol target — 10 minutes per block
BLOCKS_PER_EPOCH = 2016            # Difficulty re-targets every 2016 blocks
TARGET_EPOCH_TIME_S = TARGET_BLOCK_TIME_S * BLOCKS_PER_EPOCH  # ≈ 14 days


@st.cache_data(ttl=43_200, show_spinner="Loading difficulty history...")
def _load_history(timespan: str) -> pd.DataFrame:
    values = get_difficulty_history(timespan)
    df = pd.DataFrame(values)
    if df.empty:
        return df
    df["Date"] = pd.to_datetime(df["x"], unit="s")
    df = df.rename(columns={"y": "Difficulty"})
    df = df.sort_values("Date").reset_index(drop=True)

    # Time elapsed since the previous adjustment, in seconds. The first row
    # has no predecessor so its delta is NaN.
    df["EpochSeconds"] = df["x"].diff()

    # Mean block time observed during that epoch (seconds per block).
    df["MeanBlockTimeS"] = df["EpochSeconds"] / BLOCKS_PER_EPOCH

    # Actual-vs-target ratio. >1 → blocks were slower than 10 min on
    # average (next retarget will lower difficulty), <1 → blocks were
    # faster (next retarget will raise difficulty).
    df["Ratio"] = df["MeanBlockTimeS"] / TARGET_BLOCK_TIME_S
    return df


def render() -> None:
    st.header("M3 — Difficulty History")
    st.caption(
        "Long-term evolution of the Bitcoin mining difficulty, with one "
        "marker per 2016-block retarget. Source: mempool.space."
    )

    timespan = st.selectbox(
        "Time window",
        options=["1m", "3m", "6m", "1y", "2y", "3y"],
        index=4,  # default to 2y
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

    # ------------------------------------------------------------------
    # Chart 1 — Difficulty over time, with adjustment markers
    # ------------------------------------------------------------------
    st.subheader("Difficulty over time")
    fig_diff = px.line(
        df,
        x="Date",
        y="Difficulty",
        markers=True,  # one dot per difficulty adjustment event
        title=f"Bitcoin mining difficulty — {timespan} "
              f"({len(df)} adjustments shown)",
    )
    fig_diff.update_traces(
        marker=dict(size=7),
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Difficulty: %{y:,.0f}<extra></extra>",
    )
    fig_diff.update_yaxes(title="Difficulty (dimensionless)")
    fig_diff.update_xaxes(title="Date")
    st.plotly_chart(fig_diff, use_container_width=True)
    st.caption(
        "Each dot marks one **difficulty-adjustment event**. The Bitcoin "
        "protocol re-targets every 2016 blocks (~2 weeks) so the network "
        "keeps producing one block every 10 minutes on average."
    )

    # ------------------------------------------------------------------
    # Chart 2 — Actual vs target block time per epoch
    # ------------------------------------------------------------------
    st.subheader("Actual vs target block time per epoch")

    # Drop the first row (NaN delta — no previous epoch to compare with).
    df_ratio = df.dropna(subset=["Ratio"]).copy()
    # Color bars: red if blocks were slower than target, green if faster.
    df_ratio["Color"] = df_ratio["Ratio"].apply(
        lambda r: "Slower than target" if r > 1 else "Faster than target"
    )

    fig_ratio = px.bar(
        df_ratio,
        x="Date",
        y="Ratio",
        color="Color",
        color_discrete_map={
            "Slower than target": "#e74c3c",
            "Faster than target": "#2ecc71",
        },
        title=f"Mean block time / 600 s — {timespan}",
        hover_data={
            "Date": "|%Y-%m-%d",
            "Ratio": ":.3f",
            "MeanBlockTimeS": ":.1f",
            "Color": False,
        },
    )
    # Reference line at 1.0 (perfect match with the 10-minute target).
    fig_ratio.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="#95a5a6",
        annotation_text="target = 1.0 (10 min/block)",
        annotation_position="top right",
    )
    fig_ratio.update_yaxes(title="Actual / target ratio")
    fig_ratio.update_xaxes(title="Date")
    fig_ratio.update_layout(legend_title_text="")
    st.plotly_chart(fig_ratio, use_container_width=True)
    st.caption(
        "Ratio = (mean block time observed during the epoch) / 600 s. "
        "Bars **above 1** mean the network was producing blocks more slowly "
        "than the 10-minute target during that epoch (the next retarget will "
        "**lower** the difficulty). Bars **below 1** mean blocks were faster "
        "than target (the next retarget will **raise** the difficulty). "
        "This is exactly the negative-feedback loop described in section 6.1 "
        "of the course notes."
    )