"""M1 - Proof of Work Monitor.

Live data about the Bitcoin mining network:

* Current difficulty and the 256-bit target it represents.
* Time between the last *N* blocks, compared with the theoretical
  exponential distribution that a Poisson mining process is expected to
  produce.
* Estimated network hash rate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from api.blockchain_client import get_block, get_last_n_blocks, get_tip_hash

TARGET_BLOCK_TIME_S = 600  # Bitcoin protocol target — one block every 10 minutes


def _bits_to_target(bits: int) -> int:
    """Decode the compact ``bits`` field into the full 256-bit target."""
    exponent = bits >> 24
    mantissa = bits & 0xFFFFFF
    return mantissa * (2 ** (8 * (exponent - 3)))


@st.cache_data(ttl=60, show_spinner=False)
def _load_tip_block() -> dict:
    return get_block(get_tip_hash())


@st.cache_data(ttl=60, show_spinner=False)
def _load_recent_blocks(n: int) -> list[dict]:
    return get_last_n_blocks(n)


def render() -> None:
    """Render the M1 panel."""
    st.header("M1 — Proof of Work Monitor")
    st.caption(
        "Live state of the Bitcoin mining network. "
        "Data refreshes automatically every 60 seconds."
    )

    n_blocks = st.slider(
        "Number of recent blocks to analyse",
        min_value=20,
        max_value=200,
        value=100,
        step=10,
        key="m1_n",
    )

    try:
        tip = _load_tip_block()
        recent = _load_recent_blocks(n_blocks)
    except Exception as exc:
        st.error(f"API error while fetching blocks: {exc}")
        return

    bits = int(tip["bits"])
    difficulty = float(tip["difficulty"])
    target = _bits_to_target(bits)

    # --- Top-line metrics --------------------------------------------------
    col1, col2, col3 = st.columns(3)
    col1.metric("Current block height", f"{tip['height']:,}")
    col2.metric("Difficulty", f"{difficulty:,.0f}")
    # Hash rate ≈ difficulty · 2^32 / target_block_time
    hashrate_eh = difficulty * (2 ** 32) / TARGET_BLOCK_TIME_S / 1e18
    col3.metric("Estimated hash rate", f"{hashrate_eh:,.2f} EH/s")

    # --- Target threshold visualisation ------------------------------------
    st.subheader("Target threshold in the 256-bit SHA-256 space")
    target_hex = f"{target:064x}"
    leading_zero_bits = 256 - target.bit_length()
    st.markdown(
        f"A valid block hash must be **strictly less than** the target. "
        f"Today the target requires at least **{leading_zero_bits} leading "
        f"zero bits** (≈ {leading_zero_bits // 4} hex zeros) in the resulting "
        f"hash."
    )
    st.code(target_hex, language="text")
    st.caption(
        "The leading zeros at the start of the target are the visual signature "
        "of the difficulty: the more zeros, the smaller the target, the harder "
        "the puzzle."
    )

    # --- Inter-block-time distribution -------------------------------------
    st.subheader(f"Inter-block times — last {n_blocks} blocks")

    # Blockstream returns blocks newest-first; sort oldest-first to compute deltas.
    df = pd.DataFrame(recent).sort_values("height").reset_index(drop=True)
    df["delta_s"] = df["timestamp"].diff()
    deltas = df["delta_s"].dropna()
    deltas = deltas[deltas > 0]  # drop the occasional non-monotonic timestamp

    if deltas.empty:
        st.warning("Not enough block data to plot the distribution.")
        return

    mean_delta = float(deltas.mean())

    # Theoretical exponential PDFs
    x_max = float(max(deltas.max(), 2400))
    x = np.linspace(1, x_max, 200)
    pdf_observed = (1 / mean_delta) * np.exp(-x / mean_delta)
    pdf_target = (1 / TARGET_BLOCK_TIME_S) * np.exp(-x / TARGET_BLOCK_TIME_S)

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=deltas,
            nbinsx=25,
            histnorm="probability density",
            name="Observed",
            opacity=0.65,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=pdf_observed, mode="lines",
            name=f"Exp(mean={mean_delta:.0f}s) — observed",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=pdf_target, mode="lines",
            name="Exp(mean=600s) — Bitcoin target",
            line=dict(dash="dash"),
        )
    )
    fig.update_layout(
        xaxis_title="Seconds between blocks",
        yaxis_title="Probability density",
        legend=dict(orientation="h", y=-0.2),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        f"**Observed mean:** {mean_delta:.1f} s &nbsp;·&nbsp; "
        f"**Protocol target:** {TARGET_BLOCK_TIME_S} s"
    )
    st.markdown(
        "Mining is well modelled as a **Poisson process**: each hash attempt "
        "is an independent Bernoulli trial with the same success probability, "
        "so the time until the next valid block is approximately "
        "**exponentially distributed**. Visible deviations from the curve "
        "come from the small sample size and from real-world effects "
        "(network propagation, pool variance, hash-rate drift between "
        "difficulty adjustments)."
    )