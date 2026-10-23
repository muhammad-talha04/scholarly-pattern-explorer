"use client";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import { BufferGeometry, Color, Float32BufferAttribute, NoToneMapping, Vector3 } from "three";
import type { Group } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { TopicLink } from "@/lib/graph";
import { accent, gap as gapColor, ink, plexusGold } from "@/lib/theme";
import { cardBoxBeside, createHoverLock, pickClosestPaperAt, reduceHover } from "./hoverLock";
import { DRIFT_HZ, heroVolume, neighborIds, networkLinks, plexusCore, plexusDrift, plexusTint, TWINKLE_HZ, WIDE_CANVAS, type PlexusPose, type Star } from "./stars";

/** Oblique view of the cloud. Distance is fixed so drag orbits without a zoom dolly. */
const CLOUD_SHIFT = 3.6;
const CAM_DELTA = new Vector3(7.4, 5.2, 12.2);
const CAM_DIST = CAM_DELTA.length();
const CAMERA_FOV = 42;
/** Reference depth for point size. Near nodes grow; far nodes shrink. */
const FOCAL = 32;
const FOG_NEAR = 8;
const FOG_FAR = 24;
/** Screen radius for a paper hit. Non-paper dots are not targets. */
const HIT_PX = 15;
const CARD_W = 192;
const CARD_H = 96;

const DRIFT = `
vec3 bandDrift(float phase) {
  return vec3(
    sin(uTime * ${DRIFT_HZ.x} + phase) * 0.08,
    sin(uTime * ${DRIFT_HZ.y} + phase * 1.7) * 0.045,
    cos(uTime * ${DRIFT_HZ.z} + phase * 0.85) * 0.08
  ) * uMotion;
}
`;

const POINT_VERT = `
attribute float aPhase;
attribute float aSize;
attribute float aFade;
attribute float aWash;
attribute float aTwinkle;
attribute float aGlow;
attribute vec3 aTint;
attribute vec3 aCore;
varying float vPhase;
varying float vFade;
varying float vWash;
varying float vTwinkle;
varying float vGlow;
varying vec3 vTint;
varying vec3 vCore;
uniform float uTime;
uniform float uMotion;
uniform float uFocal;
varying float vDist;
${DRIFT}
void main() {
  vec3 drifted = position + bandDrift(aPhase);
  vec4 viewPos = viewMatrix * modelMatrix * vec4(drifted, 1.0);
  gl_Position = projectionMatrix * viewPos;
  vDist = max(-viewPos.z, 0.8);
  gl_PointSize = clamp(aSize * uFocal / vDist, 1.2, 40.0);
  vPhase = aPhase;
  vFade = aFade;
  vWash = aWash;
  vTwinkle = aTwinkle;
  vGlow = aGlow;
  vTint = aTint;
  vCore = aCore;
}
`;

const POINT_FRAG = `
precision highp float;
varying float vPhase;
varying float vFade;
varying float vWash;
varying float vTwinkle;
varying float vGlow;
varying vec3 vTint;
varying vec3 vCore;
uniform float uTime;
uniform float uMotion;
uniform vec3 uFog;
uniform float uFogNear;
uniform float uFogFar;
varying float vDist;
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  float d = length(p);
  if (d > 1.0) discard;
  float fog = smoothstep(uFogNear, uFogFar, vDist);
  float depthShade = mix(1.28, 0.32, fog);
  vec4 outc;
  if (vWash > 0.5) {
    float a = exp(-2.6 * d * d) * 0.07 * mix(1.0, 0.2, fog);
    outc = vec4(mix(vTint, uFog, fog * 0.65), a);
  } else {
    float core = smoothstep(0.48, 0.06, d);
    float glow = exp(-4.6 * d * d) * 0.34;
    float tw = uMotion * vTwinkle * pow(max(sin(uTime * ${TWINKLE_HZ} + vPhase), 0.0), 28.0);
    float lit = clamp(vGlow, 0.0, 1.0);
    vec3 col = mix(vTint, vCore, 0.12 + 0.88 * core);
    col = mix(col, vec3(1.0), core * 0.22 + lit * 0.35 + tw);
    col = mix(col * depthShade, uFog, fog * 0.78);
    float alpha = max(core * (0.7 + 0.3 * vFade), glow * vFade);
    alpha = clamp(alpha * (1.0 + lit) + tw, 0.0, 1.0) * mix(1.0, 0.14, fog);
    outc = vec4(col, alpha);
  }
  if (outc.a < 0.012) discard;
  gl_FragColor = outc;
  #include <colorspace_fragment>
}
`;

const LINK_VERT = `
attribute float aPhase;
attribute vec3 aColor;
attribute float aAlpha;
attribute float aGlow;
varying vec3 vColor;
varying float vAlpha;
varying float vGlow;
varying float vDist;
uniform float uTime;
uniform float uMotion;
${DRIFT}
void main() {
  vec3 drifted = position + bandDrift(aPhase);
  vec4 viewPos = viewMatrix * modelMatrix * vec4(drifted, 1.0);
  gl_Position = projectionMatrix * viewPos;
  vDist = max(-viewPos.z, 0.8);
  vColor = aColor;
  vAlpha = aAlpha;
  vGlow = aGlow;
}
`;

const LINK_FRAG = `
precision highp float;
varying vec3 vColor;
varying float vAlpha;
varying float vGlow;
varying float vDist;
uniform vec3 uFog;
uniform float uFogNear;
uniform float uFogFar;
void main() {
  float fog = smoothstep(uFogNear, uFogFar, vDist);
  vec3 col = mix(vColor * mix(1.15, 0.35, fog), uFog, fog * 0.8);
  float alpha = clamp(vAlpha * (1.0 + vGlow * 1.5), 0.0, 0.8) * mix(1.0, 0.08, fog);
  gl_FragColor = vec4(col, alpha);
  #include <colorspace_fragment>
}
`;

function Field({ nodes: catalogue, showGaps, focus, highlight, reduce, pose, onFocus, onHighlight, onPick }: Props & { reduce: boolean; pose: PlexusPose }) {
  const { camera, gl, size } = useThree();
  const controls = useRef<OrbitControlsImpl>(null);
  const spin = useRef<Group>(null);
  const [hover, setHover] = useState<number | null>(null);
  const time = useRef(0);
  const lockRef = useRef(createHoverLock());
  const pointerInsideRef = useRef(false);
  const overCardRef = useRef(false);
  const leaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shownIdRef = useRef<string | null>(null);
  const [cardShift, setCardShift] = useState({ x: 14, y: -34 });
  const net = useMemo(() => heroVolume(catalogue), [catalogue]);
  const nodes = net.nodes;
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uMotion: { value: reduce || pose ? 0 : 1 },
    uFocal: { value: FOCAL },
    uFog: { value: new Color(ink) },
    uFogNear: { value: FOG_NEAR },
    uFogFar: { value: FOG_FAR },
  }), [reduce, pose]);
  const camReady = useRef(false);
  const draggingRef = useRef(false);
  const tilt = useRef({ x: 0, z: 0 });
  const tiltGoal = useRef({ x: 0, z: 0 });

  const geo = useMemo(() => {
    const color = new Color();
    const n = nodes.length;
    const positions = new Float32Array((n + 1) * 3);
    const sizes = new Float32Array(n + 1);
    const phases = new Float32Array(n + 1);
    const fades = new Float32Array(n + 1);
    const wash = new Float32Array(n + 1);
    const twinkle = new Float32Array(n + 1);
    const glow = new Float32Array(n + 1);
    const tint = new Float32Array((n + 1) * 3);
    const core = new Float32Array((n + 1) * 3);
    const hub = net.hub;
    positions[0] = hub[0]; positions[1] = hub[1]; positions[2] = hub[2];
    sizes[0] = 16;
    wash[0] = 1;
    fades[0] = 1;
    color.set(accent);
    tint[0] = color.r; tint[1] = color.g; tint[2] = color.b;
    color.set(plexusGold);
    core[0] = color.r; core[1] = color.g; core[2] = color.b;
    const idAt = new Map(nodes.map((node, i) => [node.id, i]));
    nodes.forEach((node, i) => {
      const o = i + 1;
      positions[o * 3] = node.pos[0]; positions[o * 3 + 1] = node.pos[1]; positions[o * 3 + 2] = node.pos[2];
      sizes[o] = node.paper ? 9.2 : 5.6;
      phases[o] = node.phase;
      fades[o] = node.fade;
      twinkle[o] = node.twinkle;
      color.set(plexusTint(node.t));
      tint[o * 3] = color.r; tint[o * 3 + 1] = color.g; tint[o * 3 + 2] = color.b;
      color.set(showGaps && node.gap ? gapColor : plexusCore(node.t));
      core[o * 3] = color.r; core[o * 3 + 1] = color.g; core[o * 3 + 2] = color.b;
    });
    const points = new BufferGeometry();
    points.setAttribute("position", new Float32BufferAttribute(positions, 3));
    points.setAttribute("aSize", new Float32BufferAttribute(sizes, 1));
    points.setAttribute("aPhase", new Float32BufferAttribute(phases, 1));
    points.setAttribute("aFade", new Float32BufferAttribute(fades, 1));
    points.setAttribute("aWash", new Float32BufferAttribute(wash, 1));
    points.setAttribute("aTwinkle", new Float32BufferAttribute(twinkle, 1));
    points.setAttribute("aTint", new Float32BufferAttribute(tint, 3));
    points.setAttribute("aCore", new Float32BufferAttribute(core, 3));
    points.setAttribute("aGlow", new Float32BufferAttribute(glow, 1));

    const lp: number[] = [];
    const lc: number[] = [];
    const la: number[] = [];
    const lph: number[] = [];
    const lg = new Float32Array(net.edges.length * 2);
    net.edges.forEach((edge) => {
      const ai = idAt.get(edge.source) ?? 0;
      const bi = idAt.get(edge.target) ?? 0;
      lp.push(edge.a[0], edge.a[1], edge.a[2], edge.b[0], edge.b[1], edge.b[2]);
      lph.push(nodes[ai]?.phase ?? 0, nodes[bi]?.phase ?? 0);
      la.push(edge.alpha, edge.alpha);
      color.set(plexusTint(nodes[ai]?.t ?? 0));
      lc.push(color.r, color.g, color.b);
      color.set(plexusTint(nodes[bi]?.t ?? 1));
      lc.push(color.r, color.g, color.b);
    });
    const lines = new BufferGeometry();
    lines.setAttribute("position", new Float32BufferAttribute(lp, 3));
    lines.setAttribute("aColor", new Float32BufferAttribute(lc, 3));
    lines.setAttribute("aAlpha", new Float32BufferAttribute(la, 1));
    lines.setAttribute("aPhase", new Float32BufferAttribute(lph, 1));
    lines.setAttribute("aGlow", new Float32BufferAttribute(lg, 1));
    return { points, lines };
  }, [nodes, net.edges, net.hub, showGaps]);

  useEffect(() => {
    const pointGlow = geo.points.getAttribute("aGlow");
    const lineGlow = geo.lines.getAttribute("aGlow");
    const arr = pointGlow.array as Float32Array;
    const lines = lineGlow.array as Float32Array;
    arr.fill(0);
    lines.fill(0);
    const hoverNode = hover == null ? null : nodes[hover];
    const near = hoverNode ? neighborIds(hoverNode.id, networkLinks(net.edges)) : new Set<string>();
    const lit = new Set<string>();
    nodes.forEach((node, i) => {
      let g = 0;
      if (highlight?.has(node.id)) g = 0.7;
      if (near.has(node.id)) g = 0.85;
      if (node.id === hoverNode?.id || node.id === focus) g = 1;
      arr[i + 1] = g;
      if (g > 0) lit.add(node.id);
    });
    net.edges.forEach((edge, i) => {
      const hot = (hoverNode && (edge.source === hoverNode.id || edge.target === hoverNode.id)) || lit.has(edge.source) || lit.has(edge.target);
      if (!hot) return;
      lines[i * 2] = 1;
      lines[i * 2 + 1] = 1;
    });
    pointGlow.needsUpdate = true;
    lineGlow.needsUpdate = true;
  }, [hover, focus, highlight, nodes, net.edges, geo]);

  useEffect(() => {
    const el = gl.domElement;
    const projectPapers = () => {
      const rect = el.getBoundingClientRect();
      spin.current?.updateWorldMatrix(true, false);
      const v = new Vector3();
      const paused = reduce || pose || document.hidden || pointerInsideRef.current || overCardRef.current;
      const points = nodes.map((node) => {
        const d = plexusDrift(node.phase, time.current, paused ? 0 : 1);
        v.set(node.pos[0] + d[0], node.pos[1] + d[1], node.pos[2] + d[2]);
        spin.current?.localToWorld(v);
        v.project(camera);
        return {
          id: node.id,
          paper: node.paper,
          x: (v.x * 0.5 + 0.5) * rect.width,
          y: (-v.y * 0.5 + 0.5) * rect.height,
        };
      });
      return { rect, points };
    };
    const hitPaper = (clientX: number, clientY: number) => {
      const { rect, points } = projectPapers();
      return { rect, hit: pickClosestPaperAt(points, clientX - rect.left, clientY - rect.top, HIT_PX) };
    };
    const publish = (id: string | null, at?: { x: number; y: number } | null, rect?: DOMRect) => {
      if (!id) {
        if (shownIdRef.current !== null) {
          shownIdRef.current = null;
          setHover(null);
        }
        return;
      }
      if (shownIdRef.current === id) return;
      shownIdRef.current = id;
      if (at && rect) {
        const box = lockRef.current.card ?? cardBoxBeside(at, { width: rect.width, height: rect.height }, CARD_W, CARD_H);
        // drei's Html overwrites the wrapper transform with the node's screen point, so the
        // card's top-left is that point plus this translate. It matches cardBoxBeside.
        setCardShift({ x: box.left - at.x, y: box.top - at.y });
      }
      const idx = nodes.findIndex((node) => node.paper && node.id === id);
      setHover(idx >= 0 ? idx : null);
    };
    const move = (ev: PointerEvent) => {
      if (ev.pointerType === "touch") return;
      pointerInsideRef.current = true;
      if (leaveRef.current) clearTimeout(leaveRef.current);
      if (ev.buttons) {
        draggingRef.current = true;
        return;
      }
      if (ev.movementX === 0 && ev.movementY === 0) return;
      const { rect, hit } = hitPaper(ev.clientX, ev.clientY);
      const nextCard = hit ? cardBoxBeside(hit, { width: rect.width, height: rect.height }, CARD_W, CARD_H) : null;
      const next = reduceHover(lockRef.current, {
        moving: true,
        hitId: hit?.id ?? null,
        hitAt: hit ? { x: hit.x, y: hit.y } : null,
        pointer: { x: ev.clientX - rect.left, y: ev.clientY - rect.top },
        movement: { x: ev.movementX, y: ev.movementY },
        overCard: overCardRef.current,
        nextCard,
      });
      lockRef.current = next;
      const shown = next.id ? (next.id === hit?.id ? hit : null) : null;
      publish(next.id, shown ?? next.anchor, rect);
    };
    const up = (ev: PointerEvent) => {
      draggingRef.current = false;
      if (ev.pointerType !== "touch") return;
      const { rect, hit } = hitPaper(ev.clientX, ev.clientY);
      const id = hit?.id ?? null;
      lockRef.current = {
        id,
        anchor: hit ? { x: hit.x, y: hit.y } : null,
        card: hit ? cardBoxBeside(hit, { width: rect.width, height: rect.height }, CARD_W, CARD_H) : null,
      };
      publish(id, hit, rect);
    };
    const enter = () => {
      pointerInsideRef.current = true;
      if (leaveRef.current) clearTimeout(leaveRef.current);
    };
    const leave = (ev: PointerEvent) => {
      if (ev.pointerType === "touch") {
        pointerInsideRef.current = false;
        return;
      }
      const next = ev.relatedTarget;
      if (next instanceof Element && next.closest("[data-galaxy-card]")) {
        overCardRef.current = true;
        return;
      }
      pointerInsideRef.current = false;
      // The card mounts under the cursor and can steal the hit in the same turn.
      if (leaveRef.current) clearTimeout(leaveRef.current);
      leaveRef.current = setTimeout(() => {
        if (overCardRef.current || pointerInsideRef.current) return;
        lockRef.current = createHoverLock();
        shownIdRef.current = null;
        setHover(null);
      }, 48);
    };
    const click = (ev: MouseEvent) => {
      const id = hitPaper(ev.clientX, ev.clientY).hit?.id ?? null;
      const node = id ? nodes.find((item) => item.id === id && item.paper) : null;
      if (!node) return;
      onFocus?.(node.id);
      if (node.gap) onHighlight?.(node.cluster);
    };
    el.addEventListener("pointerenter", enter);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointerleave", leave);
    el.addEventListener("click", click);
    return () => {
      el.removeEventListener("pointerenter", enter);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointerleave", leave);
      el.removeEventListener("click", click);
      if (leaveRef.current) clearTimeout(leaveRef.current);
    };
  }, [camera, gl, nodes, onFocus, onHighlight, pose, reduce]);

  useEffect(() => {
    const onMove = (ev: PointerEvent) => {
      if (ev.pointerType === "touch") return;
      if (pointerInsideRef.current || overCardRef.current || draggingRef.current) return;
      tiltGoal.current.x = (ev.clientY / window.innerHeight - 0.5) * 0.16;
      tiltGoal.current.z = (0.5 - ev.clientX / window.innerWidth) * 0.12;
    };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  useFrame((_, dt) => {
    if (document.hidden) return;
    const pinned = pose === "in" || pose === "out";
    const hoverFreeze = pointerInsideRef.current || overCardRef.current;
    const paused = reduce || pinned;
    const step = Math.min(dt, 0.05);
    if (!paused && !hoverFreeze) time.current += step;
    uniforms.uTime.value = time.current;
    // Keep the drift amplitude while hovering so dots don't snap back.
    // Time is held, so the field and the card stay where the pointer found them.
    uniforms.uMotion.value = paused ? 0 : 1;
    const shift = size.width >= WIDE_CANVAS ? CLOUD_SHIFT : 0;
    if (!hoverFreeze && !paused && !draggingRef.current) {
      tilt.current.x += (tiltGoal.current.x - tilt.current.x) * 0.06;
      tilt.current.z += (tiltGoal.current.z - tilt.current.z) * 0.06;
    }
    if (spin.current) {
      spin.current.position.x = shift;
      if (paused) spin.current.rotation.set(0, 0, 0);
      else {
        spin.current.rotation.y = 0;
        spin.current.rotation.x = tilt.current.x;
        spin.current.rotation.z = tilt.current.z;
      }
    }
    const controlsNow = controls.current;
    if (!controlsNow) return;
    if (!camReady.current && size.width > 0) {
      controlsNow.target.set(shift, 0, 0);
      camera.position.set(shift + CAM_DELTA.x, CAM_DELTA.y, CAM_DELTA.z);
      camera.lookAt(shift, 0, 0);
      controlsNow.update();
      camReady.current = true;
    } else if (controlsNow.target.x !== shift) {
      controlsNow.target.x = shift;
    }
    controlsNow.autoRotate = !paused && !hoverFreeze && !draggingRef.current;
  });

  const hovered = hover == null ? null : nodes[hover];
  const tip = hovered?.paper ? hovered : null;

  return (
    <>
      <group ref={spin}>
        <lineSegments geometry={geo.lines} frustumCulled={false} raycast={() => null} renderOrder={1}>
          <shaderMaterial args={[{ uniforms, vertexShader: LINK_VERT, fragmentShader: LINK_FRAG, transparent: true, depthWrite: false, toneMapped: false }]} />
        </lineSegments>
        <points geometry={geo.points} frustumCulled={false} raycast={() => null} renderOrder={2}>
          <shaderMaterial args={[{ uniforms, vertexShader: POINT_VERT, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, toneMapped: false }]} />
        </points>
        {tip && (
          <Html position={tip.pos} center zIndexRange={[12, 0]} style={{ pointerEvents: "none" }}>
            <div
              className="glass pointer-events-auto w-48 p-2.5 text-left text-xs"
              style={{ transform: `translate(${cardShift.x}px, ${cardShift.y}px)` }}
              data-testid="galaxy-paper-card"
              data-galaxy-card=""
              onPointerEnter={() => {
                overCardRef.current = true;
                if (leaveRef.current) clearTimeout(leaveRef.current);
              }}
              onPointerLeave={(ev) => {
                overCardRef.current = false;
                const next = ev.relatedTarget;
                if (next === gl.domElement) {
                  pointerInsideRef.current = true;
                  return;
                }
                lockRef.current = createHoverLock();
                shownIdRef.current = null;
                setHover(null);
              }}
              onPointerDown={(e) => e.stopPropagation()}
            >
              <div className="font-medium text-white">{tip.id}</div>
              <p className="mt-0.5 text-mist">Paper{tip.cluster ? ` · topic cluster ${tip.cluster}` : ""}</p>
              {showGaps && tip.gap && <p className="text-gap">Research gap</p>}
              <button className="btn mt-2 w-full py-1" onClick={() => onPick?.(tip.id)}>Search this paper</button>
            </div>
          </Html>
        )}
      </group>
      <OrbitControls
        ref={controls}
        enablePan={false}
        enableZoom={false}
        enableDamping
        dampingFactor={0.08}
        rotateSpeed={0.55}
        autoRotate
        autoRotateSpeed={2.4}
        minDistance={CAM_DIST}
        maxDistance={CAM_DIST}
        minPolarAngle={0.45}
        maxPolarAngle={Math.PI - 0.45}
      />
    </>
  );
}

interface Props {
  nodes: (Star & { fresh?: boolean })[];
  links: TopicLink[];
  showGaps: boolean;
  focus: string | null;
  highlight: Set<string> | null;
  onFocus?: (id: string) => void;
  onHighlight?: (cluster?: string) => void;
  onPick?: (id: string) => void;
  pose?: PlexusPose;
}

export default function Galaxy3D(p: Props) {
  const reduce = usePrefersReduced();
  const hidden = usePageHidden();
  return (
    <Canvas
      frameloop={hidden ? "never" : "always"}
      camera={{ position: [CLOUD_SHIFT + CAM_DELTA.x, CAM_DELTA.y, CAM_DELTA.z], fov: CAMERA_FOV }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, toneMapping: NoToneMapping }}
    >
      <color attach="background" args={[ink]} />
      <Field {...p} reduce={reduce} pose={p.pose ?? null} />
    </Canvas>
  );
}

function usePrefersReduced() {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduce(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);
  return reduce;
}

function usePageHidden() {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    const apply = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", apply);
    apply();
    return () => document.removeEventListener("visibilitychange", apply);
  }, []);
  return hidden;
}
