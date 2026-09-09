#!/usr/bin/env python3
"""Extract embedded WEM blobs from a Wwise .BNK soundbank via proper chunk walking.

Usage: bnk_extract.py <input.bnk> <output_dir>
Writes <output_dir>/<wem_id>.wem for every entry in the bank's DIDX index.
"""
import struct
import sys
from pathlib import Path


def extract_bnk(bnk_path: Path, out_dir: Path) -> list[int]:
    data = bnk_path.read_bytes()
    pos = 0
    didx = None
    data_chunk_start = None
    data_chunk_payload = None

    while pos + 8 <= len(data):
        tag = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        payload_start = pos + 8
        payload = data[payload_start:payload_start + size]

        if tag == b"DIDX":
            didx = payload
        elif tag == b"DATA":
            data_chunk_payload = payload

        pos = payload_start + size
        if size % 2 == 1:
            pos += 1  # chunks are word-aligned

    if didx is None or data_chunk_payload is None:
        raise ValueError(f"{bnk_path}: missing DIDX or DATA chunk")

    if len(didx) % 12 != 0:
        raise ValueError(f"{bnk_path}: DIDX size {len(didx)} not a multiple of 12")

    out_dir.mkdir(parents=True, exist_ok=True)
    wem_ids = []
    for i in range(0, len(didx), 12):
        wem_id, offset, length = struct.unpack_from("<III", didx, i)
        blob = data_chunk_payload[offset:offset + length]
        if len(blob) != length:
            raise ValueError(f"{bnk_path}: entry {wem_id} truncated ({len(blob)} != {length})")
        (out_dir / f"{wem_id}.wem").write_bytes(blob)
        wem_ids.append(wem_id)
    return wem_ids


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.bnk> <output_dir>", file=sys.stderr)
        sys.exit(1)
    ids = extract_bnk(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Extracted {len(ids)} wem(s): {ids}")
