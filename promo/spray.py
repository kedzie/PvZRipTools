import random, math
from PIL import Image, ImageDraw, ImageFilter


def _stroke(d, p0, p1, width, rnd, fill):
    n = max(8, int(math.dist(p0, p1) / 2))
    for i in range(n + 1):
        t = i / n
        x = p0[0] + (p1[0] - p0[0]) * t + rnd.uniform(-1.2, 1.2)
        y = p0[1] + (p1[1] - p0[1]) * t + rnd.uniform(-1.2, 1.2)
        r = width / 2 * rnd.uniform(0.82, 1.08)
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def spray_plus(canvas, cx, cy, size, color=(240, 56, 40), angle=-7, seed=3):
    """Draw a spray-painted '+' centred at (cx, cy), roughly `size` px across, onto canvas (RGBA)."""
    rnd = random.Random(seed)
    pad = int(size * 0.9)
    S = int(size + pad * 2)
    layer = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = S / 2
    h = size / 2
    w = size * 0.24
    solid = color + (255,)
    # two slightly uneven bars
    _stroke(d, (c - h, c + size * 0.03), (c + h, c - size * 0.02), w, rnd, solid)
    _stroke(d, (c + size * 0.02, c - h), (c - size * 0.03, c + h), w, rnd, solid)
    # drips off the lower ends
    for (x, y0, ln) in [(c - size * 0.03 + w * 0.12, c + h, size * 0.34),
                        (c - h + w * 0.2, c + size * 0.05 + w * 0.3, size * 0.22),
                        (c + h - w * 0.25, c - size * 0.02 + w * 0.3, size * 0.16)]:
        dw = w * 0.2
        d.rectangle((x - dw / 2, y0, x + dw / 2, y0 + ln), fill=solid)
        d.ellipse((x - dw * 0.75, y0 + ln - dw * 0.6, x + dw * 0.75, y0 + ln + dw * 0.9), fill=solid)
    core = layer.copy()
    # overspray halo
    halo = core.filter(ImageFilter.GaussianBlur(size * 0.08))
    halo.putalpha(halo.getchannel('A').point(lambda v: int(v * 0.55)))
    # speckles
    spk = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spk)
    for _ in range(int(size * 4)):
        a = rnd.uniform(0, 2 * math.pi)
        # sprinkle around the bars
        if rnd.random() < 0.5:
            x = c + rnd.uniform(-h * 1.15, h * 1.15)
            y = c + rnd.gauss(0, w * 0.9)
        else:
            x = c + rnd.gauss(0, w * 0.9)
            y = c + rnd.uniform(-h * 1.15, h * 1.15)
        r = rnd.uniform(0.6, 1.8)
        sd.ellipse((x - r, y - r, x + r, y + r), fill=color + (rnd.randint(110, 230),))
    # a lighter spray-through highlight on the bars
    hi = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    lite = tuple(min(255, v + 60) for v in color) + (170,)
    _stroke(hd, (c - h * 0.8, c + size * 0.03 - w * 0.2), (c + h * 0.8, c - size * 0.02 - w * 0.2), w * 0.28, rnd, lite)
    _stroke(hd, (c + size * 0.02 - w * 0.2, c - h * 0.8), (c - size * 0.03 - w * 0.2, c + h * 0.8), w * 0.28, rnd, lite)
    hi = Image.composite(hi, Image.new('RGBA', (S, S), (0, 0, 0, 0)), core.getchannel('A'))
    out = Image.alpha_composite(halo, spk)
    out = Image.alpha_composite(out, core)
    out = Image.alpha_composite(out, hi.filter(ImageFilter.GaussianBlur(1.2)))
    # dark drop shadow for pop on light chips
    sh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    sh.putalpha(core.getchannel('A').point(lambda v: int(v * 0.35)))
    sh = sh.filter(ImageFilter.GaussianBlur(2.5))
    final = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    final.alpha_composite(sh, (3, 4))
    final = Image.alpha_composite(final, out)
    final = final.rotate(angle, resample=Image.BICUBIC)
    canvas.alpha_composite(final, (int(cx - S / 2), int(cy - S / 2)))
