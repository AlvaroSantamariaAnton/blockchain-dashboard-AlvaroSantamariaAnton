"""M4 - AI Component (skeleton).

Chosen approach: **anomaly detector** for Bitcoin block inter-arrival times.

The baseline distribution is the theoretical exponential distribution that
a Poisson mining process is expected to follow. Each block can then be
scored by the survival function `S(Δt) = exp(-Δt / μ)`: blocks whose
inter-arrival time falls in a low-probability tail are flagged as
statistically abnormal.

This file is currently a **skeleton**: it sets up the data pipeline (block
fetching, delta computation) and the layout of the panel, leaving clearly
marked TODOs where the model scoring, the flagging threshold and the
evaluation metrics will be added in the next milestone.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from api.blockchain_client import get_last_n_blocks

TARGET_BLOCK_TIME_S = 600  # Bitcoin protocol target — 10 minutes per block


@st.cache_data(ttl=300, show_spinner=False)
def _load_recent_blocks(n: int) -> list[dict]:
    return get_last_n_blocks(n)


def _build_deltas(blocks: list[dict]) -> pd.DataFrame:
    """Sort blocks oldest-first and compute the inter-arrival deltas.

    Returns a dataframe with one row per block (the oldest one has a NaN
    delta because there is no previous block to compare with).
    """
    df = pd.DataFrame(blocks).sort_values("height").reset_index(drop=True)
    df["Date"] = pd.to_datetime(df["timestamp"], unit="s")
    df["DeltaSeconds"] = df["timestamp"].diff()
    return df


def render() -> None:
    """Render the M4 panel."""
    st.header("M4 — AI Component")

    # ------------------------------------------------------------------
    # Approach summary — what the model will do once implemented
    # ------------------------------------------------------------------
    st.subheader("Chosen approach: anomaly detector")
    st.markdown(
        """
        The time between consecutive Bitcoin blocks is well-modelled as an
        **exponential distribution** `Exp(λ = 1/600 s)` because mining is a
        Poisson process: each hash attempt is an independent Bernoulli
        trial with the same success probability, so the time until the
        next valid block follows an exponential law.

        The detector will flag blocks whose inter-arrival time falls in a
        low-probability tail of this baseline. The model needs no labelled
        training data — the theoretical distribution itself acts as the
        baseline.

        **Pipeline**
        1. Pull a long window of recent blocks (≥ 500) and compute their
           inter-arrival times Δt.
        2. Score each block with the survival function
           `S(Δt) = exp(-Δt / μ)`, where μ is the mean of the observed
           series.
        3. Flag a block as an anomaly when `S(Δt) < α` (e.g. α = 0.01) —
           i.e. its arrival was significantly slower than expected.
        4. Evaluate against the theoretical false-positive rate and
           qualitatively against known events (mining-pool outages, etc.).
        """
    )

    # ------------------------------------------------------------------
    # Data pipeline — already wired, ready to feed the model
    # ------------------------------------------------------------------
    st.subheader("Input data — inter-arrival times")

    n_blocks = st.slider(
        "Number of recent blocks to analyse",
        min_value=100,
        max_value=500,
        value=200,
        step=50,
        key="m4_n",
    )

    try:
        blocks = _load_recent_blocks(n_blocks)
    except Exception as exc:
        st.error(f"API error while fetching blocks: {exc}")
        return

    df = _build_deltas(blocks)
    deltas = df["DeltaSeconds"].dropna()

    if deltas.empty:
        st.warning("Not enough block data to build the deltas.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Blocks analysed", f"{len(df):,}")
    col2.metric("Observed mean Δt", f"{deltas.mean():.0f} s")
    col3.metric("Protocol target", f"{TARGET_BLOCK_TIME_S} s")

    st.caption(
        "These deltas are the input the anomaly detector will score. "
        "The data pipeline is already in place so that, once the model is "
        "implemented, it can be plugged in without further plumbing."
    )

    with st.expander("Preview the data the model will consume"):
        st.dataframe(
            df[["height", "Date", "DeltaSeconds"]].tail(20),
            use_container_width=True,
        )

    # ------------------------------------------------------------------
    # Model + evaluation — to be implemented in the next milestone (May 7)
    # ------------------------------------------------------------------
    st.subheader("Model and evaluation")
    st.info(
        "**Skeleton only — implementation scheduled for milestone M4 (May 7).**\n\n"
        "**TODO**\n"
        "- Compute `S(Δt) = exp(-Δt / μ)` per block.\n"
        "- Flag blocks where `S(Δt) < α` and surface them in the UI.\n"
        "- Plot the score distribution vs. the theoretical exponential PDF.\n"
        "- Evaluate: empirical false-positive rate vs. theoretical α, "
        "and qualitative comparison against known network events."
    )