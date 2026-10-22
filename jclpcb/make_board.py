#!/usr/bin/env python3
"""
WS2812B 7-segment display -- 100 x 170 mm, TWO copper layers.

Top : 5 V pour + data chain + all components
Bottom: solid GND plane; every LED GND pad has a via to it
24 x WS2812B, 4 per horizontal segment (A,G,D), 3 per vertical (B,C,E,F)
Connectors both on the BOTTOM edge: J1 (in) right, J2 (out) left
470 uF / 10 V bulk capacitor at the 5 V input.

Board: 100 x 170 x 1.0 mm, 1 oz, HASL.  Digit: 80 x 150 mm (x 10..90, y 10..160).
"""
from __future__ import annotations

import csv
import math
import os
import zipfile
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
GERB = os.path.join(OUT, "gerbers")
PROJECT = "WS2812B-7SEG-2L"
DATE = "2026-10-18T19:00:00-04:00"

W, H = 100.0, 170.0
R_CORNER = 3.0

# ---------------------------------------------------------------------------
# 1. LED placement  (chain runs B3 -> ... -> G1, i.e. right to left)
# ---------------------------------------------------------------------------
SEGMENTS = {
    "A": [(20, 157.5), (40, 157.5), (60, 157.5), (80, 157.5)],
    "G": [(20, 85.0), (40, 85.0), (60, 85.0), (80, 85.0)],
    "D": [(20, 12.5), (40, 12.5), (60, 12.5), (80, 12.5)],
    "F": [(12.5, 145.0), (12.5, 122.5), (12.5, 100.0)],
    "B": [(87.5, 100.0), (87.5, 122.5), (87.5, 145.0)],
    "E": [(12.5, 70.0), (12.5, 47.5), (12.5, 25.0)],
    "C": [(87.5, 25.0), (87.5, 47.5), (87.5, 70.0)],
}
SEG_ROT = {"A": 180, "G": 0, "D": 0, "F": 270, "E": 270, "B": 90, "C": 90}

PAD_OFF = {
    1: (-2.45, 1.60),   # VDD
    2: (-2.45, -1.60),  # DOUT
    3: (2.45, -1.60),   # GND
    4: (2.45, 1.60),    # DIN
}
PAD_WH = (1.50, 1.00)
GND_VIA = {0: (4.00, -1.60), 90: (1.60, 4.00),
           180: (-4.00, 1.60), 270: (-1.60, -4.00)}


def rot_pt(dx, dy, r):
    if r == 0:
        return dx, dy
    if r == 90:
        return -dy, dx
    if r == 180:
        return -dx, -dy
    return dy, -dx


LEDS = {}
for seg, pts in SEGMENTS.items():
    for i, (x, y) in enumerate(pts, start=1):
        LEDS[f"{seg}{i}"] = dict(seg=seg, x=x, y=y, rot=SEG_ROT[seg])


def led_pad(ref, pin):
    led = LEDS[ref]
    dx, dy = rot_pt(*PAD_OFF[pin], led["rot"])
    return led["x"] + dx, led["y"] + dy


CHAIN = ([f"B{i}" for i in range(3, 0, -1)]
         + [f"C{i}" for i in range(3, 0, -1)]
         + [f"D{i}" for i in range(4, 0, -1)]
         + [f"E{i}" for i in range(3, 0, -1)]
         + [f"F{i}" for i in range(3, 0, -1)]
         + [f"A{i}" for i in range(1, 5)]
         + [f"G{i}" for i in range(4, 0, -1)])
assert len(CHAIN) == 24 and len(set(CHAIN)) == 24

# ---------------------------------------------------------------------------
# 2. Connectors / capacitor / holes
# ---------------------------------------------------------------------------
J1 = [(78.00, 4.5), (80.54, 4.5), (83.08, 4.5)]        # 5V, DIN, GND
J2 = [(12.00, 4.5), (14.54, 4.5), (17.08, 4.5)]        # 5V, DOUT, GND
CAP = (68.0, 5.0)          # SMD 8x10.5, pads at +/-3.7 (KiCad CP_Elec_8x10.5)
CAP_PAD = (5.00, 3.00)
PAD_THT = 1.80
DRILL_THT = 1.00
NPTH = [(2.80, 2.80, 2.20), (97.20, 2.80, 2.20),
        (2.80, 167.20, 2.20), (97.20, 167.20, 2.20)]

# back-side surface solder pads for the connectors (customer wires)
BACK_Y = 8.0
BACK_PADS = []
for ref, pins in (("J1", J1), ("J2", J2)):
    for i, (x, y) in enumerate(pins):
        BACK_PADS.append(dict(ref=ref, pin=i + 1, x=x, y=BACK_Y,
                              w=2.0, h=2.0, net=("5V", "DATA", "GND")[i]))
BACK_VIAS = [(b["x"], b["y"], 0.6, 0.3)
             for b in BACK_PADS if b["net"] in ("5V", "DATA")]

# ---------------------------------------------------------------------------
# 3. Data routing
# ---------------------------------------------------------------------------
DATA_TRACES = []


def add(pts, w=0.30):
    DATA_TRACES.append((pts, w))


# J1.DIN -> B3.DIN (up the right margin)
add([J1[1], (80.54, 8.0), (91.50, 8.0), (91.50, 151.0),
     (85.90, 151.0), (85.90, 147.45)])

for a, b in zip(CHAIN[:-1], CHAIN[1:]):
    ax, ay = led_pad(a, 2)
    bx, by = led_pad(b, 4)
    if a == "A4" and b == "G4":
        add([(ax, ay), (84.50, ay), (84.50, by), (bx, by)])
    else:
        add([(ax, ay), (bx, by)])

# G1.DOUT -> J2.DOUT (down the left side)
add([(17.55, 83.40), (19.50, 83.40), (19.50, 8.0),
     (14.54, 8.0), (14.54, 4.5)])

# ---------------------------------------------------------------------------
# 4. Gerber writer
# ---------------------------------------------------------------------------
def gc(v):
    return str(int(round(v * 1e6)))


class Gerber:
    def __init__(self, function):
        self.function = function
        self.aps = {}
        self.next_d = 10
        self.body = []
        self.cur = None
        self.dark = True

    def ap(self, shape, p):
        key = (shape, p)
        if key not in self.aps:
            self.aps[key] = self.next_d
            self.next_d += 1
        return self.aps[key]

    def _use(self, d):
        if self.cur != d:
            self.body.append(f"D{d}*")
            self.cur = d

    def polarity(self, dark):
        if dark != self.dark:
            self.body.append("%LPD*%" if dark else "%LPC*%")
            self.dark = dark

    def flash(self, x, y, shape, *p):
        d = self.ap(shape, p)
        self._use(d)
        self.body.append(f"X{gc(x)}Y{gc(y)}D03*")

    def polyline(self, pts, w):
        d = self.ap("C", (round(w, 4),))
        self._use(d)
        x0, y0 = pts[0]
        self.body.append(f"X{gc(x0)}Y{gc(y0)}D02*")
        for x, y in pts[1:]:
            self.body.append(f"X{gc(x)}Y{gc(y)}D01*")

    def region(self, pts):
        self.polarity(True)
        self._use(self.ap("C", (0.01,)))
        self.body.append("G36*")
        x0, y0 = pts[0]
        self.body.append(f"X{gc(x0)}Y{gc(y0)}D02*")
        for x, y in pts[1:]:
            self.body.append(f"X{gc(x)}Y{gc(y)}D01*")
        self.body.append(f"X{gc(x0)}Y{gc(y0)}D01*")
        self.body.append("G37*")

    def save(self, path):
        head = [
            f"G04 {os.path.basename(path)} -- {PROJECT} 100x170 2-layer*",
            "%TF.GenerationSoftware,DeepSeek Harness,AI-GEN,1.0*%",
            f"%TF.CreationDate,{DATE}*%",
            f"%TF.FileFunction,{self.function}*%",
            "%TF.FilePolarity,Positive*%",
            "%FSLAX46Y46*%",
            "%MOMM*%",
            "%LPD*%",
            "G01*",
        ]
        for (shape, p), d in self.aps.items():
            if shape == "C":
                spec = f"C,{p[0]:.4f}"
            elif shape == "R":
                spec = f"R,{p[0]:.4f}X{p[1]:.4f}"
            else:
                spec = f"O,{p[0]:.4f}X{p[1]:.4f}"
            head.append(f"%ADD{d}{spec}*%")
        with open(path, "w", encoding="ascii") as fh:
            fh.write("\n".join(head + self.body + ["M02*"]) + "\n")


def rounded_rect(w, h, r, seg=24):
    pts = []

    def arc(cx, cy, a0, a1):
        for i in range(seg + 1):
            a = math.radians(a0 + (a1 - a0) * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    pts.append((r, 0))
    pts.append((w - r, 0))
    arc(w - r, r, -90, 0)
    pts.append((w, h - r))
    arc(w - r, h - r, 0, 90)
    pts.append((r, h))
    arc(r, h - r, 90, 180)
    pts.append((0, r))
    arc(r, r, 180, 270)
    pts.append((r, 0))
    return pts


# ---------------------------------------------------------------------------
# 5. Pad tables
# ---------------------------------------------------------------------------
@dataclass
class Pad:
    ref: str
    pin: str
    x: float
    y: float
    w: float
    h: float
    shape: str
    drill: float | None
    net: str


PADS = []
for ref, led in LEDS.items():
    for pin, net in ((1, "5V"), (2, "DATA"), (3, "GND"), (4, "DATA")):
        x, y = led_pad(ref, pin)
        w, h = PAD_WH
        if led["rot"] in (90, 270):
            w, h = h, w
        PADS.append(Pad(ref, str(pin), x, y, w, h, "rect", None, net))

for i, (x, y) in enumerate(J1):
    PADS.append(Pad("J1", str(i + 1), x, y, PAD_THT, PAD_THT, "round", DRILL_THT,
                    ("5V", "DATA", "GND")[i]))
for i, (x, y) in enumerate(J2):
    PADS.append(Pad("J2", str(i + 1), x, y, PAD_THT, PAD_THT, "round", DRILL_THT,
                    ("5V", "DATA", "GND")[i]))
# C10 is mounted on the BACK by the customer: SMD pads on B.Cu only.
# Pad 1 (+5V) reaches the top 5V pour through two vias; pad 2 is the GND plane.
CAP_PADS = [
    Pad("C10", "1", CAP[0] - 3.7, CAP[1], *CAP_PAD, "rect", None, "5V"),
    Pad("C10", "2", CAP[0] + 3.7, CAP[1], *CAP_PAD, "rect", None, "GND"),
]
CAP_VIAS = [(CAP[0] - 4.7, CAP[1] - 0.9, 0.6, 0.3),
            (CAP[0] - 4.7, CAP[1] + 0.9, 0.6, 0.3)]

# GND pad -> via islands
GND_ISLANDS = []
for ref, led in LEDS.items():
    gx, gy = led_pad(ref, 3)
    vdx, vdy = GND_VIA[led["rot"]]
    vx, vy = led["x"] + vdx, led["y"] + vdy
    w, h = PAD_WH
    if led["rot"] in (90, 270):
        w, h = h, w
    GND_ISLANDS.append(dict(ref=ref, px=gx, py=gy, pw=w, ph=h, vx=vx, vy=vy))

# ---------------------------------------------------------------------------
# 6. Build
# ---------------------------------------------------------------------------
def build():
    os.makedirs(GERB, exist_ok=True)
    top = Gerber("Copper,L1,Top")
    bot = Gerber("Copper,L2,Bot")
    mask_t = Gerber("Soldermask,Top")
    mask_b = Gerber("Soldermask,Bot")
    paste = Gerber("Paste,Top")
    silk = Gerber("Legend,Top")
    edge = Gerber("Profile,NP")

    # ---------------- top: 5 V pour ----------------
    top.region([(x + 0.5, y + 0.5) for x, y in
                rounded_rect(W - 1.0, H - 1.0, R_CORNER - 0.5)])
    top.polarity(False)
    # data pads and traces
    for p in PADS:
        if p.net == "DATA":
            top.flash(p.x, p.y, "C", p.w + 0.8) if p.shape == "round" else \
                top.flash(p.x, p.y, "R", p.w + 0.8, p.h + 0.8)
    for pts, w in DATA_TRACES:
        top.polyline(pts, w + 0.8)
    # GND pad + stub + via islands
    for g in GND_ISLANDS:
        top.flash(g["px"], g["py"], "R", g["pw"] + 0.8, g["ph"] + 0.8)
        top.polyline([(g["px"], g["py"]), (g["vx"], g["vy"])], 0.50 + 0.8)
        top.flash(g["vx"], g["vy"], "C", 0.60 + 0.8)
    # GND / DATA through-hole pads
    for p in PADS:
        if p.drill is not None and p.net in ("GND", "DATA"):
            top.flash(p.x, p.y, "C", p.w + 1.0)
    # mounting holes
    for hx, hy, hd in NPTH:
        top.flash(hx, hy, "C", hd + 1.0)
    top.polarity(True)

    # ---------------- top: copper ----------------
    for pts, w in DATA_TRACES:
        top.polyline(pts, w)
    for p in PADS:
        if p.net == "DATA":
            top.flash(p.x, p.y, "R", p.w, p.h) if p.shape == "rect" else \
                top.flash(p.x, p.y, "C", p.w)
    for g in GND_ISLANDS:
        top.flash(g["px"], g["py"], "R", g["pw"], g["ph"])
        top.polyline([(g["px"], g["py"]), (g["vx"], g["vy"])], 0.50)
        top.flash(g["vx"], g["vy"], "C", 0.60)
    for p in PADS:
        if p.drill is not None:
            top.flash(p.x, p.y, "C", p.w)

    # ---------------- bottom: GND plane ----------------
    bot.region([(x + 0.5, y + 0.5) for x, y in
                rounded_rect(W - 1.0, H - 1.0, R_CORNER - 0.5)])
    bot.polarity(False)
    for p in PADS:
        if p.drill is not None and p.net in ("5V", "DATA"):
            bot.flash(p.x, p.y, "C", p.w + 1.0)
    cp = CAP_PADS[0]                     # C10 +5V pad isolated from the plane
    bot.flash(cp.x, cp.y, "R", cp.w + 0.8, cp.h + 0.8)
    cg = CAP_PADS[1]                     # C10 GND pad: thermal relief for hand soldering
    bot.flash(cg.x, cg.y, "R", cg.w + 0.6, cg.h + 0.6)
    for b in BACK_PADS:
        if b["net"] in ("5V", "DATA"):
            bot.flash(b["x"], b["y"], "R", b["w"] + 0.8, b["h"] + 0.8)
        else:
            bot.flash(b["x"], b["y"], "R", b["w"] + 0.6, b["h"] + 0.6)
    for hx, hy, hd in NPTH:
        bot.flash(hx, hy, "C", hd + 1.0)
    bot.polarity(True)
    for p in PADS:
        if p.drill is not None:
            bot.flash(p.x, p.y, "C", p.w)
    # four thermal spokes + pads
    sp = 0.55
    for (x1, y1, x2, y2) in (
            (cg.x - cg.w / 2 - sp, cg.y, cg.x - cg.w / 2, cg.y),
            (cg.x + cg.w / 2, cg.y, cg.x + cg.w / 2 + sp, cg.y),
            (cg.x, cg.y - cg.h / 2 - sp, cg.x, cg.y - cg.h / 2),
            (cg.x, cg.y + cg.h / 2, cg.x, cg.y + cg.h / 2 + sp)):
        bot.polyline([(x1, y1), (x2, y2)], 0.60)
    for cp in CAP_PADS:                  # +5V isolated, GND thermally connected
        bot.flash(cp.x, cp.y, "R", cp.w, cp.h)
    for b in BACK_PADS:                  # back solder pads
        bot.flash(b["x"], b["y"], "R", b["w"], b["h"])
        if b["net"] == "GND":
            # only vertical spokes: the 2.54 mm pitch leaves no room sideways
            sp = 0.55
            bot.polyline([(b["x"], b["y"] - b["h"] / 2 - sp), (b["x"], b["y"] - b["h"] / 2)], 0.60)
            bot.polyline([(b["x"], b["y"] + b["h"] / 2), (b["x"], b["y"] + b["h"] / 2 + sp)], 0.60)

    # ---------------- masks ----------------
    for p in PADS:
        if p.shape == "round":
            mask_t.flash(p.x, p.y, "C", p.w + 0.10)
            if p.drill is not None:
                mask_b.flash(p.x, p.y, "C", p.w + 0.10)
        else:
            mask_t.flash(p.x, p.y, "R", p.w + 0.10, p.h + 0.10)
    for cp in CAP_PADS:
        mask_b.flash(cp.x, cp.y, "R", cp.w + 0.10, cp.h + 0.10)
    for b in BACK_PADS:
        mask_b.flash(b["x"], b["y"], "R", b["w"] + 0.10, b["h"] + 0.10)
    for hx, hy, hd in NPTH:
        mask_t.flash(hx, hy, "C", hd + 0.20)
        mask_b.flash(hx, hy, "C", hd + 0.20)

    # ---------------- paste ----------------
    for p in PADS:
        if p.drill is None:
            paste.flash(p.x, p.y, "R", p.w, p.h)

    # ---------------- silkscreen ----------------
    for ref in CHAIN:
        led = LEDS[ref]
        if led["seg"] in ("A", "G", "D"):
            tx, ty = led["x"] + 5.2, led["y"]
        elif led["seg"] in ("F", "E"):
            tx, ty = led["x"] + 5.0, led["y"]
        else:
            tx, ty = led["x"] - 5.0, led["y"]
        silk_text(silk, ref, tx, ty, 0.18)

    for i, (x, y) in enumerate(J1):
        silk_text(silk, ("5V", "DIN", "GND")[i], x, 6.2, 0.11)
    for i, (x, y) in enumerate(J2):
        silk_text(silk, ("5V", "DOUT", "GND")[i], x, 6.2, 0.11)

    silk_text(silk, "WS2812B 7-SEG 24", 50, 166.5, 0.30)

    # bottom silkscreen: C10 (customer-installed on the back)
    bsilk = Gerber("Legend,Bot")
    silk_text(bsilk, "C10", 68.0, 9.0, 0.28, mirror=True)
    silk_text(bsilk, "470uF", 68.0, 11.3, 0.16, mirror=True)
    bsilk.polyline([(60.5, 2.5), (75.5, 2.5), (75.5, 7.5),
                    (60.5, 7.5), (60.5, 2.5)], 0.15)
    silk_text(bsilk, "J1 GND DIN 5V", 80.5, 10.8, 0.12, mirror=True)
    silk_text(bsilk, "J2 GND DOUT 5V", 14.5, 10.8, 0.12, mirror=True)
    silk_text(bsilk, "+", 59.3, 5.0, 0.26, mirror=True)
    bsilk.polyline([(64.0, 0.9), (72.0, 0.9)], 0.15)
    bsilk.polyline([(64.0, 9.1), (72.0, 9.1)], 0.15)

    edge.polyline(rounded_rect(W, H, R_CORNER), 0.10)

    for obj, fn in ((top, f"{PROJECT}-F_Cu.gtl"),
                    (bot, f"{PROJECT}-B_Cu.gbl"),
                    (mask_t, f"{PROJECT}-F_Mask.gts"),
                    (mask_b, f"{PROJECT}-B_Mask.gbs"),
                    (paste, f"{PROJECT}-F_Paste.gtp"),
                    (silk, f"{PROJECT}-F_Silkscreen.gto"),
                    (bsilk, f"{PROJECT}-B_Silkscreen.gbo"),
                    (edge, f"{PROJECT}-Edge_Cuts.gm1")):
        obj.save(os.path.join(GERB, fn))

    pth = [(p.x, p.y, p.drill) for p in PADS if p.drill]
    pth += [(g["vx"], g["vy"], 0.30) for g in GND_ISLANDS]
    pth += [(vx, vy, dr) for vx, vy, pad, dr in CAP_VIAS]
    pth += [(vx, vy, dr) for vx, vy, pad, dr in BACK_VIAS]
    write_drill(os.path.join(GERB, f"{PROJECT}-PTH.drl"),
                [(1, 0.30), (2, 1.00)], pth)
    write_drill(os.path.join(GERB, f"{PROJECT}-NPTH.drl"), [(1, 2.20)],
                [(x, y, d) for x, y, d in NPTH])

    des = ",".join(CHAIN)
    with open(os.path.join(OUT, "BOM_JLCPCB.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        wr.writerow(["WS2812B", des, "LED5050_WS2812B", "C2761795"])
    with open(os.path.join(OUT, "BOM_full.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["Line", "Qty", "Designator", "Comment", "Footprint",
                     "LCSC Part #", "Assembly"])
        wr.writerow([1, 24, des, "WS2812B", "LED5050_WS2812B", "C2761795",
                     "SMT - placed by fab"])
        wr.writerow([2, 1, "C10", "470uF 10V", "CAP_SMD_8x10.5", "C3039784",
                     "DNP - customer installs on BACK"])
        wr.writerow([3, 2, "J1,J2", "1x3 2.54mm", "PinHeader_1x03_P2.54", "",
                     "DNP - wires soldered from BACK"])
    with open(os.path.join(OUT, "CPL_JLCPCB.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref in CHAIN:
            led = LEDS[ref]
            wr.writerow([ref, f"{led['x']:.3f}", f"{led['y']:.3f}", "Top", led["rot"]])


    write_dxf(os.path.join(OUT, "segment_mask.dxf"))

    zip_path = os.path.join(OUT, f"{PROJECT}_gerbers.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in sorted(os.listdir(GERB)):
            zf.write(os.path.join(GERB, fn), fn)
    return zip_path


# ---------------------------------------------------------------------------
# 7. Text
# ---------------------------------------------------------------------------
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    " ": ("00000",) * 7,
}


def silk_text(g, s, cx, cy, px, mirror=False):
    n = len(s)
    tw = (n * 6 - 1) * px
    for i, ch in enumerate(s.upper()):
        for row, bits in enumerate(FONT.get(ch, FONT[" "])):
            for col, bit in enumerate(bits):
                if bit == "1":
                    x = cx + (i * 6 + col) * px - tw / 2 + px / 2
                    if mirror:
                        x = 2 * cx - x
                    y = cy + (3 - row) * px
                    g.flash(x, y, "R", px, px)


# ---------------------------------------------------------------------------
# 8. PVC DXF
# ---------------------------------------------------------------------------
SEG_CUT = {
    "A": (17.0, 154.0, 83.0, 161.0),
    "G": (17.0, 81.5, 83.0, 88.5),
    "D": (17.0, 9.5, 83.0, 16.5),
    "F": (9.0, 97.0, 15.5, 148.0),
    "B": (84.5, 97.0, 91.0, 148.0),
    "E": (9.0, 22.0, 15.5, 73.0),
    "C": (84.5, 22.0, 91.0, 73.0),
}


def write_dxf(path):
    e = []

    def line(x1, y1, x2, y2, layer="CUT"):
        e.extend(["0", "LINE", "8", layer,
                  "10", f"{x1:.3f}", "20", f"{y1:.3f}",
                  "11", f"{x2:.3f}", "21", f"{y2:.3f}"])

    def rect(x0, y0, x1, y1, layer="CUT"):
        line(x0, y0, x1, y0, layer)
        line(x1, y0, x1, y1, layer)
        line(x1, y1, x0, y1, layer)
        line(x0, y1, x0, y0, layer)

    def circle(cx, cy, r, layer="HOLES"):
        e.extend(["0", "CIRCLE", "8", layer,
                  "10", f"{cx:.3f}", "20", f"{cy:.3f}", "40", f"{r:.3f}"])

    def text(s, x, y, h=3.0, layer="LABEL"):
        e.extend(["0", "TEXT", "8", layer,
                  "10", f"{x:.3f}", "20", f"{y:.3f}",
                  "40", f"{h:.3f}", "1", s])

    rect(0, 0, W, H, "OUTLINE")
    for name, (x0, y0, x1, y1) in SEG_CUT.items():
        rect(x0, y0, x1, y1)
        text(name, (x0 + x1) / 2 - 1.0, (y0 + y1) / 2 - 1.5)
    for hx, hy, hd in NPTH:
        circle(hx, hy, hd / 2)
    with open(path, "w", encoding="ascii") as fh:
        fh.write("0\nSECTION\n2\nENTITIES\n")
        fh.write("\n".join(e))
        fh.write("\n0\nENDSEC\n0\nEOF\n")


# ---------------------------------------------------------------------------
# 9. Drill writer
# ---------------------------------------------------------------------------
def write_drill(path, tools, holes):
    lines = ["M48", f";DRILL file -- {PROJECT}",
             ";FORMAT={-:-/ absolute / metric / decimal}", "FMAT,2", "METRIC"]
    for tno, dia in tools:
        lines.append(f"T{tno}C{dia:.3f}")
    lines += ["%", "G90", "G05"]
    for tno, dia in tools:
        lines.append(f"T{tno}")
        for (x, y, d) in holes:
            if abs(d - dia) < 1e-9:
                lines.append(f"X{x:.3f}Y{y:.3f}")
    lines.append("M30")
    with open(path, "w", encoding="ascii") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    print(build())
