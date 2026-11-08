@echo off
rem Re-bakes frame-driven PlaySound Animation Events onto ALREADY-imported plants (no reimport, so
rem hand-tuned controllers survive) and rebuilds the bundles with their existing names.
rem Reads D:\PvZ2RipTest\bake_sounds.txt: one plant per line (lowercase project folder name)
rem (plant clips only - projectile hit sounds are code-driven via SetHitSfx). Needs export_all\<NAME>\sounds_manifest.json (plant_sounds.py).
rem Unity must NOT be open on the project. Check D:\PvZ2RipTest\unity_bake_sounds.log for [BakeSound] lines.
"C:\Program Files\Unity\Hub\Editor\6000.0.60f1\Editor\Unity.exe" -batchmode -nographics -logFile "D:\PvZ2RipTest\unity_bake_sounds.log" -projectPath "D:\PvZ\ReverseEngineering\AssetBundle-UnityProject" -executeMethod PvZRip.Editor.PvZBundleBuilder.BakeSoundEventsListed -quit
