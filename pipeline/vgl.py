"""Read the Van Gogh Letters TEI files (vendor/vangoghletters-tei).

Each file yields a metadata record and an English HTML body (translation + notes).
The original-language text is deliberately not extracted.
"""

import html
import re
import xml.etree.ElementTree as ET

TEI = "http://www.tei-c.org/ns/1.0"
VG = "http://www.vangoghletters.org/ns/"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
NS = {"t": TEI, "vg": VG}


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _text(el):
    """Plain text of an element, whitespace collapsed."""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


# ---------------------------------------------------------------------------
# TEI -> HTML
# ---------------------------------------------------------------------------

RS_CLASSES = {
    "pers": "person",
    "ill": "artwork",  # works by Van Gogh (F / JH numbers)
    "otherart": "other-artwork",
    "lit": "literature",
    "sketch": "sketch-ref",
    "topo": "place",
}


class _HtmlWriter:
    def __init__(self, letter_id):
        self.letter_id = letter_id
        self.out = []

    def esc(self, s):
        if s:
            self.out.append(html.escape(re.sub(r"\s+", " ", s), quote=False))

    def children(self, el):
        self.esc(el.text)
        for child in el:
            self.node(child)
            self.esc(child.tail)

    def wrap(self, tag, el, attrs=""):
        self.out.append(f"<{tag}{attrs}>")
        self.children(el)
        self.out.append(f"</{tag}>")

    def node(self, el):
        tag = _local(el.tag)
        if tag == "ab":
            rend = (el.get("rend") or "").strip()
            self.wrap("p", el, f' class="{rend}"' if rend in ("indent", "separate") else "")
        elif tag == "hi":
            rend = el.get("rend")
            if rend == "ital":
                self.wrap("em", el)
            elif rend == "bold":
                self.wrap("strong", el)
            elif rend == "sc":
                self.wrap("span", el, ' class="smallcaps"')
            elif rend == "ss":
                self.wrap("sup", el)
            else:
                self.children(el)
        elif tag == "rs":
            cls = RS_CLASSES.get(el.get("type"), "ref")
            key = el.get("key")
            self.wrap("span", el, f' class="{cls}"' + (f' data-key="{html.escape(key)}"' if key else ""))
        elif tag == "anchor":
            n = el.get("n")
            self.out.append(f'<sup class="note-ref"><a href="#{self.letter_id}-n-{n}">{n}</a></sup>')
        elif tag == "figure":
            # Sketch in the manuscript; images live on vangoghletters.org.
            self.out.append(f'<span class="sketch" data-n="{html.escape(el.get("n") or "")}"></span>')
        elif tag == "whiteline":
            self.out.append('<hr class="whiteline">')
        elif tag == "ref":
            target = el.get("target") or ""
            m = re.match(r"(let\d+[a-z]?|RM\d+)\.xml", target)
            if m:
                self.wrap("a", el, f' class="letter-ref" data-letter="{m.group(1)}"')
            else:
                # Line references (#l-12) point into the original text, which we don't show.
                self.children(el)
        elif tag == "bibleref":
            self.wrap("cite", el, ' class="bible"')
        elif tag == "c" and el.get("type") in ("kp", "kk"):
            pass  # typographic marks in the manuscript
        elif tag in ("pb", "lb"):
            pass
        else:  # supplied, c, and anything unforeseen: keep the text
            self.children(el)

    def html(self):
        return "".join(self.out)


def _render(el, letter_id):
    w = _HtmlWriter(letter_id)
    w.children(el)
    return w.html()


def _render_body(root, letter_id):
    parts = []
    translation = root.find(".//t:body/t:div[@type='translation']", NS)
    if translation is not None:
        parts.append(f'<section class="letter">{_render(translation, letter_id)}</section>')
    notes = root.find(".//t:body/t:div[@type='notes']", NS)
    items = []
    if notes is not None:
        for note in notes.findall("t:note", NS):
            # Notes targeting the original text (#note-o-*) are textual notes on the Dutch/French.
            if not (note.get("target") or "").startswith("#note-t-"):
                continue
            n = note.get("n")
            items.append(f'<li id="{letter_id}-n-{n}" value="{n}">{_render(note, letter_id)}</li>')
    if items:
        parts.append('<section class="notes"><ol>' + "".join(items) + "</ol></section>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def read_letter(path):
    root = ET.parse(path).getroot()
    letter_id = path.stem
    heading = root.find(".//vg:letHeading", NS)
    ids = {
        i.get("type"): (i.text or "").strip()
        for i in root.findall(".//vg:letIdentifier/t:idno", NS)
    }
    original = root.find(".//t:body/t:div[@type='original']", NS)
    record = {
        "id": letter_id,
        "kind": "related" if letter_id.startswith("RM") else "letter",
        "title": _text(root.find(".//t:titleStmt/t:title", NS)),
        "numbers": {
            "edition": ids.get("jlb") or None,
            "collectedLetters": ids.get("collectedletters") or None,  # 1958 Complete Letters = webexhibits ids
            "brieven1990": ids.get("brieven1990") or None,
        },
        "author": _text(heading.find("t:author", NS)),
        "addressee": _text(heading.find("vg:addressee", NS)),
        "placeText": _text(heading.find("vg:placeLet", NS)),
        "dateText": _text(heading.find("vg:dateLet", NS)),
        "dateNote": _text(root.find(".//t:note[@type='date']", NS)) or None,
        "sourceStatus": _text(root.find(".//t:note[@type='sourceStatus']", NS)) or None,
        "holding": _text(root.find(".//t:note[@type='location']", NS)) or None,
        "originalLanguage": original.get("{http://www.w3.org/XML/1998/namespace}lang") if original is not None else None,
        "sketches": len(root.findall(".//t:div[@type='translation']//t:figure", NS)),
        "url": (root.find(".//t:publicationStmt/t:ptr", NS).get("target")
                if root.find(".//t:publicationStmt/t:ptr", NS) is not None else None),
    }
    refs = sorted({
        m.group(1)
        for r in root.iter(f"{{{TEI}}}ref")
        if (m := re.match(r"(let\d+[a-z]?|RM\d+)\.xml", r.get("target") or "")) and m.group(1) != letter_id
    })
    record["refs"] = refs
    return record, _render_body(root, letter_id)


def read_people(path):
    root = ET.parse(path).getroot()
    people = {}
    for p in root.iter(f"{{{TEI}}}person"):
        pid = p.get(XML_ID)
        people[pid.lstrip("P")] = {
            "name": _text(p.find("t:persName", NS)),
            "note": _text(p.find("t:note", NS)) or None,
        }
    return people
