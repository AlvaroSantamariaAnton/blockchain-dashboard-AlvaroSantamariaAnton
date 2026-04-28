"""M2 - Block Header Analyzer.

Display the 80-byte block header structure and verify the Proof of Work
locally with ``hashlib``. The verification is the central evidence required
by rubric criterion C1 (Cryptographic Correctness).
"""

from __future__ import annotations

import hashlib

import streamlit as st

from api.blockchain_client import get_block, get_block_header_hex, get_tip_hash


def _bits_to_target(bits: int) -> int:
    """Decode the compact ``bits`` field into the full 256-bit target."""
    exponent = bits >> 24
    mantissa = bits & 0xFFFFFF
    return mantissa * (2 ** (8 * (exponent - 3)))


def _double_sha256(data: bytes) -> bytes:
    """Return SHA-256(SHA-256(data)) — Bitcoin's hash function."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _parse_header(header_hex: str) -> dict:
    """Parse the 80-byte serialized header and return its 6 fields.

    Layout (Section 6 of the course notes):

    ===========  =======  ==========================================
    Field        Bytes    Encoding
    ===========  =======  ==========================================
    version       4       little-endian int32
    prev_block   32       little-endian (display = byte-reversed)
    merkle_root  32       little-endian (display = byte-reversed)
    timestamp     4       little-endian uint32 (unix seconds)
    bits          4       little-endian uint32 (compact target)
    nonce         4       little-endian uint32
    ===========  =======  ==========================================
    """
    raw = bytes.fromhex(header_hex)
    if len(raw) != 80:
        raise ValueError(f"Header must be 80 bytes, got {len(raw)}")

    return {
        "version":     int.from_bytes(raw[0:4],   "little"),
        "prev_block":  raw[4:36][::-1].hex(),
        "merkle_root": raw[36:68][::-1].hex(),
        "timestamp":   int.from_bytes(raw[68:72], "little"),
        "bits":        int.from_bytes(raw[72:76], "little"),
        "nonce":       int.from_bytes(raw[76:80], "little"),
    }


@st.cache_data(ttl=60, show_spinner=False)
def _load_tip_hash() -> str:
    return get_tip_hash()


@st.cache_data(ttl=300, show_spinner=False)
def _load_header_and_block(block_hash: str) -> tuple[str, dict]:
    return get_block_header_hex(block_hash), get_block(block_hash)


def render() -> None:
    """Render the M2 panel."""
    st.header("M2 — Block Header Analyzer")
    st.caption(
        "Inspect the 80-byte header of any Bitcoin block and verify the "
        "Proof of Work locally with hashlib."
    )

    try:
        tip_hash = _load_tip_hash()
    except Exception as exc:
        st.error(f"Could not fetch the chain tip: {exc}")
        return

    # Follow the chain tip automatically unless the user wants to inspect a
    # specific block. When 'follow tip' is on, the input is disabled and
    # always shows the current tip — so the panel updates as new blocks
    # arrive without losing what the user typed.
    follow_tip = st.checkbox(
        "Follow chain tip (auto-update with each new block)",
        value=True,
        key="m2_follow_tip",
    )

    if follow_tip:
        block_hash = tip_hash
        st.text_input(
            "Block hash",
            value=tip_hash,
            disabled=True,
            key="m2_hash_display",
            help="Uncheck the box above to inspect a specific historical block.",
        )
    else:
        block_hash = st.text_input(
            "Block hash to analyse",
            value=tip_hash,
            key="m2_hash_manual",
        ).strip()

    if not block_hash:
        st.info("Enter a block hash and the panel will refresh.")
        return

    try:
        header_hex, block = _load_header_and_block(block_hash)
    except Exception as exc:
        st.error(f"API error: {exc}")
        return

    fields = _parse_header(header_hex)

    # --- Raw 80-byte header ------------------------------------------------
    st.subheader("Raw 80-byte header (hex)")
    st.code(header_hex, language="text")
    st.caption(
        f"Length: {len(header_hex) // 2} bytes — exactly the byte-string "
        "that miners hash twice with SHA-256 to satisfy the PoW."
    )

    # --- Six header fields -------------------------------------------------
    st.subheader("Six header fields parsed from the raw bytes")
    st.table(
        {
            "Field":  ["version", "prev_block", "merkle_root",
                       "timestamp", "bits", "nonce"],
            "Bytes":  ["4", "32", "32", "4", "4", "4"],
            "Value":  [
                f"{fields['version']}",
                fields["prev_block"],
                fields["merkle_root"],
                f"{fields['timestamp']} (unix seconds)",
                f"{fields['bits']} (0x{fields['bits']:08x})",
                f"{fields['nonce']}",
            ],
        }
    )
    st.caption(
        "All multi-byte integers in the serialized header are stored "
        "**little-endian**. The 32-byte hashes (`prev_block`, `merkle_root`) "
        "are also byte-reversed when displayed by Bitcoin block explorers, "
        "which is why the explorer representation looks different from the "
        "raw bytes above."
    )

    # --- Manual Proof-of-Work verification ---------------------------------
    st.subheader("Proof-of-Work verification with hashlib")

    raw_header = bytes.fromhex(header_hex)
    digest = _double_sha256(raw_header)
    # Bitcoin displays the hash in reverse byte order (RPC/explorer convention).
    computed_hash = digest[::-1].hex()
    target = _bits_to_target(fields["bits"])
    hash_int = int(computed_hash, 16)
    is_valid = hash_int < target

    col1, col2 = st.columns(2)
    col1.markdown("**Computed `SHA-256(SHA-256(header))`**")
    col1.code(computed_hash, language="text")
    col2.markdown("**Reported block hash**")
    col2.code(block["id"], language="text")

    if computed_hash == block["id"]:
        st.success(
            "✅ Computed hash matches the reported block hash — "
            "the 80 bytes really are this block's header."
        )
    else:
        st.error(
            "❌ Computed hash does not match the reported one. "
            "Check the byte order or the input hex."
        )

    st.markdown("**Target threshold (decoded from `bits`):**")
    st.code(f"{target:064x}", language="text")

    if is_valid:
        st.success("✅ hash < target → the Proof of Work is valid.")
    else:
        st.error(
            "❌ hash ≥ target → invalid PoW "
            "(should never happen for a real block)."
        )

    leading_zero_bits = 256 - hash_int.bit_length() if hash_int else 256
    st.metric("Leading zero bits in the block hash", leading_zero_bits)
    st.caption(
        "To be valid, the hash must be smaller than the target, which forces "
        "at least the same number of leading zero bits as the target itself. "
        "More zero bits ⇒ smaller hash ⇒ rarer event ⇒ more hashes had to be "
        "tried on average."
    )