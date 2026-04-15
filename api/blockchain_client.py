"""
Blockchain API client.

Provides helper functions to fetch blockchain data from public APIs.
"""

import requests

BASE_URL = "https://blockchain.info"


def get_latest_block() -> dict:
    """Return the latest block summary."""
    response = requests.get(f"{BASE_URL}/latestblock", timeout=10)
    response.raise_for_status()
    return response.json()


def get_block(block_hash: str) -> dict:
    """Return full details for a block identified by *block_hash*."""
    response = requests.get(
        f"{BASE_URL}/rawblock/{block_hash}", timeout=10
    )
    response.raise_for_status()
    return response.json()


def get_difficulty_history(n_points: int = 100) -> list[dict]:
    """Return the last *n_points* difficulty values as a list of dicts."""
    response = requests.get(
        f"{BASE_URL}/charts/difficulty",
        params={"timespan": "1year", "format": "json", "sampled": "true"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("values", [])[-n_points:]


if __name__ == "__main__":
    # --- Milestone 2: First API Call ---
    # Fetch latest block summary and full block details
    latest = get_latest_block()
    block = get_block(latest["hash"])

    print(f"Height:        {block['height']}")
    print(f"Hash:          {block['hash']}")
    # The hash starts with many leading zeros — this is the visual proof of
    # the Proof of Work. The miner had to find a nonce such that
    # SHA256(SHA256(header)) produced a hash below the target threshold.
    leading_zeros = len(block['hash']) - len(block['hash'].lstrip('0'))
    print(f"Leading zeros: {leading_zeros}")
    print(f"Nonce:         {block['nonce']}")
    # The 'bits' field encodes the target threshold in compact form:
    # the first byte is the exponent and the next 3 bytes are the mantissa.
    # target = mantissa * 2^(8*(exponent-3))
    # The difficulty is how many times harder this is vs the genesis target.
    bits = block['bits']
    exp = bits >> 24
    mantissa = bits & 0xFFFFFF
    target = mantissa * (2 ** (8 * (exp - 3)))
    difficulty_1 = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
    difficulty = difficulty_1 / target

    print(f"Bits:          {bits}  # compact encoding of the 256-bit target")
    print(f"Difficulty:    {difficulty:,.0f}")
    print(f"Transactions:  {block['n_tx']}")