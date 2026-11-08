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

                    // Frame-driven PlaySound Animation Events from the rip's sounds_manifest.json
                    // (no-op if the plant was ripped before plant_sounds.py existed).
                    BakeSoundEventsForPlant(plantName, rawName);

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

        // Safe, rebuild-only re-application of FixCelerystalkerAnimatorController
        // (e.g. after tweaking which state is the Animator's default) onto the
        // ALREADY-imported prefab - deliberately does NOT call
        // BuildCelerystalkerBundle above, which reimports from scratch and
        // would wipe out hand-baked Animation Events added in the Editor
        // since import. FixCelerystalkerAnimatorController itself is
        // idempotent (just adjusts the existing controller asset in place),
        // safe to call standalone like this.
        public static void FixCelerystalkerDefaultsAndBuild()
        {
            const string outputDir = "D:/PvZ2RipTest/bundles";
            const string plantName = "celerystalker";

            FixCelerystalkerAnimatorController($"Assets/plantrip/{plantName}/models/default/plant/ac.controller");

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

            Debug.Log($"[PvZBundleBuilder] Built celerystalker bundle (defaults fix only, no reimport) -> {outputDir}/pvzcelerystalkerbundle");
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

            // Real PvZ2 Celery Stalker starts standing up the instant he's
            // planted, not hidden - "idle" (not "idle_down") is the correct
            // default so no PlayAnimation call is needed for the starting
            // pose at all (calling PlayAnimation this early in a plant's
            // life doesn't reliably take effect - confirmed as a real bug).
            var idleState = Get("idle");
            if (idleState != null)
            {
                stateMachine.defaultState = idleState;
            }

            EditorUtility.SetDirty(controller);
            AssetDatabase.SaveAssets();
        }

        // Tumbleweed was imported via ImportAndBuildAllRipped (build_only.txt
        // restricted to just TUMBLEWEED so the other already-hand-tuned plants
        // weren't touched). Its bulk-picked defaults are wrong for what the
        // gameplay code needs.
        //
        // Plant default is "attack2" (was "idle2_1") - same fix as Celery
        // Stalker's idle_down->idle: calling PlayAnimation this early in a
        // plant's life doesn't reliably take effect (confirmed repeatedly),
        // so instead of trying to trigger the vanish-into-light transition at
        // spawn, the Animator just starts on it directly. No literal "idle"
        // label exists among idle1_1/idle1_2/attack/idle2_1/idle2_2/attack2/
        // idle3_1/idle3_2/attack3, so the bulk importer's "idle" fallback
        // picked whatever came first instead, hence needing this fix at all.
        // The launch sound is now baked directly onto attack2 in the Editor
        // (by hand, alongside the projectile's whoosh sounds) rather than
        // injected here - no PlaySound baking needed in this method anymore.
        //
        // projectile/projectile_hit still default to animation3 specifically
        // - the rolling and impact poses TumbleweedProjectileBehaviorController
        // expects to already be showing without having to explicitly switch
        // state at runtime. animation3 also isn't "idle"/"water"/"loop"-named
        // so the bulk importer's IsLoopingLabel heuristic built it as
        // one-shot - forced to loop here since the projectile needs to keep
        // rolling continuously, not freeze after one cycle.
        static void FixTumbleweedAnimatorControllers()
        {
            const string root = "Assets/plantrip/tumbleweed/models/default";

            SetDefaultState($"{root}/plant/ac.controller", "attack2");
            SetDefaultState($"{root}/projectile/ac.controller", "animation3");
            SetDefaultState($"{root}/projectile_hit/ac.controller", "animation3");

            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>($"{root}/projectile/animation3/animation3.anim");
            if (clip == null)
            {
                Debug.LogError("[PvZBundleBuilder] Could not find Tumbleweed projectile's animation3 clip to force looping.");
            }
            else
            {
                var settings = AnimationUtility.GetAnimationClipSettings(clip);
                settings.loopTime = true;
                AnimationUtility.SetAnimationClipSettings(clip, settings);
            }
        }

        static void SetDefaultState(string controllerPath, string stateName)
        {
            var controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(controllerPath);
            if (controller == null)
            {
                Debug.LogError($"[PvZBundleBuilder] Could not load AnimatorController at {controllerPath}");
                return;
            }

            var stateMachine = controller.layers[0].stateMachine;
            AnimatorState found = null;
            foreach (var childState in stateMachine.states)
            {
                if (childState.state.name == stateName)
                {
                    found = childState.state;
                    break;
                }
            }

            if (found == null)
            {
                Debug.LogError($"[PvZBundleBuilder] {controllerPath} is missing expected state '{stateName}'.");
                return;
            }

            stateMachine.defaultState = found;
            EditorUtility.SetDirty(controller);
            AssetDatabase.SaveAssets();
        }

        // Rebuild-only, like BuildBambooSpartanBundle - Tumbleweed was already
        // imported by ImportAndBuildAllRipped, this just fixes its Animator
        // defaults and (re)tags/builds the bundle from current project state.
        public static void BuildTumbleweedBundle()
        {
            const string outputDir = "D:/PvZ2RipTest/bundles";

            FixTumbleweedAnimatorControllers();

            TagPlantBundle("pvztumbleweedbundle", "tumbleweed",
                hasProjectile: true, hasImpact: true, hasSeedPacket: true);

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

            Debug.Log($"[PvZBundleBuilder] Built tumbleweed bundle -> {outputDir}/pvztumbleweedbundle");
            EditorApplication.Exit(0);
        }

        // First-time import + build for Iceweed - real PvZ2 rip, never imported before, same
        // fresh-import-then-fix-in-code approach as Endurian/Celery Stalker. No projectile/
        // projectile_hit passed (Plant Food's sawblade effect is out of scope - this mod doesn't
        // implement Plant Food at all, same as Celery Stalker's own plantfood* clips being
        // imported-but-left-unused rather than wired up).
        public static void BuildIceweedBundle()
        {
            const float sampleRate = 12f;
            const string plantName = "iceweed";
            const string framesDir = "D:/PvZ2RipTest/export_all/ICEWEED/frames";
            const string soundsDir = "D:/PvZ2RipTest/export_all/ICEWEED/sounds";
            const string seedPacketPng = "D:/PvZ2RipTest/export_all/ICEWEED/seedpacket/SPR_SeedPacket_Iceweed.png";
            const string outputDir = "D:/PvZ2RipTest/bundles";

            PvZRipImporter.ImportPlantFull(plantName, framesDir, soundsDir, null, null, seedPacketPng, sampleRate);

            string modelsRoot = $"Assets/plantrip/{plantName}/models/default";
            FixIceweedAnimatorController($"{modelsRoot}/plant/ac.controller");

            TagPlantBundle("pvziceweedbundle", plantName, hasProjectile: false, hasImpact: false, hasSeedPacket: true);

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

            Debug.Log($"[PvZBundleBuilder] Built iceweed bundle -> {outputDir}/pvziceweedbundle");
            EditorApplication.Exit(0);
        }

        // Iceweed's real rip has no "idle"/"loop"-named default and no separate attack_loop
        // state the way Celery Stalker does - just stage1_idle1/stage1_idle2 (a visual-variety
        // pair, only stage1_idle1 is actually used - see IceweedBehaviorController's own comment)
        // and a single one-shot stage1_attack "poke" clip. Two fixes needed:
        //   (1) stage1_attack forced to loop, so IceweedBehaviorController's single PlayAnimation
        //       call at the start of an attack keeps it visually poking for as long as a zombie
        //       remains, instead of playing once and auto-returning to idle after ~1 frame while
        //       the plant keeps dealing damage every tick underneath a now-idle-looking sprite.
        //   (2) default state forced to stage1_idle1 - the bulk importer's "idle" fallback only
        //       matches a state literally named "idle", so without this it silently defaults to
        //       whichever label the manifest happened to list first (stage1_idle1 as of this
        //       writing, but by accident, not by any rule this fix can rely on).
        // stage1_idle2, every stage2_* tier, and every stage1_pf_*/stage2_pf_* Plant Food clip
        // are imported but deliberately left alone, same as Celery Stalker's own unused
        // plantfood* states - this mod doesn't implement Plant Food or the stage2 upgrade tier.
        static void FixIceweedAnimatorController(string controllerPath)
        {
            var controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(controllerPath);
            if (controller == null)
            {
                Debug.LogError($"[PvZBundleBuilder] Could not load Iceweed's AnimatorController at {controllerPath}");
                return;
            }

            var stateMachine = controller.layers[0].stateMachine;
            var statesByName = new Dictionary<string, AnimatorState>();
            foreach (var childState in stateMachine.states)
            {
                statesByName[childState.state.name] = childState.state;
            }

            if (!statesByName.TryGetValue("stage1_attack", out var attackState))
            {
                Debug.LogError("[PvZBundleBuilder] Iceweed AnimatorController is missing expected state 'stage1_attack'.");
            }
            else
            {
                var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(
                    "Assets/plantrip/iceweed/models/default/plant/stage1_attack/stage1_attack.anim");
                if (clip == null)
                {
                    Debug.LogError("[PvZBundleBuilder] Could not find Iceweed clip 'stage1_attack' to force looping.");
                }
                else
                {
                    var settings = AnimationUtility.GetAnimationClipSettings(clip);
                    settings.loopTime = true;
                    AnimationUtility.SetAnimationClipSettings(clip, settings);
                }

                // A looping clip has no exit time to auto-return from, so the bulk importer's
                // one-shot exit-time transition (attack -> bulk default, added before this fix
                // ever ran) needs clearing - IceweedBehaviorController itself calls
                // PlayAnimation(IdleState) explicitly once no zombie remains instead.
                foreach (var t in attackState.transitions)
                {
                    attackState.RemoveTransition(t);
                }
            }

            if (statesByName.TryGetValue("stage1_idle1", out var idleState))
            {
                stateMachine.defaultState = idleState;
            }
            else
            {
                Debug.LogError("[PvZBundleBuilder] Iceweed AnimatorController is missing expected state 'stage1_idle1'.");
            }

            EditorUtility.SetDirty(controller);
            AssetDatabase.SaveAssets();
        }

        // ------------------------------------------------------------------------------------
        // Frame-driven sound events.
        //
        // PvZRipTools/plant_sounds.py derives, from the PvZ2 data itself, which sound fires on
        // which frame of which animation (PlaySample commands in the PAM -> GLOBAL_DATA.BNK
        // events -> WEM ids) and writes D:/PvZ2RipTest/export_all/<NAME>/sounds_manifest.json
        // ("frame" = offset inside the label = index of the exported frame, one layer per Play
        // action, "pick" = the one sound a baked event uses). Here each layer becomes ONE
        // "PlaySound" Animation Event (AnimationScripts.PlaySound, clip as the object reference)
        // on that clip's own keyframe time for that frame - so it follows the game's animation
        // speed settings by construction, with no code-side timers or fps maths.
        //
        // Idempotent: it first removes every PlaySound/PlaySoundEvent event on the clips the
        // manifest covers, so re-running never stacks duplicates and hand-assigned events that
        // disagree with the PAM get replaced. Any OTHER event (e.g. ExecuteAttack) is left alone.
        // Safe on an already-imported, hand-tuned plant: it only touches Animation Events.
        // ------------------------------------------------------------------------------------
        [Serializable] class SndLayer { public int[] sounds; public int pick; }
        [Serializable] class SndEvent { public int frame; public string sample; public SndLayer[] layers; }
        [Serializable] class SndAction { public int frame; public string command; }
        [Serializable] class SndAnimation { public string label; public int frames; public SndEvent[] events; public SndAction[] actions; }

        // Plants whose "attack" clip also gets an "ExecuteAttack" Animation Event on the PAM's
        // use_action frame (the throw/launch frame). CustomPlantBehaviorController.OnAnimationAttackEvent
        // spawns the projectile from it, so launches follow the game speed instead of a code timer.
        // Opt-in on purpose: shipped plants keep their clips untouched.
        static readonly HashSet<string> LaunchEventPlants = new HashSet<string> { "dusklobber" };
        [Serializable] class SndManifest { public SndAnimation[] animations; }

        const string ExportRoot = "D:/PvZ2RipTest/export_all";

        static SndManifest LoadSoundManifest(string exportName, string sub)
        {
            string path = sub == "plant"
                ? $"{ExportRoot}/{exportName}/sounds_manifest.json"
                : $"{ExportRoot}/{exportName}/{sub}/sounds_manifest.json";
            return File.Exists(path) ? JsonUtility.FromJson<SndManifest>(File.ReadAllText(path)) : null;
        }

        // Set by BakeSoundEventsForPlant: the export_all folder name of the plant being baked.
        static string bakeExportName;

        static AudioClip LoadPlantSound(string plantName, int wem)
        {
            string path = $"Assets/plantrip/{plantName}/sounds/{wem}.ogg";
            var clip = AssetDatabase.LoadAssetAtPath<AudioClip>(path);
            if (clip == null)
            {
                // Shared-bank sounds (AUDIO_ALWAYS_LOADED etc.) are ripped into the export's
                // sounds/ folder by plant_sounds.py but were never part of the original import.
                string src = $"{ExportRoot}/{bakeExportName}/sounds/{wem}.ogg";
                if (File.Exists(src))
                {
                    Directory.CreateDirectory($"Assets/plantrip/{plantName}/sounds");
                    File.Copy(src, path, true);
                    AssetDatabase.ImportAsset(path);
                    string bundle = AssetImporter.GetAtPath($"Assets/plantrip/{plantName}/models/default/plant/{plantName}.prefab")?.assetBundleName;
                    if (!string.IsNullOrEmpty(bundle))
                    {
                        AssetImporter.GetAtPath(path)?.SetAssetBundleNameAndVariant(bundle, "");
                    }
                    clip = AssetDatabase.LoadAssetAtPath<AudioClip>(path);
                    Debug.Log($"[BakeSound] pulled {wem}.ogg into {plantName}/sounds (bundle '{bundle}')");
                }
            }
            if (clip == null)
            {
                Debug.LogWarning($"[BakeSound] missing {path} (re-run rip_plant.py / plant_sounds.py for this plant)");
            }
            return clip;
        }

        static float[] FrameTimes(AnimationClip clip)
        {
            var binding = EditorCurveBinding.PPtrCurve("", typeof(SpriteRenderer), "m_Sprite");
            var keys = AnimationUtility.GetObjectReferenceCurve(clip, binding);
            return keys == null ? new float[0] : keys.Select(k => k.time).ToArray();
        }

        // Replaces a clip's PlaySound/PlaySoundEvent events with one PlaySound per (event, layer).
        // `events` is (frame offset, sound pick) pairs. Returns a one-line summary.
        // `launchFrame` >= 0 also (re)places the clip's single ExecuteAttack event at that frame offset.
        static string ReplaceSoundEvents(string plantName, string clipPath, List<(int frame, int pick)> events, int launchFrame = -1)
        {
            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);
            if (clip == null) return null;

            var times = FrameTimes(clip);
            var kept = new List<AnimationEvent>();
            var removed = new List<string>();
            foreach (var ev in AnimationUtility.GetAnimationEvents(clip))
            {
                if (ev.functionName == "PlaySound" || ev.functionName == "PlaySoundEvent")
                {
                    removed.Add($"{(ev.objectReferenceParameter != null ? ev.objectReferenceParameter.name : ev.stringParameter)}@{ev.time:0.###}");
                }
                else if (launchFrame >= 0 && ev.functionName == "ExecuteAttack")
                {
                    removed.Add($"ExecuteAttack@{ev.time:0.###}");
                }
                else
                {
                    kept.Add(ev);
                }
            }

            var added = new List<string>();
            foreach (var (frame, pick) in events)
            {
                var sfx = LoadPlantSound(plantName, pick);
                if (sfx == null || times.Length == 0) continue;
                float t = times[Math.Min(frame, times.Length - 1)];
                if (frame >= times.Length)
                {
                    Debug.LogWarning($"[BakeSound] {clipPath}: event frame {frame} is past the clip's {times.Length} keyframes - clamped to the last frame.");
                }
                kept.Add(new AnimationEvent { time = t, functionName = "PlaySound", objectReferenceParameter = sfx });
                added.Add($"{pick}@{t:0.###}");
            }

            if (launchFrame >= 0 && times.Length > 0)
            {
                float t = times[Math.Min(launchFrame, times.Length - 1)];
                kept.Add(new AnimationEvent { time = t, functionName = "ExecuteAttack" });
                added.Add($"ExecuteAttack@{t:0.###}");
            }

            AnimationUtility.SetAnimationEvents(clip, kept.ToArray());
            EditorUtility.SetDirty(clip);
            return $"removed [{string.Join(", ", removed)}] added [{string.Join(", ", added)}]";
        }

        // Bakes a plant's own animations only. Projectile HIT sounds are deliberately NOT baked: in this
        // mod they are code-driven (CustomProjectileDefinition.SetHitSfx, like Tumbleweed/Bloomerang),
        // so an Animation Event there would play the sound twice. plant_sounds.py prints the SetHitSfx
        // line for each plant instead.
        public static void BakeSoundEventsForPlant(string plantName, string exportName)
        {
            bakeExportName = exportName;
            string modelsRoot = $"Assets/plantrip/{plantName}/models/default";
            var manifest = LoadSoundManifest(exportName, "plant");
            if (manifest == null || manifest.animations == null)
            {
                Debug.Log($"[BakeSound] {plantName}: no sounds_manifest.json - skipped.");
                return;
            }

            AssetDatabase.Refresh();
            int clipsTouched = 0;
            foreach (var anim in manifest.animations)
            {
                string clipPath = $"{modelsRoot}/plant/{anim.label}/{anim.label}.anim";
                var wanted = new List<(int, int)>();
                foreach (var e in anim.events ?? new SndEvent[0])
                    foreach (var l in e.layers ?? new SndLayer[0])
                        wanted.Add((e.frame, l.pick));

                int launchFrame = -1;
                if (LaunchEventPlants.Contains(plantName) && anim.label == "attack")
                    foreach (var a in anim.actions ?? new SndAction[0])
                        if (a.command == "use_action") { launchFrame = a.frame; break; }

                var summary = ReplaceSoundEvents(plantName, clipPath, wanted, launchFrame);
                if (summary == null)
                {
                    if (wanted.Count > 0)
                        Debug.Log($"[BakeSound] {plantName}/{anim.label}: no such clip in the project ({wanted.Count} sound(s) not baked).");
                    continue;
                }
                clipsTouched++;
                Debug.Log($"[BakeSound] {plantName}/{anim.label}: {summary}");
            }

            AssetDatabase.SaveAssets();
            Debug.Log($"[BakeSound] {plantName}: {clipsTouched} clip(s) updated.");
        }

        // Batch entry point: re-bake sounds onto ALREADY-imported plants (never re-imports, so
        // hand-tuned controllers survive) and rebuild every tagged bundle with the plants' existing
        // bundle names. Reads D:/PvZ2RipTest/bake_sounds.txt: one plant per line, lowercase project
        // folder name.
        public static void BakeSoundEventsListed()
        {
            const string listFile = "D:/PvZ2RipTest/bake_sounds.txt";
            const string outputDir = "D:/PvZ2RipTest/bundles";
            if (!File.Exists(listFile))
            {
                Debug.LogError($"[BakeSound] {listFile} not found.");
                EditorApplication.Exit(1);
                return;
            }

            foreach (var raw in File.ReadAllLines(listFile))
            {
                var parts = raw.Trim().Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length == 0) continue;
                BakeSoundEventsForPlant(parts[0].ToLowerInvariant(), parts[0].ToUpperInvariant());
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Directory.CreateDirectory(outputDir);
            var built = BuildPipeline.BuildAssetBundles(outputDir, BuildAssetBundleOptions.ForceRebuildAssetBundle,
                BuildTarget.StandaloneWindows64);
            if (built == null)
            {
                Debug.LogError("[BakeSound] BuildAssetBundles failed - manifest is null.");
                EditorApplication.Exit(1);
                return;
            }
            Debug.Log($"[BakeSound] Rebuilt {built.GetAllAssetBundles().Length} bundle(s) -> {outputDir}");
            EditorApplication.Exit(0);
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
