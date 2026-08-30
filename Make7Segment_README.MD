# Make7Segment — Communication & Iteration Notes

## Why **multiple cycles were needed**
- Visual reference ambiguity: raster images (WebP) show appearance but not which edges or vertices are intended as anchors.
- Chamfer interactions: beveled ends produce diagonal voids that don't close by simple centering — they require union or overlap tuning.
- Anchor choices change geometry: moving A, D or G can be done relative to their top, bottom, or center; each choice alters adjacent segment math.
- CAM/kerf effects: cutter diameter, pass depth, and toolpath strategy affect visible seams; 2D geometry alone doesn't guarantee the final look.
- Small mm → large visual change: a few millimetres at these sizes markedly changes the visual join, so iterative visual checks are needed.

## How to communicate so I understand immediately
- Provide an annotated reference image (WebP or SVG) with segments labeled A..G and arrows/notes for exact expectations.
- State explicit anchors: e.g. “Fix A and D positions; keep G centered; shift F/B down by X mm and do NOT shorten F/B length.”
- Give numeric targets: height/width/stroke/chamfer and desired visible seam (e.g. ≤0.5 mm or 0 mm).
- Prefer vector inputs: SVG or DXF traces remove ambiguity — vector coordinates are deterministic.
- State CAM details when relevant: cutter diameter, desired overlap, material, and whether polygon-union is acceptable.
- Define acceptance criteria: exact match tolerance, or a simple visual rule (e.g. no visible diagonal gaps at 1:1).
- Provide a small test matrix: a few `--hgap`/`--overlap` pairs to run and indicate which output looks closest.

---
If you want, I can add an automated SVG-compare helper or integrate `shapely` to do deterministic polygon unions (no trial-and-error overlap needed). Ask and I will implement the preferred approach.
