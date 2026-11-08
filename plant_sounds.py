#!/usr/bin/env python3
"""Derive a plant's sound events straight from the PvZ2 data instead of by ear.

Where the information lives:
  * The plant's decoded .pam.json carries "PlaySample" commands on specific
    frames of its main timeline (e.g. frame 97 of the attack animation fires
    "Play_Plant_DuskLobber_Attack"), plus "use_action" markers on the frame the
    plant actually acts (spawns its projectile, etc).
  * GLOBAL_DATA.BNK's HIRC chunk maps each event (id = 32-bit FNV-1 hash of the
    lower-cased event name) -> Action -> Sound / Random Container -> source WEM ids.
  * PLANT_<NAME>.BNK only holds the embedded media (DIDX/DATA) that
    bnk_extract.py already unpacks, so the WEM ids it lists are the ogg names in
    the export's sounds/ folder.

Writes <export>/sounds_manifest.json (and projectile/ + projectile_hit/ siblings
when the plant has those PAMs):

    {"frame_rate": 30,
     "animations": [{"label": "attack", "start": 96, "end": 140, "frames": 45,
                     "events": [{"frame": 1, "sample": "Play_Plant_X_Attack",
                                 "sounds": [143238138, ...], "external": []}],
                     "actions": [{"frame": 11, "command": "use_action", "parameter": ""}]}],
     "unresolved": []}

"frame" is the offset inside the label's own frame range, i.e. the index of the
exported frame_<N+1>.png, so the Unity side can time an Animation Event off that
clip's own keyframe times regardless of the clip's sample rate.

Usage: plant_sounds.py <PLANT_NAME> [<PLANT_NAME> ...]   (names as in plants.json)
"""
import json
import struct
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
EXPORT_ROOT = Path("/mnt/d/PvZ2RipTest/export_all")
PROJECTILE_TYPES = Path("/mnt/d/PvZ/ReverseEngineering/PvZ2-OBB-Rip/pvz2_original_unpacked/PACKAGES/PROJECTILETYPES.json")
SOUNDBANKS = Path("/mnt/d/PvZ/ReverseEngineering/PvZ2-OBB-Rip/pvz2_original_unpacked/SOUNDBANKS")
GLOBAL_BANK = SOUNDBANKS / "GLOBAL_DATA.BNK"

_bank_cache = {}


def fnv(name: str) -> int:
    x = 2166136261
    for c in name.lower().encode():
        x = (x * 16777619) & 0xFFFFFFFF
        x ^= c
    return x


def read_chunks(path: Path) -> dict:
    data = path.read_bytes()
    chunks = {}
    pos = 0
    while pos + 8 <= len(data):
        tag = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        chunks[tag] = data[pos + 8:pos + 8 + size]
        pos += 8 + size
    return chunks


def media_ids(path: Path) -> set:
    didx = read_chunks(path).get(b"DIDX", b"")
    return {struct.unpack_from("<I", didx, i)[0] for i in range(0, len(didx), 12)}


def hirc_objects(path: Path):
    """{object id: (type, body)} for a bank's HIRC chunk, or None if it has none."""
    if path in _bank_cache:
        return _bank_cache[path]
    h = read_chunks(path).get(b"HIRC")
    objs = None
    if h is not None:
        n = struct.unpack_from("<I", h, 0)[0]
        p = 4
        objs = {}
        for _ in range(n):
            t = h[p]
            ln = struct.unpack_from("<I", h, p + 1)[0]
            body = h[p + 5:p + 5 + ln]
            objs[struct.unpack_from("<I", body, 0)[0]] = (t, body)
            p += 5 + ln
    _bank_cache[path] = objs
    return objs


def _u32s(b):
    return [struct.unpack_from("<I", b, i)[0] for i in range(0, len(b) - 3)]


def event_sources(objs, oid, seen=None):
    """Source WEM ids behind an event/action/container, in child-list order.

    Wwise (bank v140) layout, as used here: Event = id, u8 count, u32 action ids;
    Action = id, u16 type, u32 target id; Sound SFX = id, u32 plugin, u8 stream
    type, u32 source id; Random/Sequence Container (5) and Switch Container (6)
    list their children among their other fields. A container's body also holds
    its PARENT's id, so only follow ids that are Sound (2) / Container (5)
    objects - never an Actor-Mixer (7), which would walk back up into every
    sibling plant sound.
    """
    seen = seen if seen is not None else set()
    out = []
    if oid in seen or oid not in objs:
        return out
    seen.add(oid)
    t, body = objs[oid]
    if t == 2:
        out.append(struct.unpack_from("<I", body, 9)[0])
    elif t == 3:
        out += event_sources(objs, struct.unpack_from("<I", body, 6)[0], seen)
    elif t == 4:
        for i in range(body[4]):
            out += event_sources(objs, struct.unpack_from("<I", body, 5 + 4 * i)[0], seen)
    elif t in (5, 6):
        for v in dict.fromkeys(_u32s(body[4:])):
            if v != oid and v in objs and objs[v][0] in (2, 5):
                out += event_sources(objs, v, seen)
    return list(dict.fromkeys(out))


_wem_bank_cache = {}


def bank_of(wem: int, plant_bank: Path):
    """Name of the bank whose DIDX holds this WEM (plant bank first, then shared ones)."""
    if wem in _wem_bank_cache:
        return _wem_bank_cache[wem]
    order = [plant_bank, SOUNDBANKS / "AUDIO_ALWAYS_LOADED.BNK"] + sorted(
        p for p in SOUNDBANKS.glob("*.BNK") if p not in (plant_bank, SOUNDBANKS / "AUDIO_ALWAYS_LOADED.BNK"))
    for bank in order:
        if wem in media_ids(bank):
            _wem_bank_cache[wem] = bank
            return bank
    _wem_bank_cache[wem] = None
    return None


_media_cache = {}


def media_ids_cached(path: Path):
    if path not in _media_cache:
        _media_cache[path] = media_ids(path)
    return _media_cache[path]


def event_layers(objs, eid):
    """One list of candidate WEM ids per Play action of the event.

    A PvZ2 event usually fires several actions at once (e.g. a plant-specific whoosh,
    a second plant-specific layer, and a shared impact layer), each of which picks
    ONE of its own variants. Action type 0x0403 = Play.
    """
    t, body = objs[eid]
    layers = []
    for i in range(body[4]):
        aid = struct.unpack_from("<I", body, 5 + 4 * i)[0]
        if aid not in objs or objs[aid][0] != 3:
            continue
        abody = objs[aid][1]
        if struct.unpack_from("<H", abody, 4)[0] != 0x0403:
            continue
        srcs = event_sources(objs, aid)
        if srcs:
            layers.append(srcs)
    return layers


def resolve_sample(name: str, plant_bank: Path):
    """[ {"sounds": [wem...], "banks": {wem: bank name}} per layer ] or None if the event is unknown."""
    eid = fnv(name)
    banks = [GLOBAL_BANK, plant_bank] + sorted(p for p in SOUNDBANKS.glob("*.BNK")
                                                if p not in (GLOBAL_BANK, plant_bank))
    for bank in banks:
        objs = hirc_objects(bank)
        if objs and eid in objs and objs[eid][0] == 4:
            out = []
            for srcs in event_layers(objs, eid):
                bm = {}
                for w in srcs:
                    b = bank_of(w, plant_bank)
                    bm[str(w)] = b.name if b else None
                out.append({"sounds": srcs, "banks": bm})
            return out
    return None


def assign_picks(animations):
    """Choose the ONE sound a baked PlaySound event will use for each layer.

    A frame-driven Animation Event can only reference a single clip, so the game's
    random-variant containers are flattened: occurrence N of a sample (counted across
    the whole manifest, in timeline order) takes variant N % len(variants). That keeps
    a looping hit/attack from repeating one wav and gives sibling clips that share an
    event (e.g. Endurian's eight attack clips) different variants - deterministic, so
    re-running never reshuffles a shipped plant.
    """
    seen = {}
    for a in animations:
        for e in a["events"]:
            n = seen.get(e["sample"], 0)
            seen[e["sample"]] = n + 1
            for layer in e["layers"]:
                layer["pick"] = layer["sounds"][n % len(layer["sounds"])]


def pam_json_for(pam_file: str) -> Path:
    return Path(pam_file[:-4] + ".pam.json")


def pam_events(pam_json: Path, plant_bank: Path):
    pam = json.loads(pam_json.read_text())
    frames = pam["main_sprite"]["frame"]
    labeled = [(i, f["label"]) for i, f in enumerate(frames) if f.get("label")]
    animations = []
    unresolved = []
    for n, (start, label) in enumerate(labeled):
        end = (labeled[n + 1][0] - 1) if n + 1 < len(labeled) else len(frames) - 1
        events, actions = [], []
        for gi in range(start, end + 1):
            for cmd in frames[gi].get("command", []):
                if cmd["command"] == "PlaySample":
                    res = resolve_sample(cmd["parameter"], plant_bank)
                    if res is None:
                        unresolved.append({"label": label, "frame": gi - start, "sample": cmd["parameter"]})
                        continue
                    events.append({"frame": gi - start, "sample": cmd["parameter"], "layers": res})
                else:
                    actions.append({"frame": gi - start, "command": cmd["command"],
                                    "parameter": cmd.get("parameter", "")})
        animations.append({"label": label, "start": start, "end": end, "frames": end - start + 1,
                           "events": events, "actions": actions})
    # Commands on nested sprites fire on THEIR timeline, not the main one - not mapped
    # onto the flat exported frames, so just count them so nobody is surprised.
    nested = sum(1 for s in pam.get("sprite", []) for f in s.get("frame", []) if f.get("command"))
    assign_picks(animations)
    return {"frame_rate": pam.get("frame_rate", 30), "animations": animations,
            "unresolved": unresolved, "nested_sprite_commands": nested}


def projectile_impact_event(alias: str):
    """ImpactSoundEvent of a projectile type. NOT in any PAM: PvZ2 plays it from the projectile
    definition when the shot lands. In the mod it is CODE-driven (CustomProjectileDefinition.SetHitSfx),
    never an Animation Event - the manifest only tells you which ogg to point SetHitSfx at."""
    for o in json.loads(PROJECTILE_TYPES.read_text())["objects"]:
        if any(a.split("@")[0].lower() == alias.lower() for a in o.get("aliases", [])):
            return o["objdata"].get("ImpactSoundEvent")
    return None


def write_manifests(entry: dict, export_dir: Path = None):
    export_dir = export_dir or EXPORT_ROOT / entry["name"]
    plant_bank = Path(entry["bnk"])
    written = []
    targets = [("", entry["pam_file"])]
    proj = entry.get("projectile") or {}
    if proj.get("attached_pam"):
        targets.append(("projectile", proj["attached_pam"]))
    if proj.get("impact_pam") and proj.get("impact_pam") != proj.get("attached_pam"):
        targets.append(("projectile_hit", proj["impact_pam"]))
    for sub, pam in targets:
        pj = pam_json_for(pam)
        if not pj.exists():
            written.append((sub or "plant", None, f"missing {pj.name}"))
            continue
        manifest = pam_events(pj, plant_bank)
        if sub == "projectile_hit" or (sub == "projectile" and not proj.get("impact_pam")):
            ev = projectile_impact_event(proj.get("alias", "")) if proj.get("alias") else None
            if ev:
                layers = resolve_sample(ev, plant_bank)
                if layers is None:
                    manifest["unresolved"].append({"label": "(impact)", "frame": 0, "sample": ev})
                else:
                    stub = [{"events": [{"sample": ev, "layers": layers}]}]
                    assign_picks(stub)
                    manifest["impact_sound_event"] = {"sample": ev, "layers": layers}
        out = (export_dir / sub if sub else export_dir) / "sounds_manifest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest, indent=1))
        written.append((sub or "plant", manifest, str(out)))
    return written


def extract_wems(bank: Path, wanted, out_dir: Path):
    """Write only the wanted WEM ids out of a bank's DIDX/DATA (bnk_extract.py dumps every one)."""
    ch = read_chunks(bank)
    didx, data = ch[b"DIDX"], ch[b"DATA"]
    out_dir.mkdir(parents=True, exist_ok=True)
    got = []
    for i in range(0, len(didx), 12):
        wid, off, ln = struct.unpack_from("<III", didx, i)
        if wid in wanted:
            (out_dir / f"{wid}.wem").write_bytes(data[off:off + ln])
            got.append(wid)
    return got


def extract_shared_sounds(entry: dict, manifests, export_dir: Path = None):
    """Rip every PICKED sound that lives outside the plant's own bank into <export>/sounds/*.ogg."""
    import rip_plant  # lazy: pulls in PIL + the PopStudio/ww2ogg plumbing
    export_dir = export_dir or EXPORT_ROOT / entry["name"]
    sounds_dir = export_dir / "sounds"
    own = Path(entry["bnk"]).name
    need = {}  # bank name -> {wem ids}
    for m in manifests:
        for a in m["animations"]:
            for e in a["events"]:
                for layer in e["layers"]:
                    pick = layer["pick"]
                    bank = layer["banks"].get(str(pick))
                    if bank and bank != own and not (sounds_dir / f"{pick}.ogg").exists():
                        need.setdefault(bank, set()).add(pick)
    if not need:
        return 0
    tmp = rip_plant.WORK / f"{entry['name']}_shared"
    wem_dir, ogg_dir = tmp / "wem", tmp / "ogg"
    for d in (wem_dir, ogg_dir):
        if d.exists():
            import shutil
            shutil.rmtree(d)
    for bank, ids in need.items():
        extract_wems(SOUNDBANKS / bank, ids, wem_dir)
    rip_plant.convert_wems_to_ogg(wem_dir, ogg_dir)
    sounds_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for ogg in ogg_dir.glob("*.ogg"):
        (sounds_dir / ogg.name).write_bytes(ogg.read_bytes())
        n += 1
    return n


def main():
    plants = json.loads((TOOLS_DIR / "plants.json").read_text())
    for name in sys.argv[1:]:
        entry = next((p for p in plants if p["name"].upper() == name.upper()), None)
        if entry is None:
            print(f"{name}: not in plants.json")
            continue
        plant_bank_name = Path(entry['bnk']).name
        results = write_manifests(entry)
        n_shared = extract_shared_sounds(entry, [m for _, m, _ in results if m])
        if n_shared:
            print(f"{entry['name']}: ripped {n_shared} shared sound(s) into export sounds/")
        for sub, manifest, info in results:
            if manifest is None:
                print(f"{entry['name']}/{sub}: {info}")
                continue
            print(f"{entry['name']}/{sub}: -> {info}")
            for a in manifest["animations"]:
                for e in a["events"]:
                    desc = " + ".join(f"{len(l['sounds'])}x{'own' if all(b == plant_bank_name for b in l['banks'].values()) else 'shared'}"
                                      for l in e["layers"]) or "silent"
                    print(f"    {a['label']:<22} f+{e['frame']:<3} {e['sample']:<44} {desc}")
                for ac in a["actions"]:
                    print(f"    {a['label']:<18} f+{ac['frame']:<3} [{ac['command']}]")
            if manifest.get("impact_sound_event"):
                ie = manifest["impact_sound_event"]
                print(f"    (impact event, from PROJECTILETYPES) {ie['sample']}: {len(ie['layers'])} layer(s)"
                      " - CODE-driven, not an animation event:")
                for l in ie["layers"]:
                    print(f"        SetHitSfx(<BundleId>, \"assets/plantrip/{entry['name'].lower()}/sounds/{l['pick']}.ogg\");"
                          f"   // variants: {l['sounds']}")
            for u in manifest["unresolved"]:
                print(f"    UNRESOLVED {u}")
            if manifest["nested_sprite_commands"]:
                print(f"    note: {manifest['nested_sprite_commands']} command(s) on nested sprites not mapped")


if __name__ == "__main__":
    main()
