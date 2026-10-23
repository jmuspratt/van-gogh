// Playback state and the timeline bar: play/pause, speed, and a scrubbable histogram of letters per
// month, stacked by author colour.

import type { Flight } from "./letters";
import { AUTHOR_COLORS } from "./letters";
import { formatDay, monthIndex, toDay } from "./time";

export const START = toDay("1872-09-01");
export const END = toDay("1890-08-15");

export const SPEEDS = [
  { label: "1 week / s", days: 7 },
  { label: "1 month / s", days: 30 },
  { label: "3 months / s", days: 91 },
  { label: "1 year / s", days: 365 },
];

const hex = (c: number) => `#${c.toString(16).padStart(6, "0")}`;

export class Timeline {
  t = START;
  playing = false;
  speed = SPEEDS[1].days;
  private dragging = false;
  private readonly canvas: HTMLCanvasElement;
  private readonly playhead: HTMLElement;
  private readonly playButton: HTMLButtonElement;
  private readonly dateYear: HTMLElement;
  private readonly dateMonth: HTMLElement;

  constructor(root: HTMLElement, dateEl: HTMLElement, private readonly flights: Flight[]) {
    root.innerHTML = `
      <button class="play" title="Play / pause (space)">▶</button>
      <div class="track"><canvas></canvas><div class="playhead"></div><div class="years"></div></div>
      <select class="speed" title="Playback speed">${SPEEDS.map((s) => `<option value="${s.days}">${s.label}</option>`).join("")}</select>`;
    this.canvas = root.querySelector("canvas")!;
    this.playhead = root.querySelector(".playhead")!;
    this.playButton = root.querySelector(".play")!;
    const speed = root.querySelector<HTMLSelectElement>(".speed")!;
    speed.value = String(this.speed);
    speed.onchange = () => (this.speed = Number(speed.value));
    this.playButton.onclick = () => this.toggle();

    dateEl.innerHTML = `<div class="year"></div><div class="month"></div>`;
    this.dateYear = dateEl.querySelector(".year")!;
    this.dateMonth = dateEl.querySelector(".month")!;

    const track = root.querySelector<HTMLElement>(".track")!;
    const seek = (e: PointerEvent) => {
      const r = track.getBoundingClientRect();
      this.t = START + Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * (END - START);
    };
    track.onpointerdown = (e) => {
      this.dragging = true;
      track.setPointerCapture(e.pointerId);
      seek(e);
    };
    track.onpointermove = (e) => this.dragging && seek(e);
    track.onpointerup = () => (this.dragging = false);

    const years = root.querySelector(".years")!;
    for (let y = 1873; y <= 1890; y++) {
      const span = document.createElement("span");
      span.textContent = y % 5 === 0 || y === 1873 ? String(y) : "·";
      span.style.left = `${((toDay(`${y}-01-01`) - START) / (END - START)) * 100}%`;
      years.appendChild(span);
    }
    new ResizeObserver(() => this.drawHistogram()).observe(track);
  }

  toggle(force?: boolean) {
    this.playing = force ?? !this.playing;
    if (this.playing && this.t >= END) this.t = START;
    this.playButton.textContent = this.playing ? "❚❚" : "▶";
  }

  step(days: number) {
    this.t = Math.min(END, Math.max(START, this.t + days));
  }

  tick(dt: number) {
    if (this.playing && !this.dragging) {
      this.t += dt * this.speed;
      if (this.t >= END) {
        this.t = END;
        this.toggle(false);
      }
    }
    this.playhead.style.left = `${((this.t - START) / (END - START)) * 100}%`;
    const d = formatDay(this.t);
    this.dateYear.textContent = d.year;
    this.dateMonth.textContent = d.month;
  }

  drawHistogram() {
    const c = this.canvas;
    const dpr = window.devicePixelRatio || 1;
    c.width = c.clientWidth * dpr;
    c.height = c.clientHeight * dpr;
    const g = c.getContext("2d")!;
    const m0 = monthIndex(START);
    const months = monthIndex(END) - m0 + 1;
    const counts = Array.from({ length: months }, () => ({ vincent: 0, theo: 0, other: 0 }));
    for (const f of this.flights) {
      const m = monthIndex(f.send) - m0;
      if (m < 0 || m >= months) continue;
      const who = f.letter.authorKey === "vincent" ? "vincent" : f.letter.authorKey === "theo" ? "theo" : "other";
      counts[m][who]++;
    }
    const max = Math.max(...counts.map((k) => k.vincent + k.theo + k.other));
    const bw = c.width / months;
    for (let i = 0; i < months; i++) {
      let y = c.height;
      for (const who of ["vincent", "theo", "other"] as const) {
        const h = (counts[i][who] / max) * c.height * 0.95;
        g.fillStyle = hex(AUTHOR_COLORS[who]);
        g.globalAlpha = 0.75;
        g.fillRect(i * bw, y - h, Math.max(1, bw - dpr), h);
        y -= h;
      }
    }
  }
}
