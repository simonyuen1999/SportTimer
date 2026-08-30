# Make7Segment

Generate an SVG preview and simple CNC G-code for a single 7-segment digit.

This repository contains two generator scripts:

- `Make7Segment.py` — canonical generator. Produces an SVG preview and a simple per-segment CNC G-code outline. Defaults are tuned to the user's preferred geometry.
- `Make7SegmentShapely.py` — same generator but performs a deterministic polygon union using Shapely (GEOS) to remove seams between chamfered segments. Note: Shapely is optional but recommended for seam-free results.

Quick example:

```bash
python3 Make7Segment.py --height 200 --width 120 --stroke 20 --radius 10
```

This creates `Make7Segment_H200_W120.svg` and `Make7Segment_H200_W120.gcode` in the current folder.

Common CLI options
- `--height` (H): overall digit height in mm (default: 200)
- `--width` (W): overall digit width in mm (default: 120)
- `--stroke` (t): segment stroke thickness in mm (default: 20)
- `--radius` (r): chamfer radius (bevel amount) in mm (default: 10)
- `--gap`: inter-segment gap (default: 0)
- `--overlap` (ov): horizontal overlap used historically to empirically close chamfer gaps (default: 4). Note: `Make7SegmentShapely.py` makes this unnecessary.
- `--hgap`: vertical gap measured from the middle of `G` controlling how top/bottom verticals terminate (default: 5)

Using Shapely (recommended for seam removal)
1. Install Shapely in your Python environment:

```bash
pip install shapely
```

2. Run the shapely variant:

```bash
python3 Make7SegmentShapely.py --height 200 --width 120 --stroke 20 --radius 10
```

The script attempts a geometry union (`unary_union`) of the segment polygons and then clips the unioned result to the original board bounding box to avoid tiny outward expansions. If you see a small change in overall width after union, try one of these approaches (the shapely script now applies clipping by default):

- Quick workaround: use `--width` to respecify the exact desired width (this rescales the whole digit and is a hack).
- Recommended: let `Make7SegmentShapely.py` run (with Shapely installed). If a very small expansion remains, the script can be patched to either snap coordinates within a small tolerance to the original bounds or automatically translate/scale the merged geometry back to exact W×H — contact me and I will add an automatic post-process.

Notes and tips
- The original `Make7Segment.py` uses chamfered (beveled) rectangular segments. Small visible seams where bevels meet are best resolved by boolean union rather than guessing numeric overlaps.
- `--overlap` was added historically to close visible diagonal gaps; when using the Shapely union script you can set `--overlap 0` (or omit it) because the union removes seams deterministically.
- Always inspect the generated SVG before running G-code on a machine.

Troubleshooting
- If `Make7SegmentShapely.py` prints "Shapely not available", install Shapely with `pip install shapely` and re-run the script.
- If unioned output is slightly wider: run the shapely script (it clips to board extents). If you still want an automated fix, open an issue or ask me to add an option that snaps/auto-fits merged geometry back to W×H when the deviation is below a small tolerance.

License & safety
- Generated G-code is simple perimeter outlines for visualization and basic CAM. Inspect and validate toolpaths, feeds, plunges, and safe heights before running on hardware.

If you'd like, I can add an automatic post-process to `Make7SegmentShapely.py` that snaps merged coordinates to the original extents when deviations are tiny — shall I implement that change?
