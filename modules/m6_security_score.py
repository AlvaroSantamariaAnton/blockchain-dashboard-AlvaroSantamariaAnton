"""M6 - Security Score (optional module).

Estimate the cost of a 51% attack on Bitcoin from the live network hash
rate, and visualise how confirmation depth reduces an attacker's
probability of overtaking the honest chain.

The attack-success probability follows the formula given in the Bitcoin
whitepaper (Nakamoto 2008, Section 11), which models the honest chain's
advance as a Poisson process while the attacker tries to catch up from
``z`` blocks behind.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from api.blockchain_client import get_block, get_tip_hash

TARGET_BLOCK_TIME_S = 600
DEFAULT_ELECTRICITY_PRICE_USD_KWH = 0.05  # industrial mining electricity
DEFAULT_ASIC_EFFICIENCY_J_PER_TH = 20.0   # mix of current top-tier ASICs


def _attacker_success_probability(q: float, z: int) -> float:
    """Probability that an attacker with hashrate share *q* eventually
    overtakes a chain that is *z* blocks ahead.

    Direct port of the C++ snippet given in the Bitcoin whitepaper
    (Nakamoto 2008 §11). For q ≥ 0.5 the attacker eventually wins with
    probability 1 (the 51% attack); for q < 0.5 the probability decays
    exponentially with z.
    """
    if q >= 0.5:
        return 1.0
    if z <= 0:
        return 1.0
    p = 1.0 - q
    lam = z * (q / p)
    s = 1.0
    for k in range(z + 1):
        # Poisson PMF P(K = k) where K ~ Poisson(lam)
        poisson = math.exp(-lam)
        for i in range(1, k + 1):
            poisson *= lam / i
        s -= poisson * (1 - (q / p) ** (z - k))
    return max(0.0, min(1.0, s))


@st.cache_data(ttl=300, show_spinner=False)
def _load_tip_block() -> dict:
    return get_block(get_tip_hash())


def render() -> None:
    """Render the M6 panel."""
    st.header("M6 — Security Score (optional)")
    st.caption(
        "Cost of a 51% attack on Bitcoin and the probability that a "
        "less-than-majority attacker overtakes z confirmations. Formula "
        "from Nakamoto 2008 §11."
    )

    try:
        tip = _load_tip_block()
    except Exception as exc:
        st.error(f"API error while fetching the chain tip: {exc}")
        return

    difficulty = float(tip["difficulty"])
    # Same hashrate formula as M1 — keeps the dashboard internally consistent.
    hashrate_eh = difficulty * (2 ** 32) / TARGET_BLOCK_TIME_S / 1e18
    hashrate_th = hashrate_eh * 1e6  # 1 EH/s = 10^6 TH/s

    # ------------------------------------------------------------------
    # Attack-cost calculator
    # ------------------------------------------------------------------
    st.subheader("Attack cost (USD/hour)")

    col_a, col_b, col_c = st.columns(3)
    elec_price = col_a.number_input(
        "Electricity price (USD/kWh)",
        min_value=0.01, max_value=0.50,
        value=DEFAULT_ELECTRICITY_PRICE_USD_KWH,
        step=0.01,
        key="m6_elec",
        help="Industrial-scale Bitcoin miners typically pay $0.03-0.07/kWh "
             "by colocating with cheap-power sources (hydro, gas flares, "
             "geothermal). Residential rates ($0.12-0.30+) do not apply: "
             "a rational attacker would set up next to cheap power, like "
             "honest miners do.",
    )
    asic_eff = col_b.number_input(
        "ASIC efficiency (J/TH)",
        min_value=10.0, max_value=80.0,
        value=DEFAULT_ASIC_EFFICIENCY_J_PER_TH,
        step=1.0,
        key="m6_asic",
        help="Energy needed to compute one terahash. Top-tier 2024-25 ASICs "
             "reach ~13-20 J/TH; older fleets average higher.",
    )
    attacker_share = col_c.slider(
        "Attacker hashrate share q",
        min_value=0.10, max_value=0.99, value=0.51, step=0.01,
        format="%.2f",
        key="m6_q",
    )

    # To control share q of total network, attacker needs h_a such that
    # q = h_a / (h_a + H_honest). Solving: h_a = H * q / (1 - q).
    attacker_hashrate_th = hashrate_th * attacker_share / (1 - attacker_share)

    # Power [W] = efficiency [J/TH] * hashrate [TH/s] = J/s
    # kWh per hour = Power_W * 3600 / 3.6e6 = Power_W / 1000
    power_w = asic_eff * attacker_hashrate_th
    energy_kwh_per_hour = power_w / 1000
    cost_per_hour = energy_kwh_per_hour * elec_price

    col_x, col_y, col_z = st.columns(3)
    col_x.metric("Network hashrate", f"{hashrate_eh:,.2f} EH/s")
    col_y.metric(
        "Attacker hashrate needed",
        f"{attacker_hashrate_th / 1e6:,.2f} EH/s",
        help=f"To keep share q = {attacker_share:.0%} of the combined network.",
    )
    col_z.metric("Pure-electricity cost", f"${cost_per_hour:,.0f}/hour")

    st.caption(
        "**Electricity-only estimate.** Does not include hardware "
        "acquisition (~$3-5B at scale to outpace today's network), "
        "cooling, real estate, network bandwidth, or the opportunity "
        "cost of forfeiting honest block-reward income. Realistic full "
        "attack cost is one to two orders of magnitude higher."
    )

    # ------------------------------------------------------------------
    # Success probability vs confirmation depth (Nakamoto §11)
    # ------------------------------------------------------------------
    st.subheader("Success probability vs confirmation depth")

    z_values = np.arange(0, 21)
    q_curves = [0.10, 0.20, 0.30, 0.40, 0.45]

    fig = go.Figure()
    for q in q_curves:
        probs = [_attacker_success_probability(q, int(z)) for z in z_values]
        fig.add_trace(go.Scatter(
            x=z_values, y=probs,
            mode="lines+markers",
            name=f"q = {q:.0%}",
        ))
    fig.add_vline(
        x=6,
        line_dash="dash", line_color="#e74c3c",
        annotation_text="6 confirmations (standard)",
        annotation_position="top right",
    )
    fig.update_layout(
        xaxis_title="Confirmations z",
        yaxis_title="P(attacker overtakes chain)",
        yaxis=dict(range=[0, 1]),
        height=420,
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Probability of double-spend at the standard 6 confirmations:**")
    rows = []
    for q in [0.10, 0.20, 0.30, 0.40, 0.45, 0.49]:
        p = _attacker_success_probability(q, 6)
        rows.append({
            "Attacker share q": f"{q:.0%}",
            "P(success | z = 6)": f"{p:.6f}",
        })
    st.table(pd.DataFrame(rows))

    st.caption(
        "Source: Bitcoin whitepaper (Nakamoto 2008, §11 *Calculations*). "
        "An attacker with q < 50% of the network hashrate has an "
        "exponentially decaying probability of overtaking the honest "
        "chain as confirmations accumulate. With q = 50% the race is "
        "even and catch-up is no longer bounded; with q > 50% the "
        "attacker eventually wins regardless of depth — this is the "
        "51% attack scenario."
    )