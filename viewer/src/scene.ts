// Renderer, camera, controls, and the base map laid flat on the ground plane.
//
// World coordinates: 1 unit = 100 scan pixels (~25 km). The map's x axis is world +x, the map's
// y axis (downwards on the sheet) is world +z, and world +y is up, so arcs rise off the paper.

import * as THREE from "three";
import { MapControls } from "three/addons/controls/MapControls.js";
import { mapUrl, type Tiles } from "./data";

export const PX_PER_UNIT = 100;
const AZIMUTH_LIMIT = (75 * Math.PI) / 180;
const WHEEL_RADIANS_PER_PX = 0.003;

export class MapScene {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera: THREE.PerspectiveCamera;
  readonly controls: MapControls;
  private readonly center: { x: number; y: number };

  constructor(container: HTMLElement, private readonly tiles: Tiles) {
    const [x0, y0, x1, y1] = tiles.crop;
    this.center = { x: (x0 + x1) / 2, y: (y0 + y1) / 2 };

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x0d0c0a);
    container.appendChild(this.renderer.domElement);

    this.camera = new THREE.PerspectiveCamera(32, 1, 0.5, 2000);
    this.controls = new MapControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.screenSpacePanning = false;
    this.controls.minDistance = 4;
    this.controls.maxDistance = 140;
    this.controls.maxPolarAngle = 1.2; // never look along the paper
    this.controls.zoomToCursor = true;
    // Keep the sheet readable: limited spin, and never upside down.
    this.controls.minAzimuthAngle = -AZIMUTH_LIMIT;
    this.controls.maxAzimuthAngle = AZIMUTH_LIMIT;
    this.modifierWheel(container);

    this.addMap();
    this.frame("overview");
    this.resize();
    window.addEventListener("resize", () => this.resize());
  }

  /**
   * Shift-scroll rotates the view around the target; Option/Alt-scroll tilts it. Plain scroll still
   * zooms (handled by MapControls). Listens on the container in the capture phase so it runs before
   * MapControls' own wheel handler and can stop it.
   */
  private modifierWheel(container: HTMLElement) {
    const spherical = new THREE.Spherical();
    const offset = new THREE.Vector3();
    container.addEventListener(
      "wheel",
      (e) => {
        if (!e.shiftKey && !e.altKey) return;
        e.preventDefault();
        e.stopPropagation();
        // macOS turns Shift + mouse wheel into horizontal scrolling, so take whichever axis moved.
        const raw = Math.abs(e.deltaY) >= Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
        const delta = raw * (e.deltaMode === WheelEvent.DOM_DELTA_LINE ? 16 : 1) * WHEEL_RADIANS_PER_PX;
        offset.subVectors(this.camera.position, this.controls.target);
        spherical.setFromVector3(offset);
        if (e.shiftKey) spherical.theta = THREE.MathUtils.clamp(spherical.theta + delta, -AZIMUTH_LIMIT, AZIMUTH_LIMIT);
        else spherical.phi = THREE.MathUtils.clamp(spherical.phi + delta, 0.01, this.controls.maxPolarAngle);
        offset.setFromSpherical(spherical);
        this.camera.position.copy(this.controls.target).add(offset);
        this.camera.lookAt(this.controls.target);
        this.controls.update();
      },
      { capture: true, passive: false },
    );
  }

  /** Scan pixel position -> world position on the paper (y = 0). */
  toWorld(px: number, py: number, height = 0): THREE.Vector3 {
    return new THREE.Vector3((px - this.center.x) / PX_PER_UNIT, height, (py - this.center.y) / PX_PER_UNIT);
  }

  /** Camera presets. "overview" shows the whole region at an atlas-on-a-table tilt. */
  frame(view: "overview" | "lowlands" | "provence") {
    const targets = {
      overview: { px: [4000, 4300], dist: 85 },
      lowlands: { px: [4500, 2900], dist: 22 },
      provence: { px: [3650, 6450], dist: 18 },
    } as const;
    const t = targets[view];
    const target = this.toWorld(t.px[0], t.px[1]);
    const tilt = 0.62; // radians from vertical
    this.controls.target.copy(target);
    this.camera.position.set(target.x, target.y + t.dist * Math.cos(tilt), target.z + t.dist * Math.sin(tilt));
    this.camera.lookAt(target);
    this.controls.update();
  }

  private addMap() {
    const loader = new THREE.TextureLoader();
    const [x0, y0, x1, y1] = this.tiles.crop;
    const maxAniso = this.renderer.capabilities.getMaxAnisotropy();

    // The paper is darkened and slightly desaturated so the letters read as light on top of it.
    const paperMaterial = (tex: THREE.Texture) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = maxAniso;
      // Layers are stacked by render order rather than depth, so they can't z-fight at a distance.
      return new THREE.MeshBasicMaterial({ map: tex, color: new THREE.Color(0.62, 0.6, 0.56), depthWrite: false, depthTest: false });
    };
    const plane = (px: number, py: number, w: number, h: number, mat: THREE.Material, order: number) => {
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w / PX_PER_UNIT, h / PX_PER_UNIT), mat);
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.copy(this.toWorld(px + w / 2, py + h / 2));
      mesh.renderOrder = order;
      this.scene.add(mesh);
      return mesh;
    };

    // Low-res preview first, full-res tiles on top as they arrive.
    loader.load(mapUrl(this.tiles.preview), (tex) => plane(x0, y0, x1 - x0, y1 - y0, paperMaterial(tex), -2));
    for (const t of this.tiles.tiles) {
      loader.load(mapUrl(t.file), (tex) => plane(t.x, t.y, t.w, t.h, paperMaterial(tex), -1));
    }

    // A dark table under the sheet.
    const table = new THREE.Mesh(
      new THREE.PlaneGeometry(2000, 2000),
      new THREE.MeshBasicMaterial({ color: 0x0d0c0a, depthWrite: false, depthTest: false }),
    );
    table.rotation.x = -Math.PI / 2;
    table.renderOrder = -3;
    this.scene.add(table);
  }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.renderer.domElement.parentElement!;
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  get size() {
    return this.renderer.getSize(new THREE.Vector2());
  }
}
