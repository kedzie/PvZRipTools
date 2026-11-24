#!/usr/bin/env python3
"""
PAM (PopCap Animation) -> flat PNG frame sequence compositor.

Resolves a decoded PAM JSON (from PopStudio's DecodePam, command code 180) plus a
plant's atlas rect mapping (from RESOURCES.RTON) and atlas PNG, and rasterizes the
global animation timeline into one flat, cropped PNG per frame -- matching the
convention already observed in PvZCompleteCollection's shipped AssetBundle-UnityProject
(frame_NNN.png, one Sprite per PAM frame, sliced into folders at label boundaries).
"""
import json
import math
import os
import sys
from pathlib import Path

from PIL import Image


def to_matrix6(t):
    """Normalize a PAM transform array (len 2, 3, or 6) to (a,b,c,d,tx,ty)."""
    if t is None:
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    if len(t) == 6:
        return tuple(t)
    if len(t) == 3:
        theta = t[0]
        a, b, c, d = math.cos(theta), math.sin(theta), -math.sin(theta), math.cos(theta)
        return (a, b, c, d, t[1], t[2])
    if len(t) == 2:
        return (1.0, 0.0, 0.0, 1.0, t[0], t[1])
    raise ValueError(f"unexpected transform length {len(t)}: {t}")


def mat_mul(m1, m2):
    """Compose m1 after m2: world = m1 . m2  (apply m2 first, then m1)."""
    a1, b1, c1, d1, tx1, ty1 = m1
    a2, b2, c2, d2, tx2, ty2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * tx2 + c1 * ty2 + tx1,
        b1 * tx2 + d1 * ty2 + ty1,
    )


def mat_invert(m):
    a, b, c, d, tx, ty = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        det = 1e-12
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    itx = -(ia * tx + ic * ty)
    ity = -(ib * tx + id_ * ty)
    return (ia, ib, ic, id_, itx, ity)


# Some PAMs carry TWO complete art sets drawn on top of each other and let the game pick one at
# runtime (Dusk Lobber: every part exists as "<name>" - the normal green plant - and "<name>_2",
# the blue "_dark" variant, both appended on frame 0 with no colour/alpha transform hiding either).
# Flattening them composites the dark set over the normal one, so the export came out blue. Set
# PAM_SKIP_IMAGE_SUFFIX (rip_plant.py does it from plants.json "skip_image_suffix") to drop the
# images whose name ends with it. Default off - every other plant renders exactly as before.
SKIP_IMAGE_SUFFIX = os.environ.get("PAM_SKIP_IMAGE_SUFFIX", "")


class PamAsset:
    SKIP_SPRITE_NAMES = {"_custom"}

    def __init__(self, pam_json_path, resources_json_path, atlas_png_path, plant_group_id):
        self.pam = json.load(open(pam_json_path))
        resources = json.load(open(resources_json_path))
        self.rect_by_id = {}
        for g in resources["groups"]:
            if g.get("id") == plant_group_id and g.get("type") == "simple":
                for r in g.get("resources", []):
                    if "ax" in r:
                        self.rect_by_id[r["id"]] = (r["ax"], r["ay"], r["aw"], r["ah"])
        if not self.rect_by_id:
            raise ValueError(f"no atlas rects found for group {plant_group_id}")
        self.atlas = Image.open(atlas_png_path).convert("RGBA")
        self.sprites_by_name = {s["name"]: s for s in self.pam["sprite"]}

    def image_rect_and_crop(self, image_index):
        img = self.pam["image"][image_index]
        res_id = img["name"].split("|")[-1]
        rect = self.rect_by_id.get(res_id)
        if rect is None:
            return None, None
        ax, ay, aw, ah = rect
        crop = self.atlas.crop((ax, ay, ax + aw, ay + ah))
        local_mat = to_matrix6(img.get("transform"))
        return crop, local_mat

    def _replay(self, frame_list, upto_index):
        """Replay append/remove/change events 0..upto_index inclusive; return active layer dict."""
        layers = {}
        for i in range(upto_index + 1):
            fr = frame_list[i]
            for rem in fr.get("remove", []) or []:
                layers.pop(rem["index"], None)
            for app in fr.get("append", []) or []:
                layers[app["index"]] = dict(app)
                layers[app["index"]].setdefault("transform", None)
                layers[app["index"]].setdefault("color", None)
                layers[app["index"]].setdefault("src_rect", None)
                layers[app["index"]].setdefault("anim_frame_num", 0)
            for ch in fr.get("change", []) or []:
                idx = ch["index"]
                if idx not in layers:
                    layers[idx] = dict(ch)
                    continue
                for k in ("transform", "color", "src_rect", "anim_frame_num"):
                    if ch.get(k) is not None:
                        layers[idx][k] = ch[k]
        return layers

    def resolve_leaves(self, sprite, frame_index, parent_matrix, depth=0):
        """Recursively resolve a sprite's active layers at frame_index into a flat
        list of (world_matrix, color, crop_image) leaf draws, back-to-front by index."""
        if depth > 8:
            return []
        frames = sprite["frame"]
        frame_index = max(0, min(frame_index, len(frames) - 1))
        layers = self._replay(frames, frame_index)
        leaves = []
        for idx in sorted(layers.keys()):
            layer = layers[idx]
            local_mat = to_matrix6(layer.get("transform"))
            world_mat = mat_mul(parent_matrix, local_mat)
            resource = layer.get("resource", 0)
            if layer.get("sprite"):
                child = self.pam["sprite"][resource]
                if child.get("name") in self.SKIP_SPRITE_NAMES:
                    continue
                child_frame = layer.get("anim_frame_num", 0) or 0
                leaves.extend(self.resolve_leaves(child, child_frame, world_mat, depth + 1))
            else:
                if SKIP_IMAGE_SUFFIX:
                    img = self.pam["image"][resource]
                    img_name = (img["name"] if isinstance(img, dict) else str(img)).split("|")[0]
                    if img_name.endswith(SKIP_IMAGE_SUFFIX):
                        continue
                crop, img_local_mat = self.image_rect_and_crop(resource)
                if crop is None:
                    continue
                final_mat = mat_mul(world_mat, img_local_mat)
                leaves.append((final_mat, layer.get("color"), crop))
        return leaves

    def render_global_frame(self, global_index, canvas_size=1600, origin=(800, 800)):
        main = self.pam["main_sprite"]
        identity = (1.0, 0.0, 0.0, 1.0, origin[0], origin[1])
        leaves = self.resolve_leaves(main, global_index, identity)
        canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        for mat, color, crop in leaves:
            if color is not None and len(color) >= 4 and color[3] <= 0.001:
                continue
            inv = mat_invert(mat)
            a, b, c, d, tx, ty = inv
            layer_img = crop
            if color is not None and (color[0] < 0.999 or color[1] < 0.999 or color[2] < 0.999 or color[3] < 0.999):
                r, g, bch, al = layer_img.split()
                r = r.point(lambda v, m=color[0]: int(v * m))
                g = g.point(lambda v, m=color[1]: int(v * m))
                bch = bch.point(lambda v, m=color[2]: int(v * m))
                al = al.point(lambda v, m=color[3]: int(v * m))
                layer_img = Image.merge("RGBA", (r, g, bch, al))
            transformed = layer_img.transform(
                (canvas_size, canvas_size),
                Image.AFFINE,
                (a, c, tx, b, d, ty),
                resample=Image.BICUBIC,
            )
            canvas.alpha_composite(transformed)
        return canvas


    def label_ranges(self):
        """[(label, start_global_index, end_global_index_inclusive), ...] from main_sprite labels."""
        frames = self.pam["main_sprite"]["frame"]
        labeled = [(i, f["label"]) for i, f in enumerate(frames) if f.get("label")]
        ranges = []
        for n, (start, label) in enumerate(labeled):
            end = (labeled[n + 1][0] - 1) if n + 1 < len(labeled) else len(frames) - 1
            ranges.append((label, start, end))
        return ranges

    def export_all(self, out_dir, canvas_size=1600, origin=(800, 800), skip_labels_containing=("plantfood",),
                   anchor="standing", anchor_ignore_label_prefixes=("water", "pf", "plantfood")):
        """Render every global frame, sliced into <out_dir>/<label>/frame_<N+1>.png,
        matching the AssetBundle-UnityProject convention (1-indexed filenames).

        No PAM-derived math, no per-plant hand-tuned offset (there isn't one
        anywhere in the actual mod code - the per-character correction real
        prefabs have is baked into each one's own "anim" child transform, not any
        runtime C# field, so we bake ours in at export time the same way).

        Width is cropped PER FRAME, not to one fixed size for the whole timeline:
        each frame's own canvas is sized to exactly 2x its own furthest excursion
        (left or right) from a single shared horizontal reference - idle's own
        first frame's center - and stays symmetric around that same reference,
        so pivot_x=0.5 always lands on the correct world anchor no matter which
        frame is shown, even though each frame's width differs. A frame with a
        small side-to-side sway gets a small, tightly-cropped canvas instead of
        inheriting padding sized for the widest excursion anywhere in the whole
        timeline (previously one shared width covered every frame, which meant
        most frames - anything narrower than the single widest lunge/reach in
        the whole clip - carried large, pure-transparent side margins; measured
        as high as ~75-90% wasted pixel area per frame on FirePeashooter).
        ANCHOR (vertical): every frame shares ONE fixed anchor point, bottom-middle of a reference line
        (the largest bbox bottom over the frames that define it), so the subject stands centred in its
        square and anything that jumps, slides, lunges or sinks does so RELATIVE to that point.
          anchor="standing" (plants, the default): the lowest point of the STANDING clips (every clip whose
            label contains "idle"), i.e. the plant's feet on the ground line. A clip that reaches lower
            (an explosion, a lunge, a burst below the feet) hangs below the feet and keeps its real motion;
            it does not lift the idle pose off the ground. A plant with no idle clip (e.g. an instant plant)
            falls back to the first frame of its first clip (its planted pose).
          anchor="lowest" (effects, projectiles, hit effects): the lowest point of the WHOLE animation set,
            because they have no standing pose.
          anchor="frame_bottom": every frame at its OWN bottom edge - the old behaviour, kept only for
            comparing: it makes static parts wobble and flattens jumps.
        Unity's pivot is a fraction of each frame's own (tight) image, so a frame whose own bottom is above
        the reference gets a pivot BELOW its image (negative pivot_y = (frame_bottom - reference) /
        frame_height) and one that reaches below it a positive pivot_y > 0 (above its bottom edge). Frame
        heights stay tight (no transparent padding, so no extra texture memory).
        Clips whose label starts with anchor_ignore_label_prefixes ("water": the plant standing in a
        ducky tube, which hangs below the feet; "pf*"/"plantfood*": Plant Food clips, which Replanted
        never plays) still get exported with the same anchor but do not take part in finding the
        lowest point - otherwise every land plant would be lifted by the tube / the Plant Food art
        (Bamboo Spartan's pf_attack alone reaches 170 px below his feet).

        plantfood-labeled frames are excluded (and not exported) since Plant Food
        is a PvZ2 mobile feature not present in Replanted.
        """
        out_dir = Path(out_dir)
        frame_list = []
        for label, start, end in self.label_ranges():
            if any(s in label.lower() for s in skip_labels_containing):
                continue
            for global_index in range(start, end + 1):
                frame_list.append((label, global_index))

        # Single render pass: cache each frame's own tight crop (small - just the
        # visible content, not the full 1600x1600 canvas) instead of discarding it
        # after measuring the bbox. The final fixed-width crop can't be produced
        # until every frame's bbox is known (the width has to cover the widest
        # frame in the whole timeline), but building it from the cached tight
        # crop via a plain paste is orders of magnitude cheaper than re-rendering
        # the frame from PAM data a second time.
        bboxes = {}
        tight_crops = {}
        first_frame_bbox = None
        for _, global_index in frame_list:
            canvas = self.render_global_frame(global_index, canvas_size, origin)
            bbox = canvas.getbbox()
            bboxes[global_index] = bbox
            if bbox is not None:
                tight_crops[global_index] = canvas.crop(bbox)
                if first_frame_bbox is None:
                    first_frame_bbox = bbox

        center_x = (first_frame_bbox[0] + first_frame_bbox[2]) / 2.0 if first_frame_bbox else None

        def counts_for_anchor(label):
            return not any(label.lower().startswith(p) for p in anchor_ignore_label_prefixes)

        counted = [(lbl, gi) for lbl, gi in frame_list if bboxes[gi] is not None and counts_for_anchor(lbl)]
        if not counted:  # every clip is an ignored one: fall back to all of them
            counted = [(lbl, gi) for lbl, gi in frame_list if bboxes[gi] is not None]
        lowest = None
        if anchor == "standing":
            standing = [bboxes[gi][3] for lbl, gi in counted if "idle" in lbl.lower()]
            if standing:
                lowest = max(standing)
            elif counted:
                lowest = bboxes[counted[0][1]][3]  # no idle clip: the planted pose (first frame)
        elif counted:
            lowest = max(bboxes[gi][3] for _, gi in counted)

        manifest = {}
        for label, global_index in frame_list:
            label_dir = out_dir / label
            label_dir.mkdir(parents=True, exist_ok=True)
            bbox = bboxes[global_index]
            if bbox is None or center_x is None:
                cropped = tight_crops.get(global_index) or Image.new("RGBA", (1, 1), (0, 0, 0, 0))
                left = right = None
            else:
                half_width = max(abs(bbox[0] - center_x), abs(bbox[2] - center_x))
                left = center_x - half_width
                right = center_x + half_width
                cropped = Image.new("RGBA", (int(right - left), int(bbox[3] - bbox[1])), (0, 0, 0, 0))
                tight = tight_crops[global_index]
                paste_x = int(bbox[0] - left)
                cropped.paste(tight, (paste_x, 0), tight)
            fname = f"frame_{global_index + 1}.png"
            cropped.save(label_dir / fname)
            pivot_y = 0.0
            if anchor != "frame_bottom" and bbox is not None and lowest is not None:
                pivot_y = (bbox[3] - lowest) / float(max(1, cropped.size[1]))
            manifest[f"{label}/{fname}"] = {
                "bbox": [left, bbox[1], right, bbox[3]] if bbox and left is not None else bbox,
                "pivot": [0.5, pivot_y],
                "size": list(cropped.size),
            }
        with open(out_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        with open(out_dir / "manifest.tsv", "w") as f:
            for key, info in manifest.items():
                label, fname = key.split("/", 1)
                px, py = info["pivot"]
                f.write(f"{label}\t{fname}\t{px}\t{py}\n")
        return manifest


def main():
    if len(sys.argv) < 5:
        print("usage: pam_compositor.py <pam.json> <resources.json> <atlas.png> <plant_group_id> [frame_idx out.png | --all out_dir]")
        sys.exit(1)
    pam_json, resources_json, atlas_png, group_id = sys.argv[1:5]
    asset = PamAsset(pam_json, resources_json, atlas_png, group_id)
    if len(sys.argv) > 5 and sys.argv[5] == "--all":
        out_dir = sys.argv[6] if len(sys.argv) > 6 else "export"
        anchor = "standing"
        if "--anchor" in sys.argv:
            anchor = sys.argv[sys.argv.index("--anchor") + 1]
        manifest = asset.export_all(out_dir, anchor=anchor)
        print(f"exported {len(manifest)} frames to {out_dir}, labels: {[l for l,_,_ in asset.label_ranges()]}")
    else:
        frame_idx = sys.argv[5] if len(sys.argv) > 5 else "0"
        out = sys.argv[6] if len(sys.argv) > 6 else "out.png"
        canvas = asset.render_global_frame(int(frame_idx))
        bbox = canvas.getbbox()
        if bbox:
            canvas = canvas.crop(bbox)
        canvas.save(out)
        print(f"wrote {out} size={canvas.size} bbox={bbox}")


if __name__ == "__main__":
    main()
