import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { Galaxy2D } from "@/features/galaxy/Galaxy2D";
import { breathAmount, heroNetwork, ORBIT_SPEED, plexusDrift, REST_SHIFT, ROCK_X_HZ, ROCK_Z_HZ, WIDE_CANVAS, zoomScale } from "@/features/galaxy/stars";

const WIDTH = 1100;
const HEIGHT = 700;

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

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("keeps the same paper card while the pointer is stationary and the plexus moves", () => {
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
    constructor(type: string, props?: MouseEventInit) { super(type, props); }
  }
  vi.stubGlobal("PointerEvent", PointerEventPolyfill);

  const net = heroNetwork(papers(48));
  const far = net.nodes.filter((n) => n.paper).map((n) => {
    const [x, y] = project(n, 0);
    return { n, x, y, r: Math.hypot(x - WIDTH / 2, y - HEIGHT * 0.52) };
  }).sort((a, b) => b.r - a.r)[0];
  expect(far.r).toBeGreaterThan(80);

  render(<Galaxy2D nodes={papers(48)} links={[]} showGaps={false} />);
  const canvas = document.querySelector("canvas");
  expect(canvas).toBeTruthy();

  const steps = Math.ceil((Math.PI / 2) / ORBIT_SPEED / 0.05);
  const later = steps * 0.05;
  const [x1, y1] = project(far.n, later);
  expect(Math.hypot(x1 - far.x, y1 - far.y)).toBeGreaterThan(40);

  fireEvent.pointerMove(canvas!, { clientX: far.x, clientY: far.y });
  const card = screen.getByTestId("galaxy-paper-card");
  expect(card).toHaveTextContent(far.n.id);
  const before = card.textContent;

  act(() => {
    for (let i = 0; i < steps; i++) {
      const cb = queue.shift();
      now += 50;
      cb?.(now);
    }
  });
  expect(Number(canvas!.dataset.plexusTime)).toBeGreaterThan(1);

  for (let i = 0; i < 8; i++) {
    fireEvent.pointerMove(canvas!, { clientX: far.x, clientY: far.y, movementX: 0, movementY: 0 });
  }
  expect(screen.getByTestId("galaxy-paper-card").textContent).toBe(before);

  fireEvent.pointerMove(canvas!, { clientX: 2, clientY: 2 });
  expect(screen.queryByTestId("galaxy-paper-card")).toBeNull();
});
