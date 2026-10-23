"""Compare the canonical dataset against the 2008–09 sources.

    python3 pipeline/compare.py     # writes build/reports/compare.md and prints a summary

Sections:
1. Concordance: webexhibits letter files (source/archive/letters) <-> edition ids, via the
   edition's "collectedletters" number.
2. Dates: webexhibits DC.Date outside the edition's date interval.
3. Sender places: webexhibits Location vs the edition heading.
4. Routes: the 2009 KML's from/to (source/2009-routes.csv) vs resolved from/to.
"""

import csv
import html
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from resolve import resolve_all  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "data"
WEBEX = ROOT / "source" / "archive" / "letters"
ROUTES_2009 = ROOT / "source" / "2009-routes.csv"
REPORT = ROOT / "build" / "reports" / "compare.md"

# 2009 place names -> place ids
NAMES_2009 = {
    "The Hague": "the-hague", "Oisterwijk": "oisterwijk", "Brussels": "brussels", "London": "london",
    "Paris": "paris", "Etten": "etten", "Isleworth": "isleworth", "Ramsgate": "ramsgate",
    "Dordrecht": "dordrecht", "Amsterdam": "amsterdam", "Laeken": "laeken", "Petit-Wasmes": "wasmes",
    "Cuesmes": "cuesmes", "Drenthe": "drenthe", "Nuenen": "nuenen", "Antwerp": "antwerp",
    "Arles": "arles", "Saint-Remy": "saint-remy", "Auvers-sur-Oise": "auvers-sur-oise",
    "Helvoirt": "helvoirt",
}


def norm_number(s):
    """'009a' -> '9a', 'B01' -> 'B1', 'T3a' -> 'T3a', 'etc-Gauguin-GAC28' / 'GAC 28' -> 'GAC28'."""
    if m := re.fullmatch(r"(?:etc-Gauguin-)?GAC ?(\d+)", s or ""):
        return f"GAC{m.group(1)}"
    m = re.fullmatch(r"([A-Za-z]?)0*(\d+)([a-z]?)", s or "")
    return f"{m.group(1).upper()}{m.group(2)}{m.group(3)}" if m else None


def edition_numbers(s):
    """The edition sometimes merges old numbers: '91+91a', '538-538a', '588 and 589', '602 / 602a', '82a-1'."""
    s = re.sub(r"^(\d+[a-z]?)-\d$", r"\1", s or "")  # '82a-1': part 1 of 82a
    parts = re.split(r"\s*(?:\+|/| and |-(?=\d))\s*", s)
    return [n for n in map(norm_number, parts) if n]


def read_webexhibits():
    out = {}
    for f in WEBEX.glob("*/*.htm"):
        if re.search(r"-(fr|nl)\.htm$", f.name):
            continue
        text = f.read_text(encoding="latin-1")
        meta = {k: html.unescape(v) for k, v in re.findall(r'<meta name="([^"]+)"[^>]*?content=\s*"([^"]*)"', text, re.S)}
        out[f.stem] = meta
    return out


def main():
    letters = json.loads((BUILD / "letters.json").read_text())
    by_id = {l["id"]: l for l in letters}
    by_number = {}
    for l in letters:
        for n in edition_numbers(l["numbers"]["collectedLetters"]):
            by_number.setdefault(n, []).append(l["id"])
    webex = read_webexhibits()
    resolved = resolve_all(letters)
    md = ["# Comparison with the 2008–09 sources", ""]

    # 1. Concordance
    matched, unmatched = {}, []
    for wid in sorted(webex):
        ids = by_number.get(norm_number(wid))
        if ids:
            matched[wid] = ids[0]
        else:
            unmatched.append(wid)
    md += ["## 1. Concordance", "",
           f"{len(matched)} of {len(webex)} webexhibits documents map to an edition letter via the "
           f"Complete Letters number; {len(unmatched)} do not (mostly family/third-party documents the "
           "edition excludes or renumbers):", "", ", ".join(f"`{u}`" for u in unmatched), ""]

    # 2. Dates
    rows = []
    for wid, lid in matched.items():
        wd, d = webex[wid].get("DC.Date"), by_id[lid]["date"]
        if not wd or not re.fullmatch(r"\d{4}-\d\d-\d\d", wd):
            continue
        lo, hi = d["earliest"], d["latest"] or "9999-12-31"
        if not lo <= wd <= hi:
            off = min(abs((date.fromisoformat(wd) - date.fromisoformat(x)).days) for x in (lo, hi) if x != "9999-12-31")
            rows.append((off, wid, lid, wd, webex[wid].get("Date.Spread"), by_id[lid]["dateText"]))
    rows.sort(reverse=True)
    date_diffs = len(rows)
    buckets = Counter("≤7 days" if r[0] <= 7 else "8–30 days" if r[0] <= 30 else "31–365 days" if r[0] <= 365 else "> 1 year" for r in rows)
    md += ["## 2. Dates", "",
           f"{len(rows)} of {len(matched)} webexhibits dates fall outside the edition's interval: {dict(buckets)}.", "",
           "| webexhibits | edition | webexhibits date (± spread) | edition date | days off |", "|---|---|---|---|---|"]
    md += [f"| {w} | {l} | {wd} (±{sp}) | {t} | {off} |" for off, w, l, wd, sp, t in rows]
    md.append("")

    # 3. Sender places
    rows = []
    for wid, lid in matched.items():
        wl, el = webex[wid].get("Location", ""), by_id[lid]["placeText"]
        if _fold(wl) != _fold(el) and not (_fold(wl).startswith("saintr") and _fold(el).startswith("saintr")):
            rows.append((wid, lid, by_id[lid]["author"], wl, el))
    md += ["## 3. Sender places", "",
           f"{len(rows)} documents where the webexhibits `Location` differs from the edition heading "
           "(note: webexhibits `Location` was Vincent's location even for letters Theo wrote):", "",
           "| webexhibits | edition | author | webexhibits Location | edition heading |", "|---|---|---|---|---|"]
    md += [f"| {w} | {l} | {a} | {x} | {y} |" for w, l, a, x, y in rows]
    md.append("")

    # 4. 2009 routes
    changes, unresolved = [], 0
    with ROUTES_2009.open() as f:
        for r in csv.DictReader(f):
            wid = r["file"].removesuffix(".htm")
            lid = by_number.get(norm_number(wid), [None])[0]
            if not lid or lid not in resolved:
                continue
            new = resolved[lid]
            nf, nt = new["from"].get("place"), new["to"].get("place")
            if not nf or not nt:
                unresolved += 1
            of, ot = NAMES_2009.get(r["from"], r["from"]), NAMES_2009.get(r["to"], r["to"])
            if (nf and nf != of) or (nt and nt != ot):
                changes.append((lid, r["date"], by_id[lid]["date"]["earliest"], f"{of} → {ot}", f"{nf} → {nt}",
                                "; ".join(new["to"].get("evidence", [])[:2])))
    md += ["## 4. Routes vs the 2009 KML", "",
           f"{len(changes)} of 669 Vincent→Theo routes change; {unresolved} could not yet be resolved.", "",
           "| letter | 2009 date | edition date | 2009 route | new route | evidence (recipient) |", "|---|---|---|---|---|---|"]
    md += [f"| {a} | {b} | {c} | {d} | {e} | {g} |" for a, b, c, d, e, g in changes]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(md) + "\n")
    print(f"concordance: {len(matched)}/{len(webex)} matched")
    print(f"dates outside edition interval: {date_diffs}")
    print(f"sender place differences: {len(rows)}")
    print(f"2009 route changes: {len(changes)} (unresolved: {unresolved})")
    print(f"-> {REPORT.relative_to(ROOT)}")


def _fold(s):
    import unicodedata
    return re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower())


if __name__ == "__main__":
    main()
