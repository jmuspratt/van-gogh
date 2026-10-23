// Types for, and loading of, the pipeline's build output (build/data, served at /data).

export interface MapPos {
  x: number;
  y: number;
  printed: boolean;
}

export interface Place {
  name: string;
  lat: number;
  lon: number;
  kind?: string;
  country?: string;
  map: MapPos | null;
}

export interface LetterEnd {
  place: string | null;
  basis: string; // edition | residence | trip | atLetters | override | unresolved
  approx?: boolean;
  ambiguous?: string[];
  evidence?: string[];
}

export interface Letter {
  id: string;
  kind: "letter" | "related";
  title: string;
  author: string;
  addressee: string;
  authorKey: string | null;
  addresseeKey: string | null;
  placeText: string;
  dateText: string;
  dateNote: string | null;
  sourceStatus: string | null;
  url: string | null;
  sketches: number;
  date: { earliest: string; latest: string | null; precision: string; approximate: boolean; probable: boolean } | null;
  from: LetterEnd;
  to: LetterEnd;
}

export interface Stay {
  place: string;
  from: string;
  to: string;
  kind: "residence" | "trip";
  approx?: boolean;
  note?: string;
}

export interface Itinerary {
  name: string;
  stays: Stay[];
}

export interface Tiles {
  crop: [number, number, number, number];
  preview: string;
  tiles: { file: string; x: number; y: number; w: number; h: number }[];
}

export interface MapInfo {
  title: string;
  authors: string;
  year: number;
  scale: string;
  source: string;
  pxPerKm: number;
}

export interface Data {
  letters: Letter[];
  places: Record<string, Place>;
  itineraries: Record<string, Itinerary>;
  map: MapInfo;
  tiles: Tiles;
}

const BASE = `${import.meta.env.BASE_URL}data/`;

async function json<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`${path}: ${res.status} (run pipeline/build.py and pipeline/texture.py)`);
  return res.json();
}

export async function loadData(): Promise<Data> {
  const [letters, places, itineraries, map, tiles] = await Promise.all([
    json<Letter[]>("letters.json"),
    json<Record<string, Place>>("places.json"),
    json<Record<string, Itinerary>>("itineraries.json"),
    json<MapInfo>("map.json"),
    json<Tiles>("map/tiles.json"),
  ]);
  return { letters, places, itineraries, map, tiles };
}

export const mapUrl = (file: string) => `${BASE}map/${file}`;

export async function loadBody(id: string): Promise<string> {
  const res = await fetch(`${BASE}bodies/${id}.html`);
  return res.ok ? res.text() : `<p class="error">Could not load ${id}.</p>`;
}
