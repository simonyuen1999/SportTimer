#!/usr/bin/env python3
"""Make7Alter.py

Photo-matched 7-segment generator variant.

This script keeps the canonical CNC output pipeline from Make7Segment for
G-code, but applies tuned geometry defaults and custom SVG/WEBP rendering so
the visual output better matches the provided 7Segment.jpg style.
"""

import os
import sys
import configparser

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
    # photo transform parameters (can be overridden via profile)
    'extend_factor': 1.5,
    'shift_frac': 0.25,
    'reduce_frac': 0.5,
    'move_partway_frac': 0.5,
    # two-digit options
    'two_digit': False,
    'two_digit_gap': 20.0,
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
        ('extend_factor', 'extend-factor'),
        ('shift_frac', 'shift-frac'),
        ('reduce_frac', 'reduce-frac'),
        ('move_partway_frac', 'move-partway-frac'),
        ('two_digit', 'two-digit'),
        ('two_digit_gap', 'two-digit-gap'),
    ]
    for attr, flag in mapping:
        # If the profile provided a value for this attribute and the
        # user didn't pass the CLI flag, prefer the profile value.
        if (not _arg_given(argv, flag)) and (attr in PROFILE_DEFAULTS):
            setattr(args, attr, PROFILE_DEFAULTS[attr])
        # Otherwise, if no profile and no CLI flag, apply the photo default.
        elif (not _arg_given(argv, flag)) and (attr not in PROFILE_DEFAULTS):
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
    if not profile_path:
        return

    # Try to use the canonical loader from Make7Segment; if the profile
    # contains duplicate options configparser in strict mode will raise
    # DuplicateOptionError. To avoid modifying Make7Segment.py (preserve
    # backward compatibility), fall back to a tolerant parse here that
    # accepts duplicate keys (last-one-wins) and normalizes keys like
    # load_profile() does.
    try:
        PROFILE_DEFAULTS.update(load_profile(profile_path))
        return
    except Exception as e:
        # If load_profile raised DuplicateOptionError or similar, attempt
        # a non-strict parse locally and build a compatible dict.
        try:
            cfg = configparser.ConfigParser(strict=False)
            cfg.read(profile_path)
            if 'profile' not in cfg:
                return
            sec = cfg['profile']
            out = {}
            # lightweight type converters mirroring Make7Segment.load_profile
            type_map = {
                'height': float,
                'width': float,
                'stroke': float,
                'radius': float,
                'bit': float,
                'depth': float,
                'passdepth': float,
                'board_thickness': float,
                'cutting_paths': int,
                'board_height': float,
                'board_width': float,
                'board_outline': str,
                'outprefix': str,
                'spindle_speed': int,
                'feed': float,
                'plunge': float,
                'gap': float,
                'overlap': float,
                'hgap': float,
                'vert_length': float,
                'hort_length': float,
                'render_source': str,
                'rough_bit': float,
                'rough_step': float,
                'pocket_step': float,
                'pocket_inset': float,
                'rough_feed': float,
            }
            boolean_keys = set([
                'show_board_dim', 'debug_centers', 'allow_vertical_overlap', 'pause_after_seg', 'pause_after_layer', 'debug_gcode', 'use_shapely', 'no_shapely', 'rotate', 'pocket_middle', 'rough_last'
            ])

            for raw_key in sec:
                key = raw_key.replace('-', '_')
                raw = sec.get(raw_key)
                if raw is None:
                    continue
                raw = raw.strip()
                if raw == '':
                    continue
                try:
                    if key in boolean_keys:
                        val = cfg.getboolean('profile', raw_key)
                    else:
                        conv = type_map.get(key, str)
                        val = conv(raw)
                except Exception:
                    val = raw
                out[key] = val

            PROFILE_DEFAULTS.update(out)
            return
        except Exception:
            # give up silently and leave PROFILE_DEFAULTS empty
            return


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


def write_photo_webp(filename, W, H, segments, margin=10, scale=8, bit_dia=None):
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

    green = (0, 200, 0)
    for seg in segments:
        pts = seg.get('poly')
        if not pts:
            continue
        poly = [((margin + x) * scale * ss, (margin + y) * scale * ss) for (x, y) in pts]

        # Draw cutter footprint (approx) as a wide green stroke around the polygon
        try:
            if bit_dia is not None and float(bit_dia) > 0:
                stroke_px = float(bit_dia) * scale * ss
                # use draw.line with closed path to simulate a band
                int_width = max(1, int(round(stroke_px)))
                draw.line(poly + [poly[0]], fill=green, width=int_width)
        except Exception:
            pass

        # draw the original segment on top so the visual matches real part
        draw.polygon(poly, fill=seg_fill, outline=seg_stroke)

    img = img.resize((out_w, out_h), Image.Resampling.LANCZOS)
    img.save(filename, format='WEBP', quality=96, method=6)


def write_show_dim_webp(filename, W, H, segments, board_w, board_h, summary_lines, margin=10, scale=8, two_digit=False, per_digit_w=None, two_digit_gap=0.0):
    """Render a black-and-white line-only WEBP showing board/digit outlines and overlay summary text."""
    if not _HAS_PIL:
        raise RuntimeError('Pillow not available; install with pip install pillow')
    # Reserve extra space to the right for board/digit labels, and space
    # at the bottom for the summary text so everything fits comfortably.
    bottom_mm = max(24, len(summary_lines) * 6)
    extra_right_mm = max(40, 6 * scale)  # mm of extra space to the right
    canvas_mm_w = (W + 2 * margin + extra_right_mm)
    canvas_mm_h = (H + 2 * margin + bottom_mm)
    out_w = int(canvas_mm_w * scale)
    out_h = int(canvas_mm_h * scale)
    img = Image.new('RGB', (out_w, out_h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # compute centering offsets so the digit/block sits in the page center
    left_offset_mm = extra_right_mm / 2.0
    top_offset_mm = bottom_mm / 2.0
    def _tx(x, y):
        return ((margin + left_offset_mm + x) * scale, (margin + top_offset_mm + y) * scale)

    # draw digit bounding box
    dbp = [(0.0, 0.0), (W, 0.0), (W, H), (0.0, H), (0.0, 0.0)]
    pts = [_tx(x, y) for (x, y) in dbp]
    draw.line(pts, fill=(0, 0, 0), width=1)

    # draw segment outlines as lines
    for seg in segments:
        poly = seg.get('poly')
        if not poly:
            continue
        tx_pts = [_tx(x, y) for (x, y) in poly]
        if len(tx_pts) > 1:
            draw.line(tx_pts + [tx_pts[0]], fill=(0, 0, 0), width=1)

    # draw board perimeter if provided
    try:
        off_x = -((board_w - W) / 2.0)
        off_y = -((board_h - H) / 2.0)
        bp = [(off_x, off_y), (off_x + board_w, off_y), (off_x + board_w, off_y + board_h), (off_x, off_y + board_h), (off_x, off_y)]
        bpts = [_tx(x, y) for (x, y) in bp]
        draw.line(bpts, fill=(0, 0, 0), width=1)
    except Exception:
        pass

    # helper to format coordinates
    def _fmt(x, y):
        try:
            return f"({x:.3f},{y:.3f})"
        except Exception:
            return f"({x},{y})"

    # annotate digit bounding box corners with (X,Y)
    try:
        db_corners = [(0.0, 0.0), (W, 0.0), (W, H), (0.0, H)]
        for (cx, cy) in db_corners:
            tx, ty = _tx(cx, cy)
            # small offset so text doesn't overlap corner
            draw.text((tx + 2, ty + 2), _fmt(cx + 0.0, cy + 0.0), fill=(0, 0, 0))
    except Exception:
        pass

    # annotate board perimeter corners with (X,Y)
    try:
        for (bx, by) in bp[:4]:
            tx, ty = _tx(bx, by)
            draw.text((tx + 2, ty + 2), _fmt(bx, by), fill=(0, 0, 0))
    except Exception:
        pass

    # Draw dotted per-digit boxes and annotate their corners
    try:
        # derive per-digit width if not explicitly provided
        pdw = per_digit_w if (per_digit_w is not None) else (W if not two_digit else (W - two_digit_gap) / 2.0)
        gap = float(two_digit_gap)
        digit_boxes = []
        if two_digit:
            left_box = (0.0, 0.0, pdw, H)
            right_box = (pdw + gap, 0.0, pdw + gap + pdw, H)
            digit_boxes = [left_box, right_box]
        else:
            digit_boxes = [(0.0, 0.0, pdw, H)]

        def _draw_dashed_rect(box, dash=4, gap_px=4):
            x0, y0, x1, y1 = box
            # rectangle as 4 segments
            segs = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
            for (ax, ay), (bx_, by_) in segs:
                # draw dashed line between (ax,ay) and (bx_,by_)
                ax_px, ay_px = _tx(ax, ay)
                bx_px, by_px = _tx(bx_, by_)
                import math
                dist = math.hypot(bx_px - ax_px, by_px - ay_px)
                if dist < 1:
                    continue
                vx = (bx_px - ax_px) / dist
                vy = (by_px - ay_px) / dist
                pos = 0.0
                dash_len = dash * scale
                gap_len = gap_px
                while pos < dist:
                    seg_end = min(pos + dash_len, dist)
                    sx = ax_px + vx * pos
                    sy = ay_px + vy * pos
                    ex = ax_px + vx * seg_end
                    ey = ay_px + vy * seg_end
                    draw.line([(sx, sy), (ex, ey)], fill=(0, 0, 0), width=1)
                    pos += dash_len + gap_len

        for box in digit_boxes:
            _draw_dashed_rect(box)
            # annotate 4 corners
            x0, y0, x1, y1 = box
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            for (cx, cy) in corners:
                tx, ty = _tx(cx, cy)
                draw.text((tx + 2, ty + 2), _fmt(cx, cy), fill=(0, 0, 0))
    except Exception:
        pass

    # compute digit bounding box from segments so we can place the digit-area label
    try:
        all_x = []
        all_y = []
        for seg in segments:
            for (x, y) in seg.get('poly', []):
                all_x.append(x)
                all_y.append(y)
        if all_x and all_y:
            seg_minx = min(all_x)
            seg_maxx = max(all_x)
            seg_miny = min(all_y)
            seg_maxy = max(all_y)
        else:
            seg_minx, seg_maxx, seg_miny, seg_maxy = 0.0, W, 0.0, H
    except Exception:
        seg_minx, seg_maxx, seg_miny, seg_maxy = 0.0, W, 0.0, H

    # overlay summary text: board size placed inside the board frame, digit area
    # placed inside board frame near the digits, and remaining lines centered
    # at the bottom outside the board frame.
    try:
        font = None
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
        except Exception:
            font = None

        # Board size: place inside the board perimeter (top-left area)
        bx, by = _tx(off_x + 6, off_y + 6)
        draw.text((bx, by), summary_lines[0], fill=(0, 0, 0), font=font)

        # Digit area: place inside the board at top-right, same vertical level
        if len(summary_lines) > 1:
            digit_line = summary_lines[1]
            try:
                tw, th = font.getsize(digit_line) if font is not None else (len(digit_line) * 6, 10)
            except Exception:
                tw = len(digit_line) * 6
            # right padding 6 mm
            dx_px, _ = _tx(off_x + board_w - 6, off_y + 6)
            # place text so its right edge is at dx_px
            draw.text((dx_px - tw, by), digit_line, fill=(0, 0, 0), font=font)

        # Remaining lines: place them in the extra-right area (outside board frame)
        # so they don't overlap the board/digit visuals. Append current timestamp.
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y-%b-%d %I:%M:%S %p')
        except Exception:
            timestamp = ''

        rem_lines = summary_lines[2:]
        # If there are stray/empty lines before the real summary (Cut depth: ...),
        # detect and drop them so the first displayed line is the Cut depth line.
        # Prefer the first line that starts with 'Cut depth' as the start.
        try:
            start_idx = next(i for i, l in enumerate(rem_lines) if (l or '').strip().startswith('Cut depth'))
            rem_lines = rem_lines[start_idx:]
        except StopIteration:
            # fallback: drop leading empty/whitespace-only lines
            while rem_lines and (rem_lines[0] or '').strip() == '':
                rem_lines.pop(0)

        if timestamp:
            rem_lines = rem_lines + [f"Generated: {timestamp}"]

        line_h = int(12 * scale / 8)
        # Place the summary block centered horizontally, below the actual board frame
        # Compute the bottom of the board perimeter (may extend beyond H)
        try:
            board_bottom = max(H, off_y + board_h)
        except Exception:
            board_bottom = H
        # Start Y at board-height - 5 mm (move the summary block up by 5 mm)
        start_y_px = int((margin + top_offset_mm + (board_h - 5.0)) * scale)

        # measure max text width in pixels
        max_tw = 0
        for line in rem_lines:
            try:
                tw, th = font.getsize(line) if font is not None else (len(line) * 6, 10)
            except Exception:
                tw = len(line) * 6
            if tw > max_tw:
                max_tw = tw

        center_x_px = int((margin + left_offset_mm + W / 2.0) * scale)
        left_start = center_x_px - (max_tw // 2)

        for i, line in enumerate(rem_lines):
            draw.text((left_start, start_y_px + i * line_h), line, fill=(0, 0, 0), font=font)
    except Exception:
        pass

    img.save(filename, format='WEBP')


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

    # Preserve the original width/height values from args so two-digit
    # rendering does not mutate or re-calculate the base digit size.
    orig_width = float(args.width)
    orig_height = float(args.height)
    # W/H represent the total digit area as provided by profile/CLI.
    # For two-digit mode, `orig_width` is the total width for both
    # digits plus the gap; we must build per-digit geometry to fit
    # inside that total area.
    W = orig_width
    H = orig_height

    # Decide two-digit and per-digit width before generating segments.
    # Profile `width` is treated as ONE digit width.
    two_digit = bool(getattr(args, 'two_digit', False))
    two_digit_gap = float(getattr(args, 'two_digit_gap', 20.0))
    per_digit_w = orig_width

    # Generate segments using the per-digit width while preserving
    # `args.width` as the profile/CLI value. Temporarily assign for
    # _build_segments, then restore.
    saved_width = getattr(args, 'width', None)
    args.width = per_digit_w
    segments = _build_segments(args)
    # restore original
    args.width = saved_width

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

                        # extend D2 along the same angle by configured factor
                        new_L = L * float(getattr(args, 'extend_factor', 1.5))
                        new_x2 = x1 + ux * new_L
                        new_y2 = y1 + uy * new_L

                        # move D3 to the right by a small offset proportional to L
                        right_offset = L * float(getattr(args, 'shift_frac', 0.25))
                        prov_x3 = x3 + right_offset
                        prov_y3 = y3

                        # compute provisional vector from new D2 to provisional D3
                        pvx = prov_x3 - new_x2
                        pvy = prov_y3 - new_y2

                        # reduce that vector length by configured fraction
                        final_x3 = new_x2 + pvx * float(getattr(args, 'reduce_frac', 0.5))
                        final_y3 = new_y2 + pvy * float(getattr(args, 'reduce_frac', 0.5))

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

                        # extend D5 along same direction by configured factor
                        new_L5 = L * float(getattr(args, 'extend_factor', 1.5))
                        new_x5 = x0 + ux * new_L5
                        new_y5 = y0 + uy * new_L5

                        # provisional move D4 left by a fraction of L
                        left_offset = L * float(getattr(args, 'shift_frac', 0.25))
                        prov_x4 = x4 - left_offset
                        prov_y4 = y4

                        # vector from new D5 to provisional D4
                        pvx = prov_x4 - new_x5
                        pvy = prov_y4 - new_y5

                        # reduce that span by configured fraction
                        final_x4 = new_x5 + pvx * float(getattr(args, 'reduce_frac', 0.5))
                        final_y4 = new_y5 + pvy * float(getattr(args, 'reduce_frac', 0.5))

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

                    # offsets proportional to L (configurable)
                    right_offset = L * float(getattr(args, 'shift_frac', 0.25))
                    up_offset = L * float(getattr(args, 'shift_frac', 0.25))

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
                    final_x0 = final_x1 - vx * float(getattr(args, 'reduce_frac', 0.5))
                    final_y0 = final_y1 - vy * float(getattr(args, 'reduce_frac', 0.5))

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
                        up_offset = math.hypot(x1 - x0, y1 - y0) * float(getattr(args, 'shift_frac', 0.25))
                        prov_x1 = x1
                        prov_y1 = y1 - up_offset

                        # vector from new B0 to provisional B1
                        vx = prov_x1 - new_x0
                        vy = prov_y1 - new_y0
                        target = float(getattr(args, 'reduce_frac', 0.5)) * math.hypot(vx, vy)

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
                            # fallback: move partway in x towards x5 using configured fraction
                            new_x0 = new_x5 + (x0 - new_x5) * float(getattr(args, 'move_partway_frac', 0.5))

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

                        # find B0.x and B0-B1 length
                        b0x = None
                        b01_len = None
                        for s in segments:
                            if s.get('name') == 'B':
                                bpts = s.get('poly', [])
                                if len(bpts) > 1:
                                    b0x = bpts[0][0]
                                    bx0, by0 = bpts[0]
                                    bx1, by1 = bpts[1]
                                    b01_len = math.hypot(bx1 - bx0, by1 - by0)
                                break

                        if b0x is None or b01_len is None:
                            # no B or insufficient points; skip
                            continue

                        # compute unit vector along C4->C3 (preserve this angle)
                        ux = (x3 - x4)
                        uy = (y3 - y4)
                        ul = math.hypot(ux, uy)
                        if ul < 1e-9:
                            # degenerate: can't preserve angle; fallback: set x only
                            new_x3 = b0x
                            new_y3 = y3
                        else:
                            ux /= ul
                            uy /= ul
                            # solve for t so that x4 + t*ux == b0x
                            t = (b0x - x4) / ux
                            new_x3 = b0x
                            new_y3 = y4 + t * uy

                        # commit C3 change, then set C2.y so distance C2-C3 == B0-B1
                        cpts[3] = (new_x3, new_y3)

                        # keep C2.x, solve for C2.y where |C2-C3| == b01_len
                        dx = new_x3 - x2
                        rem = b01_len * b01_len - dx * dx
                        if rem >= 0:
                            dy = math.sqrt(rem)
                            # choose C2 above C3 if originally above, else below
                            if y2 < new_y3:
                                new_y2 = new_y3 - dy
                            else:
                                new_y2 = new_y3 + dy
                        else:
                            # impossible to match exactly; move C2 partway toward C3
                            new_y2 = y2 + 0.5 * (new_y3 - y2)

                        cpts[2] = (x2, new_y2)
                        seg['poly'] = cpts
                    except Exception:
                        pass
                break
    # --- User-requested E/C/F alignments ---
    # Move E4.y -> C2.y; Move E3.x -> F0.x; Move E3.y -> C3.y
    c2y = None
    c3y = None
    for seg in segments:
        if seg.get('name') == 'C':
            cpts = seg.get('poly', [])
            if len(cpts) > 3:
                c2y = cpts[2][1]
                c3y = cpts[3][1]
            break

    f0x = None
    for seg in segments:
        if seg.get('name') == 'F':
            fpts = seg.get('poly', [])
            if len(fpts) > 0:
                f0x = fpts[0][0]
            break

    if c2y is not None and c3y is not None:
        for seg in segments:
            if seg.get('name') == 'E':
                epts = seg.get('poly', [])
                # E3 index 3, E4 index 4 (if present)
                if len(epts) > 4:
                    ex3, ey3 = epts[3]
                    ex4, ey4 = epts[4]
                    new_ex3 = f0x if (f0x is not None) else ex3
                    new_ey3 = c3y
                    new_ey4 = c2y
                    epts[3] = (new_ex3, new_ey3)
                    epts[4] = (ex4, new_ey4)
                    seg['poly'] = epts
                break

    prefix = args.outprefix or 'example_output'
    margin = 10

    svgfn = prefix + '.svg'
    gfn = prefix + '.gcode'
    webpfn = prefix + '.webp'

    points_svgfn = prefix + '_points.svg'

    # Handle optional two-digit duplication: create a shifted copy of
    # the canonical segments and adjust the working width accordingly.
    combined_segments = segments
    # W_out is the rendered/composed width. When two-digit is enabled the
    # total rendered width is two per-digit widths plus the gap.
    if two_digit:
        W_out = per_digit_w * 2.0 + two_digit_gap
        import copy, math
        # compute original segments span so we can nudge digits inward
        all_x = [x for seg in segments for (x, y) in seg.get('poly', [])]
        if all_x:
            left_max_x = max(all_x)
            right_min_x = min(all_x)
        else:
            left_max_x = per_digit_w
            right_min_x = 0.0

        # Target positions: left digit should end at x = per_digit_w
        # right digit should start at x = per_digit_w + two_digit_gap
        target_left_end = per_digit_w
        target_right_start = per_digit_w + two_digit_gap

        t_left = target_left_end - left_max_x
        t_right = target_right_start - right_min_x

        left_shifted = []
        right_shifted = []
        for seg in segments:
            newseg = copy.deepcopy(seg)
            pts = newseg.get('poly', [])
            newseg['poly'] = [(x + t_left, y) for (x, y) in pts]
            left_shifted.append(newseg)

        for seg in segments:
            newseg = copy.deepcopy(seg)
            pts = newseg.get('poly', [])
            newseg['poly'] = [(x + t_right, y) for (x, y) in pts]
            right_shifted.append(newseg)

        combined_segments = left_shifted + right_shifted
    else:
        W_out = per_digit_w

    # Defensive check: ensure the original `args.width` value was not
    # modified by any two-digit handling. two-digit only affects W_out.
    try:
        assert float(args.width) == orig_width
    except AssertionError:
        raise AssertionError('args.width changed unexpectedly; two-digit must not modify base width')

    # SVG / WEBP renderings are custom photo-like style.
    write_photo_svg(svgfn, W_out, H, combined_segments, margin=margin)
    print(f"Wrote {svgfn}")

    # Also write an annotated SVG that labels each polygon vertex.
    write_photo_svg_with_points(points_svgfn, W_out, H, combined_segments, margin=margin)
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
    base_board_w = float(args.board_width) if (args.board_width is not None) else (W + 2.0 * margin)
    # Keep physical board width unchanged even when rendering two digits side-by-side.
    # two_digit only affects rendered/canvas digit layout (`W_out`) but does not
    # change the final board physical width used for board perimeter and dims.
    board_w = base_board_w

    # If pocket_middle requested and a rough bit was provided, emit
    # separate rough/finish g-code files. Otherwise emit a single g-code.
    if args.pocket_middle and (getattr(args, 'rough_bit', None) is not None):
        rough_fn = prefix + '_rough.gcode'
        finish_fn = prefix + '_finish.gcode'

        # Print summary information for rough and finish passes
        import math
        print(f"Board size: {board_w:.3f} x {board_h:.3f} mm")
        print(f"Digit area: {W_out:.3f} x {H:.3f} mm (combined)")
        print(f"Cut depth: {cut_depth:.3f} mm, per-pass depth: {pass_depth:.3f} mm")
        # compute finish pass layering
        if pass_depth > 0:
            finish_passes = max(1, int(math.ceil(abs(cut_depth) / pass_depth)))
            finish_step = float(cut_depth) / finish_passes
        else:
            finish_passes = 1
            finish_step = float(cut_depth)
        # list Z depths for each finish layer (negative values for G-code)
        finish_depths = [-(min((i + 1) * finish_step, cut_depth)) for i in range(finish_passes)]
        finish_depths_str = '[' + ', '.join(f"{d:.3f}" for d in finish_depths) + ']'
        print(f"Finish passes: {finish_passes}, layer depths (Z): {finish_depths_str}")

        rough_bit = float(getattr(args, 'rough_bit', 0))
        rough_step = getattr(args, 'rough_step', None) if getattr(args, 'rough_step', None) is not None else getattr(args, 'pocket_step', None)
        if rough_step is None and rough_bit and rough_bit > 0:
            rough_step = rough_bit * 0.9
        print(f"Rough bit: {rough_bit:.3f} mm, rough pocket step: {str(rough_step)}")
        # rough passes: either only final rough layer or match finish passes
        if getattr(args, 'rough_last', False):
            rough_passes = 1
            rough_depths = [-(cut_depth)]
        else:
            rough_passes = finish_passes
            rough_depths = list(finish_depths)
        rough_depths_str = '[' + ', '.join(f"{d:.3f}" for d in rough_depths) + ']'
        print(f"Rough passes: {rough_passes}, layer depths (Z): {rough_depths_str}")

        # Rough pass: use rough_bit, rough_step/rough_feed if provided
        write_gcode(
            rough_fn,
            W_out,
            H,
            combined_segments,
            bit_dia=args.rough_bit,
            cut_depth=cut_depth,
            pass_depth=pass_depth,
            feed=(args.rough_feed if getattr(args, 'rough_feed', None) is not None else args.feed),
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
            pocket_middle=True,
            pocket_step=(args.rough_step if getattr(args, 'rough_step', None) is not None else args.pocket_step),
            pocket_inset=args.pocket_inset,
        )
        print(f"Wrote {rough_fn}")

        # Finish pass: use main bit and only emit the final finish pass
        write_gcode(
            finish_fn,
            W_out,
            H,
            combined_segments,
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
            pocket_middle=True,
            pocket_step=args.pocket_step,
            pocket_inset=args.pocket_inset,
            finish_only=True,
        )
        print(f"Wrote {finish_fn}")
    else:
        write_gcode(
            gfn,
            W_out,
            H,
            combined_segments,
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
        # Emit a black-and-white line-only WEBP with dimensional summary for quick inspection.
        import math

        if pass_depth > 0:
            finish_passes = max(1, int(math.ceil(abs(cut_depth) / pass_depth)))
            finish_step = float(cut_depth) / finish_passes
        else:
            finish_passes = 1
            finish_step = float(cut_depth)

        finish_depths = [-(min((i + 1) * finish_step, cut_depth)) for i in range(finish_passes)]
        finish_depths_str = '[' + ', '.join(f"{d:.3f}" for d in finish_depths) + ']'

        raw_rough_bit = getattr(args, 'rough_bit', None)
        rough_bit = float(raw_rough_bit) if (raw_rough_bit is not None) else 0.0
        rough_step = getattr(args, 'rough_step', None) if getattr(args, 'rough_step', None) is not None else getattr(args, 'pocket_step', None)
        if rough_step is None and rough_bit and rough_bit > 0:
            rough_step = rough_bit * 0.9

        if raw_rough_bit is None:
            rough_passes = 0
            rough_depths = []
            rough_depths_str = '[]'
        else:
            if getattr(args, 'rough_last', False):
                rough_passes = 1
                rough_depths = [-(cut_depth)]
            else:
                rough_passes = finish_passes
                rough_depths = list(finish_depths)
            rough_depths_str = '[' + ', '.join(f"{d:.3f}" for d in rough_depths) + ']'

        rough_bit_str = f"{rough_bit:.3f}" if raw_rough_bit is not None else 'None'
        rough_step_str = str(rough_step) if (rough_step is not None) else 'None'

        summary_lines = [
            f"Board size: {board_w:.3f} x {board_h:.3f} mm",
            f"Digit area: {W_out:.3f} x {H:.3f} mm (combined)",
            f"Cut depth: {cut_depth:.3f} mm, per-pass depth: {pass_depth:.3f} mm",
            f"Finish passes: {finish_passes}, layer depths (Z): {finish_depths_str}",
            f"Rough bit: {rough_bit_str} mm, rough pocket step: {rough_step_str}",
            f"Rough passes: {rough_passes}, layer depths (Z): {rough_depths_str}",
        ]

        # Always attempt to write the show-dim WEBP when Pillow is available
        showfn = prefix + '_show-dim.webp'
        try:
            write_show_dim_webp(showfn, W_out, H, combined_segments, board_w, board_h, summary_lines, margin=margin, scale=8, two_digit=two_digit, per_digit_w=per_digit_w, two_digit_gap=two_digit_gap)
            print(f"Wrote {showfn}")
        except Exception as e:
            print(f"Skipped show-dim WEBP: {e}")

        write_photo_webp(webpfn, W_out, H, combined_segments, margin=margin, scale=8, bit_dia=getattr(args, 'bit', None))
        print(f"Wrote {webpfn}")
    else:
        print('Skipped WEBP: Pillow not installed in current Python environment.')


if __name__ == '__main__':
    main()
