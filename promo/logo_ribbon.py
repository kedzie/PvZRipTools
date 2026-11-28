import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PV = os.environ.get('PVZ2_UNPACKED', '/mnt/d/PvZ/ReverseEngineering/PvZ2-OBB-Rip/pvz2_original_unpacked/')
BRIANNE = PV + 'PRIMEFONTS/BRIANNETOD.TTF'
BLOCKY = PV + 'PRIMEFONTS/HOUSE OF TERROR.TTF'
LOGO = PV + 'ATLASES/UI_MAINMENULOGO_1536_00.PNG'


TWO = os.path.join(os.environ.get('PROMO_ASSETS', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')), 'two_clean.png')


def _short_logo():
    """'PvZ' in the blocky PvZ lettering (small-cap v) + the real orange 2 cut from the PvZ 2 logo."""
    two = Image.open(TWO).convert('RGBA')
    size = 150
    sw = 9
    big = ImageFont.truetype(BLOCKY, size)
    small = ImageFont.truetype(BLOCKY, int(size * 0.70))
    tmp = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
    wp, wv, wz = (tmp.textlength('P', font=big), tmp.textlength('V', font=small), tmp.textlength('Z', font=big))
    gap = -2
    tw = int(wp + wv + wz + gap * 2)
    W = tw + two.width + sw * 2 + 10
    H = max(two.height + 12, size + sw * 3)
    base = H * 0.80
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = sw + 2
    for ch, f, w in (('P', big, wp), ('V', small, wv), ('Z', big, wz)):
        d.text((x, base), ch, font=f, fill=(120, 220, 50), anchor='ls', stroke_width=sw, stroke_fill=(16, 64, 18))
        x += w + gap
    im.alpha_composite(two, (tw - 4 + sw, int((H - two.height) / 2)))
    return im.crop(im.getchannel('A').getbbox())


def _logo(short=True):
    if short:
        return _short_logo()
    im = Image.open(LOGO).convert('RGBA')
    # trim the transparent margin and the tiny trademark mark under the 2
    bb = im.getchannel('A').getbbox()
    im = im.crop(bb)
    return im


def ref_ribbon(canvas, cx, y, h, text_size, pad=34, gap=26, arrow_w=None, short=True):
    """Dark pill: [PvZ 2 logo] -> [REPLANTED lettering], centred on cx with top edge y and height h."""
    logo = _logo(short)
    lh = int(h * (0.78 if short else 0.68))
    lw = int(logo.width * lh / logo.height)
    logo = logo.resize((lw, lh), Image.LANCZOS)

    font = ImageFont.truetype(BRIANNE, text_size)
    word = 'REPLANTED'
    tmp = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
    tw = tmp.textlength(word, font=font)
    aw = arrow_w or int(h * 0.62)
    total = pad + lw + gap + aw + gap + tw + pad
    x0 = cx - total / 2

    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    r = int(h * 0.24)
    ld.rounded_rectangle((x0 + 4, y + 6, x0 + total + 4, y + h + 6), radius=r, fill=(0, 0, 0, 120))
    ld.rounded_rectangle((x0, y, x0 + total, y + h), radius=r, fill=(34, 24, 62, 245), outline=(255, 232, 70, 255), width=4)
    canvas.alpha_composite(layer)

    # logo (with a soft white lift so the grey lettering reads on the dark pill)
    lx = int(x0 + pad)
    ly = int(y + (h - lh) / 2)
    glow = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    gl = Image.new('RGBA', logo.size, (255, 255, 255, 0))
    gl.putalpha(logo.getchannel('A').point(lambda v: int(v * 0.9)))
    glow.paste(gl, (lx, ly))
    glow = glow.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(2))
    canvas.alpha_composite(glow)
    canvas.alpha_composite(logo, (lx, ly))

    # arrow
    ax = lx + lw + gap
    ay = y + h / 2
    ah = h * 0.30
    d = ImageDraw.Draw(canvas)
    body = aw * 0.55
    d.polygon([(ax, ay - ah * 0.30), (ax + body, ay - ah * 0.30), (ax + body, ay - ah * 0.62),
               (ax + aw, ay), (ax + body, ay + ah * 0.62), (ax + body, ay + ah * 0.30), (ax, ay + ah * 0.30)],
              fill=(255, 232, 70), outline=(110, 50, 6))

    # REPLANTED lettering: bright green face, dark-green outline, soft drop shadow
    tx = ax + aw + gap
    ty = y + h / 2
    d.text((tx + 3, ty + 4), word, font=font, fill=(0, 20, 0, 200), anchor='lm', stroke_width=max(3, text_size // 12), stroke_fill=(0, 20, 0, 200))
    d.text((tx, ty), word, font=font, fill=(150, 235, 60), anchor='lm', stroke_width=max(3, text_size // 12), stroke_fill=(24, 84, 22))
    return total
