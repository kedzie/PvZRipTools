#!/usr/bin/env python3
"""Incrementally add projectile/projectile_hit/seedpacket exports to plants that
already have their base frames+sounds rendered (from an earlier rip_plant.py run),
without re-rendering the (already correct) base plant frames.

Usage: add_extras.py [--all | NAME ...]
"""
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rip_plant import (  # noqa: E402
    TOOLS_DIR, EXPORT_WIN_ROOT, run_popstudio_decode_pam, run_pam_compositor, crop_seedpacket,
)
import shutil  # noqa: E402


def add_extras(entry: dict) -> dict:
    name = entry["name"]
    export_dir = EXPORT_WIN_ROOT / name
    if not export_dir.exists():
        raise RuntimeError(f"{export_dir} missing - run rip_plant.py for base frames first")

    work = Path("/mnt/d/PvZ2RipTest/rip_work") / name
    work.mkdir(parents=True, exist_ok=True)

    proj_status = None
    hit_status = None
    projectile = entry.get("projectile")
    if projectile:
        if projectile.get("attached_pam") and not (export_dir / "projectile" / "frames" / "manifest.tsv").exists():
            try:
                pam_json = run_popstudio_decode_pam(Path(projectile["attached_pam"]))
                out = work / "projectile_frames"
                run_pam_compositor(pam_json, entry["resources_json"], entry["atlas_png"], entry["group_id"], out)
                shutil.rmtree(export_dir / "projectile", ignore_errors=True)
                shutil.copytree(out, export_dir / "projectile" / "frames")
                proj_status = "OK"
            except Exception as e:
                proj_status = f"FAILED: {e}"
        if projectile.get("impact_pam") and not (export_dir / "projectile_hit" / "frames" / "manifest.tsv").exists():
            try:
                pam_json = run_popstudio_decode_pam(Path(projectile["impact_pam"]))
                out = work / "projectile_hit_frames"
                run_pam_compositor(pam_json, entry["resources_json"], entry["atlas_png"], entry["group_id"], out)
                shutil.rmtree(export_dir / "projectile_hit", ignore_errors=True)
                shutil.copytree(out, export_dir / "projectile_hit" / "frames")
                hit_status = "OK"
            except Exception as e:
                hit_status = f"FAILED: {e}"

    seed_status = None
    seedpacket = entry.get("seedpacket")
    if seedpacket:
        seed_png = export_dir / "seedpacket" / f"SPR_SeedPacket_{entry['camel']}.png"
        if not seed_png.exists():
            try:
                crop_seedpacket(seedpacket, seed_png)
                seed_status = "OK"
            except Exception as e:
                seed_status = f"FAILED: {e}"

    return {"name": name, "projectile": proj_status, "impact": hit_status, "seedpacket": seed_status}


def main():
    with open(TOOLS_DIR / "plants.json") as f:
        plants = json.load(f)

    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        targets = plants
    else:
        names = set(sys.argv[1:])
        targets = [p for p in plants if p["name"] in names]

    for entry in targets:
        try:
            res = add_extras(entry)
            print(f"OK  {entry['name']}: projectile={res['projectile']} impact={res['impact']} "
                  f"seedpacket={res['seedpacket']}")
        except Exception as e:
            print(f"FAIL {entry['name']}: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
