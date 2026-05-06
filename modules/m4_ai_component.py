"""M4 - AI Component (complete).

Anomaly detector for Bitcoin block inter-arrival times.

The baseline is the theoretical exponential distribution that a Poisson
mining process is expected to follow. Each block is scored by the
survival function `S(Δt) = exp(-Δt / μ)` where μ is the observed mean.
Blocks whose score falls below a threshold α are flagged as
statistically abnormal.

Evaluation uses two complementary checks:

* **Goodness-of-fit (Kolmogorov-Smirnov):** measures how well the data
  matches the theoretical exponential distribution overall.
* **Calibration:** compares the nominal threshold α with the empirical
  false-positive rate over the data — a well-fitting model should show
  empirical ≈ nominal.

A histogram with the fitted exponential curve and the flagged blocks
highlighted serves as visual evidence of the detector's behaviour.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from api.blockchain_client import get_last_n_blocks

TARGET_BLOCK_TIME_S = 600  # Bitcoin protocol target — 10 minutes per block


@st.cache_data(ttl=300, show_spinner=False)
def _load_recent_blocks(n: int) -> list[dict]:
    return get_last_n_blocks(n)


def _build_deltas(blocks: list[dict]) -> pd.DataFrame:
    """Sort blocks oldest-first and compute the inter-arrival deltas."""
    df = pd.DataFrame(blocks).sort_values("height").reset_index(drop=True)
    df["Date"] = pd.to_datetime(df["timestamp"], unit="s")
    df["DeltaSeconds"] = df["timestamp"].diff()
    return df


def _ks_test_exponential(deltas: np.ndarray, mu: float) -> tuple[float, float]:
    """Kolmogorov-Smirnov goodness-of-fit test against ``Exp(1/mu)``.

    Returns ``(D, p_value)`` where D is the KS statistic and p_value
    uses the standard asymptotic Kolmogorov approximation
    ``p ≈ 2·exp(-2·n·D²)``, valid for n ≳ 50.
    """
    n = len(deltas)
    sorted_d = np.sort(deltas)
    f_theo = 1 - np.exp(-sorted_d / mu)
    f_emp_above = np.arange(1, n + 1) / n
    f_emp_below = np.arange(0, n) / n
    d_stat = max(
        float(np.max(np.abs(f_emp_above - f_theo))),
        float(np.max(np.abs(f_emp_below - f_theo))),
    )
    p_value = float(min(2.0 * np.exp(-2.0 * n * d_stat ** 2), 1.0))
    return d_stat, p_value


def render() -> None:
    """Render the M4 panel."""
    st.header("M4 — AI Component")

    # ------------------------------------------------------------------
    # Approach summary
    # ------------------------------------------------------------------
    st.subheader("Chosen approach: anomaly detector")
    st.markdown(
        """
        The time between consecutive Bitcoin blocks is well-modelled as an
        **exponential distribution** `Exp(λ = 1/μ)` because mining is a
        Poisson process: each hash attempt is an independent Bernoulli
        trial with the same success probability, so the time until the
        next valid block follows an exponential law.

        The detector flags blocks whose inter-arrival time falls in the
        upper tail of this baseline (i.e. arrived significantly later
        than expected). The model needs no labelled training data — the
        theoretical distribution itself is the baseline.

        **Score:** `S(Δt) = exp(-Δt / μ)` (survival function).
        **Decision rule:** flag if `S(Δt) < α`.
        """
    )

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    st.subheader("Input data — inter-arrival times")

    col_a, col_b = st.columns(2)
    n_blocks = col_a.slider(
        "Number of recent blocks to analyse",
        min_value=100,
        max_value=500,
        value=500,
        step=50,
        key="m4_n",
    )
    alpha = col_b.select_slider(
        "Anomaly threshold α",
        options=[0.001, 0.005, 0.01, 0.02, 0.05, 0.1],
        value=0.01,
        key="m4_alpha",
        help="A block is flagged as anomalous if its survival score S(Δt) < α.",
    )

    try:
        blocks = _load_recent_blocks(n_blocks)
    except Exception as exc:
        st.error(f"API error while fetching blocks: {exc}")
        return

    df = _build_deltas(blocks)
    scored = df.dropna(subset=["DeltaSeconds"]).copy()
    scored = scored[scored["DeltaSeconds"] > 0]

    if len(scored) < 30:
        st.warning("Not enough block data to run the detector.")
        return

    deltas = scored["DeltaSeconds"].to_numpy()
    mu = float(deltas.mean())

    col1, col2, col3 = st.columns(3)
    col1.metric("Blocks analysed", f"{len(scored):,}")
    col2.metric("Observed mean Δt", f"{mu:.0f} s")
    col3.metric("Protocol target", f"{TARGET_BLOCK_TIME_S} s")

    # ------------------------------------------------------------------
    # Anomaly scoring
    # ------------------------------------------------------------------
    st.subheader("Anomaly scoring")

    scored["Score"] = np.exp(-scored["DeltaSeconds"] / mu)
    scored["Anomaly"] = scored["Score"] < alpha
    threshold_seconds = -mu * float(np.log(alpha))
    n_anom = int(scored["Anomaly"].sum())

    col_x, col_y, col_z = st.columns(3)
    col_x.metric(
        "Threshold Δt",
        f"{threshold_seconds:.0f} s (≈ {threshold_seconds/60:.1f} min)",
    )
    col_y.metric("Flagged blocks", n_anom)
    col_z.metric("Flagged ratio", f"{n_anom / len(scored) * 100:.2f} %")

    # Histogram with theoretical PDF overlay and flagged-block markers.
    n_bins = 30
    bin_width = float(deltas.max()) / n_bins
    x_grid = np.linspace(0, float(deltas.max()), 200)
    pdf_counts = (1 / mu) * np.exp(-x_grid / mu) * len(deltas) * bin_width

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=deltas,
        nbinsx=n_bins,
        name="All blocks",
        marker_color="#3498db",
        opacity=0.65,
    ))
    fig.add_trace(go.Scatter(
        x=x_grid, y=pdf_counts,
        mode="lines",
        name=f"Exp(mean={mu:.0f}s) — fitted",
        line=dict(color="#2c3e50", width=2),
    ))
    fig.add_vline(
        x=threshold_seconds,
        line_dash="dash", line_color="#e74c3c",
        annotation_text=f"α = {alpha} → Δt > {threshold_seconds:.0f}s",
        annotation_position="top right",
    )
    if n_anom:
        anom_deltas = scored.loc[scored["Anomaly"], "DeltaSeconds"]
        fig.add_trace(go.Scatter(
            x=anom_deltas, y=[0] * len(anom_deltas),
            mode="markers",
            name=f"Flagged ({n_anom})",
            marker=dict(symbol="triangle-up", size=12, color="#e74c3c"),
        ))
    fig.update_layout(
        xaxis_title="Seconds between blocks",
        yaxis_title="Block count",
        height=420,
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, use_container_width=True)

    if n_anom:
        st.markdown("**Flagged blocks** (most anomalous first)")
        flagged = (
            scored.loc[scored["Anomaly"], ["height", "Date", "DeltaSeconds", "Score"]]
            .sort_values("Score")
            .reset_index(drop=True)
        )
        flagged["DeltaSeconds"] = flagged["DeltaSeconds"].map(lambda v: f"{v:.0f}")
        flagged["Score"] = flagged["Score"].map(lambda v: f"{v:.2e}")
        st.dataframe(flagged.head(10), use_container_width=True)
    else:
        st.info(f"No block in this window scores below α = {alpha}.")

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    st.subheader("Evaluation")

    # --- Goodness of fit (KS) ---
    d_stat, p_ks = _ks_test_exponential(deltas, mu)
    col_g1, col_g2 = st.columns(2)
    col_g1.metric("KS statistic D", f"{d_stat:.4f}")
    col_g2.metric("KS p-value (asymp.)", f"{p_ks:.3f}")
    if p_ks > 0.05:
        st.success(
            "✅ The KS test does **not** reject the exponential model "
            f"(p = {p_ks:.3f} > 0.05). The data is consistent with the "
            "Poisson-process baseline."
        )
    else:
        st.warning(
            "⚠ The KS test rejects the exponential model "
            f"(p = {p_ks:.3f} ≤ 0.05). Real-world effects (network "
            "propagation, hash-rate drift, pool variance) are visible "
            "in this window."
        )
    st.caption(
        "The Kolmogorov-Smirnov statistic D is the maximum vertical "
        "distance between the empirical CDF and the theoretical "
        "exponential CDF. The asymptotic p-value uses the standard "
        "Kolmogorov approximation; because μ is estimated from the "
        "data, the test is mildly conservative (Lilliefors correction "
        "is left out for clarity)."
    )

    # --- Calibration ---
    st.markdown("**Calibration — nominal α vs empirical false-positive rate**")
    alphas_eval = np.array([0.001, 0.005, 0.01, 0.02, 0.05, 0.1])
    emp_fpr = np.array([
        float((scored["Score"] < a).mean()) for a in alphas_eval
    ])
    fig_cal = go.Figure()
    fig_cal.add_trace(go.Scatter(
        x=alphas_eval, y=emp_fpr,
        mode="lines+markers",
        name="Empirical FPR",
        marker=dict(size=10),
    ))
    fig_cal.add_trace(go.Scatter(
        x=[0, 0.1], y=[0, 0.1],
        mode="lines",
        name="Perfect calibration",
        line=dict(dash="dash", color="#95a5a6"),
    ))
    fig_cal.update_layout(
        xaxis_title="Nominal α (chosen threshold)",
        yaxis_title="Empirical false-positive rate",
        height=350,
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig_cal, use_container_width=True)
    st.caption(
        "A well-calibrated detector should produce an empirical "
        "false-positive rate that tracks the nominal α (dashed line). "
        "Systematic deviation **above** the line means the model "
        "under-fits the upper tail (over-flags); **below** the line "
        "means it over-fits the upper tail (under-flags)."
    )