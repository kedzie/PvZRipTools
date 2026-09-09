#!/usr/bin/env python3
"""Resolve projectile (AttachedPAM/ImpactPAM via PROJECTILETYPES.RTON) and seed
packet (UI_SeedPackets atlas crop) data for every plant in plants.json, writing
the results back in place as "projectile" / "seedpacket" keys (null if none)."""
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from enumerate_plants import NAME_ALIASES  # noqa: E402

# A few plants use a shorter/different name specifically in the seed-packet
# UI atlas than in the resource group (e.g. HOCUS_CROCUS's group is
# "PlantHocusCrocus" but its packet icon is just "IMAGE_UI_PACKETS_HOCUS").
SEEDPACKET_ALIASES = {
    "HOCUS_CROCUS": "Hocus",
}
RIP_ROOT = Path("/mnt/d/PvZ/ReverseEngineering/PvZ2-OBB-Rip/pvz2_original_unpacked")
RESOURCES_JSON = Path("/mnt/d/PvZ2RipTest/RESOURCES.json")
PROJECTILETYPES_JSON = RIP_ROOT / "PACKAGES/PROJECTILETYPES.json"
EFFECTS_DIR = RIP_ROOT / "IMAGES/768/INITIAL/EFFECTS"
ATLAS_DIR = RIP_ROOT / "ATLASES"


def popanim_to_pam(popanim_name: str):
    """'POPANIM_EFFECTS_T_BLOOMERANG_PROJECTILE' -> EFFECTS/T_BLOOMERANG_PROJECTILE/....PAM"""
    if not popanim_name or not popanim_name.startswith("POPANIM_EFFECTS_"):
        return None
    name = popanim_name[len("POPANIM_EFFECTS_"):]
    pam_file = EFFECTS_DIR / name / f"{name}.PAM"
    return pam_file if pam_file.exists() else None


def main():
    with open(RESOURCES_JSON) as f:
        resources = json.load(f)
    groups_by_id = {g["id"]: g for g in resources["groups"]}

    with open(PROJECTILETYPES_JSON) as f:
        proj_data = json.load(f)
    alias_to_obj = {}
    for o in proj_data["objects"]:
        for a in o.get("aliases", []):
            alias_to_obj[a.upper()] = o

    seedpacket_rect_by_name = {}
    for suffix, res in (("_1536", 1536), ("_768", 768)):
        g = groups_by_id.get(f"UI_SeedPackets{suffix}")
        if not g:
            continue
        atlas_png = ATLAS_DIR / f"UI_SEEDPACKETS_{res}_00.PNG"
        if not atlas_png.exists():
            continue
        for r in g.get("resources", []):
            if "ax" not in r:
                continue
            rid = r["id"]
            if not rid.startswith("IMAGE_UI_PACKETS_"):
                continue
            name = rid[len("IMAGE_UI_PACKETS_"):]
            if name not in seedpacket_rect_by_name:
                seedpacket_rect_by_name[name] = {
                    "atlas_png": str(atlas_png),
                    "rect": [r["ax"], r["ay"], r["aw"], r["ah"]],
                }

    with open(TOOLS_DIR / "plants.json") as f:
        plants = json.load(f)

    n_proj = 0
    n_seed = 0
    for p in plants:
        name_norm = p["name"].replace("_", "")
        candidates = [a for a in alias_to_obj if a.startswith(name_norm)]
        proj_entry = None
        if candidates:
            candidates.sort(key=lambda a: (not a.endswith("DEFAULT"), a))
            obj = alias_to_obj[candidates[0]]
            attached = popanim_to_pam(obj["objdata"].get("AttachedPAM", ""))
            impact = popanim_to_pam(obj["objdata"].get("ImpactPAM", ""))
            if attached or impact:
                proj_entry = {
                    "alias": candidates[0],
                    "attached_pam": str(attached) if attached else None,
                    "impact_pam": str(impact) if impact else None,
                }
                n_proj += 1
        p["projectile"] = proj_entry

        seed_core = SEEDPACKET_ALIASES.get(p["name"]) or NAME_ALIASES.get(p["name"], p["name"].replace("_", ""))
        seed = seedpacket_rect_by_name.get(seed_core.upper())
        p["seedpacket"] = seed
        if seed:
            n_seed += 1

    with open(TOOLS_DIR / "plants.json", "w") as f:
        json.dump(plants, f, indent=2)

    print(f"{n_proj}/{len(plants)} plants resolved a projectile")
    print(f"{n_seed}/{len(plants)} plants resolved a seed packet")


if __name__ == "__main__":
    main()
