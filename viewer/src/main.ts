import * as THREE from "three";
import "./style.css";
import { loadData } from "./data";
import { CATEGORY_LABELS, LetterLayer, type Category, type Flight } from "./letters";
import { PeopleLayer } from "./people";
import { Reader } from "./reader";
import { MapScene } from "./scene";
import { Timeline } from "./timeline";

const $ = (sel: string) => document.querySelector<HTMLElement>(sel)!;

async function main() {
  const data = await loadData();
  const view = new MapScene($("#stage"), data.tiles);
  const letters = new LetterLayer(view, data);
  const people = new PeopleLayer(view, data, $("#overlay"));
  const timeline = new Timeline($("#timeline"), $("#date"), letters.flights);
  const byId = new Map(letters.flights.map((f) => [f.letter.id, f]));

  // Jump to a letter: open it and move time to just after it arrived.
  const show = (f: Flight) => {
    letters.selected = f;
    timeline.t = Math.max(timeline.t, f.send + 3);
    if (timeline.t > f.send + 400) timeline.t = f.send + 3;
    reader.open(f.letter);
  };
  const reader = new Reader($("#reader"), data, (id) => {
    const f = byId.get(id);
    if (f) show(f);
  });

  // Side panel: filters, camera presets, credit.
  $("#filters").innerHTML = (Object.entries(CATEGORY_LABELS) as [Category, string][])
    .map(([k, label]) => {
      const n = letters.flights.filter((f) => f.category === k).length;
      return `<label class="${k}"><input type="checkbox" value="${k}" checked> ${label} <span>${n}</span></label>`;
    })
    .join("");
  $("#filters").onchange = (e) => {
    const box = e.target as HTMLInputElement;
    if (box.checked) letters.enabled.add(box.value as Category);
    else letters.enabled.delete(box.value as Category);
  };
  $("#views").onclick = (e) => {
    const v = (e.target as HTMLElement).dataset.view as "overview" | "lowlands" | "provence" | undefined;
    if (v) view.frame(v);
  };
  $("#panel .credit").innerHTML =
    `Letters: <a href="https://vangoghletters.org" target="_blank" rel="noopener">Van Gogh Museum &amp; Huygens ING</a> (CC BY-NC-SA). ` +
    `Map: ${data.map.authors}, <a href="${data.map.source}" target="_blank" rel="noopener"><i>${data.map.title.split(".")[0]}</i>, ${data.map.year}</a>.`;

  // Hover tooltip and click-to-read.
  const tooltip = $("#tooltip");
  const ndc = new THREE.Vector2();
  let pointer: { x: number; y: number } | null = null;
  view.renderer.domElement.addEventListener("pointermove", (e) => (pointer = { x: e.clientX, y: e.clientY }));
  view.renderer.domElement.addEventListener("pointerleave", () => (pointer = null));
  let downAt = { x: 0, y: 0 };
  view.renderer.domElement.addEventListener("pointerdown", (e) => (downAt = { x: e.clientX, y: e.clientY }));
  view.renderer.domElement.addEventListener("click", (e) => {
    if (Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 4) return; // a drag, not a click
    if (letters.hovered) show(letters.hovered);
  });
  const place = (id: string | null) => (id ? data.places[id]?.name ?? id : "?");
  const updateHover = () => {
    letters.hovered = null;
    if (pointer) {
      const { width, height, left, top } = view.renderer.domElement.getBoundingClientRect();
      ndc.set(((pointer.x - left) / width) * 2 - 1, -((pointer.y - top) / height) * 2 + 1);
      letters.hovered = letters.pick(ndc);
    }
    const f = letters.hovered;
    view.renderer.domElement.style.cursor = f ? "pointer" : "";
    tooltip.style.display = f && pointer ? "block" : "none";
    if (f && pointer) {
      tooltip.style.transform = `translate(${pointer.x + 14}px, ${pointer.y + 14}px)`;
      tooltip.innerHTML = `<b>${f.letter.dateText}</b><br>${f.letter.author} → ${f.letter.addressee}<br>` +
        `<span>${place(f.letter.from.place)} → ${place(f.letter.to.place)}</span>`;
    }
  };

  window.addEventListener("keydown", (e) => {
    if ((e.target as HTMLElement).tagName === "SELECT") return;
    if (e.key === " ") {
      e.preventDefault();
      timeline.toggle();
    } else if (e.key === "Escape") {
      reader.close();
      letters.selected = null;
    } else if (e.key === "ArrowRight") timeline.step(30);
    else if (e.key === "ArrowLeft") timeline.step(-30);
  });

  $("#status").remove();
  const clock = new THREE.Clock();
  let frame = 0;
  view.renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.1);
    timeline.tick(dt);
    if (frame++ % 2 === 0) updateHover(); // raycasting ~900 lines: every other frame is plenty
    letters.update(timeline.t, timeline.speed);
    people.update(timeline.t, dt, timeline.playing);
    view.controls.update();
    view.renderer.render(view.scene, view.camera);
  });
}

main().catch((err) => {
  $("#status").textContent = String(err);
  console.error(err);
});
