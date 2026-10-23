// Vincent and Theo as markers that follow their itineraries (trips override residences), with HTML
// labels. When the place changes during playback the marker glides there; when scrubbing it jumps.

import * as THREE from "three";
import type { Data, Itinerary, Stay } from "./data";
import type { MapScene } from "./scene";
import { AUTHOR_COLORS } from "./letters";
import { toDay } from "./time";

interface Person {
  key: string;
  label: string;
  stays: (Stay & { lo: number; hi: number })[];
  marker: THREE.Sprite;
  el: HTMLElement;
  placeId: string | null;
  from: THREE.Vector3;
  to: THREE.Vector3;
  tween: number; // 0..1 progress of the current move
}

const MOVE_SECONDS = 0.9;

function ringTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  g.strokeStyle = "white";
  g.lineWidth = 6;
  g.beginPath();
  g.arc(32, 32, 22, 0, Math.PI * 2);
  g.stroke();
  g.fillStyle = "rgba(255,255,255,0.35)";
  g.beginPath();
  g.arc(32, 32, 8, 0, Math.PI * 2);
  g.fill();
  return new THREE.CanvasTexture(c);
}

export class PeopleLayer {
  private readonly people: Person[] = [];

  constructor(private readonly view: MapScene, private readonly data: Data, overlay: HTMLElement) {
    const tex = ringTexture();
    const who: [string, string, number][] = [
      ["vincent", "Vincent", AUTHOR_COLORS.vincent],
      ["theo", "Theo", AUTHOR_COLORS.theo],
    ];
    for (const [key, label, color] of who) {
      const itin: Itinerary | undefined = data.itineraries[key];
      if (!itin) continue;
      const marker = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color, depthWrite: false, transparent: true, sizeAttenuation: false }));
      marker.scale.setScalar(0.03);
      marker.visible = false;
      view.scene.add(marker);
      const el = document.createElement("div");
      el.className = `person-label ${key}`;
      overlay.appendChild(el);
      this.people.push({
        key, label, marker, el, placeId: null, from: new THREE.Vector3(), to: new THREE.Vector3(), tween: 1,
        stays: itin.stays.map((s) => ({ ...s, lo: toDay(s.from), hi: toDay(s.to) + 1 })),
      });
    }
  }

  private placeAt(p: Person, t: number): string | null {
    const covering = p.stays.filter((s) => s.lo <= t && t < s.hi);
    return (covering.find((s) => s.kind === "trip") ?? covering[0])?.place ?? null;
  }

  update(t: number, dt: number, playing: boolean) {
    for (const p of this.people) {
      const id = this.placeAt(p, t);
      const pos = id ? this.data.places[id]?.map : null;
      if (!pos) {
        p.marker.visible = false;
        p.el.style.display = "none";
        p.placeId = id;
        continue;
      }
      if (id !== p.placeId) {
        const target = this.view.toWorld(pos.x, pos.y, 0.02);
        p.from.copy(p.placeId && playing ? p.marker.position : target);
        p.to.copy(target);
        p.tween = p.placeId && playing ? 0 : 1;
        p.placeId = id;
      }
      p.tween = Math.min(1, p.tween + dt / MOVE_SECONDS);
      const e = p.tween < 1 ? p.tween * p.tween * (3 - 2 * p.tween) : 1;
      p.marker.position.lerpVectors(p.from, p.to, e);
      p.marker.visible = true;

      // HTML label next to the marker.
      const s = p.marker.position.clone().project(this.view.camera);
      const { x: w, y: h } = this.view.size;
      p.el.style.display = s.z < 1 ? "block" : "none";
      p.el.style.transform = `translate(${((s.x + 1) / 2) * w + 12}px, ${((1 - s.y) / 2) * h - 9}px)`;
      p.el.textContent = `${p.label} · ${this.data.places[id!]?.name ?? ""}`;
    }
  }
}
