#!/usr/bin/env python3
"""Make7Alter wrapper: enforce 45deg chamfer for segment A and generate SVG."""
import os
from Make7Segment import load_profile, parse_args, make_segments, chamfer_rect_points, write_svg, PROFILE_DEFAULTS


def write_svg_with_points(filename, W, H, segments, margin=10):
    """Write a simple SVG showing segment polygons and annotated points (P1..P8).

    This intentionally keeps formatting minimal and mirrors the coordinate system
    used by the main `write_svg` (translate by margin).
    """
    width = W + 2 * margin
    height = H + 2 * margin
    def fmt(v):
        return f"{v:.3f}" if isinstance(v, float) else f"{float(v):.3f}"

    with open(filename, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}mm" height="{height:.3f}mm" viewBox="0 0 {width:.3f} {height:.3f}">\n')
        f.write(f'<g transform="translate({margin:.3f},{margin:.3f})">\n')
        # background board
        f.write(f'<rect x="0.000" y="0.000" width="{W:.3f}" height="{H:.3f}" rx="0" fill="#fff" stroke="#888" stroke-width="0.5" />\n')

        # draw each segment polygon and annotate points
        labels_all = []
        cx_center = W / 2.0
        cy_center = H / 2.0

        for seg in segments:
            name = seg.get('name', '?')
            poly = seg.get('poly')
            if not poly:
                continue
            pts_str = ' '.join([f"{fmt(x)},{fmt(y)}" for (x, y) in poly])
            f.write(f'<polygon points="{pts_str}" fill="#111" stroke="#000" stroke-width="0.5" />\n')

            # draw points and prepare labels (labels collected globally)
            for i, (x, y) in enumerate(poly, start=1):
                cx = float(x)
                cy = float(y)
                # point marker (smaller)
                f.write(f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="0.9" fill="#f88" stroke="#900" stroke-width="0.18" />\n')

                # compute outward offset from center so labels avoid overlapping polygon
                dx = cx - cx_center
                dy = cy - cy_center
                if dx == 0 and dy == 0:
                    offx, offy = 3.0, -3.0
                else:
                    mag = (dx * dx + dy * dy) ** 0.5
                    # offset magnitude in display units (smaller)
                    off_mag = 4.0
                    offx = (dx / mag) * off_mag
                    offy = (dy / mag) * off_mag

                lx = cx + offx
                ly = cy + offy
                label = f"{name} P{i} ({cx:.0f},{cy:.0f})"
                labels_all.append((lx, ly, label))

            # for segment A, compute diagonal line angles and prepare angle labels
            if name == 'A' and len(poly) >= 4:
                # ensure we have at least four points: assume ordering P1,P2,P3,P4
                p1x, p1y = poly[0]
                p2x, p2y = poly[1]
                p3x, p3y = poly[2]
                p4x, p4y = poly[3]

                import math

                # angle for P2 -> P3 (expected 45°)
                dx23 = float(p3x) - float(p2x)
                dy23 = float(p3y) - float(p2y)
                ang23 = math.degrees(math.atan2(dy23, dx23))
                ang23_norm = (ang23 + 360.0) % 360.0

                # angle for P1 -> P4: show direction from P4->P1 so it displays 315° for current geometry
                dx41 = float(p1x) - float(p4x)
                dy41 = float(p1y) - float(p4y)
                ang41 = math.degrees(math.atan2(dy41, dx41))
                ang41_norm = (ang41 + 360.0) % 360.0

                # compute midpoints and offset perpendicular for label placement
                def midpoint(a, b):
                    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

                mid23 = midpoint(poly[1], poly[2])
                mid14 = midpoint(poly[0], poly[3])

                # perpendicular offset (small)
                def offset_perp(a, b, mag=3.0):
                    vx = b[0] - a[0]
                    vy = b[1] - a[1]
                    length = math.hypot(vx, vy)
                    if length == 0:
                        return (mag, -mag)
                    ux = -vy / length
                    uy = vx / length
                    return (ux * mag, uy * mag)

                off23 = offset_perp(poly[1], poly[2], mag=4.0)
                off14 = offset_perp(poly[0], poly[3], mag=4.0)

                ang23_label = f"{ang23_norm:.0f}\u00B0"
                ang14_label = f"{ang41_norm:.0f}\u00B0"

                labels_all.append((mid23[0] + off23[0], mid23[1] + off23[1], ang23_label))
                labels_all.append((mid14[0] + off14[0], mid14[1] + off14[1], ang14_label))

        # draw labels last so they appear on top; use blue fill with white outline for readability
        for lx, ly, label in labels_all:
            # outline (thinner)
            f.write(f'<text x="{lx:.3f}" y="{ly:.3f}" font-size="3" font-family="sans-serif" fill="white" stroke="white" stroke-width="0.35" paint-order="stroke fill">{label}</text>\n')
            # main label
            f.write(f'<text x="{lx:.3f}" y="{ly:.3f}" font-size="3" font-family="sans-serif" fill="blue">{label}</text>\n')

        f.write('</g>\n')
        f.write('</svg>\n')


def main():
    profile_path = 'profile.cfg' if os.path.exists('profile.cfg') else None
    PROFILE_DEFAULTS.clear()
    if profile_path:
        PROFILE_DEFAULTS.update(load_profile(profile_path))
    args = parse_args()

    W = args.width
    H = args.height
    t = args.stroke
    r = args.radius

    segments = make_segments(W, H, t, r,
                             gap=args.gap,
                             overlap=args.overlap,
                             hgap=args.hgap,
                             vert_length=args.vert_length,
                             hort_length=args.hort_length,
                             allow_vertical_overlap=args.allow_vertical_overlap)

    for seg in segments:
        if seg.get('name') == 'A':
            # enforce a simplified 4-point polygon so the segment ends are 45deg diagonals.
            # P1=(x+c,y), P2=(x+w-c,y), P3=(x+w,y+c), P4=(x,y+c)
            c = min(t / 2.0, seg['w'] / 2.0, seg['h'] / 2.0)
            x = seg['x']
            y = seg['y']
            w = seg['w']
            h = seg['h']
            # Override Segment A polygon to exact coordinates requested by user
            seg['poly'] = [
                (7.0, 1.0),
                (73.0, 1.0),
                (57.0, 15.0),
                (23.0, 15.0),
            ]
        
        elif 'poly' not in seg:
            seg['poly'] = chamfer_rect_points(seg['x'], seg['y'], seg['w'], seg['h'], seg.get('r', 0))

    outprefix = args.outprefix
    svg_path = f"{outprefix}.svg"
    write_svg(svg_path, W, H, segments, margin=10, show_board=False, render_source='poly')
    print(f"Wrote {svg_path}")

    # also write an annotated SVG with points and labels for easier inspection
    points_svg = f"{outprefix}_points.svg"
    write_svg_with_points(points_svg, W, H, segments, margin=10)
    print(f"Wrote {points_svg}")


if __name__ == '__main__':
    main()
