# Blockchain Dashboard Project

Use this repository to build your blockchain dashboard project.
Update this README every week.

## Student Information

| Field | Value |
|---|---|
| Student Name | Alvaro Santamaria Anton |
| GitHub Username | AlvaroSantamariaAnton |
| Project Title | CryptoChain Analyzer Dashboard |
| Chosen AI Approach | Anomaly Detector — identifies blocks with statistically abnormal inter-arrival times using an exponential distribution as baseline |

## Module Tracking

Use one of these values: `Not started`, `In progress`, `Done`

| Module | What it should include | Status |
|---|---|---|
| M1 | Proof of Work Monitor | Done |
| M2 | Block Header Analyzer | Done |
| M3 | Difficulty History | Done |
| M4 | AI Component | Done |
| M6 | Security Score (optional) | Done |

## Current Progress

Write 3 to 5 short lines about what you have already done.

- **M1 done:** live difficulty, target-threshold visualisation in the 256-bit space, hash-rate estimate, and inter-block-time histogram with the theoretical Exp(mean = 600 s) curve overlaid.
- **M2 done:** raw 80-byte header parsed into its 6 little-endian fields and SHA-256(SHA-256(header)) computed with `hashlib`; the result matches the reported block hash and is verified to be below the target decoded from `bits`.
- **M3 done:** difficulty history with one marker per 2016-block retarget plus a second chart showing the actual-vs-target block-time ratio per epoch (red = slower than target, green = faster).
- **M4 done:** anomaly detector with score `S(Δt) = exp(-Δt / μ)`, flagged-blocks table, fitted exponential overlay on the histogram, and two-pronged evaluation — Kolmogorov-Smirnov goodness-of-fit (D statistic + asymptotic p-value) and a calibration curve comparing nominal α with empirical false-positive rate.
- **M6 done (optional):** 51% attack cost calculator from live hashrate data with configurable electricity price and ASIC efficiency, plus the attack-success probability vs confirmation depth curve from Nakamoto 2008 §11.
- **Report done:** 3-page PDF covering cryptographic metrics and their meaning, AI model choice and evaluation results, and 5 external references including the Nakamoto whitepaper.

## Next Step

Write the next small step you will do before the next class.

- Project complete.

## Main Problem or Blocker

Write here if you are stuck with something.

- 

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project Structure

```text
blockchain-dashboard-AlvaroSantamariaAnton/
|-- README.md
|-- requirements.txt
|-- .gitignore
|-- app.py
|-- api/
|   `-- blockchain_client.py
|-- modules/
|   |-- m1_pow_monitor.py
|   |-- m2_block_header.py
|   |-- m3_difficulty_history.py
|   |-- m4_ai_component.py
|   `-- m6_security_score.py
`-- reports/
    `-- CryptoChain_Analyzer_Final_Report.pdf
```

<!-- student-repo-auditor:teacher-feedback:start -->
## Teacher Feedback

### Kick-off Review

Review time: 2026-04-29 20:44 CEST
Status: Green

Strength:
- I can see the dashboard structure integrating the checkpoint modules.

Improve now:
- The checkpoint evidence is strong: the dashboard and core modules are visibly progressing.

Next step:
- Keep building on this checkpoint and prepare the final AI integration.
<!-- student-repo-auditor:teacher-feedback:end -->