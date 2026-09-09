#!/usr/bin/env python3
"""Make7Alter.py

Photo-matched 7-segment generator variant.

This script keeps the canonical CNC output pipeline from Make7Segment for
G-code, but applies tuned geometry defaults and custom SVG/WEBP rendering so
the visual output better matches the provided 7Segment.jpg style.
"""

import os
import sys

from Make7Segment import (
    PROFILE_DEFAULTS,
    chamfer_rect_points,
    load_profile,
    make_segments,
    parse_args,
    write_gcode,
)

# Optional Pillow support for WEBP output
try:
    from PIL import Image, ImageDraw
    _HAS_PIL = True
except Exception:
    Image = None
    ImageDraw = None
    _HAS_PIL = False


def _fr(v):
    try:
        return f"{float(v):.3f}".rstrip('0').rstrip('.')
    except Exception:
        return str(v)


def _arg_given(argv, long_name):
    flag = f"--{long_name}"
    prefix = flag + "="
    for a in argv:
        if a == flag or a.startswith(prefix):
            return True
    return False


# Photo-oriented defaults used when profile/CLI do not specify values.
PHOTO_DEFAULTS = {
    'width': 44.0,
    'height': 88.0,
    'stroke': 2.0,
    'radius': 1.0,
    'gap': 2.0,
    'overlap': 0.5,
    'hgap': 2.0,
    'vert_length': 20.0,
    'hort_length': 10.0,
    'render_source': 'photo',
    'd_scale': 1.0,
    'outprefix': 'A',
}
 


def _apply_photo_defaults(args, argv):
    # Only apply geometry defaults when user did not explicitly pass the option.
    mapping = [
        ('height', 'height'),
        ('width', 'width'),
        ('stroke', 'stroke'),
        ('radius', 'radius'),
        ('gap', 'gap'),
        ('overlap', 'overlap'),
        ('hgap', 'hgap'),
        ('vert_length', 'vert-length'),
        ('hort_length', 'hort-length'),
        ('render_source', 'render-source'),
        ('d_scale', 'd-scale'),
    ]
    for attr, flag in mapping:
        # Only apply the photo default when the user didn't pass the
        # flag on the CLI and the profile did not provide this value.
        if (not _arg_given(argv, flag)) and (attr not in PROFILE_DEFAULTS):
            setattr(args, attr, PHOTO_DEFAULTS[attr])

    # Do NOT unconditionally override profile-specified `outprefix`.
    # Only use the photo default when the user did not pass `--outprefix`
    # and no profile provided one (args.outprefix is empty/None).
    if (not _arg_given(argv, 'outprefix')) and (getattr(args, 'outprefix', None) in (None, '')):
        args.outprefix = PHOTO_DEFAULTS['outprefix']

    # Keep gaps visible like the reference image unless user explicitly asked
    # for Shapely union behavior.
    if (not _arg_given(argv, 'use-shapely')) and (not _arg_given(argv, 'no-shapely')):
        args.use_shapely = False
        args.no_shapely = True


def _preload_profile_defaults(argv):
    # Parse --profile path early so parse_args() can use profile defaults.
    cli_profile = None
    for idx, a in enumerate(argv):
        if a == '--profile' and (idx + 1) < len(argv):
            cli_profile = argv[idx + 1]
            break
        if a.startswith('--profile='):
            cli_profile = a.split('=', 1)[1]
            break

    profile_path = cli_profile or ('profile.cfg' if os.path.exists('profile.cfg') else None)
    PROFILE_DEFAULTS.clear()
    if profile_path:
        PROFILE_DEFAULTS.update(load_profile(profile_path))


def _build_segments(args):
    segments = make_segments(
        args.width,
        args.height,
        args.stroke,
        args.radius,
        gap=args.gap,
        overlap=args.overlap,
        hgap=args.hgap,
        vert_length=args.vert_length,
        hort_length=args.hort_length,
        allow_vertical_overlap=args.allow_vertical_overlap,
    )
    for seg in segments:
        seg['poly'] = chamfer_rect_points(seg['x'], seg['y'], seg['w'], seg['h'], seg.get('r', 0))
    return segments


def write_photo_svg(filename, W, H, segments, margin=10):
    """Render a photo-like SVG (dark background, warm white segments)."""
    vw = W + 2 * margin
    vh = H + 2 * margin
    bg = '#6d7986'
    seg_fill = '#f1eee4'
    seg_stroke = '#d8d3c6'

    with open(filename, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fr(vw)}mm" '
            f'height="{_fr(vh)}mm" viewBox="0 0 {_fr(vw)} {_fr(vh)}">\n'
        )
        f.write(f'<rect x="0" y="0" width="{_fr(vw)}" height="{_fr(vh)}" fill="{bg}" />\n')
        f.write(f'<g transform="translate({_fr(margin)},{_fr(margin)})">\n')
        for seg in segments:
            pts = seg.get('poly')
            if not pts:
                continue
            pts_s = ' '.join([f"{_fr(x)},{_fr(y)}" for (x, y) in pts])
            f.write(
                f'<polygon points="{pts_s}" fill="{seg_fill}" '
                f'stroke="{seg_stroke}" stroke-width="0.30" />\n'
            )
        f.write('</g>\n')
        f.write('</svg>\n')


def write_photo_webp(filename, W, H, segments, margin=10, scale=8):
    """Render a photo-like WEBP using supersampling for smoother edges."""
    if not _HAS_PIL:
        raise RuntimeError('Pillow not available; install with pip install pillow')

    bg = (109, 121, 134)
    seg_fill = (241, 238, 228)
    seg_stroke = (214, 209, 196)

    out_w = int((W + 2 * margin) * scale)
    out_h = int((H + 2 * margin) * scale)
    ss = 4
    hi_w = out_w * ss
    hi_h = out_h * ss

    img = Image.new('RGB', (hi_w, hi_h), color=bg)
    draw = ImageDraw.Draw(img)

    for seg in segments:
        pts = seg.get('poly')
        if not pts:
            continue
        poly = [((margin + x) * scale * ss, (margin + y) * scale * ss) for (x, y) in pts]
        draw.polygon(poly, fill=seg_fill, outline=seg_stroke)

    img = img.resize((out_w, out_h), Image.Resampling.LANCZOS)
    img.save(filename, format='WEBP', quality=96, method=6)


def write_photo_svg_with_points(filename, W, H, segments, margin=10):
    """Render the photo-like SVG and annotate each polygon vertex with a point
    number and the segment name for easy inspection.
    """
    vw = W + 2 * margin
    vh = H + 2 * margin
    bg = '#6d7986'
    seg_fill = '#f1eee4'
    seg_stroke = '#d8d3c6'
    point_fill = '#e03a3a'
    text_fill = '#111111'

    with open(filename, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fr(vw)}mm" '
            f'height="{_fr(vh)}mm" viewBox="0 0 {_fr(vw)} {_fr(vh)}">\n'
        )
        f.write(f'<rect x="0" y="0" width="{_fr(vw)}" height="{_fr(vh)}" fill="{bg}" />\n')
        f.write(f'<g transform="translate({_fr(margin)},{_fr(margin)})">\n')

        for seg in segments:
            pts = seg.get('poly')
            if not pts:
                continue
            pts_s = ' '.join([f"{_fr(x)},{_fr(y)}" for (x, y) in pts])
            f.write(
                f'<polygon points="{pts_s}" fill="{seg_fill}" '
                f'stroke="{seg_stroke}" stroke-width="0.30" />\n'
            )

            # annotate points
            for i, (x, y) in enumerate(pts):
                cx = _fr(x)
                cy = _fr(y)
                # small red circle for the point
                f.write(f'<circle cx="{cx}" cy="{cy}" r="0.55" fill="{point_fill}" />\n')
                # numeric label offset slightly right/down
                lx = _fr(x + 1.0)
                ly = _fr(y + 1.0)
                f.write(
                    f'<text x="{lx}" y="{ly}" font-size="2.0" fill="{text_fill}">{seg.get("name","?")}{i}</text>\n'
                )

            # segment name near centroid
            try:
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                f.write(
                    f'<text x="{_fr(cx)}" y="{_fr(cy - 2.0)}" font-size="3.0" fill="{text_fill}" '
                    f'font-weight="bold">{seg.get("name","?")}</text>\n'
                )
            except Exception:
                pass

        f.write('</g>\n')
        f.write('</svg>\n')


def main():
    argv = sys.argv[1:]
    _preload_profile_defaults(argv)
    args = parse_args()
    _apply_photo_defaults(args, argv)

    W = float(args.width)
    H = float(args.height)
    segments = _build_segments(args)

    # Apply user-specified vertex removals so selected edges become
    # single straight lines. Remove by zero-based point indices as
    # shown in the annotated `<out>_points.svg` file.
    removals = {
        'A': (3, 6),
        'B': (0,),
        'F': (1,),
        'C': (5,),
        'E': (4,),
    }

    # Join (merge) specific vertex pairs by replacing the pair with
    # their midpoint (so both indices become a single vertex).
    joins = {
        'G': ((6, 7), (2, 3)),
        'C': ((0, 1),),
        'E': ((0, 1),),
        'B': ((3, 4),),
        'F': ((3, 4),),
        # Merge D2 and D3 into a single vertex (midpoint)
        # Also merge D5 and D6 into a single vertex
        'D': ((2, 3), (5, 6)),
    }

    for seg in segments:
        name = seg.get('name')
        pts = seg.get('poly', [])
        if not pts:
            continue

        # First apply removals (delete single indices)
        if name in removals and len(pts) >= 8:
            remove_idxs = set(removals[name])
            pts = [p for i, p in enumerate(pts) if i not in remove_idxs]

        # Then apply joins (merge index pairs into midpoint)
        if name in joins and len(pts) >= 2:
            # Build a map of index -> (new_point or None) and skip set
            skip = set()
            new_pts = []
            # We must handle indices relative to the current pts list.
            # The join tuples are given in the original (pre-removal)
            # indexing. To be resilient, clamp indices to current length
            # and ignore invalid pairs.
            # Convert join pairs to operate on current-length indices
            for pair in joins[name]:
                i, j = pair
                if i == j:
                    continue
                if i < 0 or j < 0:
                    continue
            # We'll process by iterating indices and merging when a pair matches
            pair_map = {}
            for pair in joins[name]:
                i, j = pair
                # normalize so i < j
                if i > j:
                    i, j = j, i
                if i < len(pts) and j < len(pts):
                    pair_map[i] = j

            idx = 0
            while idx < len(pts):
                if idx in pair_map:
                    j = pair_map[idx]
                    # compute midpoint
                    x1, y1 = pts[idx]
                    x2, y2 = pts[j]
                    mx = (x1 + x2) / 2.0
                    my = (y1 + y2) / 2.0
                    new_pts.append((mx, my))
                    # skip over the paired index
                    # if j == idx+1 we move idx by 2, else mark j to skip
                    if j == idx + 1:
                        idx += 2
                    else:
                        # mark j as effectively removed; continue with next
                        # we'll skip j when we reach it
                        skip.add(j)
                        idx += 1
                else:
                    if idx in skip:
                        idx += 1
                        continue
                    new_pts.append(pts[idx])
                    idx += 1

            pts = new_pts

        # write back modified polygon
        seg['poly'] = pts

    # No explicit D merges; D remains as generated by canonical geometry.

    # Specific geometric tweak for Segment A per user request:
    # - keep the A2->A3 chamfer vector unchanged (preserve its angle/length)
    # - extend A1 to the right by half of the current A1->A2 length
    # - shorten the A1->A2 segment to half its original length (along same direction)
    for seg in segments:
        if seg.get('name') == 'A':
            pts = seg.get('poly', [])
            if len(pts) >= 4:
                # indices: A0=0, A1=1, A2=2, A3=3, A4=4, A5=5
                x1, y1 = pts[1]
                x2, y2 = pts[2]
                x3, y3 = pts[3]

                vx = x2 - x1
                vy = y2 - y1
                import math
                L = math.hypot(vx, vy)
                if L > 1e-9:
                    L2 = L / 2.0
                    ux = vx / L
                    uy = vy / L

                    # move A1 right by dx = L/2 (along +x axis)
                    new_x1 = x1 + (L / 2.0)
                    new_y1 = y1

                    # new A2 = new A1 + unit_vector * L2
                    new_x2 = new_x1 + ux * L2
                    new_y2 = new_y1 + uy * L2

                    # Keep A3 at its previous absolute position; only
                    # update A1 and A2 as requested.
                    pts[1] = (new_x1, new_y1)
                    pts[2] = (new_x2, new_y2)
                    seg['poly'] = pts
    # Apply the symmetric logic to the left/top side: A0, A5, A4.
    for seg in segments:
        if seg.get('name') == 'A':
            pts = seg.get('poly', [])
            if len(pts) >= 6:
                x0, y0 = pts[0]
                x5, y5 = pts[5]
                x4, y4 = pts[4]
                import math
                vx = x5 - x0
                vy = y5 - y0
                L = math.hypot(vx, vy)
                if L > 1e-9:
                    L2 = L / 2.0
                    ux = vx / L
                    uy = vy / L

                    # move A0 left by L/2
                    new_x0 = x0 - (L / 2.0)
                    new_y0 = y0

                    # new A5 = new A0 + unit_vector * L2
                    new_x5 = new_x0 + ux * L2
                    new_y5 = new_y0 + uy * L2

                    # keep A4 fixed (do not move)
                    pts[0] = (new_x0, new_y0)
                    pts[5] = (new_x5, new_y5)
                    seg['poly'] = pts

    # Apply the same pair of transforms to Segment D:
    # - for indices D1 (1), D2 (2), D3 (3): move D1 right by half D1->D2,
    #   shorten D1->D2 to half, keep D3 fixed.
    # - for indices D0 (0), D5 (5), D4 (4): move D0 left by half D0->D5,
    #   shorten D0->D5 to half, keep D4 fixed.
    # D-specific transforms removed; D will use canonical geometry.

    # Make D a scaled copy of A (minor of A) so shapes match but D is
    # slightly smaller. Scale factor controlled by args.d_scale.
    # No D scaling: keep segment D as computed by canonical geometry.

    # After joins, adjust D4 to align X with D0 and Y with D3
    for seg in segments:
        if seg.get('name') == 'D':
            pts = seg.get('poly', [])
            # Ensure we have at least 5 points after merges
            if len(pts) > 4:
                try:
                    x0, y0 = pts[0]
                    x3, y3 = pts[3]
                    # Set D4.x = D0.x, D4.y = D3.y
                    pts[4] = (x0, y3)
                    seg['poly'] = pts
                except Exception:
                    pass

    # Segment D additional tweaks per user request:
    # - Keep D1 fixed
    # - Preserve D1->D2 angle, extend D2 further along that direction
    # - Move D3 to the right, then reduce the D2->D3 span by half
    for seg in segments:
        if seg.get('name') == 'D':
            pts = seg.get('poly', [])
            if len(pts) > 3:
                try:
                    import math

                    x1, y1 = pts[1]
                    x2, y2 = pts[2]
                    x3, y3 = pts[3]

                    # keep D1 unchanged (pts[1] stays as is)

                    # vector from D1 to D2
                    vx = x2 - x1
                    vy = y2 - y1
                    L = math.hypot(vx, vy)
                    if L > 1e-9:
                        ux = vx / L
                        uy = vy / L

                        # extend D2 along the same angle by 50% (L -> 1.5L)
                        new_L = L * 1.5
                        new_x2 = x1 + ux * new_L
                        new_y2 = y1 + uy * new_L

                        # move D3 to the right by a small offset proportional to L
                        right_offset = L * 0.25
                        prov_x3 = x3 + right_offset
                        prov_y3 = y3

                        # compute provisional vector from new D2 to provisional D3
                        pvx = prov_x3 - new_x2
                        pvy = prov_y3 - new_y2

                        # reduce that vector length by half
                        final_x3 = new_x2 + pvx * 0.5
                        final_y3 = new_y2 + pvy * 0.5

                        # write back updated points
                        pts[2] = (new_x2, new_y2)
                        pts[3] = (final_x3, final_y3)
                        # enforce D3.y == D4.y per user request
                        if len(pts) > 4:
                            try:
                                dx3, dy3 = pts[3]
                                dx4, dy4 = pts[4]
                                pts[3] = (dx3, dy4)
                            except Exception:
                                pass
                        seg['poly'] = pts
                except Exception:
                    pass

    # Now apply D-side edits for D0/D5/D4 per user request:
    # - do not move D0
    # - preserve D0->D5 angle, extend D5 down/left along that direction
    # - extend D4 to left, keep D4.y same as D3.y
    # - reduce the D5->D4 distance by half
    for seg in segments:
        if seg.get('name') == 'D':
            pts = seg.get('poly', [])
            if len(pts) > 5:
                try:
                    import math

                    x0, y0 = pts[0]
                    x3, y3 = pts[3]
                    x4, y4 = pts[4]
                    x5, y5 = pts[5]

                    # direction from D0 to D5
                    vx = x5 - x0
                    vy = y5 - y0
                    L = math.hypot(vx, vy)
                    if L > 1e-9:
                        ux = vx / L
                        uy = vy / L

                        # extend D5 along same direction by 50%
                        new_L5 = L * 1.5
                        new_x5 = x0 + ux * new_L5
                        new_y5 = y0 + uy * new_L5

                        # provisional move D4 left by a fraction of L
                        left_offset = L * 0.25
                        prov_x4 = x4 - left_offset
                        prov_y4 = y4

                        # vector from new D5 to provisional D4
                        pvx = prov_x4 - new_x5
                        pvy = prov_y4 - new_y5

                        # reduce that span by half
                        final_x4 = new_x5 + pvx * 0.5
                        final_y4 = new_y5 + pvy * 0.5

                        # enforce D4.y == D3.y
                        final_x4 = final_x4
                        final_y4 = y3

                        # commit updates (D0 unchanged)
                        pts[5] = (new_x5, new_y5)
                        pts[4] = (final_x4, final_y4)
                        seg['poly'] = pts
                except Exception:
                    pass

    # Align A points to D X coordinates per user request:
    # Set A1.x = D3.x and A2.x = D2.x (preserve original Y values)
    d_x0 = d_x2 = d_x3 = d_x4 = d_x5 = None
    for seg in segments:
        if seg.get('name') == 'D':
            dpts = seg.get('poly', [])
            if len(dpts) > 5:
                d_x0 = dpts[0][0]
                d_x2 = dpts[2][0]
                d_x3 = dpts[3][0]
                d_x4 = dpts[4][0]
                d_x5 = dpts[5][0]
            elif len(dpts) > 3:
                d_x2 = dpts[2][0]
                d_x3 = dpts[3][0]
            break

    if d_x2 is not None and d_x3 is not None:
        for seg in segments:
            if seg.get('name') == 'A':
                apts = seg.get('poly', [])
                if len(apts) > 2:
                    ay1 = apts[1][1]
                    ay2 = apts[2][1]
                    apts[1] = (d_x3, ay1)
                    apts[2] = (d_x2, ay2)
                    # also align A0.x to D4.x and A5.x to D5.x if available
                    if d_x4 is not None and len(apts) > 0:
                        apts[0] = (d_x4, apts[0][1])
                    if d_x5 is not None and len(apts) > 5:
                        apts[5] = (d_x5, apts[5][1])
                    seg['poly'] = apts
                break

    # Adjust Segment B per user request:
    # - keep B5 unchanged
    # - extend B0 up and right, extend B1 up (keep B1.x unchanged)
    # - then reduce the B0-B1 distance to half while keeping B1.x fixed
    for seg in segments:
        if seg.get('name') == 'B':
            bpts = seg.get('poly', [])
            if len(bpts) > 5:
                try:
                    import math
                    x0, y0 = bpts[0]
                    x1, y1 = bpts[1]
                    x5, y5 = bpts[5]

                    # original distance between B0 and B1
                    L = math.hypot(x1 - x0, y1 - y0)
                    if L < 1e-9:
                        continue

                    # offsets proportional to L
                    right_offset = L * 0.25
                    up_offset = L * 0.25

                    # provisional moves: B0 moves up (y - up_offset) and right (+right_offset)
                    prov_x0 = x0 + right_offset
                    prov_y0 = y0 - up_offset

                    # B1 moves up; x remains unchanged
                    prov_x1 = x1
                    prov_y1 = y1 - up_offset

                    # compute vector from provisional B0 to provisional B1
                    vx = prov_x1 - prov_x0
                    vy = prov_y1 - prov_y0

                    # shorten that vector by half, keeping B1.x fixed (we move B0 towards B1)
                    final_x1 = prov_x1
                    final_y1 = prov_y1
                    final_x0 = final_x1 - vx * 0.5
                    final_y0 = final_y1 - vy * 0.5

                    # commit: keep B5 unchanged
                    bpts[0] = (final_x0, final_y0)
                    bpts[1] = (final_x1, final_y1)
                    bpts[5] = (x5, y5)
                    seg['poly'] = bpts
                except Exception:
                    pass

    # Re-orient the line between B0 and B5 to match the angle of A2->A3.
    # Keep B5 fixed. Only move B0 and B1 (B1.x unchanged).
    # Compute angle from A2->A3, rotate B0 around B5 to that angle preserving distance.
    a2 = a3 = None
    for seg in segments:
        if seg.get('name') == 'A':
            apts = seg.get('poly', [])
            if len(apts) > 3:
                a2 = apts[2]
                a3 = apts[3]
            break

    if a2 is not None and a3 is not None:
        for seg in segments:
            if seg.get('name') == 'B':
                bpts = seg.get('poly', [])
                if len(bpts) > 5:
                    try:
                        import math
                        x0, y0 = bpts[0]
                        x1, y1 = bpts[1]
                        x5, y5 = bpts[5]

                        # angle of A2->A3
                        theta = math.atan2(a3[1] - a2[1], a3[0] - a2[0])

                        # preserve distance from B5 to B0
                        r = math.hypot(x5 - x0, y5 - y0)

                        # new B0 so that vector B0->B5 has angle theta
                        new_x0 = x5 - r * math.cos(theta)
                        new_y0 = y5 - r * math.sin(theta)

                        # provisional B1: keep x, move up by same up_offset as before
                        up_offset = math.hypot(x1 - x0, y1 - y0) * 0.25
                        prov_x1 = x1
                        prov_y1 = y1 - up_offset

                        # vector from new B0 to provisional B1
                        vx = prov_x1 - new_x0
                        vy = prov_y1 - new_y0
                        target = 0.5 * math.hypot(vx, vy)

                        dx = prov_x1 - new_x0
                        # solve for y such that distance^2 = target^2
                        rem = target * target - dx * dx
                        if rem >= 0:
                            sign = -1 if prov_y1 < new_y0 else 1
                            final_y1 = new_y0 + sign * math.sqrt(rem)
                        else:
                            # fallback: use provisional y
                            final_y1 = prov_y1

                        # assign B0 and B1 (keep B1.x unchanged)
                        bpts[0] = (new_x0, new_y0)
                        bpts[1] = (x1, final_y1)
                        seg['poly'] = bpts
                    except Exception:
                        pass
                break

    # Align Segment F per user request:
    # - keep F1 position unchanged
    # - keep F5.x unchanged (we keep F5 fully fixed for stability)
    # - move F0 so that the line F1->F0 has the same angle as A4->A5
    # - ensure the distance F0-F5 is half its original length
    a4 = a5 = None
    for seg in segments:
        if seg.get('name') == 'A':
            apts = seg.get('poly', [])
            if len(apts) > 5:
                a4 = apts[4]
                a5 = apts[5]
            break

    if a4 is not None and a5 is not None:
        for seg in segments:
            if seg.get('name') == 'F':
                fpts = seg.get('poly', [])
                if len(fpts) > 5:
                    try:
                        import math

                        x0, y0 = fpts[0]
                        x1, y1 = fpts[1]
                        x5, y5 = fpts[5]

                        # find B0.y and B1.y to align F5.y and F0.y
                        b0y = None
                        b1y = None
                        for s in segments:
                            if s.get('name') == 'B':
                                bpts = s.get('poly', [])
                                if len(bpts) > 1:
                                    b0y = bpts[0][1]
                                    b1y = bpts[1][1]
                                break

                        # desired target distance between F0 and F5 is half the current
                        r = math.hypot(x0 - x5, y0 - y5)
                        target = r * 0.5

                        # set F5.y to B1.y if available, keep F5.x unchanged
                        new_x5 = x5
                        new_y5 = b1y if (b1y is not None) else y5

                        # set F0.y to B0.y if available
                        new_y0 = b0y if (b0y is not None) else y0

                        # solve for new_x0 such that distance between (new_x0,new_y0) and (new_x5,new_y5) == target
                        dy = new_y0 - new_y5
                        rem = target * target - dy * dy
                        if rem >= 0:
                            dx = math.sqrt(rem)
                            # choose side consistent with original x0 relative to x5
                            if x0 < x5:
                                new_x0 = new_x5 - dx
                            else:
                                new_x0 = new_x5 + dx
                        else:
                            # fallback: move halfway in x towards x5
                            new_x0 = new_x5 + (x0 - new_x5) * 0.5

                        # apply changes: keep F1 unchanged, set F0 and F5 as computed
                        fpts[0] = (new_x0, new_y0)
                        fpts[5] = (new_x5, new_y5)
                        seg['poly'] = fpts
                    except Exception:
                        pass
                break

    # Adjust Segment C per user request:
    # - C4 stays fixed
    # - C2.x stays the same, C2.y may change
    # - C3 changes
    # - reduce the C2-C3 span by half (move both toward each other vertically while keeping C2.x)
    # - angle of C4->C3 should match angle of D1->D2
    d1 = d2 = None
    for seg in segments:
        if seg.get('name') == 'D':
            dpts = seg.get('poly', [])
            if len(dpts) > 2:
                d1 = dpts[1]
                d2 = dpts[2]
            break

    if d1 is not None and d2 is not None:
        import math
        theta_cd = math.atan2(d2[1] - d1[1], d2[0] - d1[0])
        cos_td = math.cos(theta_cd)
        sin_td = math.sin(theta_cd)

        for seg in segments:
            if seg.get('name') == 'C':
                cpts = seg.get('poly', [])
                if len(cpts) > 4:
                    try:
                        # indices: C0..C5 ; we care about C2 (index 2), C3 (3), C4 (4)
                        x2, y2 = cpts[2]
                        x3, y3 = cpts[3]
                        x4, y4 = cpts[4]

                        # preserve C4
                        # preserve original C2-C3 length
                        orig_len = math.hypot(x3 - x2, y3 - y2)


                        # compute unit vector along C4->C3 (preserve this angle)
                        ux = (x3 - x4)
                        uy = (y3 - y4)
                        ul = math.hypot(ux, uy)
                        if ul < 1e-9:
                            ul = 1.0
                        ux /= ul
                        uy /= ul

                        # project vector from C4 to C2 onto this unit vector to get r_proj
                        vx = x2 - x4
                        vy = y2 - y4
                        r_proj = vx * ux + vy * uy

                        # place C3 at projection distance along the preserved angle
                        new_x3 = x4 + r_proj * ux
                        new_y3 = y4 + r_proj * uy

                        # now set target distance is half original
                        target = orig_len * 0.5

                        # compute horizontal offset between C2.x and new C3.x
                        dx = new_x3 - x2
                        rem = target * target - dx * dx
                        if rem >= 0:
                            dy = math.sqrt(rem)
                            # choose new C2.y above C3 (smaller y value)
                            new_y2 = new_y3 - dy
                        else:
                            # if impossible, fall back to moving C2 partly toward new_y3
                            new_y2 = y2 + 0.25 * (new_y3 - y2)

                        # write back: keep C4 unchanged
                        cpts[2] = (x2, new_y2)
                        cpts[3] = (new_x3, new_y3)
                        # cpts[4] remains (x4,y4)
                        seg['poly'] = cpts
                    except Exception:
                        pass
                break

    prefix = args.outprefix or 'example_output'
    margin = 10

    svgfn = prefix + '.svg'
    gfn = prefix + '.gcode'
    webpfn = prefix + '.webp'

    points_svgfn = prefix + '_points.svg'

    # SVG / WEBP renderings are custom photo-like style.
    write_photo_svg(svgfn, W, H, segments, margin=margin)
    print(f"Wrote {svgfn}")

    # Also write an annotated SVG that labels each polygon vertex.
    write_photo_svg_with_points(points_svgfn, W, H, segments, margin=margin)
    print(f"Wrote {points_svgfn}")

    # CNC output uses the same polygons for geometric consistency.
    if args.depth is not None:
        cut_depth = float(args.depth)
    else:
        cut_depth = float(args.board_thickness)

    if args.passdepth is not None:
        pass_depth = float(args.passdepth)
    else:
        pass_depth = cut_depth / max(1, int(args.cutting_paths))

    board_h = float(args.board_height)
    board_w = float(args.board_width) if (args.board_width is not None) else (W + 2.0 * margin)

    write_gcode(
        gfn,
        W,
        H,
        segments,
        bit_dia=args.bit,
        cut_depth=cut_depth,
        pass_depth=pass_depth,
        feed=args.feed,
        plunge=args.plunge,
        show_board=args.show_board_dim,
        board_w=board_w,
        board_h=board_h,
        margin=margin,
        rotate=args.rotate,
        spindle_speed=args.spindle_speed,
        pause_after_segment=args.pause_after_seg,
        pause_after_layer=args.pause_after_layer,
        debug_gcode=args.debug_gcode,
        pocket_middle=args.pocket_middle,
        pocket_step=args.pocket_step,
        pocket_inset=args.pocket_inset,
    )
    print(f"Wrote {gfn}")

    if _HAS_PIL:
        write_photo_webp(webpfn, W, H, segments, margin=margin, scale=8)
        print(f"Wrote {webpfn}")
    else:
        print('Skipped WEBP: Pillow not installed in current Python environment.')


if __name__ == '__main__':
    main()
