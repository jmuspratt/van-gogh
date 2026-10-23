"""Georeference a scanned map: control points (town dots) -> polynomial lat/lon -> pixel model.

    python3 pipeline/georef.py fit                       # fit, print residuals, write the model
    python3 pipeline/georef.py sheet OUT.jpg id [id...]  # zoomed crops around predicted positions, with a pixel grid
    python3 pipeline/georef.py snap OUT.jpg id@x,y ... [--save]  # snap guesses to printed town rings, verify, save
    python3 pipeline/georef.py missing                   # place ids used by letters that have no control point yet

Output: "positions" in the same file, {place_id: {x, y, printed}} for every place in data/places.json on
the sheet. Printed towns keep their printed position; others get the polynomial's estimate.

Control points live in data/maps/<map>.json under "gcps": {id: [x, y]} where id is a place id from
data/places.json or an anchor id from that file's "anchors" (extra well-known towns that spread the
fit across the map). Pixel coordinates are in the full-resolution scan.

The model is a bivariate polynomial in (lon, lat) for x and y, fit by least squares. Degree 3 is
plenty for a conic projection over this extent; leave-one-out residuals show how well it generalises.

Authoring-time only: needs numpy and Pillow. The build and viewer just read the fitted coefficients.
"""

import json
import sys
from itertools import product
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "data" / "maps" / "dubois-kergomard-1914.json"
Image.MAX_IMAGE_PIXELS = None


def load():
    spec = json.loads(MAP.read_text())
    places = json.loads((ROOT / "data" / "places.json").read_text())
    coords = {pid: (p["lon"], p["lat"]) for pid, p in places.items() if "lat" in p}
    coords.update({aid: (a["lon"], a["lat"]) for aid, a in spec.get("anchors", {}).items() if "lat" in a})
    return spec, coords


def terms(lon, lat, degree, origin):
    u, v = lon - origin[0], lat - origin[1]
    return [u ** i * v ** j for i, j in product(range(degree + 1), repeat=2) if i + j <= degree]


def fit(points, coords, degree, origin):
    ids = [k for k in points if k in coords]
    A = np.array([terms(*coords[k], degree, origin) for k in ids])
    xy = np.array([points[k] for k in ids], dtype=float)
    cx, *_ = np.linalg.lstsq(A, xy[:, 0], rcond=None)
    cy, *_ = np.linalg.lstsq(A, xy[:, 1], rcond=None)
    return ids, cx, cy


def predict(model, lon, lat):
    t = np.array(terms(lon, lat, model["degree"], model["origin"]))
    return float(t @ model["cx"]), float(t @ model["cy"])


def choose_degree(n):
    return 3 if n >= 20 else 2 if n >= 8 else 1


def cmd_fit(spec, coords):
    gcps = spec["gcps"]
    degree = choose_degree(len(gcps))
    origin = [float(np.mean([coords[k][i] for k in gcps])) for i in (0, 1)]
    ids, cx, cy = fit(gcps, coords, degree, origin)
    model = {"degree": degree, "origin": origin, "cx": cx.tolist(), "cy": cy.tolist()}
    gcps = {k: v for k, v in gcps.items() if k in coords}

    # px per km near the centre, for readable residuals
    x0, y0 = predict(model, *origin)
    x1, y1 = predict(model, origin[0], origin[1] + 1)
    px_per_km = np.hypot(x1 - x0, y1 - y0) / 111.2

    rows = []
    for k in ids:
        px, py = predict(model, *coords[k])
        res = np.hypot(px - gcps[k][0], py - gcps[k][1])
        loo = None
        if len(ids) > len(cx) + 2:  # leave-one-out
            rest = {j: gcps[j] for j in ids if j != k}
            _, lx, ly = fit(rest, coords, degree, origin)
            lm = {"degree": degree, "origin": origin, "cx": lx, "cy": ly}
            qx, qy = predict(lm, *coords[k])
            loo = np.hypot(qx - gcps[k][0], qy - gcps[k][1])
        rows.append((res, loo, k))
    rows.sort(key=lambda r: -(r[1] or r[0]))
    print(f"degree {degree}, {len(ids)} control points, {px_per_km:.2f} px/km")
    print(f"{'id':24} {'resid px':>8} {'km':>6} {'LOO px':>8} {'km':>6}")
    for res, loo, k in rows:
        print(f"{k:24} {res:8.1f} {res / px_per_km:6.2f} {loo or 0:8.1f} {(loo or 0) / px_per_km:6.2f}")
    rms = np.sqrt(np.mean([r[0] ** 2 for r in rows]))
    print(f"RMS residual {rms:.1f} px = {rms / px_per_km:.2f} km")

    # Engraving errors turn out to be independent from town to town (a TPS through the residuals
    # predicts held-out towns worse than the polynomial alone), so: printed towns keep their printed
    # position; everything else gets the polynomial's estimate (typical error = the LOO figures above).
    loo = [r[1] for r in rows if r[1] is not None]
    loo_med = float(np.median(loo))
    print(f"expected error for unprinted places: leave-one-out median {loo_med:.1f} px = {loo_med / px_per_km:.2f} km")

    # Positions of every known place that falls on the sheet.
    w, h = spec["size"]
    places = json.loads((ROOT / "data" / "places.json").read_text())
    positions = {}
    for pid, p in places.items():
        if "lat" not in p:
            continue
        printed = pid in gcps
        x, y = gcps[pid] if printed else predict(model, p["lon"], p["lat"])
        if 0 <= x < w and 0 <= y < h:
            positions[pid] = {"x": round(float(x), 1), "y": round(float(y), 1), "printed": printed}
    spec["positions"] = dict(sorted(positions.items()))
    spec["model"] = {**model, "pxPerKm": round(float(px_per_km), 3), "rmsPx": round(float(rms), 2),
                     "looMedianPx": round(loo_med, 2)}
    MAP.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote model and {len(positions)} place positions to {MAP.relative_to(ROOT)}")


def current_model(spec, coords):
    gcps = spec["gcps"]
    degree = choose_degree(len(gcps))
    origin = [float(np.mean([coords[k][i] for k in gcps])) for i in (0, 1)]
    _, cx, cy = fit(gcps, coords, degree, origin)
    return {"degree": degree, "origin": origin, "cx": cx, "cy": cy}


def cmd_sheet(spec, coords, out, ids, half=300, cell=500, step=50):
    """Contact sheet: for each id a (2*half)^2 px crop around the predicted point, with a pixel grid.

    An id may be written `id@x,y` to centre the crop on (x, y) instead of the prediction (second, zoomed pass).
    """
    model = current_model(spec, coords)
    if any("@" in i for i in ids):
        half, step = 80, 10
    im = Image.open(ROOT / spec["image"])
    cols = 3
    rows = (len(ids) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 20)), "white")
    for n, k in enumerate(ids):
        k, _, at = k.partition("@")
        px, py = map(float, at.split(",")) if at else predict(model, *coords[k])
        cx0, cy0 = int(round(px / step) * step) - half, int(round(py / step) * step) - half
        crop = im.crop((cx0, cy0, cx0 + 2 * half, cy0 + 2 * half)).resize((cell, cell))
        d = ImageDraw.Draw(crop)
        s = cell / (2 * half)
        for g in range(0, 2 * half + 1, step):
            col = (255, 0, 0) if g % (2 * step) == 0 else (255, 170, 170)
            d.line([(g * s, 0), (g * s, cell)], fill=col, width=1)
            d.line([(0, g * s), (cell, g * s)], fill=col, width=1)
            if g % (4 * step) == 0:
                d.text((g * s + 2, 2), str(cx0 + g), fill=(180, 0, 0))
                d.text((2, g * s + 2), str(cy0 + g), fill=(180, 0, 0))
        if not at:
            d.ellipse([(px - cx0) * s - 4, (py - cy0) * s - 4, (px - cx0) * s + 4, (py - cy0) * s + 4], outline=(0, 0, 255), width=2)
        x, y = (n % cols) * cell, (n // cols) * (cell + 20)
        sheet.paste(crop, (x, y + 20))
        ImageDraw.Draw(sheet).text((x + 4, y + 4), f"{k}  (predicted {px:.0f},{py:.0f})", fill=(0, 0, 0))
    sheet.save(out, quality=90)
    print(f"wrote {out} ({len(ids)} crops)")


def _ring_templates():
    """Dark printed town rings of radius 2.5-5 px on light paper, as zero-mean templates."""
    out = []
    for r in (2.5, 3, 3.5, 4, 4.5, 5):
        n = int(r) + 4
        yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
        d = np.hypot(xx, yy)
        t = -np.exp(-((d - r) ** 2) / (2 * 0.6 ** 2))  # dark ring
        t -= t.mean()
        out.append((r, n, t / np.linalg.norm(t)))
    return out


def snap(gray, x, y, radius=25):
    """Centre of the best-matching town ring within `radius` px of (x, y), by normalised cross-correlation."""
    best = (-1, x, y, 0)
    for r, n, t in _ring_templates():
        x0, y0 = int(x) - radius - n, int(y) - radius - n
        win = gray[y0:y0 + 2 * (radius + n) + 1, x0:x0 + 2 * (radius + n) + 1]
        views = np.lib.stride_tricks.sliding_window_view(win, t.shape)
        v = views - views.mean(axis=(-1, -2), keepdims=True)
        score = (v * t).sum(axis=(-1, -2)) / (np.linalg.norm(v, axis=(-1, -2)) + 1e-6)
        iy, ix = np.unravel_index(np.argmax(score), score.shape)
        if score[iy, ix] > best[0]:
            best = (float(score[iy, ix]), x0 + ix + n, y0 + iy + n, r)
    return best


def cmd_snap(spec, coords, out, items, save=False):
    """Snap `id@x,y` guesses to ring centres; write a verification sheet with crosshairs."""
    im = Image.open(ROOT / spec["image"])
    results = []
    model = current_model(spec, coords)
    for item in items:
        k, _, at = item.partition("@")
        if not at:  # no guess given: centre on the model's prediction, no snapping
            item = f"{k.rstrip('!')}!@" + ",".join(f"{v:.0f}" for v in predict(model, *coords[k.rstrip('!')]))
            k, _, at = item.partition("@")
        gx, gy = map(float, at.split(","))
        manual = k.endswith("!")  # `id!@x,y`: keep the guess as-is (e.g. hatched big-city symbols)
        k = k.rstrip("!")
        if manual:
            results.append((k, gx, gy, None, None))
            continue
        x0, y0 = int(gx) - 40, int(gy) - 40
        gray = np.asarray(im.crop((x0, y0, x0 + 81, y0 + 81)).convert("L"), dtype=float)
        score, sx, sy, r = snap(gray, gx - x0, gy - y0)
        results.append((k, sx + x0, sy + y0, score, r))
    cell, half, cols = 500, 60, 3
    rows = (len(results) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 20)), "white")
    for n, (k, x, y, score, r) in enumerate(results):
        crop = im.crop((int(x) - half, int(y) - half, int(x) + half, int(y) + half)).resize((cell, cell))
        d = ImageDraw.Draw(crop)
        c = cell / 2 + (x - int(x)) * cell / (2 * half)
        d.line([(c, 0), (c, cell / 2 - 25)], fill=(255, 0, 0), width=2)
        d.line([(c, cell / 2 + 25), (c, cell)], fill=(255, 0, 0), width=2)
        d.line([(0, cell / 2), (cell / 2 - 25, cell / 2)], fill=(255, 0, 0), width=2)
        d.line([(cell / 2 + 25, cell / 2), (cell, cell / 2)], fill=(255, 0, 0), width=2)
        px, py = n % cols * cell, n // cols * (cell + 20)
        sheet.paste(crop, (px, py + 20))
        label = f"{k} -> {x:.0f},{y:.0f}" + (f"  score {score:.2f} r={r}" if score is not None else "  (manual)")
        ImageDraw.Draw(sheet).text((px + 4, py + 4), label, fill=(0, 0, 0))
        print(label)
    sheet.save(out, quality=90)
    print(f"wrote {out}")
    if save:
        for k, x, y, score, r in results:
            spec["gcps"][k] = [round(x, 1), round(y, 1)]
        MAP.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
        print(f"saved {len(results)} control points")


def cmd_missing(spec, coords):
    letters = json.loads((ROOT / "build" / "data" / "letters.json").read_text())
    used = {l[e]["place"] for l in letters for e in ("from", "to") if l[e].get("place")}
    model = current_model(spec, coords)
    w, h = spec["size"]
    for pid in sorted(used - set(spec["gcps"])):
        if pid not in coords:
            print(pid, "(no coordinates)")
            continue
        x, y = predict(model, *coords[pid])
        print(f"{pid:24} predicted {x:7.0f} {y:7.0f}" + ("" if 0 <= x < w and 0 <= y < h else "  OFF MAP"))


def main():
    spec, coords = load()
    cmd, *args = sys.argv[1:] or ["fit"]
    if cmd == "fit":
        cmd_fit(spec, coords)
    elif cmd == "sheet":
        cmd_sheet(spec, coords, args[0], args[1:])
    elif cmd == "snap":
        save = "--save" in args
        args = [a for a in args if a != "--save"]
        cmd_snap(spec, coords, args[0], args[1:], save)
    elif cmd == "missing":
        cmd_missing(spec, coords)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
