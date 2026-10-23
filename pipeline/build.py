"""Build the letter dataset from the Van Gogh Letters TEI.

    python3 pipeline/build.py

Writes build/data/letters.json, build/data/people.json and build/data/bodies/<id>.html,
then prints a validation report. Exits non-zero if any date fails to parse.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dates import DateParseError, parse_date  # noqa: E402
from vgl import read_letter, read_people  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEI_DIR = ROOT / "vendor" / "vangoghletters-tei"
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

    letters.sort(key=lambda r: (r["date"] or {}).get("earliest") or "9999", reverse=False)
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
