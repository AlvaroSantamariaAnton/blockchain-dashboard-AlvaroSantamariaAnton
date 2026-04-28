"""
Blockchain API client.

We use two complementary public APIs (no key required):

* **Blockstream** (https://blockstream.info/api) — current chain tip, parsed
  block details and the raw 80-byte serialized header. The raw header is what
  miners hash twice with SHA-256 to produce the Proof of Work, so we need it
  for the manual verification in module M2.

* **blockchain.info** (https://blockchain.info) — long historical series of
  the network difficulty, used by module M3 (with a Blockstream fallback).
"""

from __future__ import annotations

import requests

BLOCKSTREAM_URL = "https://blockstream.info/api"
BLOCKCHAIN_INFO_URL = "https://blockchain.info"

_TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# Blockstream — current chain state, block details, raw 80-byte header
# ---------------------------------------------------------------------------

def get_tip_height() -> int:
    """Return the height of the current best block."""
    response = requests.get(f"{BLOCKSTREAM_URL}/blocks/tip/height", timeout=_TIMEOUT)
    response.raise_for_status()
    return int(response.text)


def get_tip_hash() -> str:
    """Return the hash of the current best block (hex string)."""
    response = requests.get(f"{BLOCKSTREAM_URL}/blocks/tip/hash", timeout=_TIMEOUT)
    response.raise_for_status()
    return response.text.strip()


def get_block(block_hash: str) -> dict:
    """Return the parsed block details: height, time, nonce, bits, ..."""
    response = requests.get(f"{BLOCKSTREAM_URL}/block/{block_hash}", timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_block_header_hex(block_hash: str) -> str:
    """Return the raw 80-byte block header as a hex string (160 chars)."""
    response = requests.get(
        f"{BLOCKSTREAM_URL}/block/{block_hash}/header", timeout=_TIMEOUT
    )
    response.raise_for_status()
    return response.text.strip()


def get_recent_blocks(start_height: int | None = None) -> list[dict]:
    """Return up to 10 block summaries.

    If *start_height* is None, returns the 10 most recent blocks. Otherwise
    returns 10 blocks starting at *start_height* and going backwards.
    """
    url = f"{BLOCKSTREAM_URL}/blocks"
    if start_height is not None:
        url = f"{url}/{start_height}"
    response = requests.get(url, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_last_n_blocks(n: int) -> list[dict]:
    """Return the most recent *n* block summaries, newest-first."""
    blocks: list[dict] = []
    next_height: int | None = None
    while len(blocks) < n:
        page = get_recent_blocks(next_height)
        if not page:
            break
        blocks.extend(page)
        next_height = page[-1]["height"] - 1
        if next_height < 0:
            break
    return blocks[:n]


# ---------------------------------------------------------------------------
# Difficulty history — primary: blockchain.info, fallback: Blockstream
# ---------------------------------------------------------------------------

def _get_difficulty_history_blockchain_info(timespan: str) -> list[dict]:
    """Return long-term difficulty samples from blockchain.info.

    *timespan* accepts blockchain.info chart values (``1year``, ``2years``,
    ``5years``, ``all``).
    """
    response = requests.get(
        f"{BLOCKCHAIN_INFO_URL}/charts/difficulty",
        params={"timespan": timespan, "format": "json", "sampled": "true"},
        timeout=_TIMEOUT,
        headers={"User-Agent": "CryptoChainAnalyzer/0.1 (UAX student project)"},
    )
    response.raise_for_status()
    data = response.json()
    return data.get("values", [])


def _get_difficulty_history_blockstream(timespan: str) -> list[dict]:
    """Build a difficulty history by sampling Blockstream every 2016 blocks.

    Bitcoin re-targets every 2016 blocks (~2 weeks). We walk backwards from
    the chain tip in 2016-block steps so each sample corresponds to one
    real difficulty epoch.
    """
    # Roughly how many 2016-block epochs fit in each window:
    epochs_per_window = {"1year": 26, "2years": 52, "5years": 130, "all": 400}
    n_epochs = epochs_per_window.get(timespan, 52)

    tip_height = get_tip_height()
    samples: list[dict] = []
    for i in range(n_epochs):
        height = tip_height - i * 2016
        if height <= 0:
            break
        # /block-height/{n} returns the hash of the block at that height
        h_resp = requests.get(
            f"{BLOCKSTREAM_URL}/block-height/{height}", timeout=_TIMEOUT
        )
        h_resp.raise_for_status()
        block_hash = h_resp.text.strip()
        block = get_block(block_hash)
        samples.append({"x": block["timestamp"], "y": block["difficulty"]})

    return list(reversed(samples))  # oldest-first for plotting


def get_difficulty_history(timespan: str = "2years") -> list[dict]:
    """Return difficulty samples as a list of {x: unix_ts, y: difficulty}.

    Tries blockchain.info first (one cheap request); if it is unavailable,
    falls back to building the series from Blockstream.
    """
    try:
        values = _get_difficulty_history_blockchain_info(timespan)
        if values:
            return values
    except Exception:
        pass  # fall through to the Blockstream fallback
    return _get_difficulty_history_blockstream(timespan)


# ---------------------------------------------------------------------------
# Quick CLI test — keeps Milestone-2 evidence working from the command line:
#     python -m api.blockchain_client
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tip_hash = get_tip_hash()
    block = get_block(tip_hash)
    header_hex = get_block_header_hex(tip_hash)

    print(f"Height:        {block['height']}")
    print(f"Hash:          {block['id']}")
    leading_hex_zeros = len(block["id"]) - len(block["id"].lstrip("0"))
    print(f"Leading hex 0: {leading_hex_zeros}")
    print(f"Nonce:         {block['nonce']}")
    print(f"Bits:          {block['bits']}  # compact 256-bit target")
    print(f"Difficulty:    {block['difficulty']:,.0f}")
    print(f"Tx count:      {block['tx_count']}")
    print(f"Header (hex):  {header_hex}  ({len(header_hex)//2} bytes)")