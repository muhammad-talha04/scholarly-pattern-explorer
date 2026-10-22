"use client";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls, Stars } from "@react-three/drei";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  BufferGeometry, CircleGeometry, Color, Float32BufferAttribute, InstancedBufferAttribute, InstancedMesh,
  Matrix4, NoToneMapping, Raycaster, Sphere, SphereGeometry, Vector2, Vector3,
} from "three";
import type { Group } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { TopicLink } from "@/lib/graph";
import { NODE_BRIGHTNESS, clusterColors, gap as gapColor, galaxyColor, ink, linkGrey } from "@/lib/theme";
import { HOVER_STICK_PX, resolvePaperHover, type PaperHit } from "./hover";
import { centroid, neighborIds, posedPosition, type Star } from "./stars";

const NODE_VERT = `
attribute vec3 aColor;
attribute float aGlow;
attribute float aTwinkle;
attribute float aEmerging;
attribute float aPhase;
varying vec3 vColor;
varying vec3 vNormalV;
varying float vGlow;
varying float vTwinkle;
varying float vEmerging;
varying float vPhase;
void main() {
  vec4 viewPos = viewMatrix * modelMatrix * instanceMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * viewPos;
  vNormalV = normalize(mat3(viewMatrix) * mat3(instanceMatrix) * normal);
  vColor = aColor;
  vGlow = aGlow;
  vTwinkle = aTwinkle;
  vEmerging = aEmerging;
  vPhase = aPhase;
}
`;

const NODE_FRAG = `
precision highp float;
varying vec3 vColor;
varying vec3 vNormalV;
varying float vGlow;
varying float vTwinkle;
varying float vEmerging;
varying float vPhase;
uniform float uTime;
uniform float uMotion;
uniform float uBrightness;
uniform vec3 uWarm;
void main() {
  float base = mix(uBrightness, 1.0, clamp(vGlow, 0.0, 1.0));
  float tw = uMotion * vTwinkle * pow(max(sin(uTime * 2.4 + vPhase), 0.0), 18.0);
  vec3 col = vColor * min(1.0, base + tw * 0.22);
  col = mix(col, uWarm, clamp(vEmerging, 0.0, 1.0) * 0.35);
  float rim = pow(1.0 - abs(dot(normalize(vNormalV), vec3(0.0, 0.0, 1.0))), 3.0);
  col += rim * 0.045;
  gl_FragColor = vec4(min(col, vec3(1.0)), 1.0);
  #include <colorspace_fragment>
}
`;

const SHADOW_VERT = `
varying vec2 vUv;
void main() {
  vUv = uv;
  vec3 pos = position + vec3(0.04, -0.12, 0.02);
  gl_Position = projectionMatrix * viewMatrix * modelMatrix * instanceMatrix * vec4(pos, 1.0);
}
`;

const SHADOW_FRAG = `
precision highp float;
varying vec2 vUv;
void main() {
  float d = length((vUv - 0.5) * 2.0);
  float alpha = (1.0 - smoothstep(0.78, 0.98, d)) * 0.35;
  if (alpha < 0.02) discard;
  gl_FragColor = vec4(0.0, 0.0, 0.0, alpha);
}
`;

function CameraRig({ look, still, controls }: { look: [number, number, number]; still: boolean; controls: React.RefObject<OrbitControlsImpl | null> }) {
  const { camera } = useThree();
  const intro = useRef(still ? 1 : 0);
  const from = useRef(new Vector3(0, 6.2, 18));
  const to = useRef(new Vector3());
  const lookV = useRef(new Vector3());
  useEffect(() => {
    lookV.current.set(look[0], look[1], look[2]);
    to.current.set(look[0] * 0.2, look[1] + 3.4, look[2] + 12.5);
    if (still) {
      camera.position.copy(to.current);
      if (controls.current) { controls.current.target.copy(lookV.current); controls.current.update(); }
    }
  }, [look, still, camera, controls]);
  useFrame((_, dt) => {
    if (document.hidden) return;
    if (still) {
      camera.position.copy(to.current);
      if (controls.current) { controls.current.target.copy(lookV.current); controls.current.update(); }
      return;
    }
    intro.current = Math.min(1, intro.current + dt * 0.45);
    const k = 1 - Math.exp(-dt * 2.4);
    const dest = from.current.clone().lerp(to.current, intro.current);
    camera.position.lerp(dest, k);
    if (controls.current) {
      controls.current.target.lerp(lookV.current, k);
      controls.current.update();
    }
  });
  return null;
}

function Field({ nodes, links, showGaps, focus, highlight, still, onFocus, onHighlight, onPick }: Props & { still: boolean }) {
  const { camera, gl } = useThree();
  const controls = useRef<OrbitControlsImpl>(null);
  const groupRef = useRef<Group>(null);
  const nodesRef = useRef<InstancedMesh>(null);
  const shadowRef = useRef<InstancedMesh>(null);
  const anchorRef = useRef<Group>(null);
  const glowAttr = useRef<InstancedBufferAttribute | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const hoverRef = useRef<number | null>(null);
  const stickRef = useRef<{ x: number; y: number; id: number | null } | null>(null);
  const positions = useRef<[number, number, number][]>([]);
  const scales = useRef<Float32Array>(new Float32Array(0));
  const time = useRef(0);
  const nodesLive = useRef(nodes);
  nodesLive.current = nodes;
  const stillRef = useRef(still);
  stillRef.current = still;
  const focusRef = useRef(onFocus);
  focusRef.current = onFocus;
  const highlightRef = useRef(onHighlight);
  highlightRef.current = onHighlight;
  const cameraRef = useRef(camera);
  cameraRef.current = camera;
  const raycaster = useRef(new Raycaster());
  const ndc = useRef(new Vector2());
  const tmp = useRef(new Vector3());
  const mat = useRef(new Matrix4());
  const sphere = useMemo(() => new SphereGeometry(1, 22, 16), []);
  const disc = useMemo(() => { const g = new CircleGeometry(0.62, 20); g.rotateX(-Math.PI / 2); return g; }, []);
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uMotion: { value: 1 },
    uBrightness: { value: NODE_BRIGHTNESS },
    uWarm: { value: new Color(clusterColors[2]) },
  }), []);
  const shadowUniforms = useMemo(() => ({ uTime: uniforms.uTime, uMotion: uniforms.uMotion }), [uniforms]);

  const segments = useMemo(() => {
    const by = new Map(nodes.map((n, i) => [n.id, i]));
    const pairs: [number, number][] = [];
    for (const link of links) {
      const a = by.get(link.source);
      const b = by.get(link.target);
      if (a == null || b == null) continue;
      pairs.push([a, b]);
    }
    return pairs;
  }, [nodes, links]);
  const lineGeo = useMemo(() => {
    const g = new BufferGeometry();
    g.setAttribute("position", new Float32BufferAttribute(new Float32Array(Math.max(segments.length, 1) * 6), 3));
    return g;
  }, [segments.length]);

  useLayoutEffect(() => {
    const mesh = nodesRef.current;
    const shadow = shadowRef.current;
    if (!mesh || !shadow) return;
    const color = new Color();
    const n = nodes.length;
    const colors = new Float32Array(n * 3);
    const twinkle = new Float32Array(n);
    const emerging = new Float32Array(n);
    const phases = new Float32Array(n);
    const glow = new Float32Array(n);
    const sized = new Float32Array(n);
    const maxS = Math.max(...nodes.map((node) => node.support), 0.01);
    nodes.forEach((node, i) => {
      sized[i] = 0.09 + 0.32 * Math.sqrt(node.support / maxS);
      const hex = showGaps && node.gap ? gapColor : galaxyColor(node.colorIndex, node.clusterId);
      color.set(hex);
      colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b;
      twinkle[i] = node.fresh ? 1 : 0;
      emerging[i] = node.gap ? 0 : Math.max(0, Math.min(1, node.emerging || 0));
      phases[i] = (i * 17) % 628 / 100;
      glow[i] = 0;
    });
    scales.current = sized;
    const put = (target: InstancedMesh, name: string, data: Float32Array, size: number) => {
      const attr = new InstancedBufferAttribute(data, size);
      target.geometry.setAttribute(name, attr);
      return attr;
    };
    put(mesh, "aColor", colors, 3);
    put(mesh, "aTwinkle", twinkle, 1);
    put(mesh, "aEmerging", emerging, 1);
    put(mesh, "aPhase", phases, 1);
    glowAttr.current = put(mesh, "aGlow", glow, 1);
    mesh.count = n;
    shadow.count = n;
    mesh.frustumCulled = false;
    shadow.frustumCulled = false;
    const wide = new Sphere(new Vector3(), 1e5);
    mesh.boundingSphere = wide;
    shadow.boundingSphere = wide.clone();
  }, [nodes, showGaps]);

  useEffect(() => {
    const attr = glowAttr.current;
    if (!attr) return;
    const arr = attr.array as Float32Array;
    const hoverId = hover == null ? null : nodes[hover]?.id;
    const near = hoverId ? neighborIds(hoverId, links) : new Set<string>();
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i];
      let g = 0;
      if (highlight?.has(n.id)) g = 0.62;
      if (near.has(n.id)) g = 0.48;
      if (n.id === hoverId || n.id === focus) g = 1;
      arr[i] = g;
    }
    attr.needsUpdate = true;
  }, [hover, focus, highlight, nodes, links]);

  useFrame((_, dt) => {
    if (document.hidden) return;
    const frozen = stillRef.current;
    if (!frozen) time.current += Math.min(dt, 0.05);
    const motion = frozen ? 0 : 1;
    uniforms.uTime.value = time.current;
    uniforms.uMotion.value = motion;
    const list = nodesLive.current;
    const mesh = nodesRef.current;
    const shadow = shadowRef.current;
    if (!mesh || !shadow) return;
    const posed = positions.current;
    posed.length = list.length;
    const m = mat.current;
    for (let i = 0; i < list.length; i++) {
      const p = posedPosition(list[i], time.current, motion);
      posed[i] = p;
      const s = scales.current[i] || 0.12;
      m.makeScale(s, s, s);
      m.setPosition(p[0], p[1], p[2]);
      mesh.setMatrixAt(i, m);
      shadow.setMatrixAt(i, m);
    }
    mesh.instanceMatrix.needsUpdate = true;
    shadow.instanceMatrix.needsUpdate = true;
    if (segments.length && lineGeo) {
      const attr = lineGeo.getAttribute("position");
      const arr = attr.array as Float32Array;
      segments.forEach(([a, b], i) => {
        const pa = posed[a];
        const pb = posed[b];
        if (!pa || !pb) return;
        const o = i * 6;
        arr[o] = pa[0]; arr[o + 1] = pa[1]; arr[o + 2] = pa[2];
        arr[o + 3] = pb[0]; arr[o + 4] = pb[1]; arr[o + 5] = pb[2];
      });
      attr.needsUpdate = true;
    }
    const tip = hoverRef.current;
    if (anchorRef.current) {
      const p = tip == null ? null : posed[tip];
      if (p) anchorRef.current.position.set(p[0], p[1], p[2]);
    }
  });

  useEffect(() => {
    const el = gl.domElement;
    const screenDistance = (index: number, px: number, py: number, rect: DOMRect) => {
      const p = positions.current[index];
      if (!p || rect.width === 0 || rect.height === 0) return Number.POSITIVE_INFINITY;
      const v = tmp.current;
      v.set(p[0], p[1], p[2]);
      groupRef.current?.updateWorldMatrix(true, false);
      groupRef.current?.localToWorld(v);
      v.project(cameraRef.current);
      const x = (v.x * 0.5 + 0.5) * rect.width;
      const y = (-v.y * 0.5 + 0.5) * rect.height;
      return Math.hypot(x - px, y - py);
    };
    const sample = (ev: { clientX: number; clientY: number }) => {
      const rect = el.getBoundingClientRect();
      const px = ev.clientX - rect.left;
      const py = ev.clientY - rect.top;
      const mesh = nodesRef.current;
      const hits: PaperHit[] = [];
      if (mesh && rect.width > 0 && rect.height > 0) {
        ndc.current.set((px / rect.width) * 2 - 1, -(py / rect.height) * 2 + 1);
        groupRef.current?.updateWorldMatrix(true, true);
        raycaster.current.setFromCamera(ndc.current, cameraRef.current);
        const found = raycaster.current.intersectObject(mesh, false);
        const seen = new Set<number>();
        for (const hit of found) {
          const id = hit.instanceId;
          if (id == null || seen.has(id) || id >= nodesLive.current.length) continue;
          seen.add(id);
          hits.push({ id, distance: screenDistance(id, px, py, rect) });
        }
      }
      const locked = stickRef.current?.id ?? null;
      const lockedDistance = locked == null ? null : screenDistance(locked, px, py, rect);
      return { hits, lockedDistance };
    };
    const move = (ev: PointerEvent) => {
      const stick = stickRef.current;
      const travel = stick ? Math.hypot(ev.clientX - stick.x, ev.clientY - stick.y) : Number.POSITIVE_INFINITY;
      const locked = stick?.id ?? null;
      if (locked != null && travel < HOVER_STICK_PX) return;
      const { hits, lockedDistance } = sample(ev);
      const next = resolvePaperHover({ locked, travelPx: travel, hits, lockedDistance });
      stickRef.current = { x: ev.clientX, y: ev.clientY, id: next };
      if (next !== hoverRef.current) {
        hoverRef.current = next;
        const p = next == null ? null : positions.current[next];
        if (anchorRef.current && p) anchorRef.current.position.set(p[0], p[1], p[2]);
        setHover(next);
      }
    };
    const leave = (ev: PointerEvent) => {
      const next = ev.relatedTarget;
      const card = el.parentElement?.querySelector("[data-testid=galaxy-paper-card]");
      if (next instanceof Node && card?.contains(next)) return;
      stickRef.current = null;
      hoverRef.current = null;
      setHover(null);
    };
    const click = (ev: MouseEvent) => {
      const { hits } = sample(ev);
      if (!hits.length) return;
      hits.sort((a, b) => a.distance - b.distance);
      const node = nodesLive.current[hits[0].id];
      if (!node) return;
      focusRef.current?.(node.id);
      if (node.gap) highlightRef.current?.(node.cluster);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", leave);
    el.addEventListener("click", click);
    return () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", leave);
      el.removeEventListener("click", click);
    };
  }, [gl]);

  const look = useMemo(() => {
    const picked = highlight && highlight.size ? nodes.filter((n) => highlight.has(n.id)) : [];
    if (picked.length) return centroid(picked.map((n) => ({ pos: n.center })));
    const focused = nodes.find((n) => n.id === focus);
    return focused ? focused.pos : centroid(nodes);
  }, [highlight, focus, nodes]);

  const tip = hover == null ? null : nodes[hover] ?? null;

  return (
    <>
      <group ref={groupRef}>
        <instancedMesh key={`shadow-${nodes.length}`} ref={shadowRef} args={[disc, undefined, Math.max(nodes.length, 1)]} frustumCulled={false} raycast={() => null}>
          <shaderMaterial args={[{ uniforms: shadowUniforms, vertexShader: SHADOW_VERT, fragmentShader: SHADOW_FRAG, transparent: true, depthWrite: false, toneMapped: false }]} />
        </instancedMesh>
        <instancedMesh key={`nodes-${nodes.length}`} ref={nodesRef} args={[sphere, undefined, Math.max(nodes.length, 1)]} frustumCulled={false}>
          <shaderMaterial args={[{ uniforms, vertexShader: NODE_VERT, fragmentShader: NODE_FRAG, toneMapped: false }]} />
        </instancedMesh>
        {segments.length > 0 && (
          <lineSegments geometry={lineGeo} frustumCulled={false} raycast={() => null}>
            <lineBasicMaterial color={linkGrey} transparent opacity={0.28} toneMapped={false} />
          </lineSegments>
        )}
        <group ref={anchorRef}>
          {tip && (
            <Html position={[0.72, 0.42, 0]} zIndexRange={[12, 0]} style={{ pointerEvents: "none" }}>
              <div className="glass w-48 p-2.5 text-left text-xs" role="tooltip" data-testid="galaxy-paper-card" style={{ pointerEvents: "none" }}>
                <div className="font-medium text-white">{tip.id}</div>
                <p className="mt-0.5 text-mist">Paper{tip.cluster ? ` · topic cluster ${tip.cluster}` : ""}</p>
                {showGaps && tip.gap && <p className="text-gap">Research gap</p>}
                <button className="btn mt-2 w-full py-1" style={{ pointerEvents: "auto" }} onPointerDown={(e) => e.stopPropagation()} onClick={() => onPick?.(tip.id)}>Search this paper</button>
              </div>
            </Html>
          )}
        </group>
      </group>
      <CameraRig look={look} still={still} controls={controls} />
      <OrbitControls ref={controls} enablePan={false} enableZoom={!still} enableRotate={!still} minDistance={5} maxDistance={26} />
      <Stars radius={80} depth={40} count={1100} factor={2} fade speed={still ? 0 : 0.22} />
    </>
  );
}

interface Props {
  nodes: (Star & { fresh?: boolean })[];
  links: TopicLink[];
  showGaps: boolean;
  focus: string | null;
  highlight: Set<string> | null;
  /** Low power or reduced motion: the same galaxy, held still. */
  still?: boolean;
  onFocus?: (id: string) => void;
  onHighlight?: (cluster?: string) => void;
  onPick?: (id: string) => void;
}

export default function Galaxy3D(p: Props) {
  const reduce = usePrefersReduced();
  const hidden = usePageHidden();
  const still = !!p.still || reduce;
  if (!p.nodes.length) return null;
  return (
    <Canvas
      className="h-full w-full"
      frameloop={hidden ? "never" : "always"}
      camera={{ position: [0, 4.2, 13], fov: 48 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, toneMapping: NoToneMapping }}
    >
      <color attach="background" args={[ink]} />
      <Field {...p} still={still} />
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
