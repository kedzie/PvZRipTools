#!/usr/bin/env python3
"""Full per-plant rip pipeline: PAM decode -> frame render -> WEM extract/convert
-> export to a Windows-visible dir ready for PvZRipImporter.ImportPlant.

Usage: rip_plant.py <plant_json_entry_index_or_name> [--all]
"""
import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

from PIL import Image

TOOLS_DIR = Path(__file__).resolve().parent
WORK = Path("/mnt/d/PvZ2RipTest/rip_work")
EXPORT_WIN_ROOT = Path("/mnt/d/PvZ2RipTest/export_all")
POPSTUDIO_EXE = r"D:\PvZ\ReverseEngineering\PopStudio-src\PopStudio.ConsoleProject\bin\Release\net9.0\win-x64\PopStudio.exe"
WW2OGG_EXE = r"D:\PvZ\ReverseEngineering\PvZRipTools\tools\ww2ogg\ww2ogg.exe"
WW2OGG_PCB = r"D:\PvZ\ReverseEngineering\PvZRipTools\tools\ww2ogg\packed_codebooks_aoTuV_603.bin"
PAM_COMPOSITOR = TOOLS_DIR / "pam_compositor.py"
BNK_EXTRACT = TOOLS_DIR / "bnk_extract.py"

sys.path.insert(0, str(TOOLS_DIR))
from bnk_extract import extract_bnk  # noqa: E402


def to_windows_path(p: Path) -> str:
    s = str(p.resolve())
    assert s.startswith("/mnt/d/"), f"not on D: drive: {s}"
    return "D:\\" + s[len("/mnt/d/"):].replace("/", "\\")


def run_popstudio_decode_pam(pam_file: Path):
    win_path = to_windows_path(pam_file)
    cmd = f'cmd.exe /c "{POPSTUDIO_EXE} {win_path} 180 < NUL"'
    subprocess.run(["bash", "-c", f"timeout 8 {cmd}"], capture_output=True, text=True)
    out = pam_file.with_suffix("").with_suffix(".pam.json") if False else Path(
        str(pam_file)[:-4] + ".pam.json"
    )
    if not out.exists():
        raise RuntimeError(f"DecodePam did not produce {out}")
    return out


def run_pam_compositor(pam_json, resources_json, atlas_png, group_id, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["python3", str(PAM_COMPOSITOR), str(pam_json), str(resources_json), str(atlas_png), group_id,
         "--all", str(out_dir)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pam_compositor failed: {result.stdout}\n{result.stderr}")
    if not (out_dir / "manifest.tsv").exists():
        raise RuntimeError(f"pam_compositor did not produce manifest.tsv: {result.stdout}")
    return result.stdout.strip()


def convert_wems_to_ogg(wem_dir: Path, ogg_dir: Path):
    ogg_dir.mkdir(parents=True, exist_ok=True)
    wems = sorted(wem_dir.glob("*.wem"))
    if not wems:
        return 0
    bat_lines = ["@echo off"]
    raw_ogg_dir_win = to_windows_path(ogg_dir)
    for wem in wems:
        wem_win = to_windows_path(wem)
        raw_ogg_win = f"{raw_ogg_dir_win}\\{wem.stem}_raw.ogg"
        bat_lines.append(f'"{WW2OGG_EXE}" "{wem_win}" --pcb "{WW2OGG_PCB}" -o "{raw_ogg_win}"')
    bat_path = wem_dir / "convert.bat"
    bat_path.write_text("\r\n".join(bat_lines) + "\r\n")
    bat_win = to_windows_path(bat_path)
    subprocess.run(["bash", "-c", f'cmd.exe /c "{bat_win}"'], capture_output=True, text=True, timeout=120)

    converted = 0
    wav_tmp = ogg_dir / "_tmp.wav"
    for wem in wems:
        raw_ogg = ogg_dir / f"{wem.stem}_raw.ogg"
        clean_ogg = ogg_dir / f"{wem.stem}.ogg"
        if not raw_ogg.exists():
            continue
        r1 = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw_ogg), str(wav_tmp)],
                             capture_output=True, text=True)
        if r1.returncode != 0 or not wav_tmp.exists():
            continue
        r2 = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav_tmp), "-c:a", "libvorbis", "-q:a", "5",
                              str(clean_ogg)], capture_output=True, text=True)
        raw_ogg.unlink()
        if wav_tmp.exists():
            wav_tmp.unlink()
        if r2.returncode == 0 and clean_ogg.exists():
            converted += 1
    return converted


# UI_SEEDPACKETS_*.PNG (unlike every PLANT*.PNG body atlas) comes out of the
# PTX->PNG conversion with R and B swapped. Its .PTX header's pixel-format
# field is 0, where every plant body atlas's is 147 - whatever tool did the
# conversion decodes format 147 correctly but gets format 0's channel order
# wrong. Confirmed by sampling: the raw UI_SEEDPACKETS crop for FirePeashooter
# is dominated by (0,0,192)/(0,96,224) blues, which is exactly FirePeashooter's
# real red/orange (192,0,0)/(224,96,0) with R and B swapped, while every body
# atlas (which renders correctly in-game) samples fine as-is. Fixing the
# upstream converter isn't practical here, so swap it back at the one point
# this atlas is ever read - if a future icon source atlas turns out to need
# the same fix, key this off the .PTX header's format field instead of the
# filename.
def crop_seedpacket(seedpacket: dict, out_png: Path):
    atlas = Image.open(seedpacket["atlas_png"]).convert("RGBA")
    if Path(seedpacket["atlas_png"]).name.upper().startswith("UI_SEEDPACKETS"):
        r, g, b, a = atlas.split()
        atlas = Image.merge("RGBA", (b, g, r, a))
    ax, ay, aw, ah = seedpacket["rect"]
    crop = atlas.crop((ax, ay, ax + aw, ay + ah))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out_png)


def rip_plant(entry: dict) -> dict:
    name = entry["name"]
    plant_work = WORK / name
    if plant_work.exists():
        shutil.rmtree(plant_work)
    plant_work.mkdir(parents=True)

    pam_json = run_popstudio_decode_pam(Path(entry["pam_file"]))

    frames_dir = plant_work / "frames"
    compositor_msg = run_pam_compositor(pam_json, entry["resources_json"], entry["atlas_png"],
                                         entry["group_id"], frames_dir)

    wem_dir = plant_work / "wem"
    wem_ids = extract_bnk(Path(entry["bnk"]), wem_dir)

    sounds_dir = plant_work / "sounds"
    n_converted = convert_wems_to_ogg(wem_dir, sounds_dir)

    export_dir = EXPORT_WIN_ROOT / name
    if export_dir.exists():
        shutil.rmtree(export_dir)
    (export_dir / "frames").parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(frames_dir, export_dir / "frames")
    shutil.copytree(sounds_dir, export_dir / "sounds")

    projectile_msg = None
    impact_msg = None
    projectile = entry.get("projectile")
    if projectile:
        if projectile.get("attached_pam"):
            try:
                proj_pam_json = run_popstudio_decode_pam(Path(projectile["attached_pam"]))
                proj_frames = plant_work / "projectile_frames"
                projectile_msg = run_pam_compositor(proj_pam_json, entry["resources_json"], entry["atlas_png"],
                                                      entry["group_id"], proj_frames)
                shutil.copytree(proj_frames, export_dir / "projectile" / "frames")
            except Exception as e:
                projectile_msg = f"FAILED: {e}"
        if projectile.get("impact_pam"):
            try:
                hit_pam_json = run_popstudio_decode_pam(Path(projectile["impact_pam"]))
                hit_frames = plant_work / "projectile_hit_frames"
                impact_msg = run_pam_compositor(hit_pam_json, entry["resources_json"], entry["atlas_png"],
                                                  entry["group_id"], hit_frames)
                shutil.copytree(hit_frames, export_dir / "projectile_hit" / "frames")
            except Exception as e:
                impact_msg = f"FAILED: {e}"

    seedpacket_ok = False
    seedpacket = entry.get("seedpacket")
    if seedpacket:
        try:
            crop_seedpacket(seedpacket, export_dir / "seedpacket" / f"SPR_SeedPacket_{entry['camel']}.png")
            seedpacket_ok = True
        except Exception:
            seedpacket_ok = False

    return {
        "name": name,
        "frames_msg": compositor_msg,
        "wem_total": len(wem_ids),
        "ogg_converted": n_converted,
        "projectile_msg": projectile_msg,
        "impact_msg": impact_msg,
        "seedpacket_ok": seedpacket_ok,
        "export_dir": str(export_dir),
    }


def main():
    with open(TOOLS_DIR / "plants.json") as f:
        plants = json.load(f)

    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        targets = plants
    else:
        names = set(sys.argv[1:])
        targets = [p for p in plants if p["name"] in names]

    results = []
    failures = []
    for entry in targets:
        try:
            res = rip_plant(entry)
            results.append(res)
            extras = []
            if res["projectile_msg"]:
                extras.append(f"proj={'OK' if not res['projectile_msg'].startswith('FAILED') else 'FAIL'}")
            if res["impact_msg"]:
                extras.append(f"hit={'OK' if not res['impact_msg'].startswith('FAILED') else 'FAIL'}")
            if res["seedpacket_ok"]:
                extras.append("seed=OK")
            extra_str = f" | {' '.join(extras)}" if extras else ""
            print(f"OK  {entry['name']}: {res['frames_msg']} | wem {res['ogg_converted']}/{res['wem_total']}{extra_str}")
        except Exception as e:
            failures.append((entry["name"], str(e)))
            print(f"FAIL {entry['name']}: {e}")
            traceback.print_exc()

    print(f"\n{len(results)} succeeded, {len(failures)} failed")
    with open(TOOLS_DIR / "rip_results.json", "w") as f:
        json.dump({"results": results, "failures": failures}, f, indent=2)


if __name__ == "__main__":
    main()
