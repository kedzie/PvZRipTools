#!/usr/bin/env python3
"""Re-extract + re-convert every plant's sounds with the corrected aoTuV
codebook (see rip_plant.py's WW2OGG_PCB), without re-rendering frames.
Verifies each result with the same RMS/peak noise heuristic used to find
the bug in the first place, and reports any file still flagged afterward.

Usage: reconvert_sounds.py [--all | NAME ...]
"""
import json
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from bnk_extract import extract_bnk  # noqa: E402
from rip_plant import WORK, EXPORT_WIN_ROOT, convert_wems_to_ogg  # noqa: E402

NOISE_THRESHOLD = 0.4


def noise_ratio(ogg_path: Path):
    wav_path = ogg_path.with_suffix(".scan.wav")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(ogg_path), str(wav_path)],
                        capture_output=True, text=True)
    if r.returncode != 0 or not wav_path.exists():
        return None
    try:
        w = wave.open(str(wav_path), "rb")
        n = w.getnframes()
        if n == 0:
            return None
        data = w.readframes(n)
        samples = struct.unpack(f"<{n}h", data[:n * 2])
        peak = max(abs(s) for s in samples)
        if peak == 0:
            return None
        rms = (sum(s * s for s in samples) / n) ** 0.5
        return rms / peak
    finally:
        wav_path.unlink(missing_ok=True)


def reconvert(entry: dict) -> dict:
    name = entry["name"]
    plant_work = WORK / name
    wem_dir = plant_work / "wem"
    wem_ids = extract_bnk(Path(entry["bnk"]), wem_dir)

    sounds_dir = plant_work / "sounds_v2"
    if sounds_dir.exists():
        shutil.rmtree(sounds_dir)
    n_converted = convert_wems_to_ogg(wem_dir, sounds_dir)

    still_bad = []
    for ogg in sorted(sounds_dir.glob("*.ogg")):
        ratio = noise_ratio(ogg)
        if ratio is not None and ratio > NOISE_THRESHOLD:
            still_bad.append((ogg.name, ratio))

    export_sounds = EXPORT_WIN_ROOT / name / "sounds"
    if export_sounds.exists():
        shutil.rmtree(export_sounds)
    shutil.copytree(sounds_dir, export_sounds)

    return {"name": name, "wem_total": len(wem_ids), "ogg_converted": n_converted, "still_bad": still_bad}


def main():
    with open(TOOLS_DIR / "plants.json") as f:
        plants = json.load(f)

    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        targets = plants
    else:
        names = set(sys.argv[1:])
        targets = [p for p in plants if p["name"] in names]

    total_bad = []
    for entry in targets:
        res = reconvert(entry)
        bad_str = f" STILL BAD: {res['still_bad']}" if res["still_bad"] else ""
        print(f"OK  {entry['name']}: {res['ogg_converted']}/{res['wem_total']} converted{bad_str}")
        total_bad.extend((entry["name"], fn, r) for fn, r in res["still_bad"])

    print(f"\n{len(total_bad)} file(s) still flagged as noise-like after reconversion:")
    for name, fn, r in total_bad:
        print(f"  {name}/{fn} ratio={r:.3f}")


if __name__ == "__main__":
    main()
