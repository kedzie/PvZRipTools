import math
from PIL import Image, ImageDraw


def draw_belt(length, th):
    """A horizontal conveyor belt (rollers at both ends, slanted treads, orange speed chevrons) as an RGBA image."""
    pad = 14
    k = th / 22.0
    img = Image.new('RGBA', (int(length + 2 * pad * 2), int(th + 2 * pad + 8 * k)), (0, 0, 0, 0))
    ld = ImageDraw.Draw(img)
    x0, x1, y0, y1 = pad * 2, pad * 2 + length, pad, pad + th
    r = th / 2
    ld.rounded_rectangle((x0, y0 + 5 * k, x1, y1 + 5 * k), radius=r, fill=(0, 20, 0, 150))
    ld.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=(52, 55, 62, 255), outline=(238, 238, 242, 255), width=max(2, int(3 * k)))
    step = 15 * k
    x = x0 + r + 6 * k
    while x < x1 - r - 4 * k:
        ld.line((x, y0 + 4 * k, x - 7 * k, y1 - 4 * k), fill=(92, 96, 106, 255), width=max(2, int(3 * k)))
        x += step
    ld.line((x0 + r, y0 + 3 * k, x1 - r, y0 + 3 * k), fill=(150, 154, 164, 255), width=max(1, int(2 * k)))
    x = x0 + r * 2.2
    while x < x1 - r * 3:
        for dx in (0, 11 * k):
            ld.polygon([(x + dx, y0 + 5 * k), (x + dx + 9 * k, (y0 + y1) / 2), (x + dx, y1 - 5 * k),
                        (x + dx + 4 * k, y1 - 5 * k), (x + dx + 13 * k, (y0 + y1) / 2), (x + dx + 4 * k, y0 + 5 * k)],
                       fill=(255, 170, 40, 255))
        x += 110 * k
    for cx in (x0 + r, x1 - r):
        ld.ellipse((cx - r + 2 * k, y0 + 2 * k, cx + r - 2 * k, y1 - 2 * k), fill=(88, 92, 100, 255), outline=(18, 20, 24, 255), width=max(2, int(3 * k)))
        ld.ellipse((cx - 4 * k, (y0 + y1) / 2 - 4 * k, cx + 4 * k, (y0 + y1) / 2 + 4 * k), fill=(30, 32, 36, 255))
    return img


def belt_group(canvas, cx, cy, length, th, angle, items, place, prep, extras=()):
    """An angled belt (rising to the right by `angle` degrees, centred on cx, cy) with plants standing on it.
    items: (image, height, glow colour, place() kwargs, t) with t = 0..1 from the low end to the high end.
    extras: (RGBA image, t, padding) ready-made images (e.g. a hypnotized zombie card) that also ride the belt;
    `padding` is the transparent margin below the picture that should sink into the belt."""
    a = math.radians(angle)
    rot = draw_belt(length, th).rotate(angle, resample=Image.BICUBIC, expand=True)
    canvas.alpha_composite(rot, (int(cx - rot.width / 2), int(cy - rot.height / 2)))
    for im, h, col, kw, t in sorted(items, key=lambda it: -it[4]):     # the high end is further back: draw it first
        d = (t - 0.5) * length
        x = cx + d * math.cos(a)
        feet = cy - d * math.sin(a) - (th / 2) * math.cos(a) + 5
        pad = kw.get('glow', 16) * 2 + kw.get('width', 6) + 4          # place() puts the feet this far above its ybottom
        place(canvas, prep(im, h), x, feet + pad - 8, col, **kw)
    for img, t, margin in extras:
        d = (t - 0.5) * length
        x = cx + d * math.cos(a)
        feet = cy - d * math.sin(a) - (th / 2) * math.cos(a) + 5
        canvas.alpha_composite(img, (int(x - img.width / 2), int(feet + margin - img.height)))
