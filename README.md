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
   Output lands in `D:/PvZ2RipTest/export_all/<PLANT>/`.
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
