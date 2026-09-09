using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace PvZRip.Editor
{
    /// <summary>
    /// Imports a plant exported by the PAM compositor (frames dir with per-label
    /// subfolders + manifest.tsv, plus a sounds dir of .ogg files) and builds the
    /// sprite/AnimationClip/AnimatorController/prefab set, matching the convention
    /// already used by pvzegyptianbundle/pvzmintbundle's shipped plants: frames live
    /// directly alongside their .anim clip under models/default/&lt;object&gt;/&lt;label&gt;/.
    /// </summary>
    public static class PvZRipImporter
    {
        // Convenience entry point for -batchmode -executeMethod invocation.
        public static void ImportBonkChoyTest()
        {
            ImportPlant(
                "bonkchoy_repro",
                "D:/PvZ2RipTest/export_bonkchoy",
                "D:/PvZ2RipTest/ww2ogg",
                12f);
            EditorApplication.Exit(0);
        }

        // Plant-only import (legacy entry point, still used by the bundle builder for
        // plants that only export a base "frames" dir).
        public static void ImportPlant(string plantName, string framesDir, string soundsDir, float sampleRate)
        {
            string destRoot = $"Assets/plantrip/{plantName}/models/default/plant";
            BuildAnimatedObject(destRoot, plantName, framesDir, sampleRate,
                out int frameCount, out int stateCount);

            int soundCount = ImportSounds(plantName, soundsDir);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"[PvZRipImporter] Imported '{plantName}': {stateCount} states, {frameCount} frames, " +
                      $"{soundCount} sounds -> {destRoot}/{plantName}.prefab");
        }

        // Full import: base plant + optional projectile / projectile_hit sub-objects +
        // optional seed packet sprite, matching the real shipped folder layout
        // (Assets/plant/<name>/models/default/{plant,projectile,projectile_hit}/...).
        public static void ImportPlantFull(string plantName, string plantFramesDir, string soundsDir,
            string projectileFramesDir, string projectileHitFramesDir, string seedPacketPng, float sampleRate)
        {
            string root = $"Assets/plantrip/{plantName}/models/default";
            BuildAnimatedObject($"{root}/plant", plantName, plantFramesDir, sampleRate,
                out int frameCount, out int stateCount);

            int soundCount = ImportSounds(plantName, soundsDir);

            bool hasProjectile = !string.IsNullOrEmpty(projectileFramesDir) && Directory.Exists(projectileFramesDir);
            if (hasProjectile)
            {
                BuildAnimatedObject($"{root}/projectile", "projectile", projectileFramesDir, sampleRate,
                    out _, out _);
            }

            bool hasImpact = !string.IsNullOrEmpty(projectileHitFramesDir) && Directory.Exists(projectileHitFramesDir);
            if (hasImpact)
            {
                BuildAnimatedObject($"{root}/projectile_hit", "projectile_hit", projectileHitFramesDir, sampleRate,
                    out _, out _);
            }

            bool hasSeedPacket = !string.IsNullOrEmpty(seedPacketPng) && File.Exists(seedPacketPng);
            if (hasSeedPacket)
            {
                ImportSeedPacket(plantName, seedPacketPng);
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"[PvZRipImporter] Imported '{plantName}': {stateCount} states, {frameCount} frames, " +
                      $"{soundCount} sounds, projectile={hasProjectile}, hit={hasImpact}, seedpacket={hasSeedPacket}");
        }

        static int ImportSounds(string plantName, string soundsDir)
        {
            if (string.IsNullOrEmpty(soundsDir) || !Directory.Exists(soundsDir))
            {
                return 0;
            }
            string soundsDest = $"Assets/plantrip/{plantName}/sounds";
            Directory.CreateDirectory(soundsDest);
            foreach (var ogg in Directory.GetFiles(soundsDir, "*.ogg"))
            {
                File.Copy(ogg, $"{soundsDest}/{Path.GetFileName(ogg)}", true);
            }
            AssetDatabase.Refresh();
            return Directory.GetFiles(soundsDir, "*.ogg").Length;
        }

        static void ImportSeedPacket(string plantName, string seedPacketPng)
        {
            string dest = $"Assets/plantrip/{plantName}/SPR_SeedPacket_{plantName}.png";
            File.Copy(seedPacketPng, dest, true);
            AssetDatabase.Refresh();
            var importer = (TextureImporter)AssetImporter.GetAtPath(dest);
            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.Single;
            importer.alphaIsTransparency = true;
            importer.SaveAndReimport();
        }

        // Bulk-export default for which labels are ambient/ongoing (loop) vs a
        // one-shot action that should play once and return to idle. Deliberately
        // simple - wrong for plants with multi-stage growth, reload sequences, or
        // multiple idle variants (e.g. a shield-break landing in an unshielded
        // idle instead of the default one), which get their transitions hand-fixed
        // in Unity's Animator window when that specific plant is implemented.
        static bool IsLoopingLabel(string label)
        {
            string l = label.ToLowerInvariant();
            return l.Contains("idle") || l.Contains("water") || l.Contains("loop");
        }

        // Renders one animated sub-object (plant / projectile / projectile_hit): reads
        // manifest.tsv, imports each frame as a pivot-aligned Sprite directly under
        // <objectRoot>/<label>/, builds one looping AnimationClip per label, an
        // AnimatorController switching between them, and a prefab with
        // SpriteRenderer + Animator + AudioSource. AnimationScripts is deliberately NOT
        // added here - PvZReCoreLib's SpriteRendererSkin.ApplySkin already does
        // transform.Find("anim").AddComponent<AnimationScripts>() at runtime after
        // instantiation, and baking a second copy into the prefab's serialized YAML
        // doesn't survive the Editor -> AssetBundle -> IL2CPP-player round trip (shows
        // up as "referenced script ... is missing" in the player log) and was breaking
        // the whole GameObject's rendering.
        static void BuildAnimatedObject(string objectRoot, string objectName, string framesDir, float sampleRate,
            out int frameCount, out int stateCount)
        {
            Directory.CreateDirectory(objectRoot);
            AssetDatabase.Refresh();

            var frameInfo = new Dictionary<string, (float px, float py)>();
            var labelOrder = new List<string>();
            var labelFrames = new Dictionary<string, List<string>>();

            string manifestPath = Path.Combine(framesDir, "manifest.tsv");
            foreach (var line in File.ReadAllLines(manifestPath))
            {
                if (string.IsNullOrWhiteSpace(line)) continue;
                var parts = line.Split('\t');
                if (parts.Length < 4) continue;
                string label = parts[0], filename = parts[1];
                float px = float.Parse(parts[2], CultureInfo.InvariantCulture);
                float py = float.Parse(parts[3], CultureInfo.InvariantCulture);
                frameInfo[$"{label}/{filename}"] = (px, py);
                if (!labelFrames.TryGetValue(label, out var list))
                {
                    list = new List<string>();
                    labelFrames[label] = list;
                    labelOrder.Add(label);
                }
                list.Add(filename);
            }

            foreach (var label in labelOrder)
            {
                string labelDir = $"{objectRoot}/{label}";
                Directory.CreateDirectory(labelDir);
                foreach (var filename in labelFrames[label])
                {
                    string src = Path.Combine(framesDir, label, filename);
                    string dst = $"{labelDir}/{filename}";
                    File.Copy(src, dst, true);
                }
            }
            AssetDatabase.Refresh();

            var spriteAssets = new Dictionary<string, Sprite>();
            foreach (var label in labelOrder)
            {
                foreach (var filename in labelFrames[label])
                {
                    string dst = $"{objectRoot}/{label}/{filename}";
                    var importer = (TextureImporter)AssetImporter.GetAtPath(dst);
                    importer.textureType = TextureImporterType.Sprite;
                    importer.spriteImportMode = SpriteImportMode.Single;
                    importer.alphaIsTransparency = true;

                    var settings = new TextureImporterSettings();
                    importer.ReadTextureSettings(settings);
                    // Constant per-plant pivot from the manifest (horizontal center,
                    // vertical = idle's own resting foot line) applied identically to
                    // every frame - see pam_compositor.py's export_all for why: no
                    // per-plant offset exists anywhere in the actual mod code, so this
                    // is baked in at export time instead, same as real prefabs bake
                    // their own per-character correction into the "anim" child's
                    // transform rather than into any runtime C# field.
                    settings.spriteAlignment = (int)SpriteAlignment.Custom;
                    var (px, py) = frameInfo[$"{label}/{filename}"];
                    settings.spritePivot = new Vector2(px, py);
                    // Real shipped plants use spritePixelsToUnits: 1 (1 px = 1 Unity
                    // unit), matching the game's pixel-coordinate world space. Leaving
                    // Unity's default of 100 here rendered everything at 1/100th scale
                    // - a few pixels on screen, effectively invisible.
                    settings.spritePixelsPerUnit = 1f;
                    importer.SetTextureSettings(settings);
                    importer.SaveAndReimport();

                    spriteAssets[$"{label}/{filename}"] = AssetDatabase.LoadAssetAtPath<Sprite>(dst);
                }
            }

            var clips = new Dictionary<string, AnimationClip>();
            foreach (var label in labelOrder)
            {
                var clip = new AnimationClip { frameRate = sampleRate };
                var frames = labelFrames[label];
                var keyframes = new ObjectReferenceKeyframe[frames.Count];
                for (int i = 0; i < frames.Count; i++)
                {
                    keyframes[i] = new ObjectReferenceKeyframe
                    {
                        time = i / sampleRate,
                        value = spriteAssets[$"{label}/{frames[i]}"]
                    };
                }
                var binding = EditorCurveBinding.PPtrCurve("", typeof(SpriteRenderer), "m_Sprite");
                AnimationUtility.SetObjectReferenceCurve(clip, binding, keyframes);

                // One-shot action labels (attack, etc.) must NOT loop - real
                // Bloomerang's controller has an idle<->shooting transition pair;
                // ours had no transitions at all, so with every clip set to loop,
                // calling PlayAnimation("attack") just looped the attack clip
                // forever (visibly: mouth stuck open) since nothing ever returned
                // to idle. Ambient/ongoing labels (idle, water, *loop*) still loop
                // normally. This is a bulk-export DEFAULT, not meant to be correct
                // for every plant's specific animation graph (multi-stage growth,
                // shield states, reload sequences, etc.) - those get hand-fixed in
                // Unity's Animator window per-plant when actually implementing that
                // plant's behavior controller; the generated ac.controller is a
                // normal, fully-editable asset like any hand-authored one.
                var clipSettings = AnimationUtility.GetAnimationClipSettings(clip);
                clipSettings.loopTime = IsLoopingLabel(label);
                AnimationUtility.SetAnimationClipSettings(clip, clipSettings);

                string clipPath = $"{objectRoot}/{label}/{label}.anim";
                AssetDatabase.CreateAsset(clip, clipPath);
                clips[label] = clip;
            }
            AssetDatabase.SaveAssets();

            string controllerPath = $"{objectRoot}/ac.controller";
            var controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);
            var stateMachine = controller.layers[0].stateMachine;
            AnimatorState defaultState = null;
            var states = new Dictionary<string, AnimatorState>();
            foreach (var label in labelOrder)
            {
                var state = stateMachine.AddState(label);
                state.motion = clips[label];
                state.speed = 1f;
                states[label] = state;
                if (label == "idle" || defaultState == null) defaultState = state;
            }
            stateMachine.defaultState = defaultState;

            // One-shot states (see the loopTime comment above) automatically return
            // to the default/idle state once their clip finishes playing, matching
            // real Bloomerang's idle<->shooting transition pair - no exit-time
            // condition/parameter needed since PlayAnimation() always re-triggers
            // the state directly via Animator.Play(). Bulk-export default only -
            // some plants need a one-shot to land somewhere other than the single
            // default idle (e.g. a shield-break landing in an unshielded idle
            // instead), which means rewiring this specific transition's target in
            // the Animator window when implementing that plant, not changing this
            // generator.
            foreach (var label in labelOrder)
            {
                if (IsLoopingLabel(label) || states[label] == defaultState) continue;
                var toIdle = states[label].AddTransition(defaultState);
                toIdle.hasExitTime = true;
                toIdle.exitTime = 1f;
                toIdle.duration = 0f;
                toIdle.hasFixedDuration = true;
            }

            EditorUtility.SetDirty(controller);
            AssetDatabase.SaveAssets();

            var root = new GameObject(objectName);
            var animGo = new GameObject("anim");
            animGo.transform.SetParent(root.transform);

            animGo.AddComponent<SpriteRenderer>();
            var audioSrc = animGo.AddComponent<AudioSource>();
            audioSrc.playOnAwake = false;

            var animator = animGo.AddComponent<Animator>();
            animator.runtimeAnimatorController = controller;

            string prefabPath = $"{objectRoot}/{objectName}.prefab";
            PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
            Object.DestroyImmediate(root);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            frameCount = frameInfo.Count;
            stateCount = labelOrder.Count;
        }
    }
}
