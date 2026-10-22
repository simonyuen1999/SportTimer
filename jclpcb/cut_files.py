#!/usr/bin/env python3
"""PVC overlay for the 7-segment board - bold 10 mm stroke, 4 mm gaps.

Geometry:
  * stroke (bar width) 10.0 mm for every segment
  * 4.0 mm clear between the flat sides of adjacent segments
  * both ends are 90 deg points, point length = stroke/2 = 5.0 mm
  * A/G/D overall 67.0 mm; F/B/E/C overall 64.5 mm (flat 54.5 + 2 x 5)

G-code:
  * 2.0 mm end mill, origin lower-left, Z0 = top of the 5 mm material
  * 5 passes x 1 mm (Z -1 ... -5)
  * tool centre follows the inward offset polygon; tips and corners are
    rounded R1.0 by the bit
  * raster relief lines clear the 10 mm wide slots
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

from make_board import W, H, R_CORNER

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

STROKE = 12.0
GAP = 4.0
TOOL_DIA = 2.0
DEPTH = 5.0
STEP = 1.0
SAFE_Z = 5.0
FEED_XY = 800
FEED_Z = 150
SPINDLE = 12000

# segment layout (centrelines / flat ends)
A_Y, G_Y, D_Y = 157.5, 85.0, 12.5
F_X, B_X = 12.5, 87.5
H_BAR_X0, H_BAR_X1 = 22.5, 77.5          # horizontal flat ends
F_Y0, F_Y1 = 95.0, 147.5                 # F/B flat ends
E_Y0, E_Y1 = 22.5, 75.0                  # E/C flat ends
NPTH = [(2.80, 2.80, 2.20), (97.20, 2.80, 2.20),
        (2.80, 167.20, 2.20), (97.20, 167.20, 2.20)]


def build_segments():
    seg = {}
    h = STROKE / 2.0
    # horizontal: A, G, D
    for name, yc in (("A", A_Y), ("G", G_Y), ("D", D_Y)):
        x0, x1 = H_BAR_X0, H_BAR_X1
        y0, y1 = yc - h, yc + h
        p = h
        pts = [(x0 - p, yc), (x0, y0), (x1, y0),
               (x1 + p, yc), (x1, y1), (x0, y1)]
        box = (x0 - p, y0, x1 + p, y1)
        seg[name] = dict(pts=pts, box=box, L=(x1 - x0) + 2 * p,
                         W=STROKE, P=p, horiz=True)
    # vertical: F, B, E, C
    for name, xc, ya, yb in (("F", F_X, F_Y0, F_Y1), ("B", B_X, F_Y0, F_Y1),
                             ("E", F_X, E_Y0, E_Y1), ("C", B_X, E_Y0, E_Y1)):
        x0, x1 = xc - h, xc + h
        p = h
        pts = [(xc, ya - p), (x0, ya), (x0, yb),
               (xc, yb + p), (x1, yb), (x1, ya)]
        box = (x0, ya - p, x1, yb + p)
        seg[name] = dict(pts=pts, box=box, L=(yb - ya) + 2 * p,
                         W=STROKE, P=p, horiz=False)
    return seg


SEG = build_segments()


# ---------------------------------------------------------------------------
# tool-centre path: inward offset polygon (sharp vertices)
# ---------------------------------------------------------------------------
def offset_poly(pts, r):
    n = len(pts)
    area = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    ccw = area > 0
    lines = []
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        Ln = math.hypot(dx, dy)
        nx, ny = (-dy / Ln, dx / Ln) if ccw else (dy / Ln, -dx / Ln)
        lines.append((x1 + nx * r, y1 + ny * r, dx, dy))
    out = []
    for i in range(n):
        x1, y1, dx1, dy1 = lines[i - 1]
        x2, y2, dx2, dy2 = lines[i]
        den = dx1 * dy2 - dy1 * dx2
        if abs(den) < 1e-9:
            out.append((x2, y2))
            continue
        t = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / den
        out.append((x1 + t * dx1, y1 + t * dy1))
    return out


def relief_lines(s, r, tool_d):
    """Interior raster lines across the flat part of a segment."""
    inner = s["W"] - 2 * r
    if inner <= 1e-6:
        return []
    n = max(1, int(math.ceil(inner / (0.7 * tool_d))) + 1)
    offs = [0.0] if n == 1 else [-inner / 2 + i * inner / (n - 1) for i in range(n)]
    out = []
    for off in offs:
        if abs(off) < 1e-6 or abs(abs(off) - inner / 2) < 1e-6:
            continue
        if s["horiz"]:
            yc = (s["box"][1] + s["box"][3]) / 2
            x0 = s["box"][0] + s["P"]
            x1 = s["box"][2] - s["P"]
            out.append((x0, yc + off, x1, yc + off))
        else:
            xc = (s["box"][0] + s["box"][2]) / 2
            y0 = s["box"][1] + s["P"]
            y1 = s["box"][3] - s["P"]
            out.append((xc + off, y0, xc + off, y1))
    return out


# ---------------------------------------------------------------------------
# 1. G-code
# ---------------------------------------------------------------------------
def make_gcode():
    r = TOOL_DIA / 2.0
    npass = int(round(DEPTH / STEP))
    L = []
    A = L.append
    A("(7-SEGMENT PVC OVERLAY - BOLD 12 mm STROKE)")
    A("(SHEET 100.000 x 170.000 mm, MATERIAL 5.000 mm)")
    A("(TOOL 2.0 mm END MILL - 1.000 mm PER PASS - %d PASSES)" % npass)
    A("(ORIGIN LOWER-LEFT CORNER, Z0 = TOP OF MATERIAL)")
    A("(STROKE 12.0 mm, 4.0 mm CLEAR BETWEEN SEGMENT FLATS)")
    A("(A/G/D 67.0 x 12.0, F/B/E/C 64.5 x 12.0)")
    A("(POINT 6.0 mm, 90 DEG; TIPS ROUNDED R1.0 BY THE BIT)")
    A("(4 x 2.2 mm HOLES, 1.0 mm DEEP)")
    A("(USE A 1 mm BIT OR V-BIT FOR A SHARPER POINT)")
    A("(POINT BASE SITS AT THE A/G/D END-LED CENTRES x=20/80)")
    A("")
    A("G21")
    A("G90")
    A("G17")
    A("G94")
    A("M3 S%d" % SPINDLE)
    A("G4 P2")
    A("G0 Z%.3f" % SAFE_Z)
    A("")

    # four 2.2 mm corner holes, 1 mm deep
    A("(4 x 2.2 mm HOLES - 1.0 mm DEEP)")
    for (hx, hy, hd) in NPTH:
        rr = (hd - TOOL_DIA) / 2.0
        A("(HOLE %.2f, %.2f  D%.1f)" % (hx, hy, hd))
        A("G0 Z%.3f" % SAFE_Z)
        A("G0 X%.3f Y%.3f" % (hx + rr, hy))
        A("G1 Z-1.000 F%d" % FEED_Z)
        for k in range(1, 25):
            a = 2.0 * math.pi * k / 24.0
            A("G1 X%.3f Y%.3f F400" % (hx + rr * math.cos(a), hy + rr * math.sin(a)))
        A("G0 Z%.3f" % SAFE_Z)
        A("")
    A("")

    for i in range(npass):
        z = -(i + 1) * STEP
        A("(PASS %d/%d  Z%.3f)" % (i + 1, npass, z))
        for name in "AGDFBEC":
            s = SEG[name]
            path = offset_poly(s["pts"], r)
            A("(SEG %s  %.1f x %.1f, point %.1f)" % (name, s["L"], s["W"], s["P"]))
            A("G0 Z%.3f" % SAFE_Z)
            A("G0 X%.3f Y%.3f" % path[0])
            A("G1 Z%.3f F%d" % (z, FEED_Z))
            for p in path[1:]:
                A("G1 X%.3f Y%.3f F%d" % (p[0], p[1], FEED_XY))
            A("G1 X%.3f Y%.3f" % path[0])
            # centre relief, tip to tip
            A("G1 X%.3f Y%.3f" % path[3])
            for (ax, ay, bx, by) in relief_lines(s, r, TOOL_DIA):
                A("G1 X%.3f Y%.3f" % (ax, ay))
                A("G1 X%.3f Y%.3f" % (bx, by))
            A("G0 Z%.3f" % SAFE_Z)
            A("")

    A("G0 Z%.3f" % SAFE_Z)
    A("M5")
    A("G0 X0.000 Y0.000")
    A("M30")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# 2. dimensioned PNG
# ---------------------------------------------------------------------------
SCALE = 10
MX, MY = 140, 120
CW, CH = 1340, 2240
BLACK = (0, 0, 0)
GREY = (217, 217, 217)
WHITE = (255, 255, 255)

FD = "/System/Library/Fonts/Supplemental"
def _f(name, size, fb):
    p = os.path.join(FD, name)
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default(size=fb)

F_TITLE = _f("Arial.ttf", 30, 30)
F_SUB = _f("Arial.ttf", 18, 18)
F_DIM = _f("Arial.ttf", 20, 20)
F_SEG = _f("Arial.ttf", 30, 30)
F_MONO = _f("Courier New.ttf", 18, 18)


def X(x):
    return MX + x * SCALE


def Y(y):
    return MY + (H - y) * SCALE


def make_png():
    img = Image.new("RGB", (CW, CH), WHITE)
    d = ImageDraw.Draw(img)

    d.text((MX, 26), "7-SEGMENT PVC OVERLAY - BOLD 12 mm STROKE",
           font=F_TITLE, fill=BLACK)
    d.text((MX, 64),
           "100 x 170 sheet, 5 mm material.  Stroke 12 mm, 4 mm clear "
           "between the flat sides of adjacent segments.", font=F_SUB, fill=BLACK)
    d.text((MX, 86),
           "90 deg points, 6 mm long: A/G/D 67.0 mm overall, F/B/E/C 64.5 mm.  "
           "Four D2.2 holes 1 mm deep at the corners.", font=F_SUB, fill=BLACK)

    d.rounded_rectangle([X(0), Y(H), X(W), Y(0)], radius=R_CORNER * SCALE,
                        outline=BLACK, fill=WHITE, width=3)

    for name, s in SEG.items():
        poly = [(X(x), Y(y)) for x, y in s["pts"]]
        d.polygon(poly, fill=GREY)
        d.line(poly + [poly[0]], fill=BLACK, width=3)
        bx = s["box"]
        d.text((X((bx[0] + bx[2]) / 2), Y((bx[1] + bx[3]) / 2)), name,
               font=F_SEG, fill=BLACK, anchor="mm")

    for (hx, hy, hd) in NPTH:
        r = hd / 2 * SCALE
        d.ellipse([X(hx) - r, Y(hy) - r, X(hx) + r, Y(hy) + r],
                  fill=WHITE, outline=BLACK, width=3)
        d.line([X(hx) - 5, Y(hy), X(hx) + 5, Y(hy)], fill=BLACK, width=1)
        d.line([X(hx), Y(hy) - 5, X(hx), Y(hy) + 5], fill=BLACK, width=1)

    def dim_h(x1, x2, y, label, ext=None, tdy=-16):
        X1, X2, Yv = X(x1), X(x2), Y(y)
        d.line([X1, Yv, X2, Yv], fill=BLACK, width=2)
        for x in (x1, x2):
            d.line([X(x), Yv - 6, X(x), Yv + 6], fill=BLACK, width=2)
            if ext is not None:
                d.line([X(x), Y(ext), X(x), Yv], fill=BLACK, width=1)
        d.text(((X1 + X2) / 2, Yv + tdy), label, font=F_DIM, fill=BLACK, anchor="mm")

    def rot_text(cx, cy, label):
        b = F_DIM.getbbox(label)
        w, h = b[2] - b[0], b[3] - b[1]
        t = Image.new("RGBA", (w + 8, h + 8), (255, 255, 255, 0))
        ImageDraw.Draw(t).text((4, 4), label, font=F_DIM, fill=(0, 0, 0, 255))
        t = t.rotate(90, expand=True)
        img.paste(t, (int(cx - t.width / 2), int(cy - t.height / 2)), t)

    def dim_v(y1, y2, x, label, ext=None, tdx=16):
        Y1, Y2, Xv = Y(y1), Y(y2), X(x)
        d.line([Xv, Y1, Xv, Y2], fill=BLACK, width=2)
        for y in (y1, y2):
            d.line([Xv - 6, Y(y), Xv + 6, Y(y)], fill=BLACK, width=2)
            if ext is not None:
                d.line([X(ext), Y(y), Xv, Y(y)], fill=BLACK, width=1)
        rot_text(Xv + tdx, (Y1 + Y2) / 2, label)

    dim_h(0, 100, -8, "100", ext=0, tdy=18)
    dim_v(0, 170, 112, "170", ext=100, tdx=20)

    # A chain 16.5 | 67 | 16.5
    dim_h(0, 16.5, 165.5, "16.5", ext=163.5, tdy=-14)
    dim_h(16.5, 83.5, 165.5, "67", ext=163.5, tdy=-14)
    dim_h(83.5, 100, 165.5, "16.5", ext=163.5, tdy=-14)
    dim_v(151.5, 163.5, 84, "12", ext=83.5, tdx=14)

    dim_h(22.5, 77.5, 76, "55", ext=79, tdy=-14)
    dim_h(22.5, 77.5, 4, "55", ext=6.5, tdy=-14)

    dim_v(89, 153.5, 4.5, "64.5", ext=6.5, tdx=-16)
    dim_v(89, 153.5, 95.5, "64.5", ext=93.5, tdx=16)
    dim_v(16.5, 81, 4.5, "64.5", ext=6.5, tdx=-16)
    dim_v(16.5, 81, 95.5, "64.5", ext=93.5, tdx=16)

    dim_h(6.5, 18.5, 95, "12", ext=None, tdy=-14)

    # 4 mm flat gap at the A / F corner
    dim_h(18.5, 22.5, 150, "4", ext=None, tdy=-12)

    # cut list
    tx, ty = MX, 1960
    d.text((tx, ty), "CUT LIST (mm)", font=F_TITLE, fill=BLACK)
    fmt = "{:<4}{:>8}{:>8}{:>8}{:>8}{:>7}{:>7}{:>8}"
    rows = [("SEG", "X0", "Y0", "X1", "Y1", "L", "W", "PT")]
    for name, s in SEG.items():
        b = s["box"]
        rows.append((name, "%.1f" % b[0], "%.1f" % b[1], "%.1f" % b[2], "%.1f" % b[3],
                     "%.1f" % s["L"], "%.1f" % s["W"], "%.1f" % s["P"]))
    yy = ty + 42
    for i, row in enumerate(rows):
        d.text((tx, yy), fmt.format(*row), font=F_MONO, fill=BLACK)
        if i == 0:
            d.line([tx, yy + 24, tx + 600, yy + 24], fill=BLACK, width=2)
        yy += 26

    # note
    nx = 840
    d.text((nx, 1966), "NOTE", font=F_SUB, fill=BLACK)
    note = [
        "Stroke 12 mm.  4 mm clear between the flat",
        "sides of every pair of segments (the 90 deg",
        "points leave 5.7 mm at the tips).",
        "A/G/D point base sits at the end-LED centres",
        "(x = 20/80), so those end LEDs taper into",
        "the point.",
        "Four holes D2.2 at (2.8, 2.8), (97.2, 2.8),",
        "(2.8, 167.2), (97.2, 167.2); 1 mm deep.",
        "Tips rounded R1.0 by the 2.0 mm bit.",
    ]
    for i, line in enumerate(note):
        d.text((nx, 1994 + i * 25), line, font=F_SUB, fill=BLACK)

    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    gp = os.path.join(OUT, "segments_cut.gcode")
    with open(gp, "w") as fh:
        fh.write(make_gcode())
    pp = os.path.join(OUT, "segments_cut_dimensions.png")
    make_png().save(pp)
    print(gp)
    print(pp)


if __name__ == "__main__":
    main()
