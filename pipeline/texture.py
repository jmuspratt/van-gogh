"""Cut the base map's viewer area into texture tiles for the web viewer.

    python3 pipeline/texture.py

Reads data/maps/dubois-kergomard-1914.json ("viewerCrop": [x0, y0, x1, y1] in scan pixels) and writes
build/data/map/tile-<row>-<col>.jpg (2×2 grid, each under 4096 px so any WebGL device can load it),
plus preview.jpg (1024 px) for a fast first paint, and build/data/map/tiles.json describing them.
Needs Pillow.
"""

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "data" / "maps" / "dubois-kergomard-1914.json"
OUT = ROOT / "build" / "data" / "map"
Image.MAX_IMAGE_PIXELS = None
GRID = 2


def main():
    spec = json.loads(MAP.read_text())
    x0, y0, x1, y1 = spec["viewerCrop"]
    im = Image.open(ROOT / spec["image"]).convert("RGB").crop((x0, y0, x1, y1))
    OUT.mkdir(parents=True, exist_ok=True)
    w, h = im.size
    tiles = []
    for r in range(GRID):
        for c in range(GRID):
            box = (c * w // GRID, r * h // GRID, (c + 1) * w // GRID, (r + 1) * h // GRID)
            name = f"tile-{r}-{c}.jpg"
            im.crop(box).save(OUT / name, quality=88, optimize=True, progressive=True)
            tiles.append({"file": name, "x": x0 + box[0], "y": y0 + box[1], "w": box[2] - box[0], "h": box[3] - box[1]})
    scale = 1024 / max(w, h)
    im.resize((round(w * scale), round(h * scale)), Image.LANCZOS).save(OUT / "preview.jpg", quality=85)
    (OUT / "tiles.json").write_text(json.dumps(
        {"crop": [x0, y0, x1, y1], "preview": "preview.jpg", "tiles": tiles}, indent=1))
    print(f"{len(tiles)} tiles of ~{w // GRID}×{h // GRID} px -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
