#!/usr/bin/env python3
"""Cross-reference PAM dirs / RESOURCES.json groups / atlas PNGs / soundbanks
to build a canonical, resolved plant list for the full-dump pipeline."""
import json
from pathlib import Path

RIP_ROOT = Path("/mnt/d/PvZ/ReverseEngineering/PvZ2-OBB-Rip/pvz2_original_unpacked")
RESOURCES_JSON = Path("/mnt/d/PvZ2RipTest/RESOURCES.json")

# PAM folder name -> real camel-case plant name, for the handful of plants
# whose game-data name doesn't match their PAM folder name at all (typos,
# swapped word order, extra/missing words) - found by hand, one at a time,
# after underscore-normalization alone wasn't enough. Verified against both
# the resource group (Plant<X>_768/_1536) and, where noted, the soundbank.
NAME_ALIASES = {
    "IMPEAR": "ImpPear",                  # group is "ImpPear", not "Impear"
    "VINE_PYRE": "PyreVine",              # word order swapped
    "TELEPORTATO": "TeleportatoMine",     # group has an extra "Mine"
    "KERNALPULT": "Kernelpult",           # "Kernal" -> "Kernel" typo; BNK also uses this spelling
    "HEADBUTTER_LETTUCE": "Headbutter",   # group drops "Lettuce"
    "MURKADAMIA_NUT": "Murkadamia",       # group drops "Nut"
    "VINE_BLASTBERRY": "Blastberry",      # group drops "Vine"
    "SUNFLOWER_TWIN": "TwinSunflower",    # word order swapped
    "DAZEY_CHAIN": "Reincarnation",       # internal codename, found via PLANTTYPES.RTON's
                                           # PlantResourceGroups - bears no resemblance to the plant name
}

# Soundbank filename doesn't match the plant name at all - found by reading
# PLANTTYPES.RTON's per-plant "PlantResourceGroups" -> the "<X>Audio" group's
# SoundBank resource -> its literal "path" field, which is the ground truth
# and often diverges from both the PAM folder name and the resource group name
# (typos in the original game data, alternate/legacy names, shared banks).
BNK_NAME_OVERRIDES = {
    "DAZEY_CHAIN": "DAISYCHAIN",
    "JALAPENO": "JALEPENO",
    "MEGAGATLING": "GATLINGPEA",
    "POWERLILY": "POWERLILLY",
    "HOMINGTHISTLE": "THISTLE",
    "ICEBURG": "ICEBERGLETTUCE",         # shares bonkchoy-era Iceberg Lettuce's bank
    "ZOYBEANPOD": "ZOYBEAN",
    "CHILLYPEPPER": "CHILIPEPPER",
}

# Two parallel PAM trees exist - INITIAL/PLANT (121 plants, base app content)
# and FULL/PLANT (83 more, zero overlap - almost certainly Android's OBB
# "initial download" vs "full content" split). Both share the same
# RESOURCES.json / ATLASES / SOUNDBANKS, so only the PAM source path differs.
PLANT_ROOTS = ["IMAGES/768/INITIAL/PLANT", "IMAGES/768/FULL/PLANT"]


def main():
    pam_dir_by_name = {}
    for root in PLANT_ROOTS:
        for p in (RIP_ROOT / root).iterdir():
            if p.is_dir():
                if p.name in pam_dir_by_name:
                    print(f"WARNING: {p.name} exists under both trees, keeping first seen")
                    continue
                pam_dir_by_name[p.name] = root
    pam_dirs = sorted(pam_dir_by_name)

    with open(RESOURCES_JSON) as f:
        resources = json.load(f)
    groups = resources["groups"]

    # name_upper (no separators) -> proper camel-case name, preferring the group
    # that actually has atlas rects (type == "simple") so we don't pick up e.g.
    # "_Common" placeholder groups with the same stripped name.
    camel_by_upper = {}
    for g in groups:
        gid = g.get("id", "")
        if not gid.startswith("Plant"):
            continue
        for suffix in ("_1536", "_768"):
            if gid.endswith(suffix):
                camel = gid[len("Plant"):-len(suffix)]
                camel_by_upper[camel.upper()] = camel

    atlas_dir = RIP_ROOT / "ATLASES"

    bnk_dir = RIP_ROOT / "SOUNDBANKS"
    bnk_by_stripped = {p.stem.replace("_", "").upper(): p for p in bnk_dir.glob("PLANT_*.BNK")}

    resolved = []
    missing = []
    for name_upper in pam_dirs:
        pam_file = RIP_ROOT / pam_dir_by_name[name_upper] / name_upper / f"{name_upper}.PAM"
        core = NAME_ALIASES.get(name_upper, name_upper.replace("_", ""))
        camel = camel_by_upper.get(core.upper())
        reasons = []
        if not pam_file.exists():
            reasons.append("no .PAM file")
        if camel is None:
            reasons.append("no resource group")
        atlas_png = None
        group_id = None
        if camel:
            for suffix, res in (("_1536", 1536), ("_768", 768)):
                candidate = atlas_dir / f"PLANT{core.upper()}_{res}_00.PNG"
                if candidate.exists():
                    atlas_png = candidate
                    group_id = f"Plant{camel}{suffix}"
                    break
        if camel and atlas_png is None:
            reasons.append("no atlas PNG")
        # BNK filenames generally follow the raw PAM name (underscore-insensitive),
        # not the resource-group alias - try that first, then the explicit
        # override (verified against PLANTTYPES.RTON), then the alias as a
        # last resort (needed for Kernalpult, whose BNK uses the corrected spelling).
        bnk = bnk_by_stripped.get(f"PLANT{name_upper.replace('_', '').upper()}")
        if bnk is None and name_upper in BNK_NAME_OVERRIDES:
            bnk = bnk_by_stripped.get(f"PLANT{BNK_NAME_OVERRIDES[name_upper]}")
        if bnk is None:
            bnk = bnk_by_stripped.get(f"PLANT{core.upper()}")
        if bnk is None:
            reasons.append("no soundbank")

        if reasons:
            missing.append((name_upper, reasons))
            continue

        resolved.append({
            "name": name_upper,
            "camel": camel,
            "pam_file": str(pam_file),
            "resources_json": str(RESOURCES_JSON),
            "atlas_png": str(atlas_png),
            "group_id": group_id,
            "bnk": str(bnk),
        })

    print(f"PAM dirs found: {len(pam_dirs)}")
    print(f"Fully resolved (pam+group+atlas+bnk): {len(resolved)}")
    print(f"Missing pieces: {len(missing)}")
    for name, reasons in missing:
        print(f"  {name}: {', '.join(reasons)}")

    with open(Path(__file__).resolve().parent / "plants.json", "w") as f:
        json.dump(resolved, f, indent=2)
    print(f"\nwrote {len(resolved)} plants to plants.json")


if __name__ == "__main__":
    main()
