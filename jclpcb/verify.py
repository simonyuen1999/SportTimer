#!/usr/bin/env python3
"""Verify the 2-layer WS2812B 7-seg board."""
from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from gerbonara import ExcellonFile, GerberFile
from gerbonara.apertures import CircleAperture, RectangleAperture

import make_board as mb

HERE = os.path.dirname(os.path.abspath(__file__))
GERB = os.path.join(HERE, "out", "gerbers")
S = 20

FILES = {
    "F_Cu": "WS2812B-7SEG-2L-F_Cu.gtl",
    "B_Cu": "WS2812B-7SEG-2L-B_Cu.gbl",
    "F_Mask": "WS2812B-7SEG-2L-F_Mask.gts",
    "B_Mask": "WS2812B-7SEG-2L-B_Mask.gbs",
    "F_Paste": "WS2812B-7SEG-2L-F_Paste.gtp",
    "F_Silk": "WS2812B-7SEG-2L-F_Silkscreen.gto",
    "B_Silk": "WS2812B-7SEG-2L-B_Silkscreen.gbo",
    "Edge": "WS2812B-7SEG-2L-Edge_Cuts.gm1",
}


def mm(x, y):
    return (x * S, (mb.H - y) * S)


def canvas():
    return Image.new("L", (int(mb.W * S), int(mb.H * S)), 0)


def draw_pads(d, pads, grow=0.0, fill=255, skip=None):
    for p in pads:
        if skip and p.net in skip:
            continue
        x, y = mm(p.x, p.y)
        if p.shape == "round":
            r = (p.w + grow) / 2 * S
            d.ellipse([x - r, y - r, x + r, y + r], fill=fill)
        else:
            w, h = (p.w + grow) * S, (p.h + grow) * S
            d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=fill)


def draw_traces(d, traces, grow=0.0, fill=255):
    for pts, w in traces:
        width = max(1, int(round((w + grow) * S)))
        d.line([mm(x, y) for x, y in pts], fill=fill, width=width)
        r = width / 2.0
        for x, y in pts:
            px, py = mm(x, y)
            d.ellipse([px - r, py - r, px + r, py + r], fill=fill)


def draw_islands(d, grow=0.0, fill=255):
    for g in mb.GND_ISLANDS:
        x, y = mm(g["px"], g["py"])
        w, h = (g["pw"] + grow) * S, (g["ph"] + grow) * S
        d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=fill)
        d.line([mm(g["px"], g["py"]), mm(g["vx"], g["vy"])], fill=fill,
               width=max(1, int(round((0.5 + grow) * S))))
        vx, vy = mm(g["vx"], g["vy"])
        r = (0.6 + grow) / 2 * S
        d.ellipse([vx - r, vy - r, vx + r, vy + r], fill=fill)


def rounded_pts():
    return [(x + 0.5, y + 0.5) for x, y in
            mb.rounded_rect(mb.W - 1.0, mb.H - 1.0, mb.R_CORNER - 0.5)]


def raster_5v():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.polygon([mm(x, y) for x, y in rounded_pts()], fill=255)
    draw_pads(d, [p for p in mb.PADS if p.net == "DATA"], grow=0.8, fill=0)
    draw_traces(d, mb.DATA_TRACES, grow=0.8, fill=0)
    draw_islands(d, grow=0.8, fill=0)
    for p in mb.PADS:
        if p.drill is not None and p.net in ("GND", "DATA"):
            x, y = mm(p.x, p.y)
            r = (p.w + 1.0) / 2 * S
            d.ellipse([x - r, y - r, x + r, y + r], fill=0)
    for hx, hy, hd in mb.NPTH:
        x, y = mm(hx, hy)
        r = (hd + 1.0) / 2 * S
        d.ellipse([x - r, y - r, x + r, y + r], fill=0)
    return img


def raster_data():
    img = canvas()
    d = ImageDraw.Draw(img)
    draw_traces(d, mb.DATA_TRACES)
    draw_pads(d, [p for p in mb.PADS if p.net == "DATA"])
    return img


def raster_islands():
    img = canvas()
    d = ImageDraw.Draw(img)
    draw_islands(d)
    return img


def raster_plane():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.polygon([mm(x, y) for x, y in rounded_pts()], fill=255)
    for p in mb.PADS:
        if p.drill is not None and p.net in ("5V", "DATA"):
            x, y = mm(p.x, p.y)
            r = (p.w + 1.0) / 2 * S
            d.ellipse([x - r, y - r, x + r, y + r], fill=0)
    cp = mb.CAP_PADS[0]                  # C10 +5V pad on the back, isolated
    x, y = mm(cp.x, cp.y)
    w, h = (cp.w + 0.8) * S, (cp.h + 0.8) * S
    d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=0)
    cg = mb.CAP_PADS[1]                  # C10 GND pad, thermal relief
    x, y = mm(cg.x, cg.y)
    w, h = (cg.w + 0.6) * S, (cg.h + 0.6) * S
    d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=0)
    for b in mb.BACK_PADS:
        x, y = mm(b["x"], b["y"])
        gr = 0.8 if b["net"] in ("5V", "DATA") else 0.6
        w, h = (b["w"] + gr) * S, (b["h"] + gr) * S
        d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=0)
    for hx, hy, hd in mb.NPTH:
        x, y = mm(hx, hy)
        r = (hd + 1.0) / 2 * S
        d.ellipse([x - r, y - r, x + r, y + r], fill=0)
    # C10 GND thermal spokes + pad
    cg = mb.CAP_PADS[1]
    sp = 0.55
    for (x1, y1, x2, y2) in (
            (cg.x - cg.w / 2 - sp, cg.y, cg.x - cg.w / 2, cg.y),
            (cg.x + cg.w / 2, cg.y, cg.x + cg.w / 2 + sp, cg.y),
            (cg.x, cg.y - cg.h / 2 - sp, cg.x, cg.y - cg.h / 2),
            (cg.x, cg.y + cg.h / 2, cg.x, cg.y + cg.h / 2 + sp)):
        d.line([mm(x1, y1), mm(x2, y2)], fill=255, width=max(1, int(0.6 * S)))
    x, y = mm(cg.x, cg.y)
    w, h = cg.w * S, cg.h * S
    d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=255)
    for b in mb.BACK_PADS:
        if b["net"] != "GND":
            continue
        sp = 0.55
        d.line([mm(b["x"], b["y"] - b["h"] / 2 - sp), mm(b["x"], b["y"] - b["h"] / 2)],
               fill=255, width=max(1, int(0.6 * S)))
        d.line([mm(b["x"], b["y"] + b["h"] / 2), mm(b["x"], b["y"] + b["h"] / 2 + sp)],
               fill=255, width=max(1, int(0.6 * S)))
        x, y = mm(b["x"], b["y"])
        w, h = b["w"] * S, b["h"] * S
        d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=255)
    return img


def label(mask):
    return ndimage.label(np.array(mask) > 127, structure=np.ones((3, 3)))


def main():
    parsed = {}
    for k, fn in FILES.items():
        f = GerberFile.open(os.path.join(GERB, fn))
        parsed[k] = f
        print(f"  {fn:42s} {len(f.objects):5d} obj  bbox={f.bounding_box()}")

    pth = ExcellonFile.open(os.path.join(GERB, "WS2812B-7SEG-2L-PTH.drl"))
    npth = ExcellonFile.open(os.path.join(GERB, "WS2812B-7SEG-2L-NPTH.drl"))
    print(f"  PTH {len(pth.objects)} holes   NPTH {len(npth.objects)} holes")

    pads5 = [p for p in mb.PADS if p.net == "5V"]
    padsd = [p for p in mb.PADS if p.net == "DATA"]

    # ---- 5 V pour ----
    m5 = raster_5v()
    lab, n = label(m5)
    sizes = ndimage.sum(np.array(m5) > 127, lab, range(1, n + 1))
    main_id = int(np.argmax(sizes)) + 1
    bad = []
    for p in pads5:
        x, y = mm(p.x, p.y)
        if lab[int(y), int(x)] != main_id:
            bad.append((p.ref, p.pin))
    print(f"  5V    components={n}  main={int(sizes[main_id-1])}px  "
          f"pads={len(pads5)-len(bad)}/{len(pads5)}  bad={bad}")
    assert not bad, bad

    # ---- data links ----
    md = raster_data()
    lab, n = label(md)
    used = {}
    broken = []
    for i, (pts, w) in enumerate(mb.DATA_TRACES):
        x0, y0 = mm(*pts[0])
        x1, y1 = mm(*pts[-1])
        a = int(lab[int(y0), int(x0)])
        b = int(lab[int(y1), int(x1)])
        if not a or a != b:
            broken.append((i, a, b))
        used.setdefault(a, []).append(i)
    shared = {k: v for k, v in used.items() if len(v) > 1}
    print(f"  DATA  components={n}  links={len(mb.DATA_TRACES)}  "
          f"broken={broken}  shared={shared}")
    assert not broken and not shared

    # ---- top GND islands ----
    mi = raster_islands()
    lab, n = label(mi)
    ok = 0
    for g in mb.GND_ISLANDS:
        px, py = mm(g["px"], g["py"])
        vx, vy = mm(g["vx"], g["vy"])
        if lab[int(py), int(px)] and lab[int(py), int(px)] == lab[int(vy), int(vx)]:
            ok += 1
    print(f"  GND islands: {n} components, {ok}/{len(mb.GND_ISLANDS)} pad-via connected")
    assert ok == len(mb.GND_ISLANDS) and n == len(mb.GND_ISLANDS)

    # ---- bottom GND plane ----
    mpg = raster_plane()
    lab, n = label(mpg)
    sizes = ndimage.sum(np.array(mpg) > 127, lab, range(1, n + 1))
    main_id = int(np.argmax(sizes)) + 1
    targets = [(g["vx"], g["vy"]) for g in mb.GND_ISLANDS]
    for p in mb.PADS:
        if p.drill is not None and p.net == "GND":
            targets.append((p.x, p.y))
    targets.append((mb.CAP_PADS[1].x, mb.CAP_PADS[1].y))   # C10 GND pad on the back
    targets += [(b["x"], b["y"]) for b in mb.BACK_PADS if b["net"] == "GND"]
    bad = [t for t in targets
           if lab[int(mm(*t)[1]), int(mm(*t)[0])] != main_id]
    print(f"  GND   plane components={n}  main={int(sizes[main_id-1])}px  "
          f"targets={len(targets)-len(bad)}/{len(targets)}")
    assert n == 1 and not bad

    # ---- clearance ----
    st = np.ones((5, 5), dtype=bool)
    print("  clearance (0.20 mm):", end=" ")
    for a, b, name in ((raster_5v(), raster_data(), "5V/DATA"),
                       (raster_5v(), raster_islands(), "5V/GND-islands"),
                       (raster_data(), raster_islands(), "DATA/GND-islands")):
        da = ndimage.binary_dilation(np.array(a) > 127, structure=st)
        db = ndimage.binary_dilation(np.array(b) > 127, structure=st)
        ov = da & db
        assert not ov.any(), f"{name} short: {int(ov.sum())} px"
    print("OK")

    # ---- drills ----
    exp = {(round(p.x, 3), round(p.y, 3)) for p in mb.PADS if p.drill}
    exp |= {(round(g["vx"], 3), round(g["vy"], 3)) for g in mb.GND_ISLANDS}
    exp |= {(round(vx, 3), round(vy, 3)) for vx, vy, pad, dr in mb.CAP_VIAS}
    exp |= {(round(vx, 3), round(vy, 3)) for vx, vy, pad, dr in mb.BACK_VIAS}
    got = {(round(o.x, 3), round(o.y, 3)) for o in pth.objects}
    assert exp == got, (exp - got, got - exp)
    exp = {(round(x, 3), round(y, 3)) for x, y, _ in mb.NPTH}
    got = {(round(o.x, 3), round(o.y, 3)) for o in npth.objects}
    assert exp == got
    print(f"  drills: {len(pth.objects)} PTH, {len(npth.objects)} NPTH  OK")

    # ---- silkscreen vs pads ----
    for o in parsed["F_Silk"].objects:
        bb = o.bounding_box() if callable(getattr(o, "bounding_box", None)) else o.bounding_box
        if not bb:
            continue
        (sx0, sy0), (sx1, sy1) = bb
        for p in mb.PADS:
            px0, py0 = p.x - p.w / 2 - 0.06, p.y - p.h / 2 - 0.06
            px1, py1 = p.x + p.w / 2 + 0.06, p.y + p.h / 2 + 0.06
            if sx0 < px1 and sx1 > px0 and sy0 < py1 and sy1 > py0:
                raise AssertionError(f"silk {type(o).__name__} {bb} on pad {p.ref}.{p.pin}")
    print("  silkscreen clear of pads: OK")

    # ---- C10 on the back: 5 V pad must reach the top pour through its two vias ----
    cap5 = canvas()
    d = ImageDraw.Draw(cap5)
    for p in mb.CAP_PADS:
        if p.net != "5V":
            continue
        x, y = mm(p.x, p.y)
        w, h = p.w * S, p.h * S
        d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=255)
    for vx, vy, pad, dr in mb.CAP_VIAS:
        x, y = mm(vx, vy)
        r = pad / 2 * S
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    labc, nc = label(cap5)
    vias_ok = all(labc[int(mm(vx, vy)[1]), int(mm(vx, vy)[0])] == 1
                  for vx, vy, pad, dr in mb.CAP_VIAS)
    assert nc == 1 and vias_ok
    lab5, _ = label(raster_5v())
    assert all(lab5[int(mm(vx, vy)[1]), int(mm(vx, vy)[0])] != 0
               for vx, vy, pad, dr in mb.CAP_VIAS), "C10 vias not in top 5V pour"
    print(f"  C10: {nc} back-side 5V island, {len(mb.CAP_VIAS)} vias to top pour  OK")

    da = ndimage.binary_dilation(np.array(cap5) > 127, structure=st)
    db = ndimage.binary_dilation(np.array(mpg) > 127, structure=st)
    assert not (da & db).any(), "C10 5V pad shorts to GND plane"
    print("  C10 5V pad clear of GND plane: OK")

    # J1/J2 back solder pads: 5V / DATA reach the top through their vias
    lab5, _ = label(raster_5v())
    labd, _ = label(raster_data())
    labp, _ = label(raster_plane())
    for b in mb.BACK_PADS:
        if b["net"] == "GND":
            continue
        bm = canvas()
        db = ImageDraw.Draw(bm)
        x, y = mm(b["x"], b["y"])
        w, h = b["w"] * S, b["h"] * S
        db.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=255)
        vx, vy = b["x"], b["y"]
        db.ellipse([x - 6, y - 6, x + 6, y + 6], fill=255)
        lbl, nn = label(bm)
        assert nn == 1, f"{b['ref']}.{b['pin']} pad+via split"
        top = lab5 if b["net"] == "5V" else labd
        assert top[int(y), int(x)] != 0, f"{b['ref']}.{b['pin']} via not on top net"
        da = ndimage.binary_dilation(np.array(bm) > 127, structure=st)
        dpg = ndimage.binary_dilation(np.array(raster_plane()) > 127, structure=st)
        assert not (da & dpg).any(), f"{b['ref']}.{b['pin']} back pad shorts to plane"
    print(f"  J1/J2 back pads: {len(mb.BACK_PADS)} pads, "
          f"{len(mb.BACK_VIAS)} vias to top  OK")

    # ---- Gerber-based previews (what the file actually contains) ----
    from gerbonara.apertures import ObroundAperture

    def draw_obj(d, o, col):
        n = type(o).__name__
        if n == "Region":
            d.polygon([mm(x, y) for x, y in o.outline], fill=col)
        elif n == "Flash":
            ap = o.aperture
            x, y = mm(o.x, o.y)
            if isinstance(ap, CircleAperture):
                r = ap.diameter / 2 * S
                d.ellipse([x - r, y - r, x + r, y + r], fill=col)
            elif isinstance(ap, RectangleAperture):
                w, h = ap.w * S, ap.h * S
                d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=col)
            elif isinstance(ap, ObroundAperture):
                w, h = ap.w * S, ap.h * S
                d.rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2],
                                    radius=min(w, h) / 2, fill=col)
        elif n == "Line":
            d.line([mm(o.x1, o.y1), mm(o.x2, o.y2)], fill=col,
                   width=max(1, int(round(getattr(o.aperture, "diameter", 0.1) * S))))

    def render(cu_key, mask_key, silk_key, path, top):
        out_px = 2 * S
        img = Image.new("RGB", (int(mb.W * S), int(mb.H * S)), (8, 20, 14))
        d = ImageDraw.Draw(img)
        bg = (13, 47, 32)
        d.polygon([mm(x, y) for x, y in mb.rounded_rect(mb.W, mb.H, mb.R_CORNER)], fill=bg)
        copper = (28, 92, 58)
        trace = (40, 150, 90) if top else copper
        for o in parsed[cu_key].objects:
            col = copper if o.polarity_dark else bg
            if top and type(o).__name__ == "Line" and o.polarity_dark:
                col = trace
            draw_obj(d, o, col)
        for o in parsed[mask_key].objects:
            if o.polarity_dark:
                draw_obj(d, o, (201, 162, 66))
        for o in parsed[silk_key].objects:
            if o.polarity_dark:
                draw_obj(d, o, (240, 240, 232))
        for f in (pth, npth):
            for o in f.objects:
                x, y = mm(o.x, o.y)
                r = max(2.0, o.tool.diameter / 2 * S)
                d.ellipse([x - r, y - r, x + r, y + r], fill=(10, 10, 12))
        for o in parsed["Edge"].objects:
            d.line([mm(o.x1, o.y1), mm(o.x2, o.y2)], fill=(205, 205, 195), width=2)
        img = img.resize((int(mb.W * out_px), int(mb.H * out_px)), Image.LANCZOS)
        img.save(path)
        return img

    top_img = render("F_Cu", "F_Mask", "F_Silk",
                     os.path.join(HERE, "out", "preview_top.png"), True)
    bot_img = render("B_Cu", "B_Mask", "B_Silk",
                     os.path.join(HERE, "out", "preview_bottom.png"), False)

    # ---- the C10 pads must exist in the Gerber AND in the rendered bottom image ----
    c10 = [(mb.CAP_PADS[0].x, mb.CAP_PADS[0].y), (mb.CAP_PADS[1].x, mb.CAP_PADS[1].y)]
    bflash = [(o.x, o.y, o.aperture) for o in parsed["B_Cu"].objects
              if type(o).__name__ == "Flash" and o.polarity_dark]
    for x, y in c10:
        hit = [a for fx, fy, a in bflash
               if abs(fx - x) < 0.01 and abs(fy - y) < 0.01
               and isinstance(a, RectangleAperture)
               and abs(a.w - 5.0) < 0.01 and abs(a.h - 3.0) < 0.01]
        assert hit, f"C10 pad missing in B_Cu at ({x},{y})"
    mflash = [(o.x, o.y, o.aperture) for o in parsed["B_Mask"].objects
              if type(o).__name__ == "Flash" and o.polarity_dark]
    for x, y in c10:
        hit = [a for fx, fy, a in mflash
               if abs(fx - x) < 0.01 and abs(fy - y) < 0.01
               and isinstance(a, RectangleAperture)
               and abs(a.w - 5.1) < 0.01 and abs(a.h - 3.1) < 0.01]
        assert hit, f"C10 mask opening missing in B_Mask at ({x},{y})"
    for x, y in c10:
        px, py = int(x * 2 * S), int((mb.H - y) * 2 * S)
        r, g, b = bot_img.getpixel((px, py))
        assert r > 150 and g > 100 and b < 120, \
            f"C10 pad not gold in preview at ({x},{y}): {(r, g, b)}"
    # every pad must have a mask opening in the Gerber
    def has_flash(mask, x, y):
        return any(abs(o.x - x) < 0.01 and abs(o.y - y) < 0.01
                   for o in mask.objects if type(o).__name__ == "Flash")

    for pp in mb.PADS:
        assert has_flash(parsed["F_Mask"], pp.x, pp.y), \
            f"F_Mask opening missing for {pp.ref}.{pp.pin}"
        if pp.drill is not None:
            assert has_flash(parsed["B_Mask"], pp.x, pp.y), \
                f"B_Mask opening missing for {pp.ref}.{pp.pin}"
    for b in mb.BACK_PADS:
        assert has_flash(parsed["B_Mask"], b["x"], b["y"]), \
            f"B_Mask wire-pad opening missing for {b['ref']}.{b['pin']}"
    n_bot = sum(1 for p in mb.PADS if p.drill) + len(mb.BACK_PADS) + len(mb.CAP_PADS)
    print(f"  mask openings: {len(mb.PADS)} top, {n_bot} bottom  OK")
    print(f"  C10 pads in B_Cu + B_Mask and visible in preview ({len(c10)}): OK")

    # ---- annotated 2x detail panel (C10 + J1) ----
    from PIL import ImageFont
    try:
        f_big = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 40)
        f_sm = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 30)
    except Exception:
        f_big = ImageFont.load_default(size=40)
        f_sm = ImageFont.load_default(size=30)

    red, cyn, yel, wht = (255, 75, 75), (80, 220, 255), (255, 220, 60), (255, 255, 255)
    x0, x1, y0, y1 = 55.0, 92.0, 0.0, 17.0
    sc = 4 * S
    crop = bot_img.crop((int(x0 * 2 * S), int((mb.H - y1) * 2 * S),
                         int(x1 * 2 * S), int((mb.H - y0) * 2 * S)))
    crop = crop.resize((int((x1 - x0) * sc), int((y1 - y0) * sc)), Image.LANCZOS)
    dc = ImageDraw.Draw(crop)

    def PP(x, y):
        return ((x - x0) * sc, (y1 - y) * sc)

    def box(xa, ya, xb, yb, col):
        dc.rectangle([PP(xa, yb), PP(xb, ya)], outline=col, width=5)

    box(61.5, 3.3, 67.1, 6.7, red)
    box(68.9, 3.3, 74.5, 6.7, cyn)
    box(77.0, 7.0, 84.0, 9.0, yel)
    box(77.0, 3.6, 84.0, 5.4, wht)

    dc.text((520, 1175), "C10 +5V pad", font=f_big, fill=red)
    dc.text((520, 1222), "solder + here", font=f_sm, fill=red)
    dc.text((1112, 1175), "C10 GND pad", font=f_big, fill=cyn)
    dc.text((1760, 850), "J1 wire pads", font=f_sm, fill=yel)
    dc.text((1760, 1240), "J1 through-holes", font=f_sm, fill=wht)

    bar = 72
    zoom = Image.new("RGB", (crop.width, crop.height + bar), (8, 20, 14))
    zoom.paste(crop, (0, bar))
    dz = ImageDraw.Draw(zoom)
    dz.text((20, 18), "DETAIL A  —  C10 + J1  (2x, Gerber render)", font=f_sm, fill=wht)
    zoom.save(os.path.join(HERE, "out", "c10_zoom.png"))

    # ---- overlay the detail panel on the empty GND-plane area ----
    sheet = bot_img.copy()
    px0, px1 = int(x0 * 2 * S), int(x1 * 2 * S)
    py0, py1 = int((mb.H - y1) * 2 * S), int((mb.H - y0) * 2 * S)
    dd = ImageDraw.Draw(sheet)
    dd.rectangle([px0, py0, px1, py1], outline=wht, width=4)
    dd.text((px0 + 10, py0 + 10), "DETAIL A", font=f_big, fill=wht)
    panel_x, panel_y = 520, 3300
    sheet.paste(zoom, (panel_x, panel_y))
    dd.rectangle([panel_x - 2, panel_y - 2, panel_x + zoom.width + 2,
                  panel_y + zoom.height + 2], outline=wht, width=3)
    sheet.save(os.path.join(HERE, "out", "preview_bottom.png"))
    print("  previews written (bottom includes 2x C10+J1 detail panel)")


if __name__ == "__main__":
    main()
