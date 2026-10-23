# Curated data

Hand-maintained inputs to `pipeline/build.py`. Everything here is a claim about the past, so every
claim carries evidence.

## Evidence citations

Strings in an `evidence` array, most specific first:

- `let376 n.1`: note 1 of letter 376 in the edition (find it with `pipeline/search.py`)
- `let376`: the letter text itself
- `Stolwijk & Thomson 1999, p. 184`: *Theo van Gogh 1857–1891* chronology (scans in `reference/theo bio/`)
- `inferred: <reason>`: our own reasoning, e.g. "letters 360–371 all sent from The Hague"

## `places.json`

```json
{ "nuenen": { "name": "Nuenen", "wikidata": "Q9806", "kind": "town", "lat": 51.47, "lon": 5.55 } }
```

IDs are lowercase slugs. `kind`: `city | town | village | region | address`. For `address`,
add `"within": "<place id>"` and coordinates for the building. `lat`/`lon` are fetched from Wikidata
by `pipeline/places.py` unless `"coordsSource"` says otherwise (e.g. addresses without a QID).

## `correspondents.json`

Maps the edition's author/addressee strings to person keys that have itineraries.

```json
{ "theo": { "name": "Theo van Gogh", "editionNames": ["Theo van Gogh", "Theo van Gogh and Jo van Gogh-Bonger"] } }
```

## `itineraries/<person>.json`

Where a person was, over time.

```json
{
  "person": "theo",
  "stays": [
    { "place": "brussels", "from": "1873-01-01", "to": "1873-11-11", "kind": "residence",
      "approx": true, "note": "Goupil & Cie, Montagne de la Cour 58",
      "evidence": ["Stolwijk & Thomson 1999, p. 183"] },
    { "place": "nuenen", "from": "1883-08-19", "to": "1883-08-28", "kind": "trip",
      "evidence": ["let376 n.1", "Stolwijk & Thomson 1999, p. 185"] }
  ],
  "atLetters": {
    "let376": { "place": "nuenen", "evidence": ["let376 n.1"] }
  }
}
```

- `from` / `to` are inclusive ISO dates. If a bound is only known to the month, use the
  conservative day and set `"approx": true`.
- `kind: "residence"` stays should tile the person's life without overlaps. `kind: "trip"` stays
  override the residence for their dates.
- `atLetters` pins the person's location for a specific letter (as sender or recipient) when the
  edition says so directly. It beats any stay.

Lookup order for "where was X when letter L arrived/was written": `atLetters` → `trip` → `residence`.

## `overrides.json`

Per-letter `from` / `to` places that no itinerary can express (e.g. a printed announcement from
three families). Beats every other source: `{ "let759": { "from": { "place": ..., "evidence": [...] } } }`.

## `maps/<map>.json`

Georeferencing for a scanned base map (see `pipeline/georef.py`): `gcps` are hand-verified pixel
positions of printed town symbols (`{id: [x, y]}`, ids from `places.json` or the file's own `anchors`);
`model` is a cubic polynomial lon/lat → pixel fitted to them; `positions` is the output used by the
build — printed towns keep their printed position, unprinted places get the model's estimate. The
map's own engraving accuracy at 1:3M is about ±2–3 km, which is also the typical error for unprinted
villages.
