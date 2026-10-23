// The reading pane: a letter's heading, where it went and how we know, the edition's date
// reasoning, and the full English text with the editorial notes.

import { loadBody, type Data, type Letter, type LetterEnd } from "./data";

const BASIS: Record<string, string> = {
  edition: "as headed in the letter",
  residence: "living there",
  trip: "travelling",
  atLetters: "per the edition's notes",
  override: "editorial decision",
};

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

export class Reader {
  private current: string | null = null;

  constructor(private readonly root: HTMLElement, private readonly data: Data, private readonly onNavigate: (id: string) => void) {
    root.addEventListener("click", (e) => {
      const a = (e.target as HTMLElement).closest<HTMLElement>("a.letter-ref, .close");
      if (!a) return;
      e.preventDefault();
      if (a.classList.contains("close")) this.close();
      else if (a.dataset.letter) this.onNavigate(a.dataset.letter);
    });
  }

  private end(e: LetterEnd) {
    if (!e.place) return `<span class="unknown">unknown</span>`;
    const name = this.data.places[e.place]?.name ?? e.place;
    const alt = e.ambiguous?.filter((p) => p !== e.place).map((p) => this.data.places[p]?.name ?? p);
    const basis = BASIS[e.basis] ?? e.basis;
    return `${esc(name)} <span class="basis">${esc(basis)}${alt?.length ? `; possibly ${esc(alt.join(", "))}` : ""}${e.approx ? "; dates approximate" : ""}</span>`;
  }

  async open(letter: Letter) {
    this.current = letter.id;
    this.root.classList.add("open");
    const d = letter.date;
    this.root.innerHTML = `
      <button class="close" title="Close (Esc)">×</button>
      <header>
        <div class="number">${esc(letter.id.replace(/^let0*/, "Letter "))}${letter.kind === "related" ? " · related manuscript" : ""}</div>
        <h2>${esc(letter.author)} <span>to</span> ${esc(letter.addressee)}</h2>
        <div class="date">${esc(letter.dateText)}${d?.approximate || d?.precision !== "day" ? ` <span class="basis">${d?.probable ? "probable" : "approximate"}</span>` : ""}</div>
        <dl class="route">
          <dt>From</dt><dd>${this.end(letter.from)}</dd>
          <dt>To</dt><dd>${this.end(letter.to)}</dd>
        </dl>
        ${letter.dateNote ? `<details><summary>How the edition dates this letter</summary><p>${esc(letter.dateNote)}</p></details>` : ""}
      </header>
      <article><p class="loading">Loading…</p></article>
      <footer>${esc(letter.sourceStatus ?? "")}${letter.url ? ` · <a href="${esc(letter.url)}" target="_blank" rel="noopener">vangoghletters.org</a>` : ""}</footer>`;
    const body = await loadBody(letter.id);
    if (this.current !== letter.id) return; // another letter was opened meanwhile
    this.root.querySelector("article")!.innerHTML = body;
    this.root.scrollTop = 0;
  }

  close() {
    this.current = null;
    this.root.classList.remove("open");
  }

  get isOpen() {
    return this.current !== null;
  }
}
