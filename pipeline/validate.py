"""Validate the curated itineraries in data/itineraries/.

    python3 pipeline/validate.py

Checks, per person:
- every stay/pin has evidence, and every `letNNN n.N` / `letNNN` citation exists in the edition
  (catches mistyped or invented citations);
- dates are valid ISO dates with from <= to;
- residence stays don't overlap or leave gaps between the first and last residence;
- every place id exists in data/places.json.
Also lists `inferred:` evidence so it can be reviewed.
"""

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BODIES = ROOT / "build" / "data" / "bodies"


def main(show_inferred="--inferred" in sys.argv):
    places = json.loads((ROOT / "data" / "places.json").read_text())
    note_ids = {}
    for f in BODIES.glob("*.html"):
        note_ids[f.stem] = set(re.findall(r'id="[^"]*-n-([^"]+)"', f.read_text()))
    errors, inferred = [], []

    def check_evidence(who, where, evidence):
        if not evidence:
            errors.append(f"{who}: {where}: no evidence")
        for e in evidence or []:
            if e.startswith("inferred:"):
                inferred.append(f"{who}: {where}: {e}")
            for lid, n in re.findall(r"\b(let\d{3}[a-z]?|RM\d\d)(?: n\. ?(\w+))?", e):
                if lid not in note_ids:
                    errors.append(f"{who}: {where}: cites unknown letter {lid}")
                elif n and n not in note_ids[lid]:
                    errors.append(f"{who}: {where}: cites {lid} n.{n}, which does not exist")

    for path in sorted((ROOT / "data" / "itineraries").glob("*.json")):
        who = path.stem
        spec = json.loads(path.read_text())
        residences = []
        for i, s in enumerate(spec.get("stays", [])):
            where = f"stay {s.get('place')} {s.get('from')}..{s.get('to')}"
            try:
                lo, hi = date.fromisoformat(s["from"]), date.fromisoformat(s["to"])
                if lo > hi:
                    errors.append(f"{who}: {where}: from > to")
            except (KeyError, ValueError) as e:
                errors.append(f"{who}: {where}: bad date ({e})")
                continue
            if s.get("place") not in places:
                errors.append(f"{who}: {where}: unknown place {s.get('place')!r}")
            check_evidence(who, where, s.get("evidence"))
            if s.get("kind", "residence") == "residence":
                residences.append((lo, hi, s["place"]))
        residences.sort()
        for (lo1, hi1, p1), (lo2, hi2, p2) in zip(residences, residences[1:]):
            if lo2 <= hi1:
                errors.append(f"{who}: residences overlap: {p1} ..{hi1} / {p2} {lo2}..")
            elif lo2 > hi1 + timedelta(1):
                errors.append(f"{who}: gap between residences: {p1} ..{hi1} / {p2} {lo2}..")
        for lid, pin in spec.get("atLetters", {}).items():
            if lid not in note_ids:
                errors.append(f"{who}: atLetters {lid}: unknown letter")
            if pin.get("place") not in places:
                errors.append(f"{who}: atLetters {lid}: unknown place {pin.get('place')!r}")
            check_evidence(who, f"atLetters {lid}", pin.get("evidence"))

    for e in errors:
        print("ERROR", e)
    if show_inferred:
        for e in inferred:
            print("INFERRED", e)
    print(f"-- {len(errors)} errors, {len(inferred)} inferred claims (show with --inferred)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
