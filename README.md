# PvZRipTools

Disaster-recovery kit for the PvZ2-plant-ripping pipeline used to build
Pvz Complete Collection2's custom plants. The goal: given nothing but a
copy of the PvZ2 OBB files and this repo, you should be able to re-derive
everything - unpack the OBB, re-rip any plant's frames/sounds/seed packet,
and rebuild a Unity asset bundle - without having to re-discover any of
the tooling or the exact invocation details again.

## What you need in hand

1. **The PvZ2 OBB file(s)** (`main.*.com.ea.game.pvz2_*.obb`) - the actual
   game data. Nothing here works without these; they're not included or
   redistributed by this repo.
2. **This repo.**
3. **A separate backup of `AssetBundle-UnityProject`** (the Unity project
   these scripts import into and build bundles from) - kept as its own,
   separate, **local-only** git repo (not pushed to GitHub) because it
   contains PopCap/EA's original ripped PvZ2 assets alongside our own
   custom-plant rips, which aren't ours to redistribute even privately.
   Back that repo up somewhere you control (external drive, NAS, etc.) -
   it's the other half of "can rebuild everything," not just the scripts.

## External tools this pipeline depends on

None of these are vendored here except `ww2ogg` (small, permissively
licensed, not PopCap content). Re-download the others fresh if starting
from scratch:

| Tool | Source | Version used here | Used for |
|---|---|---|---|
| PopStudio | github.com/PopGameTool/PopStudio | commit `e75c8ad4144dbcebd94557f4d807f3d74b00b91f` | Decoding `.PAM` (animation) and `.RTON` (resource database) files |
| AssetRipper | github.com/AssetRipper/AssetRipper | whatever the latest release is when you need it | Restoring the shipped `.unity3d` asset bundles (`Mods/CoreLib`, `Mods/CompleteCollection`) into an editable Unity project |
| ww2ogg | github.com/hcs64/ww2ogg (vendored in `tools/ww2ogg/`) | as vendored | Converting extracted `.wem` (Wwise) audio to `.ogg` |
| Unity Editor | unity.com | **6000.0.60f1** (must match - see `AssetBundle-UnityProject/ProjectSettings/ProjectVersion.txt`) | Importing rips and building asset bundles |

PopStudio needs building from source (`PopStudio.ConsoleProject`, .NET
6/7/9) - `dotnet publish -c Release` and point `POPSTUDIO_EXE` in
`rip_plant.py` at the resulting `PopStudio.exe`.

## The pipeline, end to end

1. **Unpack the OBB.** (The exact original unpack process isn't captured
   as a script - it was done once into a working folder referred to
   throughout these scripts as `pvz2_original_unpacked/`, containing
   `IMAGES/`, `ATLASES/`, `SOUNDBANKS/`, `PACKAGES/` etc.) Point the paths
   in `plants.json` at wherever you redo this.
2. **Decode `RESOURCES.RTON` to `RESOURCES.json`** via PopStudio's RTON
   decoder. The exact command-line invocation used originally wasn't
   captured in any script (it looks like it was run through PopStudio's
   interactive console menu, not a one-liner) - run `PopStudio.exe` with
   no arguments to get its menu and pick the RTON-decode option, pointed
   at `RESOURCES.RTON`. This is the one real gap in this recipe; if you
   redo this, capture the exact command and add it here.
3. **Rip a plant**: `python3 rip_plant.py <name-or-index>` (or `--all`).
   Reads the plant's entry from `plants.json` (already populated for all
   185 PvZ2 plants, not just the ones we've shipped - most future plants
   are "just run it," not "go find the PAM/atlas/resource IDs first").
   This decodes the plant's `.PAM` via PopStudio (`run_popstudio_decode_pam`,
   command code `180`), composites frames via `pam_compositor.py`
   (per-frame-cropped, centered on a shared reference so `pivot_x=0.5`
   always tracks correctly - see that file's own docstring), extracts and
   converts its `.BNK` sounds via `bnk_extract.py` + vendored `ww2ogg`,
   and crops its seed-packet icon via `crop_seedpacket` (note: the
   `UI_SEEDPACKETS` atlas has its R/B channels swapped at the source - see
   the comment on `crop_seedpacket` - already corrected for automatically).
   It also writes `sounds_manifest.json` (+ `projectile/` and `projectile_hit/` siblings) and rips
   any shared-bank sounds the plant's events use into `sounds/` - see "Sounds". Output lands in
   `D:/PvZ2RipTest/export_all/<PLANT>/`. **A plant with projectile art takes ~7 minutes** (PopStudio
   decode + compositing three PAMs) - run it in the background and poll, don't block on it. If a
   plant has projectile/impact art, add a `projectile` block to its `plants.json` entry first
   (alias + `attached_pam` + `impact_pam`; copy Apple Mortar's); `null` means "plant body only".
4. **Import into Unity.** From `AssetBundle-UnityProject`, run (via
   `build_all_bundles.bat`, or the equivalent `-executeMethod` call
   directly): `PvZRip.Editor.PvZBundleBuilder.ImportAndBuildAllRipped`.
   This calls `PvZRipImporter.ImportPlantFull` for every plant folder
   under `export_all/` (or just the ones listed in
   `D:/PvZ2RipTest/build_only.txt`, one name per line, if you want to
   restrict it), builds Sprites/AnimationClips/an AnimatorController/a
   prefab per plant, tags each with its own asset bundle name, and builds
   every configured bundle in one pass.

   **Important**: `ImportPlantFull` regenerates a plant's prefab and
   `AnimatorController` from scratch off the bulk-export defaults - if
   you've since hand-tuned a plant in the Editor (fixed transitions,
   added Animation Events for sounds, etc.), re-running this on that
   plant **wipes those changes**. For an already-imported, hand-tuned
   plant, add a small dedicated `Build<Plant>Bundle()` method to
   `PvZBundleBuilder.cs` that skips `ImportPlantFull` and just re-tags +
   rebuilds from the project's current state (see `BuildBambooSpartanBundle`
   for the pattern). Several plants also need their bulk-picked Animator
   defaults corrected in code after import - see
   `FixEndurianAnimatorController`, `FixCelerystalkerAnimatorController`,
   `FixTumbleweedAnimatorControllers` for the established pattern (a
   plant needs one of these whenever none of its clip labels is literally
   named "idle"/etc., or a clip that should loop doesn't have "idle",
   "water", or "loop" in its name).
5. **Bundles land in** `D:/PvZ2RipTest/bundles/` - copy the ones you need
   into the game's `Mods/CompleteCollection/` or `Mods/CoreLib/` folder.
   Note the bulk importer names them `pvz<plantname>bundle` directly (no
   "rip" prefix, no manual rename needed) as of the fix in this repo's
   history - if you're recovering from an older snapshot predating that
   fix, strip a leading "rip" from any bundle name it produces before
   copying it into place.

## What's in this repo

- `plants.json` - the master list: every PvZ2 plant's PAM/atlas/resource
  paths, pre-resolved. `plants.json.bak_*` are earlier snapshots kept for
  reference (underscore-naming fixes, etc.).
- `rip_plant.py` - the main per-plant pipeline (see above).
- `pam_compositor.py` - PAM animation timeline -> flat, per-frame-cropped
  PNG sequence.
- `bnk_extract.py` - `.BNK` soundbank -> individual `.wem` files.
- `plant_sounds.py` - derives WHICH sound plays on WHICH frame straight from the PvZ2 data (PAM
  `PlaySample` commands + the Wwise event tables) and writes `sounds_manifest.json`; also rips the
  shared-bank sounds an event uses. Run by `rip_plant.py` automatically; see "Sounds" below.
- `bake_sounds.bat` / `sync_editor_scripts.sh` - re-bake sound events onto already-imported plants /
  copy the Unity project's Editor scripts back into this repo (they drift - see "Pitfalls").
- `PVZ2_DATA_NOTES.md` - what the PvZ2 data and the Replanted decompile tell you when you go to
  IMPLEMENT a ripped plant (lob recipe, splash rule, where stats/events live, lobber shortlist).
- `enumerate_plants.py` / `resolve_extras.py` / `add_extras.py` /
  `recomposite_all.py` / `reconvert_sounds.py` - one-off/bulk helper
  scripts used while building out `plants.json` and re-running fixes
  across many plants at once.
- `PvZBundleBuilder.cs` / `PvZRipImporter.cs` - reference copies of the
  Unity Editor scripts that actually live (and get compiled from) inside
  `AssetBundle-UnityProject/Assets/Editor/` - keep both copies in sync by
  hand when editing either one.
- `tools/ww2ogg/` - vendored `ww2ogg.exe` + the aoTuV codebook it needs.
- `build_all_bundles.bat` / `build_bundle.bat` / `run_import.bat` -
  ready-to-run wrappers around the Unity `-executeMethod` invocations
  described above (assumes Unity 6000.0.60f1 installed at the default
  `C:\Program Files\Unity\...` path - edit if yours differs).


## Sounds: frame-driven `PlaySound` events, derived from the data (not by ear)

**Rule (from the mod author): sounds are baked into the Unity clips as `PlaySound` Animation Events on
the exact keyframe, never played from code with fps maths** - the game has animation speed settings,
and an event on the clip's own keyframe follows them by construction. Code-driven timing
(`RegisterSoundPool`, `SetHitSfx`, timers) is only a fallback when an Animation Event cannot do it.

Where the information lives (all verified, Dusk Lobber / Celery / Tumbleweed / Fire Peashooter):

1. **The plant's `.pam.json`** - `main_sprite.frame[n].command` entries: `PlaySample` with the Wwise
   event name (`Play_Plant_DuskLobber_Attack`) on the frame it fires, plus `use_action` /
   `use_special` markers on the frame the plant actually acts (spawns the projectile, deals the hit).
   Those markers are also the real "launch frame" - useful when timing a projectile spawn.
2. **`GLOBAL_DATA.BNK` HIRC chunk** - event id = 32-bit **FNV-1** hash of the *lower-cased* name
   (`x = x*16777619 ^ byte`, start 2166136261) -> Event(type 4) -> Action(3, type `0x0403` = Play)
   -> Random/Switch Container(5/6) -> Sound(2) -> source WEM id. **A single event is usually several
   Play actions = several simultaneous LAYERS** (Dusk Lobber attack = plant sound set A + plant sound
   set B + a shared generic layer). Each layer picks ONE of its variants at random in the real game.
3. **`PLANT_<NAME>.BNK`** only holds media (DIDX/DATA, no HIRC); its WEM ids are the ogg names
   `bnk_extract.py` writes. A layer's sounds may live in another bank (`AUDIO_ALWAYS_LOADED.BNK` for
   generic whooshes/hits, `ICEAGE_AMB_WORLD_SFX.BNK` for Endurian's attack) - `plant_sounds.py`
   rips only the PICKED ones into the plant's `sounds/` folder.
4. **Impact (projectile hit) sounds are NOT in the PAM, and are CODE-driven, not animation events.**
   `PACKAGES/PROJECTILETYPES.json` -> the projectile's `ImpactSoundEvent` (e.g.
   `Play_Plant_DuskLobber_Impact`; `..._Impact_Plantfood` for the PF shot). `plant_sounds.py` resolves
   it into `projectile_hit/sounds_manifest.json` as `impact_sound_event` and prints the ready-made
   line `SetHitSfx(<BundleId>, "assets/plantrip/<plant>/sounds/<wem>.ogg")` - that is how the mod
   plays hit sounds (Tumbleweed, Bloomerang). The Unity bake deliberately does NOT touch
   `projectile_hit` clips (an earlier version did; it was removed - baking it AND `SetHitSfx` would
   double the sound).

`sounds_manifest.json` (per sub-object) = `{frame_rate, animations:[{label,start,end,frames,
events:[{frame, sample, layers:[{sounds:[wem..], banks:{wem:bank}, pick}]}], actions:[...]}],
unresolved:[...], nested_sprite_commands:N}`. `frame` is the offset INSIDE the label = the index of the
exported frame = the clip's keyframe index (frame *file names* are global PAM frame numbers, e.g.
`attack/frame_97.png`, but the manifest and the Unity keyframes use label-relative indices).

**Variant choice (`pick`)**: an Animation Event can reference only one clip, so the random
containers are flattened deterministically: occurrence N of an event (counted across the manifest in
timeline order) uses variant `N % len(variants)` of each layer - a looping hit doesn't repeat one wav and
re-running never reshuffles. True per-play randomness would need code (`PlaySoundEvent` + a registered
pool); the manifest keeps the full variant lists if you ever want that.

### Repeatable procedure

```bash
# 1. (re)generate manifests + shared sounds for any plants; no frames re-rip needed
python3 plant_sounds.py DUSKLOBBER CELERYSTALKER ...        # prints every event/layer + any UNRESOLVED
# 2a. NEW plant: full rip (writes the manifest itself), then import - ImportAndBuildAllRipped bakes automatically
python3 rip_plant.py DUSKLOBBER                              # ~7 min if it has projectile art
echo DUSKLOBBER > D:/PvZ2RipTest/build_only.txt              # (restore the previous content afterwards!)
cmd.exe /c D:\PvZ\ReverseEngineering\PvZRipTools\build_all_bundles.bat
# 2b. ALREADY-imported (hand-tuned) plants: bake only, never reimport
printf 'celerystalker\nbamboospartan\ntumbleweed\n' > D:/PvZ2RipTest/bake_sounds.txt
cmd.exe /c D:\PvZ\ReverseEngineering\PvZRipTools\bake_sounds.bat
# 3. verify in the Unity log:  grep "\[BakeSound\]" D:/PvZ2RipTest/unity_bake_sounds.log
```

`BakeSoundEventsForPlant` (in `PvZBundleBuilder.cs`, plant clips only) is idempotent: it first removes every
`PlaySound`/`PlaySoundEvent` event on the clips the manifest covers (so re-runs never stack duplicates
and hand-assigned events that disagree with the PAM are replaced - the log lists `removed [...] added
[...]` per clip), leaves every other event alone, and copies a missing shared-bank ogg from
`export_all/<NAME>/sounds` into the plant's Unity sounds folder and tags it with the plant's bundle.
Clips that don't exist in the project (e.g. `plantfood`, which the compositor skips on purpose) are
reported as "no such clip", not an error.

### Launch frame: an `ExecuteAttack` event (so the throw follows game speed too)

The PAM's `use_action` command marks the frame a plant actually releases its projectile (Dusk Lobber:
`attack` frame +11). The manifest keeps it as `animations[].actions[]`. Plants listed in
`LaunchEventPlants` (`PvZBundleBuilder.cs`, opt-in - currently only `dusklobber`) get one
`ExecuteAttack` Animation Event on that frame of their `attack` clip (re-bakes replace it, never stack).
CoreLib forwards it: `AnimationScripts.ExecuteAttack()` -> `CustomPlantBehaviorController.OnAnimationAttackEvent()`
(virtual, no-op by default) - override that to spawn the projectile instead of using a timer. Needs a CoreLib
build that has the hook. **Not yet verified in game** (code and bake log only).

### What the 2026-11-05 six-plant bake changed (so a regression is easy to spot)

Old hand-assigned events were replaced by the PAM's. Where a plant already had events: Tumbleweed `idle2_1`
had 6 stacked identical events (`51358952`@0) -> none; Tumbleweed `attack2` `51358952` -> `983543462`
and `attack3` none -> `51358952` (the manual assignment was shifted by one clip); Celery `attack_loop`
9 single sounds ~0.167s apart -> 2 layers per beat, `down`/`up` moved to frame +1; Bamboo
`battle_trance_shield_break` `537163663` -> `862111807`. Old `.anim` files: `D:/PvZ2RipTest/anim_backup_20261105`.
Bundles were rebuilt to `D:/PvZ2RipTest/bundles` only - none shipped. Not listened to in game yet.

Caveats: events on **nested sprites** are not mapped (counted in `nested_sprite_commands`; none seen
so far). Sounds in a PROJECTILE's own PAM (`projectile/sounds_manifest.json`, e.g. Iceweed's PF saw)
are reported but not baked. The bank-v140 Wwise layout (u8 action count,
`idExt` at body offset 6, source id at body offset 9) was validated on this OBB only.

## Pitfalls found the hard way (read before touching the pipeline)

* **The Unity project's `Assets/Editor/*.cs` are the source of truth, this repo's copies drift.**
  The reference `PvZBundleBuilder.cs` once lacked all of Iceweed's methods. After editing the Unity
  copy run `./sync_editor_scripts.sh`, then commit.
* **Seed packets: always R/B-swap `UI_SEEDPACKETS` tiles - for every plant, Dusk Lobber included**
  (a green body with purple thorns is correct, confirmed by the mod author). An automatic "match the
  packet to the body frames" heuristic was tried and was WRONG; don't reintroduce it.
* **A PAM can contain TWO complete art sets** drawn on top of each other (Dusk Lobber: every part as
  `<name>` = normal green and `<name>_2` = the `_dark` blue variant, both appended on frame 0; probably
  a Plant Food / dark-state skin the game toggles at runtime). The flat export then shows the top set
  (blue). Tell: a plant whose frames don't match its packet, or `image` names ending `_2` in
  `.pam.json`. Fix: `"skip_image_suffix": "_2"` in the plant's `plants.json` entry (passed to
  `pam_compositor.py` as `PAM_SKIP_IMAGE_SUFFIX`). The dark set is not exported (could be a future
  alternate skin).
* `PlantFood` and a few other labels are skipped by the compositor (`skip_labels_containing`), so those
  clips never exist in Unity - their sound events are reported and not baked.
* Unity batch runs: ~1-3 min; Unity must not be open on the project; the log
  (`unity_*.log`) always contains ~186 `Could not load file or assembly 'MelonLoader, Version=0.7.2.0'`
  errors and `Licensing ... 404` lines - pre-existing noise, ignore. Look for `[BakeSound]`,
  `[PvZRipImporter]`, `[PvZBundleBuilder]` and `error CS`. `BuildAssetBundles` rebuilds EVERY tagged
  bundle into `D:/PvZ2RipTest/bundles` (staging only - the game's `Mods/` folder is never touched by
  these scripts; copy bundles by hand/with the release process).
* `build_only.txt` restricts `ImportAndBuildAllRipped` to the listed plants and **ImportPlantFull
  wipes hand tuning** of whatever it imports - always back up first (`cp --parents` the plant's
  `*.anim`/`ac.controller`) and restore `build_only.txt` afterwards.
* `rip_plant.py` rewrites `rip_results.json` (tracked) - `git checkout rip_results.json` after one-off
  runs unless you mean to update it.
