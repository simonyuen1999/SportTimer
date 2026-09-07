# Make7Segment — Usage & Current Implementation

This repository contains `Make7Segment.py`, a small utility to generate a single 7-segment digit preview and simple CNC G-code toolpaths. The script computes chamfered per-segment polygons (or uses simple rects), optionally performs polygon union with Shapely, writes SVG and G-code, and can render a WebP preview using Pillow.

Primary outputs (per run):
- `<prefix>.svg` — vector preview (mm units)
- `<prefix>.gcode` — CNC outline/toolpath G-code
- `<prefix>_rough.gcode` / `<prefix>_finish.gcode` — produced when `--rough-bit` is used alongside `--pocket-middle` (rough + finish flow)
- `<prefix>.webp` — optional raster preview when Pillow is installed

Quick dependencies
- Python 3
- Optional: `pillow` to generate WebP preview (`pip install pillow`)
- Optional: `shapely` for robust geometry operations and cleaner pocketing (`pip install shapely`)

Highlights (current behavior)
- `--show-board-dim` emits a single shallow reference layer in the G-code (board perimeter, digit bounding box, and simple dimension lines). It does not change the SVG or WebP content.
- `--pocket-middle` enables pocketing (horizontal scanlines) inside each segment. Pocketing runs are generated per depth pass so material removal happens progressively.
- When `--rough-bit` is provided with `--pocket-middle`, the script writes two G-code files: `<prefix>_rough.gcode` (wider bit, coarse stepover) and `<prefix>_finish.gcode` (finishing bit, perimeter/profile only).
- `--pause-after-seg` and `--pause-after-layer` implement operator pauses using `M0` (with `M3`/`M5` around segments when pausing per-segment).
- By default the generator minimizes parenthesized comments in G-code for better GRBL/Candle compatibility; enable `--debug-gcode` to add comments.

Key CLI options (high level)
- `--height` / `--width` — digit size in mm (defaults: 120.0 × 80.0)
- `--stroke` — segment thickness
- `--radius` — chamfer radius
- `--bit` / `--rough-bit` — cutter diameters for finish/rough
- `--depth` / `--passdepth` / `--cutting-paths` — control cut depth and splitting into passes (when `--depth` omitted, `--board-thickness` is used)
- `--pocket-middle` / `--pocket-step` — pocket interior material and scanline spacing
- `--rough-step` / `--rough-feed` — roughing stepover and feedrate
- `--pause-after-seg` / `--pause-after-layer` — operator pause behaviors
- `--render-source` — `poly` (default) or `rect` — controls SVG/WebP rendering method

Pocketing behavior
- If Shapely is available, pocketing uses LineString intersections to compute exact horizontal runs. If not available, a sampling-based point-in-poly fallback is used (coarser, may produce more short moves).

Included profile examples
Two ready-to-use profiles are included for thick boards. They are intended as starting points — review and tweak before cutting.

- `thick_PVC.cfg` (prefix `P`)
  - board-height: 100.0 mm, board-width: 64.0 mm, board-thickness: 6.5 mm
  - digit: height 85 mm × width 50 mm, stroke 6 mm, radius 10 mm
  - CAM: `bit=2.0`, `depth=10`, `passdepth=1.0`, `cutting-paths=10`
  - pocketing: `pocket-middle=true`, `pocket-step=1.0`, `pocket-inset=0.25`
  - roughing: `rough-bit=3.175`, `rough-step=1.25`, `rough-feed=1200`
  - outprefix: `P`

- `thick_wooden.cfg` (prefix `W`)
  - board-height: 100.0 mm, board-width: 64.0 mm, board-thickness: 6.5 mm
  - digit: height 85 mm × width 50 mm, stroke 6 mm, radius 10 mm
  - CAM: `bit=2.0`, `depth=10`, `passdepth=1.0`, `cutting-paths=10`
  - pocketing: `pocket-middle=true`, `pocket-step=1.0`, `pocket-inset=0.25`
  - roughing: `rough-bit=3.175`, `rough-step=1.0`, `rough-feed=1200`
  - outprefix: `W`

How to run (examples)
```bash
# generate rough + finish G-code using the profile
python Make7Segment.py --profile thick_PVC.cfg --pocket-middle --rough-bit 3.175

# simple run producing SVG + G-code + WEBP (if Pillow present)
python Make7Segment.py --height 120 --width 80 --outprefix N --show-board-dim

# per-segment pause workflow for operator inspection
python Make7Segment.py --profile thick_wooden.cfg --pause-after-seg

# enable debug comments in generated G-code
python Make7Segment.py --profile thick_PVC.cfg --debug-gcode
```

Notes and recommendations
- Always preview the generated G-code before cutting. The script emits explicit rapid/plunge/cut moves but does not simulate machine constraints (holder collisions, tool length, workholding).
- Inspect and, if needed, adjust `pocket-step`, `rough-step`, and feedrates to match your material and cutter.
- The included `thick_*.cfg` files set `pocket-middle=true` so runs will generate rough + finish outputs when `--rough-bit` is present; file prefixes are `P` and `W` respectively.
- If you want a requirements file, I can add `requirements.txt` with `pillow` and `shapely`.

Recommended gitignore
- `*.svg`, `*.gcode`, `*.webp`, `.venv/`, `__pycache__/`

If you'd like, I can also add a small test harness that runs the script with each profile and produces a short excerpt of the resulting G-code for verification. Say the word and I'll add it.
