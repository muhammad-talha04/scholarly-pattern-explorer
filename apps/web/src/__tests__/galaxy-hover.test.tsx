import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { Galaxy2D } from "@/features/galaxy/Galaxy2D";
import { breathAmount, heroNetwork, ORBIT_SPEED, plexusDrift, REST_SHIFT, ROCK_X_HZ, ROCK_Z_HZ, WIDE_CANVAS, zoomScale } from "@/features/galaxy/stars";

const WIDTH = 1100;
const HEIGHT = 700;
const HIT_PX = 12;

function papers(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: `Paper ${i}`,
    support: 1,
    gap: i === 3,
  }));
}

/** Screen point of a plexus node. Mirrors Galaxy2D's projection so the test can aim the pointer. */
function spinPoint(x: number, y: number, z: number, rx: number, ry: number, rz: number): [number, number] {
  const cx = Math.cos(rx);
  const sx = Math.sin(rx);
  const y1 = y * cx - z * sx;
  const z1 = y * sx + z * cx;
  const cy = Math.cos(ry);
  const sy = Math.sin(ry);
  const x2 = x * cy + z1 * sy;
  const z2 = -x * sy + z1 * cy;
  const cz = Math.cos(rz);
  const sz = Math.sin(rz);
  return [x2 * cz - y1 * sz, z2];
}

function frameAt(time: number) {
  const breath = breathAmount(time);
  const base = Math.min(WIDTH, HEIGHT) / 18.5;
  const unit = base * zoomScale(breath);
  const wide = WIDTH >= WIDE_CANVAS;
  return {
    time,
    motion: 1,
    unit,
    shift: wide ? REST_SHIFT * (1 - breath) * unit : 0,
    ox: WIDTH * 0.5,
    oy: HEIGHT * 0.52,
    rx: Math.sin(time * ROCK_X_HZ + 0.7) * 0.045,
    ry: time * ORBIT_SPEED,
    rz: Math.sin(time * ROCK_Z_HZ + 1.4) * 0.03,
  };
}

function project(node: { pos: [number, number, number]; phase: number }, time: number) {
  const frame = frameAt(time);
  const d = plexusDrift(node.phase, frame.time, frame.motion);
  const [x, z] = spinPoint(node.pos[0] + d[0], node.pos[1] + d[1], node.pos[2] + d[2], frame.rx, frame.ry, frame.rz);
  return [frame.ox + x * frame.unit + frame.shift, frame.oy + z * frame.unit] as [number, number];
}

/** Where Galaxy2D anchors the card: just beside the node, flipped to stay on the canvas. */
function cardAnchor(x: number, y: number) {
  const cardW = 208;
  const cardH = 96;
  let left = x + 14;
  let top = y - cardH * 0.35;
  if (left + cardW > WIDTH - 8) left = x - cardW - 14;
  if (left < 8) left = 8;
  if (top < 8) top = 8;
  if (top + cardH > HEIGHT - 8) top = Math.max(8, HEIGHT - cardH - 8);
  return [Math.round(left), Math.round(top)] as [number, number];
}

function translation(el: HTMLElement) {
  const match = el.style.transform.match(/translate\(([-\d.]+)px,\s*([-\d.]+)px\)/);
  expect(match).toBeTruthy();
  return [Number(match![1]), Number(match![2])] as [number, number];
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function installCanvas() {
  const queue: FrameRequestCallback[] = [];
  let now = 0;
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    queue.push(cb);
    return queue.length;
  });
  vi.stubGlobal("cancelAnimationFrame", () => {});
  vi.spyOn(performance, "now").mockImplementation(() => now);
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => {
    const g = { addColorStop() {} };
    return {
      fillStyle: "",
      strokeStyle: "",
      lineWidth: 1,
      globalAlpha: 1,
      clearRect() {},
      fillRect() {},
      beginPath() {},
      arc() {},
      fill() {},
      stroke() {},
      moveTo() {},
      lineTo() {},
      createRadialGradient: () => g,
    } as unknown as CanvasRenderingContext2D;
  });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(() => ({
    x: 0, y: 0, left: 0, top: 0, right: WIDTH, bottom: HEIGHT, width: WIDTH, height: HEIGHT, toJSON() { return {}; },
  }));
  class PointerEventPolyfill extends MouseEvent {
    pointerType: string;
    constructor(type: string, props?: MouseEventInit & { pointerType?: string }) {
      super(type, props);
      this.pointerType = props?.pointerType ?? "mouse";
      // jsdom's MouseEvent ignores movementX/Y, so shadow them for the test.
      const mx = props?.movementX ?? 0;
      const my = props?.movementY ?? 0;
      Object.defineProperty(this, "movementX", { get: () => mx });
      Object.defineProperty(this, "movementY", { get: () => my });
    }
  }
  vi.stubGlobal("PointerEvent", PointerEventPolyfill);
  return {
    step(ms: number) {
      const cb = queue.shift();
      now += ms;
      cb?.(now);
    },
  };
}

it("keeps the paper card beside the node while zero-movement pointermoves arrive", () => {
  const clock = installCanvas();
  const net = heroNetwork(papers(48));
  const far = net.nodes.filter((n) => n.paper).map((n) => {
    const [x, y] = project(n, 0);
    return { n, x, y, r: Math.hypot(x - WIDTH / 2, y - HEIGHT * 0.52) };
  }).sort((a, b) => b.r - a.r)[0];
  expect(far.r).toBeGreaterThan(80);

  render(<Galaxy2D nodes={papers(48)} links={[]} showGaps={false} />);
  const canvas = document.querySelector("canvas");
  expect(canvas).toBeTruthy();

  fireEvent.pointerMove(canvas!, { clientX: far.x, clientY: far.y, movementX: 8, movementY: 2 });
  const card = screen.getByTestId("galaxy-paper-card");
  expect(card).toHaveTextContent(far.n.id);
  expect(card.className).not.toContain("right-4");
  expect(card.className).not.toContain("top-24");
  const parked = cardAnchor(far.x, far.y);
  expect(translation(card)).toEqual(parked);

  const steps = Math.ceil((Math.PI / 2) / ORBIT_SPEED / 0.05);
  act(() => {
    for (let i = 0; i < steps; i++) clock.step(50);
  });
  const later = Number(canvas!.dataset.plexusTime);
  expect(later).toBeGreaterThan(1);
  const [x1, y1] = project(far.n, later);
  expect(Math.hypot(x1 - far.x, y1 - far.y)).toBeGreaterThan(40);

  for (let i = 0; i < 8; i++) {
    fireEvent.pointerMove(canvas!, { clientX: far.x, clientY: far.y, movementX: 0, movementY: 0 });
  }
  const still = screen.getByTestId("galaxy-paper-card");
  expect(still).toHaveTextContent(far.n.id);
  const followed = cardAnchor(x1, y1);
  expect(translation(still)).toEqual(followed);
  expect(Math.hypot(followed[0] - parked[0], followed[1] - parked[1])).toBeGreaterThan(20);

  fireEvent.pointerMove(canvas!, { clientX: 2, clientY: 2, movementX: 30, movementY: 4 });
  expect(screen.queryByTestId("galaxy-paper-card")).toBeNull();
});

it("picks a paper inside the hit radius even when a non-paper dot is closer", () => {
  installCanvas();
  const net = heroNetwork(papers(48));
  const fillers = net.nodes.filter((n) => !n.paper);
  const paperNodes = net.nodes.filter((n) => n.paper);
  let aim: { x: number; y: number; paperId: string } | null = null;
  for (const filler of fillers) {
    const [fx, fy] = project(filler, 0);
    let nearest = paperNodes[0];
    let best = Infinity;
    for (const paper of paperNodes) {
      const [px, py] = project(paper, 0);
      const d = Math.hypot(px - fx, py - fy);
      if (d < best) { best = d; nearest = paper; }
    }
    const fillerCloser = best > 0.5 && best <= HIT_PX;
    if (!fillerCloser) continue;
    aim = { x: fx, y: fy, paperId: nearest.id };
    break;
  }
  expect(aim).toBeTruthy();

  render(<Galaxy2D nodes={papers(48)} links={[]} showGaps={false} />);
  const canvas = document.querySelector("canvas");
  fireEvent.pointerMove(canvas!, { clientX: aim!.x, clientY: aim!.y, movementX: 6, movementY: 1 });
  const card = screen.getByTestId("galaxy-paper-card");
  expect(card).toHaveTextContent(aim!.paperId);
  expect(card.textContent).not.toMatch(/dot-/);

  const lonely = fillers.map((filler) => {
    const [x, y] = project(filler, 0);
    const nearestPaper = Math.min(...paperNodes.map((paper) => {
      const [px, py] = project(paper, 0);
      return Math.hypot(px - x, py - y);
    }));
    return { x, y, nearestPaper };
  }).sort((a, b) => b.nearestPaper - a.nearestPaper)[0];
  expect(lonely.nearestPaper).toBeGreaterThan(HIT_PX);
  fireEvent.pointerMove(canvas!, { clientX: lonely.x, clientY: lonely.y, movementX: 9, movementY: -3 });
  expect(screen.queryByTestId("galaxy-paper-card")).toBeNull();
});

it("pins the card on a touch tap and clears it on a tap in empty space", () => {
  installCanvas();
  const net = heroNetwork(papers(48));
  const paper = net.nodes.find((n) => n.paper)!;
  const [x, y] = project(paper, 0);
  render(<Galaxy2D nodes={papers(48)} links={[]} showGaps={false} focus={paper.id} />);
  const canvas = document.querySelector("canvas");
  expect(screen.getByTestId("galaxy-paper-card")).toHaveTextContent(paper.id);

  fireEvent.pointerUp(canvas!, { clientX: 4, clientY: 4, pointerType: "touch" });
  expect(screen.queryByTestId("galaxy-paper-card")).toBeNull();

  fireEvent.pointerUp(canvas!, { clientX: x, clientY: y, pointerType: "touch" });
  expect(screen.getByTestId("galaxy-paper-card")).toHaveTextContent(paper.id);
  fireEvent.pointerLeave(canvas!, { pointerType: "touch" });
  fireEvent.pointerMove(canvas!, { clientX: x, clientY: y, movementX: 0, movementY: 0, pointerType: "touch" });
  expect(screen.getByTestId("galaxy-paper-card")).toHaveTextContent(paper.id);

  fireEvent.pointerUp(canvas!, { clientX: 4, clientY: 4, pointerType: "touch" });
  expect(screen.queryByTestId("galaxy-paper-card")).toBeNull();
});
