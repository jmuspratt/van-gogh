// Letters as arcs over the map. Each letter is a Line2 (fat line) along a quadratic Bézier from the
// sender's place to the recipient's. As simulated time passes the letter's send date, a glowing
// head draws the arc; once it lands the arc fades out over a timeline year, so the routes in use
// at any moment build up into visible corridors.

import * as THREE from "three";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import type { Data, Letter } from "./data";
import type { MapScene } from "./scene";
import { toDay } from "./time";

export type Category = "vincent-theo" | "theo-vincent" | "vincent-other" | "other-vincent";

export const CATEGORY_LABELS: Record<Category, string> = {
  "vincent-theo": "Vincent → Theo",
  "theo-vincent": "Theo → Vincent",
  "vincent-other": "Vincent → others",
  "other-vincent": "Others → Vincent",
};

/** Colours by author: Vincent blue, Theo orange (the 2008 key), everyone else parchment. */
export const AUTHOR_COLORS = { vincent: 0x7cc8ff, theo: 0xffaa4c, other: 0xeadcb8 };

const SEGMENTS = 64;
const TRANSIT_DAYS = 2; // typical post time; also the minimum flight length in simulated days
const FLIGHT_SECONDS = 1.4; // a flight never lasts less than this in real time, whatever the speed
const TRAIL_PEAK = 0.5; // brightness just after landing
const TRAIL_LIFETIME_DAYS = 365; // a letter's arc is gone one timeline year after it was sent

export interface Flight {
  letter: Letter;
  category: Category;
  send: number; // simulated day the letter leaves
  from: THREE.Vector3;
  to: THREE.Vector3;
  local: boolean; // same place (hand-delivered note): drawn as a pulse, no arc
  curve: THREE.QuadraticBezierCurve3 | null;
  line: Line2 | null;
  material: LineMaterial | null;
  head: THREE.Sprite;
  brightness: number;
}

function category(l: Letter): Category | null {
  if (l.authorKey === "vincent") return l.addresseeKey === "theo" ? "vincent-theo" : "vincent-other";
  if (l.addresseeKey === "vincent") return l.authorKey === "theo" ? "theo-vincent" : "other-vincent";
  return null; // e.g. third-party documents with no Vincent end
}

function colorFor(l: Letter) {
  return l.authorKey === "vincent" ? AUTHOR_COLORS.vincent : l.authorKey === "theo" ? AUTHOR_COLORS.theo : AUTHOR_COLORS.other;
}

/** Deterministic pseudo-random in [0, 1) from a string, so each letter's arc keeps its shape. */
function hash(s: string, salt = 0) {
  let h = 2166136261 ^ salt;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return ((h >>> 0) % 100000) / 100000;
}

function glowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.25, "rgba(255,255,255,0.8)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

export class LetterLayer {
  readonly flights: Flight[] = [];
  readonly enabled = new Set<Category>(Object.keys(CATEGORY_LABELS) as Category[]);
  hovered: Flight | null = null;
  selected: Flight | null = null;
  private readonly group = new THREE.Group();
  private readonly raycaster = new THREE.Raycaster();
  private readonly lines: Line2[] = [];

  constructor(private readonly view: MapScene, data: Data) {
    const glow = glowTexture();
    const resolution = view.size;
    for (const letter of data.letters) {
      const cat = category(letter);
      const fp = letter.from.place ? data.places[letter.from.place]?.map : null;
      const tp = letter.to.place ? data.places[letter.to.place]?.map : null;
      if (!cat || !letter.date || !fp || !tp) continue;

      const lo = toDay(letter.date.earliest);
      const hi = letter.date.latest ? toDay(letter.date.latest) : lo;
      const from = view.toWorld(fp.x, fp.y);
      const to = view.toWorld(tp.x, tp.y);
      const local = from.distanceTo(to) < 0.05;
      const color = colorFor(letter);

      const head = new THREE.Sprite(new THREE.SpriteMaterial({
        map: glow, color, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, sizeAttenuation: false,
      }));
      head.visible = false;
      this.group.add(head);

      const flight: Flight = {
        letter, category: cat, send: (lo + hi) / 2, from, to, local, curve: null, line: null, material: null, head, brightness: 0,
      };

      if (!local) {
        // Arc height grows with distance; a little per-letter variation fans repeated routes into a sheaf.
        const dist = from.distanceTo(to);
        const side = new THREE.Vector3().subVectors(to, from).cross(new THREE.Vector3(0, 1, 0)).normalize();
        const mid = from.clone().lerp(to, 0.5);
        mid.y += (0.5 + dist * 0.3) * (0.85 + 0.3 * hash(letter.id, 1));
        mid.addScaledVector(side, (hash(letter.id, 2) - 0.5) * Math.min(dist * 0.15, 1.5));
        flight.curve = new THREE.QuadraticBezierCurve3(from, mid, to);

        const pts = flight.curve.getPoints(SEGMENTS).flatMap((p) => [p.x, p.y, p.z]);
        const geometry = new LineGeometry();
        geometry.setPositions(pts);
        const material = new LineMaterial({
          color, linewidth: 1.6, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false,
          dashed: !!letter.to.ambiguous, dashSize: 0.25, gapSize: 0.18, resolution,
        });
        const line = new Line2(geometry, material);
        if (letter.to.ambiguous) line.computeLineDistances();
        line.visible = false;
        line.userData.flight = flight;
        this.group.add(line);
        this.lines.push(line);
        flight.line = line;
        flight.material = material;
      }
      this.flights.push(flight);
    }
    view.scene.add(this.group);
    window.addEventListener("resize", () => {
      const r = view.size;
      for (const f of this.flights) f.material?.resolution.copy(r);
    });
  }

  /** Advance every letter to simulated day `t`; `daysPerSecond` sets how long a flight takes on screen. */
  update(t: number, daysPerSecond: number) {
    const duration = Math.max(TRANSIT_DAYS, daysPerSecond * FLIGHT_SECONDS);
    for (const f of this.flights) {
      const shown = this.enabled.has(f.category);
      const p = (t - f.send) / duration;
      const emphasised = f === this.hovered || f === this.selected;

      // Head: travels during the flight, then lingers briefly as a pulse at the destination.
      if (shown && p >= 0 && p < 1.5) {
        const pos = p < 1 && f.curve ? f.curve.getPoint(p) : f.to;
        f.head.position.copy(pos);
        const fade = p < 1 ? 1 : 1 - (p - 1) / 0.5;
        const pulse = f.local || p >= 1 ? 1 + (Math.min(p, 1.5) - (f.local ? 0 : 1)) * 2.5 : 1;
        f.head.scale.setScalar(0.022 * pulse);
        f.head.material.opacity = fade;
        f.head.visible = true;
      } else {
        f.head.visible = false;
      }

      if (!f.line || !f.material) continue;
      // The trail fades from landing until a year after sending (stretched only at speeds where the
      // flight itself would outlast the year).
      const landed = f.send + duration;
      const gone = f.send + Math.max(TRAIL_LIFETIME_DAYS, duration * 1.5);
      const remaining = 1 - (t - landed) / (gone - landed);
      if (!shown || p < 0 || (p >= 1 && remaining <= 0 && !emphasised)) {
        f.line.visible = false;
        f.brightness = 0;
        continue;
      }
      f.line.visible = true;
      const geometry = f.line.geometry as LineGeometry;
      if (p < 1) {
        geometry.instanceCount = Math.max(1, Math.ceil(p * SEGMENTS));
        f.brightness = 1;
      } else {
        geometry.instanceCount = SEGMENTS;
        // Ease out: bright for the first months, then dwindling to nothing at the year mark.
        f.brightness = TRAIL_PEAK * Math.max(0, remaining) ** 1.6;
      }
      f.material.opacity = emphasised ? 1 : f.brightness;
      f.material.linewidth = emphasised ? 3.2 : p < 1 ? 2.4 : 1.6;
    }
  }

  /** The visible letter arc under the cursor (normalised device coords), if any. */
  pick(ndc: THREE.Vector2): Flight | null {
    this.raycaster.setFromCamera(ndc, this.view.camera);
    this.raycaster.params.Line2 = { threshold: 8 };
    const candidates = this.lines.filter((l) => l.visible && (l.userData.flight as Flight).brightness > 0.05);
    const hits = this.raycaster.intersectObjects(candidates, false);
    // Prefer the brightest (most recent) arc among near hits.
    hits.sort((a, b) => (b.object.userData.flight as Flight).brightness - (a.object.userData.flight as Flight).brightness);
    return hits.length ? (hits[0].object.userData.flight as Flight) : null;
  }
}
