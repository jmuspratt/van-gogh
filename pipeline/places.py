"""Maintain data/places.json: merge agent proposals, look up / verify Wikidata IDs, fetch coordinates.

    python3 pipeline/places.py            # dry run: print the review table
    python3 pipeline/places.py --write    # also write data/places.json

For each place:
- with no `wikidata`, search Wikidata by name and pick the first candidate that has coordinates and
  is in the expected country (`country`, ISO 3166-1 alpha-2);
- with a `wikidata` id, check that its label/aliases match the name and its country matches;
- copy Wikidata's coordinates unless the place sets `coordsSource` (manually placed, e.g. addresses).
Problems are printed as `!` rows and never silently written.
"""

import argparse
import http.client
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES = ROOT / "data" / "places.json"
PROPOSED = ROOT / "data" / "places.proposed"
SPARQL = "https://query.wikidata.org/sparql"
UA = {"User-Agent": "van-gogh-letters-research/0.1 (private research project)"}

COUNTRY_QIDS = {"NL": "Q55", "BE": "Q31", "FR": "Q142", "GB": "Q145", "DZ": "Q262", "DK": "Q35", "DE": "Q183"}


def _sparql(query, attempts=4):
    body = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(SPARQL, data=body, headers=UA)  # POST: queries can be long
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["results"]["bindings"]
        except (urllib.error.URLError, http.client.IncompleteRead, TimeoutError) as e:
            transient = not isinstance(e, urllib.error.HTTPError) or e.code == 429 or e.code >= 500
            if not transient or attempt == attempts - 1:
                raise
            retry_after = getattr(e, "headers", None) and e.headers.get("Retry-After")
            time.sleep(int(retry_after or 5 * (attempt + 1)))


def _fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum())


def _parse_point(wkt):
    lon, lat = map(float, re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", wkt).groups())
    return round(lat, 5), round(lon, 5)


def fetch_entities(qids):
    """{qid: {label, description, names, countries, lat, lon}}"""
    qids = sorted(set(qids))
    if not qids:
        return {}
    rows = _sparql(f"""
SELECT ?item ?label ?desc ?alt ?country ?coord WHERE {{
  VALUES ?item {{ {' '.join('wd:' + q for q in qids)} }}
  OPTIONAL {{ ?item rdfs:label ?label FILTER(LANG(?label) = "en") }}
  OPTIONAL {{ ?item schema:description ?desc FILTER(LANG(?desc) = "en") }}
  OPTIONAL {{ ?item rdfs:label|skos:altLabel ?alt FILTER(LANG(?alt) IN ("en", "nl", "fr", "da")) }}
  OPTIONAL {{ ?item wdt:P17 ?country }}
  OPTIONAL {{ ?item wdt:P625 ?coord }}
}}""")
    out = {}
    for r in rows:
        qid = r["item"]["value"].rsplit("/", 1)[1]
        e = out.setdefault(qid, {"label": qid, "description": "", "names": set(), "countries": set(),
                                 "lat": None, "lon": None})
        if "label" in r:
            e["label"] = r["label"]["value"]
        if "desc" in r:
            e["description"] = r["desc"]["value"]
        if "alt" in r:
            e["names"].add(r["alt"]["value"])
        if "country" in r:
            e["countries"].add(r["country"]["value"].rsplit("/", 1)[1])
        if "coord" in r and e["lat"] is None:
            e["lat"], e["lon"] = _parse_point(r["coord"]["value"])
    return out


def lookup(names_by_pid, countries_by_pid):
    """Find the best-linked item with an exact label/alias match, coordinates, and the expected country."""
    values = " ".join(
        f'("{pid}" "{name}"@{lang} wd:{COUNTRY_QIDS[countries_by_pid[pid]]})'
        for pid, name in names_by_pid.items() if countries_by_pid.get(pid) in COUNTRY_QIDS
        for lang in ("en", "nl", "fr", "da")
    )
    if not values:
        return {}
    rows = _sparql(f"""
SELECT ?pid ?item ?links WHERE {{
  VALUES (?pid ?name ?country) {{ {values} }}
  ?item rdfs:label|skos:altLabel ?name ; wdt:P17 ?country ; wdt:P625 [] ; wikibase:sitelinks ?links .
}}""")
    best = {}
    for r in rows:
        pid, qid, links = r["pid"]["value"], r["item"]["value"].rsplit("/", 1)[1], int(r["links"]["value"])
        if pid not in best or links > best[pid][1]:
            best[pid] = (qid, links)
    return {pid: qid for pid, (qid, _) in best.items()}


def merge_proposals(places):
    notes = []
    for path in sorted(PROPOSED.glob("*.json")):
        for pid, p in json.loads(path.read_text()).items():
            if not p.get("wikidata") and p.get("kind") != "address":
                # Guessed coordinates for a real town: look it up instead of trusting the guess.
                p = {k: v for k, v in p.items() if k not in ("lat", "lon", "coordsSource")}
            if pid not in places:
                places[pid] = {**p, "proposedBy": path.stem}
            else:
                cur = places[pid]
                for k, v in p.items():
                    if v is None or k in ("lat", "lon") and not p.get("coordsSource"):
                        continue
                    if cur.get(k) is None:
                        cur[k] = v
                    elif cur[k] != v and k not in ("name", "lat", "lon"):
                        notes.append(f"{pid}: {path.stem} proposes {k}={v!r}, keeping {cur[k]!r}")
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    places = json.loads(PLACES.read_text()) if PLACES.exists() else {}
    notes = merge_proposals(places)

    # Look up missing QIDs.
    missing = {pid: p.get("search") or p["name"] for pid, p in places.items()
               if not p.get("wikidata") and not p.get("coordsSource")}
    for pid, qid in lookup(missing, {pid: places[pid].get("country") for pid in missing}).items():
        places[pid]["wikidata"] = qid
        places[pid]["_looked_up"] = True

    ents = fetch_entities({p["wikidata"] for p in places.values() if p.get("wikidata")})
    problems = 0
    print(f"{'id':26} {'qid':10} {'lat':>9} {'lon':>9}  wikidata label — description")
    for pid, p in sorted(places.items()):
        qid, e = p.get("wikidata"), ents.get(p.get("wikidata"))
        flags = []
        if p.get("coordsSource"):
            flags.append(f"manual coords ({p['coordsSource']})")
        elif not qid:
            flags.append("! no wikidata match")
        elif not e:
            flags.append("! qid not found")
        else:
            if _fold(p["name"]) not in {_fold(n) for n in e["names"]} and not any(
                    _fold(p["name"]) in _fold(n) or _fold(n) in _fold(p["name"]) for n in e["names"]):
                flags.append(f"! name mismatch")
            want = COUNTRY_QIDS.get(p.get("country"))
            if want and want not in e["countries"] and qid != want:
                flags.append("! country mismatch")
            if e["lat"] is None:
                flags.append("! no coords")
            else:
                p["lat"], p["lon"] = e["lat"], e["lon"]
        if p.pop("_looked_up", False):
            flags.append("(looked up)")
        problems += any(f.startswith("!") for f in flags)
        desc = f"{e['label']} — {e['description']}" if e else ""
        print(f"{pid:26} {qid or '-':10} {p.get('lat') or '':>9} {p.get('lon') or '':>9}  {desc[:70]}  {' '.join(flags)}")
    for n in notes:
        print("note:", n)
    print(f"-- {len(places)} places, {problems} with problems")

    if args.write:
        ordered = {k: {f: v for f, v in places[k].items() if v is not None} for k in sorted(places)}
        PLACES.write_text(json.dumps(ordered, ensure_ascii=False, indent=1) + "\n")
        print(f"wrote {PLACES.relative_to(ROOT)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
