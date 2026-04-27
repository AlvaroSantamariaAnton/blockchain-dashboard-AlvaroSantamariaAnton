"""
Blockchain API client.

We use two complementary public APIs (no key required):

* **Blockstream** (https://blockstream.info/api) — current chain tip, parsed
  block details and the raw 80-byte serialized header. The raw header is what
  miners hash twice with SHA-256 to produce the Proof of Work, so we need it
  for the manual verification in module M2.

* **blockchain.info** (https://blockchain.info) — long historical series of
  the network difficulty, used by module M3.
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
    """Return the raw 80-byte block header as a hex string (160 chars).

    This is the exact byte-string that the miner hashes twice with SHA-256
    to satisfy the Proof of Work.
    """
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
    """Return the most recent *n* block summaries, newest-first.

    The Blockstream /blocks endpoint returns 10 blocks per page; this helper
    pages backwards until *n* blocks are collected.
    """
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
# blockchain.info — long-term difficulty history
# ---------------------------------------------------------------------------

def get_difficulty_history(timespan: str = "2years") -> list[dict]:
    """Return a list of {x: unix_ts, y: difficulty} samples.

    *timespan* accepts blockchain.info chart values such as ``1year``,
    ``2years``, ``5years``, ``all``.
    """
    response = requests.get(
        f"{BLOCKCHAIN_INFO_URL}/charts/difficulty",
        params={"timespan": timespan, "format": "json", "sampled": "true"},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("values", [])


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
    # The hash starts with many leading zeros — visual proof of the PoW.
    leading_hex_zeros = len(block["id"]) - len(block["id"].lstrip("0"))
    print(f"Leading hex 0: {leading_hex_zeros}")
    print(f"Nonce:         {block['nonce']}")
    # The 'bits' field encodes the target threshold in compact form:
    # first byte = exponent, last 3 bytes = mantissa, target = mantissa * 2^(8*(exp-3)).
    print(f"Bits:          {block['bits']}  # compact 256-bit target")
    print(f"Difficulty:    {block['difficulty']:,.0f}")
    print(f"Tx count:      {block['tx_count']}")
    print(f"Header (hex):  {header_hex}  ({len(header_hex)//2} bytes)")