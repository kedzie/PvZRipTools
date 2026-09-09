#!/usr/bin/env python3
"""Re-run just the compositor step (new fixed-width/tight-height/bottom-pivot
algorithm) for every already-ripped plant, overwriting frames in place under
export_all/. Skips audio/seedpacket entirely (unchanged, no need to redo).
Reuses already-decoded .pam.json files - does not re-invoke PopStudio."""
import json
import shutil
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pam_compositor import PamAsset

EXPORT_ROOT = Path("/mnt/d/PvZ2RipTest/export_all")


def pam_json_for(pam_file: str) -> Path:
    return Path(str(Path(pam_file).with_suffix("").with_suffix(".pam.json")))


def recomposite_one(pam_json, resources_json, atlas_png, group_id, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    asset = PamAsset(str(pam_json), resources_json, atlas_png, group_id)
    manifest = asset.export_all(str(out_dir))
    return len(manifest)


def main():
    plants = json.loads(Path("/mnt/d/PvZ/ReverseEngineering/PvZRipTools/plants.json").read_text())
    already_done_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    already_done = set(already_done_file.read_text().split()) if already_done_file and already_done_file.exists() else set()
    ok, failed, skipped = 0, [], []
    for entry in plants:
        name = entry["name"]
        if name in already_done:
            print(f"RESUME-SKIP {name}: already done", flush=True)
            continue
        pam_json = pam_json_for(entry["pam_file"])
        if not pam_json.exists():
            skipped.append(name)
            print(f"SKIP {name}: no decoded pam.json", flush=True)
            continue
        export_dir = EXPORT_ROOT / name
        try:
            n = recomposite_one(pam_json, entry["resources_json"], entry["atlas_png"],
                                 entry["group_id"], export_dir / "frames")
            proj_n = hit_n = None
            projectile = entry.get("projectile")
            if projectile:
                if projectile.get("attached_pam"):
                    proj_pam_json = pam_json_for(projectile["attached_pam"])
                    if proj_pam_json.exists():
                        proj_n = recomposite_one(proj_pam_json, entry["resources_json"], entry["atlas_png"],
                                                  entry["group_id"], export_dir / "projectile" / "frames")
                if projectile.get("impact_pam"):
                    hit_pam_json = pam_json_for(projectile["impact_pam"])
                    if hit_pam_json.exists():
                        hit_n = recomposite_one(hit_pam_json, entry["resources_json"], entry["atlas_png"],
                                                 entry["group_id"], export_dir / "projectile_hit" / "frames")
            print(f"OK {name}: {n} frames, projectile={proj_n}, hit={hit_n}", flush=True)
            ok += 1
        except Exception as e:
            failed.append(name)
            print(f"FAIL {name}: {e}", flush=True)
            traceback.print_exc()

    print(f"\n{ok} succeeded, {len(failed)} failed, {len(skipped)} skipped (no decoded pam.json)", flush=True)
    if failed:
        print("failed:", failed, flush=True)
    if skipped:
        print("skipped:", skipped, flush=True)


if __name__ == "__main__":
    main()
