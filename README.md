# van-gogh
Van Gogh's letters, in Google Earth

## Data pipeline (2026)

The canonical source is the TEI edition of *Vincent van Gogh – The Letters*
(vangoghletters.org), vendored in `vendor/vangoghletters-tei/` (CC BY-NC-SA 4.0).

    python3 pipeline/build.py                 # -> build/data/{letters,people}.json, bodies/*.html
    python3 -m unittest discover pipeline     # date parser tests

No dependencies beyond Python 3.10+. `source/` holds the original 2008–09 webexhibits data and is
kept for cross-checking only.
