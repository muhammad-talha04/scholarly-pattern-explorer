"use client";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { TopicLink } from "@/lib/graph";
import { gap as gapColor, ink } from "@/lib/theme";
import { cardBoxBeside, createHoverLock, pickClosestPaperAt, reduceHover, type CardBox } from "./hoverLock";
import { breathAmount, heroNetwork, neighborIds, networkLinks, ORBIT_SPEED, plexusCore, plexusDrift, plexusTint, REST_SHIFT, ROCK_X_HZ, ROCK_Z_HZ, WIDE_CANVAS, zoomScale, type PlexusPose, type Star } from "./stars";

type Frame = {
  time: number;
  motion: number;
  unit: number;
  shift: number;
  ox: number;
  oy: number;
  rx: number;
  ry: number;
  rz: number;
};

/** Same radius the pre-#50 hit test used. Only papers open a card. */
const HIT_PX = 12;
/** Fallback box matching `w-52` and the card's padding before it has been measured. */
const CARD_W = 208;
const CARD_H = 96;

/** Flat plexus. Same band, orbit, and breathing zoom as the 3D view, unless motion is reduced. */
export function Galaxy2D({ nodes, links, showGaps, focus, highlight, pose = null, onFocus, onHighlight, onPick }: {
  nodes: (Partial<Star> & Pick<Star, "id" | "support" | "gap">)[]; links: TopicLink[]; showGaps: boolean;
  focus?: string | null; highlight?: Set<string> | null; pose?: PlexusPose;
  onFocus?: (id: string) => void; onHighlight?: (cluster?: string) => void; onPick?: (id: string) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const net = useMemo(() => heroNetwork(nodes), [nodes]);
  const [hover, setHover] = useState<string | null>(null);
  const [keepFocusCard, setKeepFocusCard] = useState(true);
  const hoverRef = useRef(hover);
  const focusRef = useRef(focus);
  const highlightRef = useRef(highlight);
  const poseRef = useRef(pose);
  const reduceRef = useRef(false);
  const keepFocusRef = useRef(keepFocusCard);
  const frameRef = useRef<Frame>({ time: 0, motion: 0, unit: 1, shift: 0, ox: 0, oy: 0, rx: 0, ry: 0, rz: 0 });
  hoverRef.current = hover;
  focusRef.current = focus;
  highlightRef.current = highlight;
  poseRef.current = pose;
  keepFocusRef.current = keepFocusCard;
  const activeId = hover ?? (keepFocusCard ? focus ?? null : null);
  const active = net.nodes.find((n) => n.paper && n.id === activeId);
  const near = useMemo(() => {
    if (!hover) return new Set<string>();
    const ids = neighborIds(hover, networkLinks(net.edges));
    for (const id of neighborIds(hover, links)) ids.add(id);
    return ids;
  }, [hover, net.edges, links]);
  const nearRef = useRef(near);
  nearRef.current = near;
  const tipRef = useRef<HTMLDivElement>(null);
  const lockRef = useRef(createHoverLock());
  const overCardRef = useRef(false);
  const frozenRef = useRef<{ id: string; left: number; top: number } | null>(null);
  const drawnRef = useRef(false);
  const pinCardRef = useRef<() => void>(() => {});

  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return;
    const apply = () => { reduceRef.current = mq.matches; };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent || typeof ResizeObserver === "undefined") return;
    let raf = 0;
    let time = 0;
    let last = performance.now();
    const draw = () => {
      const rect = parent.getBoundingClientRect();
      const w = Math.max(1, Math.floor(rect.width));
      const h = Math.max(1, Math.floor(rect.height));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      let ctx: CanvasRenderingContext2D | null = null;
      try { ctx = canvas.getContext("2d"); } catch { ctx = null; }
      if (!ctx) return;
      const pinned = poseRef.current === "in" ? 1 : poseRef.current === "out" ? 0 : null;
      const still = reduceRef.current || pinned != null;
      const breath = reduceRef.current ? 0 : (pinned ?? breathAmount(time));
      const motion = still ? 0 : 1;
      const base = Math.min(w, h) / 18.5;
      const unit = base * zoomScale(breath);
      const wide = w >= WIDE_CANVAS;
      const frame: Frame = {
        time,
        motion,
        unit,
        shift: wide ? REST_SHIFT * (1 - breath) * unit : 0,
        ox: w * 0.5,
        oy: h * 0.52,
        rx: still ? 0 : Math.sin(time * ROCK_X_HZ + 0.7) * 0.045,
        ry: still ? 0 : time * ORBIT_SPEED,
        rz: still ? 0 : Math.sin(time * ROCK_Z_HZ + 1.4) * 0.03,
      };
      frameRef.current = frame;
      const project = (pos: [number, number, number], phase: number) => projectNode(pos, phase, frame);
      const hoverId = hoverRef.current;
      const focusId = focusRef.current;
      const lit = highlightRef.current;
      const nearIds = nearRef.current;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = ink;
      ctx.fillRect(0, 0, w, h);
      const hub = project(net.hub, 0);
      const washR = unit * 4.2;
      const wash = ctx.createRadialGradient(hub[0], hub[1], 0, hub[0], hub[1], washR);
      wash.addColorStop(0, "rgba(245, 165, 74, 0.20)");
      wash.addColorStop(0.45, "rgba(253, 231, 176, 0.06)");
      wash.addColorStop(1, "rgba(245, 165, 74, 0)");
      ctx.fillStyle = wash;
      ctx.beginPath();
      ctx.arc(hub[0], hub[1], washR, 0, Math.PI * 2);
      ctx.fill();
      const tintAt = new Map(net.nodes.map((n) => [n.id, n.t]));
      const phaseAt = new Map(net.nodes.map((n) => [n.id, n.phase]));
      for (const edge of net.edges) {
        const [x1, y1] = project(edge.a, phaseAt.get(edge.source) ?? 0);
        const [x2, y2] = project(edge.b, phaseAt.get(edge.target) ?? 0);
        const hot = edge.source === hoverId || edge.target === hoverId || nearIds.has(edge.source) || nearIds.has(edge.target);
        ctx.strokeStyle = hexAlpha(plexusTint(tintAt.get(edge.source) ?? 0.5), hot ? Math.min(0.85, edge.alpha * 2.2) : edge.alpha);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      for (const node of net.nodes) {
        const [x, y] = project(node.pos, node.phase);
        const hot = node.id === hoverId || node.id === focusId || nearIds.has(node.id) || lit?.has(node.id);
        const tint = plexusTint(node.t);
        const core = showGaps && node.gap ? gapColor : plexusCore(node.t);
        ctx.globalAlpha = Math.min(1, node.fade * (hot ? 1 : 0.92));
        ctx.fillStyle = hexAlpha(tint, 0.28);
        ctx.beginPath();
        ctx.arc(x, y, hot ? 4.2 : 3.1, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = core;
        ctx.beginPath();
        ctx.arc(x, y, hot ? 2.1 : 1.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      }
      canvas.dataset.plexusTime = String(frame.time);
      drawnRef.current = true;
      pinCardRef.current();
    };
    const tick = (now: number) => {
      const poseNow = poseRef.current;
      const still = reduceRef.current || poseNow != null;
      if (!document.hidden && !still) time += Math.min(0.05, (now - last) / 1000);
      last = now;
      draw();
      raf = requestAnimationFrame(tick);
    };
    draw();
    raf = requestAnimationFrame(tick);
    const observer = new ResizeObserver(draw);
    observer.observe(parent);
    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, [net, showGaps]);

  const cardBoxAt = (x: number, y: number): CardBox | null => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const cardW = tipRef.current?.offsetWidth || CARD_W;
    const cardH = tipRef.current?.offsetHeight || CARD_H;
    return cardBoxBeside(
      { x, y },
      { width: canvas.clientWidth || canvas.width || 1, height: canvas.clientHeight || canvas.height || 1 },
      cardW,
      cardH,
    );
  };

  const cardAnchor = (id: string) => {
    const node = net.nodes.find((n) => n.paper && n.id === id);
    if (!node) return null;
    const [x, y] = projectNode(node.pos, node.phase, frameRef.current);
    const box = cardBoxAt(x, y);
    return box ? { left: box.left, top: box.top } : null;
  };

  const applyFrozen = () => {
    const el = tipRef.current;
    const frozen = frozenRef.current;
    if (!el || !frozen) return;
    el.style.transform = `translate(${frozen.left}px, ${frozen.top}px)`;
  };

  // Freeze the card where it opened. Later frames must not follow the drifting node.
  pinCardRef.current = () => {
    const id = hoverRef.current ?? (keepFocusRef.current ? focusRef.current ?? null : null);
    if (!id || !drawnRef.current) return;
    if (frozenRef.current?.id === id) {
      applyFrozen();
      return;
    }
    const pos = cardAnchor(id);
    if (!pos) return;
    frozenRef.current = { id, ...pos };
    applyFrozen();
  };

  useLayoutEffect(() => {
    pinCardRef.current();
  }, [hover, focus, keepFocusCard]);

  const pointerLocal = (ev: { clientX: number; clientY: number }) => {
    const canvas = canvasRef.current;
    const rect = canvas?.getBoundingClientRect();
    return { x: ev.clientX - (rect?.left ?? 0), y: ev.clientY - (rect?.top ?? 0) };
  };

  const pickPaperAt = (ev: { clientX: number; clientY: number }) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const { x: px, y: py } = pointerLocal(ev);
    const frame = frameRef.current;
    const points = net.nodes.map((node) => {
      const [x, y] = projectNode(node.pos, node.phase, frame);
      return { id: node.id, paper: node.paper, x, y };
    });
    return pickClosestPaperAt(points, px, py, HIT_PX);
  };

  const publish = (id: string | null) => {
    if (!id) frozenRef.current = null;
    else if (drawnRef.current && frozenRef.current?.id !== id) {
      const pos = cardAnchor(id);
      if (pos) frozenRef.current = { id, ...pos };
    }
    if (hoverRef.current === id) {
      applyFrozen();
      return;
    }
    hoverRef.current = id;
    setHover(id);
  };

  // A zero-movement pointermove is the pointer sitting still while nodes drift.
  // Touching a different paper replaces the card immediately, except along the
  // short lane from the open paper into its card.
  const onPointerMove = (ev: ReactPointerEvent<HTMLCanvasElement>) => {
    if (ev.pointerType === "touch") return;
    if (ev.movementX === 0 && ev.movementY === 0) return;
    if (!keepFocusRef.current) {
      keepFocusRef.current = true;
      setKeepFocusCard(true);
    }
    const hit = pickPaperAt(ev);
    const next = reduceHover(lockRef.current, {
      moving: true,
      hitId: hit?.id ?? null,
      hitAt: hit ? { x: hit.x, y: hit.y } : null,
      pointer: pointerLocal(ev),
      movement: { x: ev.movementX, y: ev.movementY },
      overCard: overCardRef.current,
      nextCard: hit ? cardBoxAt(hit.x, hit.y) : null,
    });
    lockRef.current = next;
    publish(next.id);
  };

  const onPointerUp = (ev: ReactPointerEvent<HTMLCanvasElement>) => {
    if (ev.pointerType !== "touch") return;
    const hit = pickPaperAt(ev);
    const id = hit?.id ?? null;
    keepFocusRef.current = id != null;
    setKeepFocusCard(id != null);
    lockRef.current = {
      id,
      anchor: hit ? { x: hit.x, y: hit.y } : null,
      card: hit ? cardBoxAt(hit.x, hit.y) : null,
    };
    publish(id);
  };

  const onPointerLeave = (ev: ReactPointerEvent<HTMLCanvasElement>) => {
    if (ev.pointerType === "touch") return;
    const next = ev.relatedTarget;
    if (next instanceof Node && tipRef.current?.contains(next)) {
      overCardRef.current = true;
      return;
    }
    overCardRef.current = false;
    lockRef.current = createHoverLock();
    publish(null);
  };

  return (
    <div className="relative h-full w-full">
      <canvas
        ref={canvasRef}
        className="h-full w-full"
        role="img"
        aria-label="Paper plexus. Color runs from copper at the lower left to pale gold at the upper right."
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerLeave}
        onClick={(ev) => {
          const id = pickPaperAt(ev)?.id ?? null;
          const node = net.nodes.find((n) => n.id === id);
          if (!node?.paper) return;
          onFocus?.(node.id);
          if (node.gap) onHighlight?.(node.cluster);
        }}
      />
      <ul className="sr-only">
        {net.nodes.filter((n) => n.paper).map((n) => (
          <li key={n.id}>
            <button data-testid={showGaps && n.gap ? "gap-node" : "topic-node"} onClick={() => { onFocus?.(n.id); onPick?.(n.id); }}>
              {n.id}, paper{n.cluster ? `, topic cluster ${n.cluster}` : ""}{showGaps && n.gap ? ", research gap" : ""}
            </button>
          </li>
        ))}
      </ul>
      {active && (
        <div
          ref={tipRef}
          className="glass pointer-events-auto absolute left-0 top-0 z-10 w-52 p-3 text-xs"
          role="tooltip"
          data-testid="galaxy-paper-card"
          data-galaxy-card=""
          onPointerEnter={() => { overCardRef.current = true; }}
          onPointerLeave={(ev) => {
            overCardRef.current = false;
            const next = ev.relatedTarget;
            if (next instanceof Node && canvasRef.current?.contains(next)) return;
            lockRef.current = createHoverLock();
            publish(null);
          }}
        >
          <p className="font-medium text-white">{active.id}</p>
          <p className="mt-1 text-mist">Paper{active.cluster ? ` · topic cluster ${active.cluster}` : ""}</p>
          {showGaps && active.gap && <p className="text-gap">Research gap</p>}
          <button className="btn mt-2 w-full py-1" onClick={() => onPick?.(active.id)}>Search this paper</button>
        </div>
      )}
    </div>
  );
}

function projectNode(pos: [number, number, number], phase: number, frame: Frame): [number, number] {
  const d = plexusDrift(phase, frame.time, frame.motion);
  const [x, z] = spinPoint(pos[0] + d[0], pos[1] + d[1], pos[2] + d[2], frame.rx, frame.ry, frame.rz);
  return [frame.ox + x * frame.unit + frame.shift, frame.oy + z * frame.unit];
}

/** Three.js XYZ euler: Rx, then Ry, then Rz. Returns screen-facing x and z. */
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

function hexAlpha(hex: string, alpha: number) {
  const n = Number.parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
