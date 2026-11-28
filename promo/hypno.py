import math, os
from PIL import Image, ImageDraw, ImageFilter, ImageChops
ASSETS = os.environ.get('PROMO_ASSETS', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets'))   # local only, not in git
Z = os.path.join(ASSETS, 'zomb', 'SPR_Almanac_Zombies_%s.png')
PINK = (255, 90, 205)


def heart(d, cx, cy, s, fill, outline):
    pts = []
    for t in range(0, 360, 6):
        a = math.radians(t)
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + x * s / 17, cy + y * s / 17))
    d.polygon(pts, fill=fill, outline=outline)


def spiral_badge(size):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((1, 1, size - 2, size - 2), fill=(255, 235, 250, 255), outline=(130, 20, 100, 255), width=max(2, size // 12))
    c = size / 2
    pts = []
    turns = 3.2
    for i in range(0, 400):
        t = i / 399
        a = t * turns * 2 * math.pi
        r = t * (size / 2 - size * 0.12)
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    d.line(pts, fill=(200, 30, 150, 255), width=max(2, size // 11), joint='curve')
    return im


def hypno_tile(name, size, angle=0, glow=18):
    im = Image.open(Z % name).convert('RGBA')
    s = size / im.width
    im = im.resize((size, int(im.height * s)), Image.LANCZOS)
    # pink wash over the portrait
    wash = Image.new('RGBA', im.size, PINK + (0,))
    k = 0.18 if name.startswith('VP') else 0.42
    wash.putalpha(im.getchannel('A').point(lambda v: int(v * k)))
    im = Image.alpha_composite(im, wash)
    badge = spiral_badge(int(size * 0.34))
    im.alpha_composite(badge, (im.width - badge.width - 4, 4))
    pad = glow * 2 + 12
    base = Image.new('RGBA', (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    base.alpha_composite(im, (pad, pad))
    a = base.getchannel('A').filter(ImageFilter.MaxFilter(9))
    g = a.filter(ImageFilter.GaussianBlur(glow))
    gl = Image.new('RGBA', base.size, PINK + (0,))
    gl.putalpha(g.point(lambda v: int(v * 0.85)))
    out = Image.alpha_composite(gl, base)
    d = ImageDraw.Draw(out)
    heart(d, out.width * 0.13, out.height * 0.86, size * 0.27, (255, 110, 190, 255), (150, 20, 100, 255))
    return out.rotate(angle, resample=Image.BICUBIC, expand=True)


def hypno_group(canvas, items):
    """items: (name, size, angle, x, y)  centre positions, drawn in order."""
    for name, size, angle, x, y in items:
        t = hypno_tile(name, size, angle)
        canvas.alpha_composite(t, (int(x - t.width / 2), int(y - t.height / 2)))
