"""Search the English letter texts and editorial notes (requires pipeline/build.py to have run).

    python3 pipeline/search.py "moved to|arrived in" --addressee Rappard --after 1881-01-01 --before 1886-01-01
    python3 pipeline/search.py "Helvoirt" --notes-only

Prints one line per matching sentence: letter id, date, author -> addressee, [note n], sentence.
"""

import argparse
import html
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "build" / "data"


def sentences(fragment):
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    text = re.sub(r"\s+", " ", text).strip()
    return re.split(r"(?<=[.!?])\s+(?=[A-Z‘“(])", text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pattern")
    ap.add_argument("--addressee", help="regex on addressee")
    ap.add_argument("--author", help="regex on author")
    ap.add_argument("--after", help="YYYY-MM-DD, compares earliest date")
    ap.add_argument("--before", help="YYYY-MM-DD, compares earliest date")
    ap.add_argument("--notes-only", action="store_true")
    ap.add_argument("--letter-only", action="store_true")
    ap.add_argument("-i", action="store_true", help="case-insensitive")
    args = ap.parse_args()
    rx = re.compile(args.pattern, re.I if args.i else 0)

    for r in json.loads((DATA / "letters.json").read_text()):
        d = r["date"]["earliest"]
        if args.addressee and not re.search(args.addressee, r["addressee"]):
            continue
        if args.author and not re.search(args.author, r["author"]):
            continue
        if (args.after and d < args.after) or (args.before and d >= args.before):
            continue
        body = (DATA / "bodies" / f"{r['id']}.html").read_text()
        letter, _, notes = body.partition('<section class="notes">')
        chunks = []
        if not args.notes_only:
            chunks.append(("", letter))
        if not args.letter_only:
            chunks += [(f"n.{n}", t) for n, t in re.findall(r'<li id="[^"]*-n-([^"]+)"[^>]*>(.*?)</li>', notes, re.S)]
        for label, chunk in chunks:
            for s in sentences(chunk):
                if rx.search(s):
                    print(f"{r['id']} {d} {r['author']} -> {r['addressee']} [{r['placeText']}] {label}: {s}")


if __name__ == "__main__":
    main()
