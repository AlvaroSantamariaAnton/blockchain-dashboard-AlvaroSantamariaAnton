"""
Blockchain API client.

We use two complementary public APIs (no key required):

* **Blockstream** (https://blockstream.info/api) — current chain tip, parsed
  block details and the raw 80-byte serialized header. The raw header is what
  miners hash twice with SHA-256 to produce the Proof of Work, so we need it
  for the manual verification in module M2.

* **Mempool.space** (https://mempool.space/api) — long historical series of
  the network difficulty (every 2016-block adjustment is included), used by
  module M3.
"""

from __future__ import annotations

import requests

BLOCKSTREAM_URL = "https://blockstream.info/api"
MEMPOOL_URL = "https://mempool.space/api"

_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Blockstream — current chain state, block details, raw 80-byte header
# ---------------------------------------------------------------------------

def get_tip_height() -> int:
    response = requests.get(f"{BLOCKSTREAM_URL}/blocks/tip/height", timeout=_TIMEOUT)
    response.raise_for_status()
    return int(response.text)


def get_tip_hash() -> str:
    response = requests.get(f"{BLOCKSTREAM_URL}/blocks/tip/hash", timeout=_TIMEOUT)
    response.raise_for_status()
    return response.text.strip()


def get_block(block_hash: str) -> dict:
    response = requests.get(f"{BLOCKSTREAM_URL}/block/{block_hash}", timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_block_header_hex(block_hash: str) -> str:
    response = requests.get(
        f"{BLOCKSTREAM_URL}/block/{block_hash}/header", timeout=_TIMEOUT
    )
    response.raise_for_status()
    return response.text.strip()


def get_recent_blocks(start_height: int | None = None) -> list[dict]:
    """Up to 10 block summaries. None = newest 10. int = 10 ending at that height."""
    url = f"{BLOCKSTREAM_URL}/blocks"
    if start_height is not None:
        url = f"{url}/{start_height}"
    response = requests.get(url, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_last_n_blocks(n: int) -> list[dict]:
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
# Difficulty history — Mempool.space
# ---------------------------------------------------------------------------

# Mempool.space accepts these intervals on /api/v1/mining/hashrate/<period>:
_MEMPOOL_INTERVALS = {"1m", "3m", "6m", "1y", "2y", "3y"}


def get_difficulty_history(timespan: str = "2y") -> list[dict]:
    """Return difficulty samples as ``[{x: unix_ts, y: difficulty}, ...]``.

    Source: mempool.space /api/v1/mining/hashrate/<timespan>. The endpoint
    returns one entry per real difficulty adjustment (every 2016 blocks).
    """
    if timespan not in _MEMPOOL_INTERVALS:
        timespan = "2y"

    response = requests.get(
        f"{MEMPOOL_URL}/v1/mining/hashrate/{timespan}",
        timeout=_TIMEOUT,
        headers={"User-Agent": "CryptoChainAnalyzer/0.1 (UAX student project)"},
    )
    response.raise_for_status()
    data = response.json()

    samples: list[dict] = []
    for item in data.get("difficulty", []):
        # Mempool.space uses "time" in some versions and "timestamp" in others.
        ts = item.get("time", item.get("timestamp"))
        diff = item.get("difficulty")
        if ts is None or diff is None:
            continue
        samples.append({"x": ts, "y": diff})
    return samples


# ---------------------------------------------------------------------------
# Quick CLI test:
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