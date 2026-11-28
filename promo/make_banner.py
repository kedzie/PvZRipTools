import math, random, glob, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hypno import hypno_group
from belt import belt_group
from hypno import hypno_tile
from logo_ribbon import ref_ribbon, BRIANNE
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

# Release being promoted (override with PROMO_VERSION / PROMO_PLANTS)
VERSION = os.environ.get('PROMO_VERSION', '1.28')
PLANT_COUNT = int(os.environ.get('PROMO_PLANTS', '32'))

W, H = 1300, 372
A = os.environ.get('PLANTRIP_A', '/mnt/d/PvZ/ReverseEngineering/AssetBundle-UnityProject/Assets/plantrip')   # local-only ripped plant frames
A2 = os.environ.get('PLANTRIP_A2', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'unity', 'Assets', 'plantrip'))
FONT = BRIANNE
random.seed(7)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def background():
    horizon = 150
    bg = Image.new('RGB', (W, H))
    px = bg.load()
    for y in range(H):
        for x in range(W):
            if y < horizon:
                c = lerp((70, 170, 235), (170, 225, 250), y / horizon)
            else:
                t = (y - horizon) / (H - horizon)
                c = lerp((92, 178, 52), (38, 112, 38), t)
                if int((x - W / 2) / (60 + 140 * t) + 50) % 2 == 0:
                    c = lerp(c, (255, 255, 255), 0.05)
            px[x, y] = c
    bg = bg.convert('RGBA')
    hedge = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hedge)
    for i in range(110):
        cx = random.randint(-40, W + 40)
        r = random.randint(24, 46)
        cy = horizon - random.randint(-4, 16)
        sh = random.randint(0, 28)
        hd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(40 + sh, 140 + sh, 40 + sh, 255),
                   outline=(16, 70, 22, 255), width=3)
    bg = Image.alpha_composite(bg, hedge)
    rays = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for k in range(-7, 8):
        a0 = math.radians(90 + k * 8 - 2.5)
        a1 = math.radians(90 + k * 8 + 2.5)
        rd.polygon([(W / 2, -60), (W / 2 + math.cos(a0) * 1500, -60 + math.sin(a0) * 1500),
                    (W / 2 + math.cos(a1) * 1500, -60 + math.sin(a1) * 1500)], fill=(255, 255, 220, 36))
    bg = Image.alpha_composite(bg, rays.filter(ImageFilter.GaussianBlur(10)))
    vig = Image.new('L', (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.2, -H * 0.5, W * 1.2, H * 1.5), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(110))
    shade = Image.new('RGBA', (W, H), (4, 20, 8, 150))
    shade.putalpha(ImageChops.invert(vig).point(lambda v: int(v * 0.6)))
    return Image.alpha_composite(bg, shade)


def frame(plant, anim, idx=None):
    fr = sorted(glob.glob(f'{A}/{plant}/models/default/plant/{anim}/*.png')) or sorted(glob.glob(f'{A2}/{plant}/models/default/plant/{anim}/*.png'))
    im = Image.open(fr[len(fr) // 3 if idx is None else idx]).convert('RGBA')
    return im.crop(im.getchannel('A').getbbox())


def prep(im, height, flip=False):
    s = height / im.height
    im = im.resize((max(1, int(im.width * s)), height), Image.LANCZOS)
    return im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im


def outline_glow(im, color, width=6, glow=16, glow_alpha=0.55):
    pad = glow * 2 + width + 4
    base = Image.new('RGBA', (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    base.paste(im, (pad, pad), im)
    ol = base.getchannel('A').filter(ImageFilter.MaxFilter(width * 2 + 1))
    g = ol.filter(ImageFilter.GaussianBlur(glow))
    gl = Image.new('RGBA', base.size, color + (0,))
    gl.putalpha(g.point(lambda v: int(v * glow_alpha)))
    dk = Image.new('RGBA', base.size, (14, 40, 18, 0))
    dk.putalpha(ol)
    return Image.alpha_composite(Image.alpha_composite(gl, dk), base)


def place(canvas, im, x, ybottom, color, **kw):
    sp = outline_glow(im, color, **kw)
    sh = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    w = im.width * 0.95
    ImageDraw.Draw(sh).ellipse((x - w / 2, ybottom - 10, x + w / 2, ybottom + 16), fill=(0, 20, 0, 140))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)))
    canvas.alpha_composite(sp, (int(x - sp.width / 2), int(ybottom - sp.height + 8)))


fire = frame('firepeashooter', 'idle')
bamboo = frame('bamboospartan', 'idle')
endur = frame('endurian', 'idle', 0)
celery = frame('celerystalker', 'idle')
tumble = frame('tumbleweed', 'idle3_1')
ice = frame('iceweed', 'stage1_idle1')
dusk = frame('dusklobber', 'idle')
wallnut = frame('primal_wallnut', 'damage')
peanut = frame('peanut', 'idle')
peapod = frame('peapod', 'idle5')
psun = frame('primal_sunflower', 'idle')
gold = frame('goldbloom', 'idle')
chilly = frame('chillypepper', 'idle')
bombe = frame('bombegranate', 'idle')
exnut = frame('explodeonut', 'idle')
stallia = frame('stallia', 'idle3')
mega = frame('megagatling', 'idle')
aloe = frame('aloe', 'idle')
snap = frame('snapdragon', 'idle')
sbean = frame('springbean', 'idle')
peapr = frame('primal_peashooter', 'idle')
pmine = frame('primal_potatomine', 'idle')
chard = frame('chardguard', 'idle_leaves3')
sour = frame('sourshot', 'idle')
pepper = frame('pepperpult', 'idle')
nshade = frame('nightshade', 'idle')
sweetp = frame('sweetpotato', 'idle')
pvine = frame('pvine', 'idle')
elec = frame('electric_peashooter', 'idle')
snappea = frame('snappea', 'idle')
coldsn = frame('cold_snapdragon', 'idle')
stunion = frame('stunion', 'idle')


def stroked(d, xy, text, font, fill, stroke, sw, shadow=0):
    x, y = xy
    if shadow:
        d.text((x, y + shadow), text, font=font, fill=(0, 20, 0, 200), anchor='mm', stroke_width=sw, stroke_fill=(0, 20, 0, 200))
    d.text((x, y), text, font=font, fill=fill, anchor='mm', stroke_width=sw, stroke_fill=stroke)


def build(with_text, out, title=True):
    canvas = background()
    if with_text:
        d = ImageDraw.Draw(canvas)
        if title:
            stroked(d, (W / 2, 58), 'COMPLETE', ImageFont.truetype(FONT, 74), (255, 255, 255), (22, 80, 30), 6, 6)
            stroked(d, (W / 2, 136), 'COLLECTION 2', ImageFont.truetype(FONT, 88), (255, 232, 70), (110, 50, 6), 7, 7)
            ref_ribbon(canvas, W / 2, 180, 76, 44, pad=26, gap=20)
        d = ImageDraw.Draw(canvas)
        # right flank (back to front)
        place(canvas, prep(wallnut, 118), 990, 372, (200, 170, 120))
        place(canvas, prep(endur, 150, flip=True), 1062, 372, (255, 215, 90))
        place(canvas, prep(bamboo, 250, flip=True), 1205, 376, (140, 255, 140), glow=20, glow_alpha=0.7)
        # left flank
        place(canvas, prep(peapod, 138), 350, 372, (150, 255, 120))
        place(canvas, prep(celery, 178), 238, 372, (200, 255, 120))
        place(canvas, prep(fire, 238), 92, 372, (255, 150, 40), glow=20, glow_alpha=0.75)
        # small plants under the chips (ybottom includes ~34px glow padding)
        row = [(tumble, 62, (255, 220, 120), {}), (peanut, 62, (255, 200, 110), {}),
               (mega, 56, (255, 215, 90), {}), (psun, 62, (255, 230, 90), {}),
               (gold, 62, (255, 215, 60), {}), (chilly, 74, (140, 220, 255), dict(glow=12, glow_alpha=0.8)),
               (bombe, 60, (255, 90, 90), {}), (exnut, 68, (190, 190, 200), {}),
               (dusk, 70, (205, 120, 255), dict(glow=12, glow_alpha=0.75)),
               (stallia, 60, (205, 120, 255), dict(glow=10, glow_alpha=0.75)),
               (ice, 52, (150, 225, 255), dict(glow=12, glow_alpha=0.8)),
               (aloe, 62, (170, 255, 190), {}), (snap, 62, (255, 190, 90), {}),
               (sbean, 60, (170, 255, 90), {}), (peapr, 58, (170, 255, 120), {}),
               (pmine, 44, (255, 170, 90), {}),
               (chard, 64, (200, 255, 140), {}), (nshade, 60, (205, 120, 255), dict(glow=12, glow_alpha=0.75)),
               (sweetp, 62, (255, 170, 90), {}), (coldsn, 66, (150, 225, 255), dict(glow=12, glow_alpha=0.8)),
               (stunion, 56, (190, 255, 120), {}),
               (sour, 64, (255, 240, 90), {}), (pepper, 66, (255, 120, 80), dict(glow=12, glow_alpha=0.8))]
        xs = [388 + i * 27 for i in range(len(row))] if title else [535 + i * 39 for i in range(len(row))]
        if title:
            for k, ((im, h, col, kw), x) in enumerate(zip(row, xs)):
                place(canvas, prep(im, int(h * 1.1)), x, 396 - (9 if k % 2 else 0), col, **kw)
        else:
            # Nexus overlay version: two staggered rows in the open middle (the title text sits bottom-left
            # and the buttons bottom-right), bigger than the strip version.
            back, front = row[:12], row[12:]
            for k, (im, h, col, kw) in enumerate(back):
                place(canvas, prep(im, int(h * 1.25)), 366 + k * 58, 268, col, **kw)
            for k, (im, h, col, kw) in enumerate(front):
                place(canvas, prep(im, int(h * 1.25)), 394 + k * 58, 326, col, **kw)
        # the last chip is the game-mode list, on two lines (it now also names the 100x conveyor belt)
        chips = [str(PLANT_COUNT) + ' NEW PLANTS', 'HYPNO ZOMBIES + ZOMBOTANY', 'ADVENTURE, SURVIVAL, MINIGAMES,\nVERSUS+, 100X CONVEYOR BELTS']
        cf = ImageFont.truetype(FONT, 16 if title else 19)
        LH = 18 if title else 21
        EX = 0     # no spray-painted '+' any more: the list says VERSUS+
        gap = 10
        wid = lambda c: max(d.textlength(l, font=cf) for l in c.split('\n'))
        total = sum(wid(c) + 24 for c in chips) + EX + gap * (len(chips) - 1)
        cx, cy = W / 2 - total / 2, (262 if title else 56)
        for ci, c in enumerate(chips):
            ex = EX if c == chips[-1] else 0
            w = wid(c) + 24 + ex
            lines = c.split('\n')
            h = 32 + (LH if title else 24) * (len(lines) - 1)
            if not title:
                # Nexus overlay version: the chips are a centred column at the top middle
                cx, cy = W / 2 - w / 2, 22 + ci * 42
            top = cy - (h - 32) / 2 if title else cy
            chip = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(chip).rounded_rectangle((cx, top, cx + w, top + h), radius=16, fill=(255, 255, 255, 235),
                                                     outline=(22, 80, 30, 255), width=3)
            canvas.alpha_composite(chip)
            d = ImageDraw.Draw(canvas)
            step = LH if title else 24
            for li, line in enumerate(lines):
                d.text((cx + (w - ex) / 2, top + h / 2 + (li - (len(lines) - 1) / 2) * step + 1), line, font=cf, fill=(22, 80, 30), anchor='mm')
            if title:
                cx += w + gap
        hypno_group(canvas, [('BucketHeadZombie', 74, -6, 44, 52), ('ConeheadZombie', 74, 4, 114, 46),
                             ('NewspaperZombie', 74, -4, 184, 52), ('Zombie', 74, 5, 254, 46),
                             ('FlagZombie', 92, -3, 336, 50),
                             ('DancingZombie', 58, 5, 868 - (0 if title else 30), 46), ('FootballZombie', 58, -5, 924 - (0 if title else 30), 50),
                             ('VP20', 66, 4, 980 - (0 if title else 30), 46), ('YetiZombie', 58, -4, 1036 - (0 if title else 30), 50),
                             ('Zomboni', 58, 5, 1092 - (0 if title else 30), 46), ('ZombieBobsledTeam', 58, -4, 1148 - (0 if title else 30), 50),
                             ('VP31', 66, 4, 1204 - (0 if title else 30), 46), ('VP34', 66, -4, 1260 - (0 if title else 30), 50),
                             ('Gargantuar', 58, -4, 896 - (0 if title else 30), 128), ('VP30', 58, 5, 952 - (0 if title else 30), 134)])
        # the three new plants ride an angled conveyor belt in the lower right (drawn last, on top)
        belt_group(canvas, 1172, 334, 290, 22, 9,
                   [(snappea, 56, (190, 255, 120), {}, 0.34), (elec, 66, (120, 220, 255), dict(glow=14, glow_alpha=0.85), 0.62),
                    (pvine, 30, (150, 255, 120), {}, 0.88)], place, prep,
                   extras=[(hypno_tile('ConeheadZombie', 46, -4), 0.1, 30)])
    else:
        # plants only, spread across the strip; Nexus overlays its own title
        items = [(fire, 250, (255, 150, 40), dict(glow=20, glow_alpha=0.75), False),
                 (celery, 200, (200, 255, 120), {}, False),
                 (chilly, 170, (140, 220, 255), dict(glow=16, glow_alpha=0.8), False),
                 (peapod, 140, (150, 255, 120), {}, False),
                 (mega, 112, (255, 215, 90), {}, False),
                 (peanut, 96, (255, 200, 110), {}, False),
                 (tumble, 88, (255, 220, 120), {}, False),
                 (psun, 108, (255, 230, 90), {}, False),
                 (gold, 100, (255, 215, 60), {}, False),
                 (dusk, 150, (205, 120, 255), dict(glow=18, glow_alpha=0.75), False),
                 (ice, 66, (150, 225, 255), dict(glow=16, glow_alpha=0.8), False),
                 (bombe, 96, (255, 90, 90), {}, False),
                 (stallia, 96, (205, 120, 255), dict(glow=14, glow_alpha=0.75), False),
                 (wallnut, 112, (200, 170, 120), {}, False),
                 (exnut, 140, (190, 190, 200), {}, False),
                 (endur, 170, (255, 215, 90), {}, True),
                 (bamboo, 262, (140, 255, 140), dict(glow=20, glow_alpha=0.7), True)]
        n = len(items)
        xs = [98 + i * (1100 / (n - 1)) for i in range(n)]
        xs[1] += 40; xs[2] += 26; xs[3] += 8; xs[11] += 26; xs[12] += 14
        order = sorted(range(n), key=lambda i: -items[i][1])  # tall ones first = at the back
        items = [items[i] for i in order]
        xs = [xs[i] for i in order]
        for (im, h, col, kw, fl), x in zip(items, xs):
            place(canvas, prep(im, h, flip=fl), x, 372, col, **kw)
    canvas.convert('RGB').save(out, quality=95)
    print('saved', out, canvas.size)


import os
D = os.path.join(os.environ.get('ART_OUT', '.'), '')
build(True, D + 'graphic-cc2-nexus-banner-1300x372-v' + VERSION + '.png')
build(True, D + 'graphic-cc2-nexus-banner-plants-only-1300x372-v' + VERSION + '.png', title=False)
