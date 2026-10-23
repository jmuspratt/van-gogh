"""Build the letter dataset from the Van Gogh Letters TEI.

    python3 pipeline/build.py

Writes build/data/letters.json, build/data/places.json (with base-map pixel positions), build/data/map.json,
build/data/people.json and build/data/bodies/<id>.html,
then prints a validation report. Exits non-zero if any date fails to parse.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dates import DateParseError, parse_date  # noqa: E402
from resolve import resolve_all  # noqa: E402
from vgl import read_letter, read_people  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEI_DIR = ROOT / "vendor" / "vangoghletters-tei"
MAP = ROOT / "data" / "maps" / "dubois-kergomard-1914.json"
OUT = ROOT / "build" / "data"


def main():
    (OUT / "bodies").mkdir(parents=True, exist_ok=True)
    letters, failures, mismatches = [], [], []

    for path in sorted(TEI_DIR.glob("let*.xml")) + sorted(TEI_DIR.glob("RM*.xml")):
        record, body = read_letter(path)
        try:
            d = parse_date(record["dateText"])
            record["date"] = {
                "earliest": d.earliest,
                "latest": d.latest,
                "precision": d.precision,
                "approximate": d.approximate,
                "probable": d.probable,
            }
            if d.weekday_mismatches:
                mismatches.append((record["id"], record["dateText"], d.weekday_mismatches))
        except DateParseError as e:
            record["date"] = None
            failures.append((record["id"], str(e)))
        letters.append(record)
        (OUT / "bodies" / f"{record['id']}.html").write_text(body + "\n", encoding="utf-8")

    letters.sort(key=lambda r: (r["date"] or {}).get("earliest") or "9999")

    # Sender / recipient places from data/ (places, correspondents, itineraries).
    resolved = resolve_all(letters)
    for r in letters:
        res = resolved.get(r["id"], {})
        r["authorKey"], r["addresseeKey"] = res.get("authorKey"), res.get("addresseeKey")
        for end in ("from", "to"):
            x = res.get(end) or {"place": None, "basis": "unresolved"}
            r[end] = {k: v for k, v in x.items() if k != "issues"}
    places = json.loads((ROOT / "data" / "places.json").read_text())
    base_map = json.loads(MAP.read_text())
    used = {r[e]["place"] for r in letters for e in ("from", "to") if r[e].get("place")}
    out_places = {}
    for pid in sorted(used):
        if pid not in places:
            continue
        p = {k: places[pid][k] for k in ("name", "lat", "lon", "kind", "country", "wikidata", "within") if k in places[pid]}
        p["map"] = base_map["positions"].get(pid)  # {x, y, printed} in scan pixels, or None if off the sheet
        out_places[pid] = p
    (OUT / "places.json").write_text(json.dumps(out_places, ensure_ascii=False, indent=1))
    # Itineraries (stays only, no evidence) so the viewer can move people between places over time.
    correspondents = json.loads((ROOT / "data" / "correspondents.json").read_text())
    itins = {}
    for path in sorted((ROOT / "data" / "itineraries").glob("*.json")):
        spec = json.loads(path.read_text())
        itins[path.stem] = {
            "name": correspondents.get(path.stem, {}).get("name", path.stem),
            "stays": sorted(({k: s[k] for k in ("place", "from", "to", "kind", "approx", "note") if k in s}
                             for s in spec.get("stays", [])), key=lambda s: s["from"]),
        }
        for st in itins[path.stem]["stays"]:
            if st["place"] in places and st["place"] not in out_places:
                pl = places[st["place"]]
                out_places[st["place"]] = {k: pl[k] for k in ("name", "lat", "lon", "kind", "country") if k in pl} | {
                    "map": base_map["positions"].get(st["place"])}
    (OUT / "places.json").write_text(json.dumps(out_places, ensure_ascii=False, indent=1))
    (OUT / "itineraries.json").write_text(json.dumps(itins, ensure_ascii=False, indent=1))
    (OUT / "map.json").write_text(json.dumps(
        {k: base_map[k] for k in ("title", "authors", "publisher", "year", "scale", "source", "rights", "image", "size")}
        | {"pxPerKm": base_map["model"]["pxPerKm"]}, ensure_ascii=False, indent=1))
    (OUT / "letters.json").write_text(json.dumps(letters, ensure_ascii=False, indent=1), encoding="utf-8")
    people = read_people(TEI_DIR / "people.xml")
    (OUT / "people.json").write_text(json.dumps(people, ensure_ascii=False, indent=1), encoding="utf-8")

    report(letters, people, failures, mismatches)
    return 1 if failures else 0


def report(letters, people, failures, mismatches):
    print(f"{len(letters)} documents, {len(people)} people -> {OUT.relative_to(ROOT)}")
    print(f"  kinds: {dict(Counter(r['kind'] for r in letters))}")
    dated = [r for r in letters if r["date"]]
    print(f"  date precision: {dict(Counter(r['date']['precision'] for r in dated))}")
    print(f"  approximate: {sum(r['date']['approximate'] for r in dated)}, probable: {sum(r['date']['probable'] for r in dated)}")
    spans = sorted(
        ((_days(r["date"]), r["id"], r["dateText"]) for r in dated if r["date"]["latest"]),
        reverse=True,
    )
    print("  widest date ranges:")
    for days, lid, text in spans[:5]:
        print(f"    {lid}: {days + 1} days  ({text})")
    print(f"  span: {dated[0]['date']['earliest']} .. {max(r['date']['latest'] or '' for r in dated)}")
    for end in ("from", "to"):
        rs = [r[end] for r in letters]
        print(f"  {end}: {sum(1 for x in rs if x.get('place'))} resolved, "
              f"{sum(1 for x in rs if x.get('ambiguous'))} ambiguous, {sum(1 for x in rs if not x.get('place'))} unresolved; "
              f"basis {dict(Counter(x['basis'] for x in rs))}")
    print(f"  date parse failures: {len(failures)}")
    for lid, err in failures:
        print(f"    {lid}: {err}")
    print(f"  weekday mismatches: {len(mismatches)}")
    for lid, text, mm in mismatches:
        print(f"    {lid}: {text!r} -> {mm}")


def _days(d):
    from datetime import date
    return (date.fromisoformat(d["latest"]) - date.fromisoformat(d["earliest"])).days


if __name__ == "__main__":
    sys.exit(main())
