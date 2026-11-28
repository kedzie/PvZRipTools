import math, random, glob, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spray import spray_plus
from hypno import hypno_group
from logo_ribbon import ref_ribbon, BRIANNE
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

# Release being promoted (override with PROMO_VERSION / PROMO_PLANTS)
VERSION = os.environ.get('PROMO_VERSION', '1.28')
PLANT_COUNT = int(os.environ.get('PROMO_PLANTS', '32'))

W, H = 1280, 720
A = os.environ.get('PLANTRIP_A', '/mnt/d/PvZ/ReverseEngineering/AssetBundle-UnityProject/Assets/plantrip')   # local-only ripped plant frames
A2 = os.environ.get('PLANTRIP_A2', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'unity', 'Assets', 'plantrip'))
import os
OUT = os.path.join(os.environ.get('ART_OUT', '.'), 'graphic-cc2-thumbnail-v' + VERSION + '.png')
FONT = BRIANNE
random.seed(7)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------- background: sky -> lawn, light rays, vignette ----------
bg = Image.new('RGB', (W, H))
px = bg.load()
horizon = 300
for y in range(H):
    for x in range(W):
        if y < horizon:
            c = lerp((70, 170, 235), (170, 225, 250), y / horizon)
        else:
            t = (y - horizon) / (H - horizon)
            c = lerp((92, 178, 52), (38, 112, 38), t)
            # alternating lawn stripes, widening toward the viewer
            stripe = int((x - W / 2) / (60 + 140 * t) + 50)
            if stripe % 2 == 0:
                c = lerp(c, (255, 255, 255), 0.05)
        px[x, y] = c
bg = bg.convert('RGBA')

# soft hedge band on the horizon
hedge = Image.new('RGBA', (W, H), (0, 0, 0, 0))
hd = ImageDraw.Draw(hedge)
for i in range(130):
    cx = random.randint(-40, W + 40)
    r = random.randint(34, 70)
    cy = horizon - random.randint(-6, 26)
    shade = random.randint(0, 28)
    hd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(40 + shade, 140 + shade, 40 + shade, 255),
               outline=(16, 70, 22, 255), width=3)
bg = Image.alpha_composite(bg, hedge)

# sun rays from the top centre
rays = Image.new('RGBA', (W, H), (0, 0, 0, 0))
rd = ImageDraw.Draw(rays)
for k in range(-6, 7):
    a0 = math.radians(90 + k * 9 - 2.5)
    a1 = math.radians(90 + k * 9 + 2.5)
    rd.polygon([(W / 2, -80),
                (W / 2 + math.cos(a0) * 1500, -80 + math.sin(a0) * 1500),
                (W / 2 + math.cos(a1) * 1500, -80 + math.sin(a1) * 1500)], fill=(255, 255, 220, 38))
bg = Image.alpha_composite(bg, rays.filter(ImageFilter.GaussianBlur(10)))

# vignette
vig = Image.new('L', (W, H), 0)
vd = ImageDraw.Draw(vig)
vd.ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
vig = vig.filter(ImageFilter.GaussianBlur(150))
dark = Image.new('RGBA', (W, H), (6, 26, 10, 255))
bg = Image.composite(bg, Image.alpha_composite(bg, Image.new('RGBA', (W, H), (0, 0, 0, 0))), vig)
shade = Image.new('RGBA', (W, H), (4, 20, 8, 150))
shade.putalpha(ImageChops.invert(vig).point(lambda v: int(v * 0.62)))
bg = Image.alpha_composite(bg, shade)


# ---------- plant sprites ----------
def frame(plant, anim, idx=None):
    fr = sorted(glob.glob(f'{A}/{plant}/models/default/plant/{anim}/*.png')) or sorted(glob.glob(f'{A2}/{plant}/models/default/plant/{anim}/*.png'))
    im = Image.open(fr[len(fr) // 3 if idx is None else idx]).convert('RGBA')
    return im.crop(im.getchannel('A').getbbox())


def prep(im, height, flip=False):
    s = height / im.height
    im = im.resize((max(1, int(im.width * s)), height), Image.LANCZOS)
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


def outline_glow(im, color, width=7, glow=18, glow_alpha=0.55):
    pad = glow * 2 + width + 4
    base = Image.new('RGBA', (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    base.paste(im, (pad, pad), im)
    a = base.getchannel('A')
    ol = a.filter(ImageFilter.MaxFilter(width * 2 + 1))
    g = ol.filter(ImageFilter.GaussianBlur(glow))
    out = Image.new('RGBA', base.size, (0, 0, 0, 0))
    gl = Image.new('RGBA', base.size, color + (0,))
    gl.putalpha(g.point(lambda v: int(v * glow_alpha)))
    out = Image.alpha_composite(out, gl)
    dk = Image.new('RGBA', base.size, (14, 40, 18, 0))
    dk.putalpha(ol)
    out = Image.alpha_composite(out, dk)
    return Image.alpha_composite(out, base)


def place(canvas, im, x, ybottom, color, shadow=True, **kw):
    sp = outline_glow(im, color, **kw)
    x0 = int(x - sp.width / 2)
    y0 = int(ybottom - sp.height + 10)
    if shadow:
        sh = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        w = im.width * 0.95
        sd.ellipse((x - w / 2, ybottom - 14, x + w / 2, ybottom + 22), fill=(0, 20, 0, 140))
        canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    canvas.alpha_composite(sp, (x0, y0))


canvas = bg.copy()

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
coldsn = frame('cold_snapdragon', 'idle')
stunion = frame('stunion', 'idle')
pvine = frame('pvine', 'idle')
elec = frame('electric_peashooter', 'idle')
snappea = frame('snappea', 'idle')


# ---------- text ----------
d = ImageDraw.Draw(canvas)


def fit(text, size):
    return ImageFont.truetype(FONT, size)


def stroked(draw, xy, text, font, fill, stroke, sw, anchor='mm', shadow=(0, 0)):
    x, y = xy
    if shadow != (0, 0):
        draw.text((x + shadow[0], y + shadow[1]), text, font=font, fill=(0, 20, 0, 200), anchor=anchor,
                  stroke_width=sw, stroke_fill=(0, 20, 0, 200))
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor, stroke_width=sw, stroke_fill=stroke)


# title block
f1 = fit('', 148)
stroked(d, (W / 2, 112), 'COMPLETE', f1, (255, 255, 255), (22, 80, 30), 9, shadow=(0, 9))
f2 = fit('', 168)
stroked(d, (W / 2, 248), 'COLLECTION 2', f2, (255, 232, 70), (110, 50, 6), 10, shadow=(0, 10))

# PvZ 2 -> Replanted ribbon
ref_ribbon(canvas, W / 2, 330, 132, 82, pad=40, gap=34)
d = ImageDraw.Draw(canvas)

def belt(canvas, x0, x1, y0, y1):
    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    r = (y1 - y0) // 2
    ld.rounded_rectangle((x0, y0 + 6, x1, y1 + 6), radius=r, fill=(0, 20, 0, 150))
    ld.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=(52, 55, 62, 255), outline=(18, 20, 24, 255), width=4)
    for x in range(int(x0 + 22), int(x1 - 16), 22):
        ld.line((x, y0 + 6, x - 10, y1 - 6), fill=(92, 96, 106, 255), width=4)
    ld.line((x0 + 22, y0 + 4, x1 - 22, y0 + 4), fill=(150, 154, 164, 255), width=3)
    for x in range(int(x0 + 80), int(x1 - 60), 150):   # speed chevrons
        for dx in (0, 16):
            ld.polygon([(x + dx, y0 + 8), (x + dx + 13, (y0 + y1) / 2), (x + dx, y1 - 8), (x + dx + 6, y1 - 8), (x + dx + 19, (y0 + y1) / 2), (x + dx + 6, y0 + 8)], fill=(255, 170, 40, 255))
    for cx in (x0 + r, x1 - r):                                      # end rollers
        ld.ellipse((cx - r + 3, y0 + 3, cx + r - 3, y1 - 3), fill=(88, 92, 100, 255), outline=(18, 20, 24, 255), width=4)
        ld.ellipse((cx - 6, (y0 + y1) / 2 - 6, cx + 6, (y0 + y1) / 2 + 6), fill=(30, 32, 36, 255))
    canvas.alpha_composite(layer)


belt(canvas, 300, 1010, 664, 712)

# plants: in front of the title ribbon, behind the chips. Crowded on purpose - back row first so
# heads peek out from behind the front row.
place(canvas, prep(wallnut, 150), 905, 672, (200, 170, 120))
place(canvas, prep(dusk, 150), 600, 668, (205, 120, 255), glow=22, glow_alpha=0.75)
place(canvas, prep(psun, 125), 705, 668, (255, 230, 90))
place(canvas, prep(gold, 112), 500, 668, (255, 215, 60))
place(canvas, prep(endur, 200, flip=True), 1030, 696, (255, 215, 90))
place(canvas, prep(peapod, 190), 392, 700, (150, 255, 120))
place(canvas, prep(celery, 215), 262, 694, (200, 255, 120))
place(canvas, prep(bamboo, 345, flip=True), 1165, 704, (140, 255, 140), glow=24, glow_alpha=0.7)
place(canvas, prep(fire, 335), 105, 702, (255, 150, 40), glow=24, glow_alpha=0.75)
place(canvas, prep(ice, 80), 805, 706, (150, 225, 255), glow=20, glow_alpha=0.8)
place(canvas, prep(tumble, 105), 548, 708, (255, 220, 120))
place(canvas, prep(chilly, 150), 748, 700, (140, 220, 255), glow=20, glow_alpha=0.8)
place(canvas, prep(exnut, 120), 868, 704, (190, 190, 200))
place(canvas, prep(mega, 100), 452, 708, (255, 215, 90))
place(canvas, prep(bombe, 92), 582, 712, (255, 90, 90))
place(canvas, prep(stallia, 96), 700, 712, (205, 120, 255), glow=16, glow_alpha=0.75)
place(canvas, prep(snap, 150), 650, 706, (255, 190, 90))
place(canvas, prep(aloe, 120), 515, 712, (170, 255, 190))
place(canvas, prep(sbean, 112), 765, 714, (170, 255, 90))
place(canvas, prep(peapr, 118), 835, 714, (170, 255, 120))
place(canvas, prep(pmine, 66), 625, 716, (255, 170, 90))
place(canvas, prep(peanut, 112), 660, 708, (255, 200, 110))
place(canvas, prep(chard, 150), 478, 706, (200, 255, 140))
place(canvas, prep(sour, 124), 630, 722, (255, 240, 90))
place(canvas, prep(pepper, 132), 706, 724, (255, 120, 80), glow=18, glow_alpha=0.8)
place(canvas, prep(nshade, 128), 548, 718, (205, 120, 255), glow=18, glow_alpha=0.75)
place(canvas, prep(sweetp, 120), 812, 716, (255, 170, 90))
place(canvas, prep(coldsn, 136), 738, 716, (150, 225, 255), glow=18, glow_alpha=0.8)
place(canvas, prep(stunion, 88), 602, 722, (190, 255, 120))
place(canvas, prep(elec, 140), 432, 714, (120, 220, 255), glow=20, glow_alpha=0.85)
place(canvas, prep(snappea, 124), 855, 722, (190, 255, 120))
place(canvas, prep(pvine, 62), 684, 728, (150, 255, 120))

# chips
chips = [str(PLANT_COUNT) + ' NEW PLANTS', 'HYPNO ZOMBIES + ZOMBOTANY', 'ADVENTURE, SURVIVAL, MINIGAMES, VERSUS']
cf = fit('', 23)
EX = 78
total = sum(d.textlength(c, font=cf) + 44 for c in chips) + EX + 18 * (len(chips) - 1)
cx = W / 2 - total / 2
cy = 476
for c in chips:
    ex = EX if c == chips[-1] else 0
    w = d.textlength(c, font=cf) + 44 + ex
    chip = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(chip)
    cd.rounded_rectangle((cx, cy, cx + w, cy + 46), radius=23, fill=(255, 255, 255, 235), outline=(22, 80, 30, 255), width=3)
    canvas.alpha_composite(chip)
    d = ImageDraw.Draw(canvas)
    d.text((cx + (w - ex) / 2, cy + 24), c, font=cf, fill=(22, 80, 30), anchor='mm')
    if ex:
        PLUS = (cx + w - 34, cy + 8, 86)
    cx += w + 18


# the conveyor chip: second line, orange, bigger
hot = 'CONVEYOR BELTS UP TO 100X FASTER'
hf = fit('', 30)
hw = d.textlength(hot, font=hf) + 56
hx, hy = W / 2 - hw / 2, cy + 58
chip = Image.new('RGBA', (W, H), (0, 0, 0, 0))
ImageDraw.Draw(chip).rounded_rectangle((hx, hy, hx + hw, hy + 56), radius=28, fill=(255, 205, 60, 245), outline=(120, 55, 6, 255), width=4)
canvas.alpha_composite(chip)
d = ImageDraw.Draw(canvas)
d.text((W / 2, hy + 30), hot, font=hf, fill=(110, 45, 4), anchor='mm')

spray_plus(canvas, *PLUS)
hypno_group(canvas, [('ConeheadZombie', 100, -5, 52, 78), ('Zombie', 100, 4, 142, 72),
                     ('FlagZombie', 116, -3, 232, 78),
                     ('VP31', 84, 4, 92, 190), ('VP34', 84, -4, 188, 196),
                     ('DancingZombie', 70, 5, 1060, 62), ('FootballZombie', 70, -5, 1132, 68),
                     ('VP20', 84, 4, 1204, 70),
                     ('YetiZombie', 70, -4, 1098, 132), ('Zomboni', 70, 5, 1170, 138),
                     ('ZombieBobsledTeam', 70, -4, 1242, 132),
                     ('Gargantuar', 60, 4, 1200, 200), ('VP30', 60, -5, 1258, 206)])

canvas.convert('RGB').save(OUT, quality=95)
print('saved', OUT, canvas.size)
