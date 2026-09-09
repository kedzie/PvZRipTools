using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace PvZRip.Editor
{
    public static class PvZBundleBuilder
    {
        // Convenience entry point for -batchmode -executeMethod invocation.
        public static void BuildRipTestBundle()
        {
            BuildBundle(
                "pvzriptestbundle",
                "Assets/plantrip/bonkchoy_repro/models/default/plant/bonkchoy_repro.prefab",
                "Assets/plantrip/bonkchoy_repro/sounds",
                "D:/PvZ2RipTest/bundles");
            EditorApplication.Exit(0);
        }

        // Batch entry point: imports every plant exported under D:/PvZ2RipTest/export_all
        // (one subfolder per plant, each with frames/ + sounds/), tags each resulting
        // prefab + its sounds with a per-plant AssetBundle name, then builds all of
        // them in a single BuildAssetBundles pass.
        // If D:/PvZ2RipTest/build_only.txt exists (one plant name per line,
        // case-insensitive), only those plants are imported/built - lets us
        // regenerate a handful of plants without touching the rest. Delete or
        // rename the file to go back to processing everything under exportRoot.
        public static void ImportAndBuildAllRipped()
        {
            const string exportRoot = "D:/PvZ2RipTest/export_all";
            const string outputDir = "D:/PvZ2RipTest/bundles";
            const string filterFile = "D:/PvZ2RipTest/build_only.txt";
            const float sampleRate = 12f;

            var succeeded = new List<string>();
            var failed = new List<(string name, string error)>();

            if (!Directory.Exists(exportRoot))
            {
                Debug.LogError($"[PvZBundleBuilder] export root not found: {exportRoot}");
                EditorApplication.Exit(1);
                return;
            }

            HashSet<string> filter = null;
            if (File.Exists(filterFile))
            {
                filter = new HashSet<string>(
                    File.ReadAllLines(filterFile)
                        .Select(l => l.Trim().ToUpperInvariant())
                        .Where(l => l.Length > 0));
                Debug.Log($"[PvZBundleBuilder] build_only.txt present - restricting to: {string.Join(", ", filter)}");
            }

            foreach (var plantDir in Directory.GetDirectories(exportRoot).OrderBy(p => p))
            {
                string rawName = Path.GetFileName(plantDir);
                if (filter != null && !filter.Contains(rawName.ToUpperInvariant()))
                {
                    continue;
                }
                string plantName = rawName.ToLowerInvariant();
                string framesDir = $"{plantDir}/frames";
                string soundsDir = $"{plantDir}/sounds";
                string projectileFramesDir = $"{plantDir}/projectile/frames";
                string projectileHitFramesDir = $"{plantDir}/projectile_hit/frames";
                string seedPacketPng = $"{plantDir}/seedpacket/SPR_SeedPacket_{plantName}.png";
                if (!File.Exists(seedPacketPng))
                {
                    // rip_plant.py names the file with the resolved camel-case plant
                    // name, not the lowercase folder name - fall back to a glob.
                    var seedDir = $"{plantDir}/seedpacket";
                    seedPacketPng = Directory.Exists(seedDir)
                        ? Directory.GetFiles(seedDir, "*.png").FirstOrDefault()
                        : null;
                }

                try
                {
                    if (!Directory.Exists(framesDir))
                    {
                        throw new DirectoryNotFoundException(framesDir);
                    }
                    PvZRipImporter.ImportPlantFull(plantName, framesDir, soundsDir,
                        projectileFramesDir, projectileHitFramesDir, seedPacketPng, sampleRate);

                    string bundleName = $"pvz{plantName}bundle";
                    TagPlantBundle(bundleName, plantName,
                        hasProjectile: Directory.Exists(projectileFramesDir),
                        hasImpact: Directory.Exists(projectileHitFramesDir),
                        hasSeedPacket: !string.IsNullOrEmpty(seedPacketPng));

                    succeeded.Add(plantName);
                }
                catch (Exception e)
                {
                    failed.Add((rawName, e.Message));
                    Debug.LogError($"[PvZBundleBuilder] Import failed for '{rawName}': {e}");
                }
            }

            Debug.Log($"[PvZBundleBuilder] Imported {succeeded.Count} plant(s), {failed.Count} failed: " +
                      string.Join(", ", failed.Select(f => f.name)));

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Directory.CreateDirectory(outputDir);

            var manifest = BuildPipeline.BuildAssetBundles(
                outputDir,
                BuildAssetBundleOptions.ForceRebuildAssetBundle,
                BuildTarget.StandaloneWindows64);

            if (manifest == null)
            {
                Debug.LogError("[PvZBundleBuilder] BuildAssetBundles failed - manifest is null.");
                EditorApplication.Exit(1);
                return;
            }

            Debug.Log($"[PvZBundleBuilder] Built {manifest.GetAllAssetBundles().Length} bundle(s) -> {outputDir}");
            EditorApplication.Exit(0);
        }

        // Batch entry point for rebuilding a single already-imported plant's
        // bundle from the project's CURRENT state (hand-tuned Animator
        // transitions, etc.) - deliberately does NOT call
        // PvZRipImporter.ImportPlantFull, which would regenerate the prefab
        // and ac.controller from scratch off the bulk-export defaults and
        // wipe out any per-plant fixes made in the Editor since import.
        public static void BuildBambooSpartanBundle()
        {
            const string outputDir = "D:/PvZ2RipTest/bundles";
            TagPlantBundle("pvzbamboospartanbundle", "bamboospartan",
                hasProjectile: false, hasImpact: false, hasSeedPacket: true);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Directory.CreateDirectory(outputDir);

            var manifest = BuildPipeline.BuildAssetBundles(
                outputDir,
                BuildAssetBundleOptions.ForceRebuildAssetBundle,
                BuildTarget.StandaloneWindows64);

            if (manifest == null)
            {
                Debug.LogError("[PvZBundleBuilder] BuildAssetBundles failed - manifest is null.");
                EditorApplication.Exit(1);
                return;
            }

            Debug.Log($"[PvZBundleBuilder] Built bamboospartan bundle -> {outputDir}/pvzbamboospartanbundle");
            EditorApplication.Exit(0);
        }

        // First-time import + build for Endurian: unlike BambooSpartan this
        // plant has never been imported into the Unity project before, so
        // this does the full fresh ImportPlantFull (not just a rebuild of an
        // already-hand-tuned prefab) and then fixes up the resulting
        // AnimatorController in code, since there's nothing to hand-edit in
        // the Editor yet.
        public static void BuildEndurianBundle()
        {
            const float sampleRate = 12f;
            const string plantName = "endurian";
            const string framesDir = "D:/PvZ2RipTest/export_all/ENDURIAN/frames";
            const string soundsDir = "D:/PvZ2RipTest/export_all/ENDURIAN/sounds";
            const string seedPacketPng = "D:/PvZ2RipTest/export_all/ENDURIAN/seedpacket/SPR_SeedPacket_Endurian.png";
            const string outputDir = "D:/PvZ2RipTest/bundles";

            PvZRipImporter.ImportPlantFull(plantName, framesDir, soundsDir, null, null, seedPacketPng, sampleRate);

            string modelsRoot = $"Assets/plantrip/{plantName}/models/default";
            FixEndurianAnimatorController($"{modelsRoot}/plant/ac.controller", $"{modelsRoot}/plant");

            TagPlantBundle("pvzendurianbundle", plantName, hasProjectile: false, hasImpact: false, hasSeedPacket: true);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Directory.CreateDirectory(outputDir);

            var manifest = BuildPipeline.BuildAssetBundles(
                outputDir,
                BuildAssetBundleOptions.ForceRebuildAssetBundle,
                BuildTarget.StandaloneWindows64);

            if (manifest == null)
            {
                Debug.LogError("[PvZBundleBuilder] BuildAssetBundles failed - manifest is null.");
                EditorApplication.Exit(1);
                return;
            }

            Debug.Log($"[PvZBundleBuilder] Built endurian bundle -> {outputDir}/pvzendurianbundle");
            EditorApplication.Exit(0);
        }

        // Endurian has 3 health-tier idle poses and 3 matching intro/loop/outro
        // attack sequences (attack_start/loop/end_damage[N]) - the bulk
        // importer's generic heuristics get this wrong in three ways: (1) the
        // idle-pose clips don't contain "idle"/"water"/"loop" so they're
        // wrongly built as one-shot instead of looping, (2) every one-shot
        // state's auto-generated exit-time transition points at the
        // bulk-picked default state instead of each attack's own matching
        // loop/idle-tier target, and (3) the default state itself needs to be
        // his real resting pose.
        //
        // The frame-rip folders (and therefore the imported clip/state names)
        // were renamed before import: the game's own periodic idle-refresh
        // call expects literal state names "idle"/"idle2"/"idle3" for the
        // three health-tier poses (previously misnamed "damage/damage2/
        // damage3" here, which caused that native call to instead snap him to
        // whatever WAS named "idle" - whichever we'd repurposed as a
        // stand-in). The genuine plant-food-upgraded look formerly at
        // "idle"/"idle2" was renamed to "armor"/"armor2" to free up the name.
        // attack_start/loop/end_damage[N] keep their original names - only
        // the idle poses moved.
        static void FixEndurianAnimatorController(string controllerPath, string clipRoot)
        {
            var controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(controllerPath);
            if (controller == null)
            {
                Debug.LogError($"[PvZBundleBuilder] Could not load Endurian's AnimatorController at {controllerPath}");
                return;
            }

            var stateMachine = controller.layers[0].stateMachine;
            var statesByName = new Dictionary<string, AnimatorState>();
            foreach (var childState in stateMachine.states)
            {
                statesByName[childState.state.name] = childState.state;
            }

            AnimatorState Get(string name)
            {
                if (!statesByName.TryGetValue(name, out var s))
                {
                    Debug.LogError($"[PvZBundleBuilder] Endurian AnimatorController is missing expected state '{name}'.");
                }
                return s;
            }

            foreach (var loopingLabel in new[]
                     {
                         "idle", "idle2", "idle3",
                         "attack_loop_damage", "attack_loop_damage2", "attack_loop_damage3"
                     })
            {
                var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>($"{clipRoot}/{loopingLabel}/{loopingLabel}.anim");
                if (clip == null)
                {
                    Debug.LogError($"[PvZBundleBuilder] Could not find Endurian clip '{loopingLabel}' to force looping.");
                    continue;
                }
                var settings = AnimationUtility.GetAnimationClipSettings(clip);
                settings.loopTime = true;
                AnimationUtility.SetAnimationClipSettings(clip, settings);
            }

            void Rewire(string fromName, string toName)
            {
                var from = Get(fromName);
                var to = Get(toName);
                if (from == null || to == null) return;

                foreach (var t in from.transitions)
                {
                    from.RemoveTransition(t);
                }

                var transition = from.AddTransition(to);
                transition.hasExitTime = true;
                transition.exitTime = 1f;
                transition.duration = 0f;
                transition.hasFixedDuration = true;
            }

            for (int tier = 1; tier <= 3; tier++)
            {
                string suffix = tier == 1 ? "" : tier.ToString();
                string idleName = tier == 1 ? "idle" : $"idle{tier}";
                Rewire($"attack_start_damage{suffix}", $"attack_loop_damage{suffix}");
                Rewire($"attack_end_damage{suffix}", idleName);
            }

            var idleState = Get("idle");
            if (idleState != null)
            {
                stateMachine.defaultState = idleState;
            }

            EditorUtility.SetDirty(controller);
            AssetDatabase.SaveAssets();
        }

        // First-time import + build for Celery Stalker - real PvZ2 rip, never
        // imported before, same fresh-import-then-fix-in-code approach as
        // Endurian.
        public static void BuildCelerystalkerBundle()
        {
            const float sampleRate = 12f;
            const string plantName = "celerystalker";
            const string framesDir = "D:/PvZ2RipTest/export_all/CELERYSTALKER/frames";
            const string soundsDir = "D:/PvZ2RipTest/export_all/CELERYSTALKER/sounds";
            const string seedPacketPng = "D:/PvZ2RipTest/export_all/CELERYSTALKER/seedpacket/SPR_SeedPacket_CeleryStalker.png";
            const string outputDir = "D:/PvZ2RipTest/bundles";

            PvZRipImporter.ImportPlantFull(plantName, framesDir, soundsDir, null, null, seedPacketPng, sampleRate);

            string modelsRoot = $"Assets/plantrip/{plantName}/models/default";
            FixCelerystalkerAnimatorController($"{modelsRoot}/plant/ac.controller");

            TagPlantBundle("pvzcelerystalkerbundle", plantName, hasProjectile: false, hasImpact: false, hasSeedPacket: true);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Directory.CreateDirectory(outputDir);

            var manifest = BuildPipeline.BuildAssetBundles(
                outputDir,
                BuildAssetBundleOptions.ForceRebuildAssetBundle,
                BuildTarget.StandaloneWindows64);

            if (manifest == null)
            {
                Debug.LogError("[PvZBundleBuilder] BuildAssetBundles failed - manifest is null.");
                EditorApplication.Exit(1);
                return;
            }

            Debug.Log($"[PvZBundleBuilder] Built celerystalker bundle -> {outputDir}/pvzcelerystalkerbundle");
            EditorApplication.Exit(0);
        }

        // Celery Stalker's clip names (idle/idle2/idle3/idle4/idle_down/
        // idle_down2/idle_down3/attack_loop/water) all contain "idle"/"loop"/
        // "water", so the bulk importer's IsLoopingLabel heuristic already
        // gets looping right with no fixing needed here - unlike Endurian.
        // What it gets wrong is the one-shot exit-time transitions: every
        // one-shot clip (down/up/attack/attack_end/plantfood*) gets
        // auto-wired to the single bulk-picked default state, when each
        // actually needs its own specific target:
        //   down -> idle_down (hidden, tier-1 default)
        //   up -> idle (revealed, tier-1 default)
        //   attack -> attack_loop
        //   attack_end -> idle
        // (plantfood* are left alone - not used, since this mod doesn't
        // implement plant food effects.) down/up/attack_end only ever land
        // on the tier-1 look regardless of current health tier since there's
        // just one shared clip for each, not per-tier variants like
        // Endurian's attack states - CelerystalkerBehaviorController
        // re-asserts the correct tier shortly after, once it's sure the
        // transition clip itself has finished playing.
        static void FixCelerystalkerAnimatorController(string controllerPath)
        {
            var controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(controllerPath);
            if (controller == null)
            {
                Debug.LogError($"[PvZBundleBuilder] Could not load Celery Stalker's AnimatorController at {controllerPath}");
                return;
            }

            var stateMachine = controller.layers[0].stateMachine;
            var statesByName = new Dictionary<string, AnimatorState>();
            foreach (var childState in stateMachine.states)
            {
                statesByName[childState.state.name] = childState.state;
            }

            AnimatorState Get(string name)
            {
                if (!statesByName.TryGetValue(name, out var s))
                {
                    Debug.LogError($"[PvZBundleBuilder] Celery Stalker AnimatorController is missing expected state '{name}'.");
                }
                return s;
            }

            void Rewire(string fromName, string toName)
            {
                var from = Get(fromName);
                var to = Get(toName);
                if (from == null || to == null) return;

                foreach (var t in from.transitions)
                {
                    from.RemoveTransition(t);
                }

                var transition = from.AddTransition(to);
                transition.hasExitTime = true;
                transition.exitTime = 1f;
                transition.duration = 0f;
                transition.hasFixedDuration = true;
            }

            Rewire("down", "idle_down");
            Rewire("up", "idle");
            Rewire("attack", "attack_loop");
            Rewire("attack_end", "idle");

            var idleDownState = Get("idle_down");
            if (idleDownState != null)
            {
                stateMachine.defaultState = idleDownState;
            }

            EditorUtility.SetDirty(controller);
            AssetDatabase.SaveAssets();
        }

        static void TagPlantBundle(string bundleName, string plantName, bool hasProjectile, bool hasImpact,
            bool hasSeedPacket)
        {
            string modelsRoot = $"Assets/plantrip/{plantName}/models/default";
            TagForBundle(bundleName, $"{modelsRoot}/plant/{plantName}.prefab", $"Assets/plantrip/{plantName}/sounds");

            if (hasProjectile)
            {
                TagAsset(bundleName, $"{modelsRoot}/projectile/projectile.prefab");
            }
            if (hasImpact)
            {
                TagAsset(bundleName, $"{modelsRoot}/projectile_hit/projectile_hit.prefab");
            }
            if (hasSeedPacket)
            {
                TagAsset(bundleName, $"Assets/plantrip/{plantName}/SPR_SeedPacket_{plantName}.png");
            }
        }

        static void TagAsset(string bundleName, string assetPath)
        {
            var importer = AssetImporter.GetAtPath(assetPath);
            importer?.SetAssetBundleNameAndVariant(bundleName, "");
        }

        static void TagForBundle(string bundleName, string assetPath, string soundsDir)
        {
            var importer = AssetImporter.GetAtPath(assetPath);
            if (importer == null)
            {
                throw new FileNotFoundException($"no asset found at '{assetPath}'");
            }
            importer.SetAssetBundleNameAndVariant(bundleName, "");

            if (!string.IsNullOrEmpty(soundsDir) && Directory.Exists(soundsDir))
            {
                foreach (var ogg in Directory.GetFiles(soundsDir, "*.ogg"))
                {
                    var soundImporter = AssetImporter.GetAtPath(ogg);
                    soundImporter?.SetAssetBundleNameAndVariant(bundleName, "");
                }
            }
        }

        public static void BuildBundle(string bundleName, string assetPath, string soundsDir, string outputDir)
        {
            var importer = AssetImporter.GetAtPath(assetPath);
            if (importer == null)
            {
                Debug.LogError($"[PvZBundleBuilder] No asset found at '{assetPath}'");
                EditorApplication.Exit(1);
                return;
            }
            importer.SetAssetBundleNameAndVariant(bundleName, "");

            if (!string.IsNullOrEmpty(soundsDir) && Directory.Exists(soundsDir))
            {
                foreach (var ogg in Directory.GetFiles(soundsDir, "*.ogg"))
                {
                    var soundImporter = AssetImporter.GetAtPath(ogg);
                    if (soundImporter != null)
                    {
                        soundImporter.SetAssetBundleNameAndVariant(bundleName, "");
                    }
                }
            }
            AssetDatabase.Refresh();

            var membersNow = AssetDatabase.GetAssetPathsFromAssetBundle(bundleName);
            Debug.Log($"[PvZBundleBuilder] '{bundleName}' members per AssetDatabase: {string.Join(", ", membersNow)}");

            Directory.CreateDirectory(outputDir);

            var manifest = BuildPipeline.BuildAssetBundles(
                outputDir,
                BuildAssetBundleOptions.ForceRebuildAssetBundle,
                BuildTarget.StandaloneWindows64);

            if (manifest == null)
            {
                Debug.LogError("[PvZBundleBuilder] BuildAssetBundles failed - manifest is null.");
                EditorApplication.Exit(1);
                return;
            }

            Debug.Log($"[PvZBundleBuilder] Built bundle '{bundleName}' -> {outputDir}/{bundleName}");
        }
    }
}
