# unity/ - the bundle-builder Unity project

Unity is only used headless (`-batchmode`) to turn ripped plant exports into AssetBundles; nobody edits
anything in the Editor. The project is just:

* `Assets/Editor/PvZRipImporter.cs` - imports an export (`D:/PvZ2RipTest/export_all/<NAME>`) as a plant
  (prefab, clips, animator controller).
* `Assets/Editor/PvZBundleBuilder.cs` - import + tag + bake the PAM-derived `PlaySound` events + build.
* `ProjectSettings/`, `Packages/` - Unity 6000.0.60f1 settings.

**Everything else is git-ignored** (see `.gitignore`, a whitelist): the imported assets under
`Assets/plantrip/` are PopCap/EA's ripped PvZ2 art and audio and are never committed. They are recreated
by the pipeline in the top-level README (`rip_plant.py`, then `build_all_bundles.bat`). Do not
`git add -f` anything under `Assets/plantrip/`.

The old private project (with its ripped-asset history) was `ReverseEngineering/AssetBundle-UnityProject`;
it stays local as an archive and is not used by the pipeline any more.
