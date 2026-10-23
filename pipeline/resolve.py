"""Resolve each letter's sender and recipient places from the curated data.

    python3 pipeline/resolve.py --person theo          # every letter to/from Theo, with his resolved place
    python3 pipeline/resolve.py --person theo --gaps   # only letters where Theo's place is unresolved/ambiguous

Library use: resolve_all(letters) -> {letter_id: {"from": {...}, "to": {...}}}
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BUILD = ROOT / "build" / "data"

# A letter usually arrived a day or two after it was written; look the recipient up across that window.
TRANSIT_DAYS = 2


def _load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


class Itinerary:
    def __init__(self, person, spec):
        self.person = person
        self.stays = spec.get("stays", [])
        self.at_letters = spec.get("atLetters", {})

    def _matching(self, day, kind):
        d = day.isoformat()
        return [s for s in self.stays if s.get("kind", "residence") == kind and s["from"] <= d <= s["to"]]

    def place_on(self, day):
        """Place on a single day: trips beat residences. Returns (stay or None, issue or None)."""
        for kind in ("trip", "residence"):
            hits = self._matching(day, kind)
            if len(hits) == 1:
                return hits[0], None
            if len(hits) > 1:
                return hits[0], f"overlapping {kind} stays on {day}"
        return None, f"no stay covers {day}"

    def locate(self, letter_id, earliest, latest):
        """Where this person was across [earliest, latest]."""
        if letter_id in self.at_letters:
            pin = self.at_letters[letter_id]
            return {"place": pin["place"], "basis": "atLetters", "evidence": pin.get("evidence", [])}
        days = [earliest + timedelta(n) for n in range((latest - earliest).days + 1)]
        seen, issues = {}, []
        for day in days:
            stay, issue = self.place_on(day)
            if issue:
                issues.append(issue)
            if stay:
                seen.setdefault(stay["place"], stay)
        if not seen:
            return {"place": None, "basis": "unresolved", "issues": sorted(set(issues))[:3]}
        stay = seen.get(self.place_on(latest)[0]["place"]) if self.place_on(latest)[0] else next(iter(seen.values()))
        result = {
            "place": stay["place"],
            "basis": stay.get("kind", "residence"),
            "approx": bool(stay.get("approx")),
            "evidence": stay.get("evidence", []),
        }
        if len(seen) > 1:
            result["ambiguous"] = sorted(seen)
        if issues:
            result["issues"] = sorted(set(issues))[:3]
        return result


def load_context():
    correspondents = _load(DATA / "correspondents.json", {})
    by_name = {n: key for key, c in correspondents.items() for n in c["editionNames"]}
    itineraries = {
        p.stem: Itinerary(p.stem, json.loads(p.read_text()))
        for p in sorted((DATA / "itineraries").glob("*.json"))
    }
    places = _load(DATA / "places.json", {})
    place_by_edition_name = {n: pid for pid, p in places.items() for n in p.get("editionNames", [])}
    overrides = _load(DATA / "overrides.json", {})
    return by_name, itineraries, places, place_by_edition_name, overrides


def resolve_letter(letter, ctx):
    by_name, itineraries, places, place_by_edition_name, overrides = ctx
    d = letter["date"]
    earliest = date.fromisoformat(d["earliest"])
    written = date.fromisoformat(d["latest"]) if d["latest"] else earliest
    out = {}

    author_key = by_name.get(letter["author"])
    pin = itineraries[author_key].at_letters.get(letter["id"]) if author_key in itineraries else None
    if pin:
        out["from"] = {"place": pin["place"], "basis": "atLetters", "evidence": pin.get("evidence", [])}
    elif letter["placeText"] in place_by_edition_name:
        out["from"] = {"place": place_by_edition_name[letter["placeText"]], "basis": "edition",
                       "evidence": [f"{letter['id']} heading"]}
    elif author_key in itineraries:
        out["from"] = itineraries[author_key].locate(letter["id"], earliest, written)
    else:
        out["from"] = {"place": None, "basis": "unresolved",
                       "issues": [f"no place for heading {letter['placeText']!r} / author {letter['author']!r}"]}

    to_key = by_name.get(letter["addressee"])
    if to_key in itineraries:
        out["to"] = itineraries[to_key].locate(letter["id"], earliest, written + timedelta(TRANSIT_DAYS))
    else:
        out["to"] = {"place": None, "basis": "unresolved",
                     "issues": [f"no itinerary for addressee {letter['addressee']!r} ({to_key})"]}
    for end, o in overrides.get(letter["id"], {}).items():  # data/overrides.json beats everything
        out[end] = {"place": o["place"], "basis": "override", "evidence": o.get("evidence", [])}
    out["authorKey"], out["addresseeKey"] = author_key, to_key
    for end in ("from", "to"):
        pid = out[end].get("place")
        if pid and pid not in places:
            out[end].setdefault("issues", []).append(f"place {pid!r} not in places.json")
    return out


def resolve_all(letters):
    ctx = load_context()
    return {l["id"]: resolve_letter(l, ctx) for l in letters if l["date"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--person", help="person key from data/correspondents.json")
    ap.add_argument("--gaps", action="store_true", help="only show unresolved, ambiguous or flagged rows")
    args = ap.parse_args()
    letters = json.loads((BUILD / "letters.json").read_text())
    resolved = resolve_all(letters)
    shown = problems = 0
    for l in letters:
        r = resolved.get(l["id"])
        if not r or (args.person and args.person not in (r["authorKey"], r["addresseeKey"])):
            continue
        ends = [e for e in ("from", "to") if not args.person or r[{"from": "authorKey", "to": "addresseeKey"}[e]] == args.person]
        bad = any(r[e].get("place") is None or r[e].get("ambiguous") or r[e].get("issues") for e in ends)
        problems += bad
        if args.gaps and not bad:
            continue
        shown += 1
        cols = []
        for e in ("from", "to"):
            x = r[e]
            flag = "" if x.get("place") else "!"
            flag += f" ambiguous={x['ambiguous']}" if x.get("ambiguous") else ""
            flag += f" issues={x['issues']}" if x.get("issues") else ""
            cols.append(f"{e}={x.get('place')}({x['basis']}){flag}")
        print(f"{l['id']:8} {l['date']['earliest']}..{l['date']['latest']}  {l['author']} -> {l['addressee']}  " + "  ".join(cols))
    print(f"-- {shown} shown, {problems} with problems")


if __name__ == "__main__":
    main()
