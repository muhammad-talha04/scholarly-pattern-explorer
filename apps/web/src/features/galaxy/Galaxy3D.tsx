"use client";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import { BufferGeometry, Color, Float32BufferAttribute, NoToneMapping, Vector3 } from "three";
import type { Group } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { TopicLink } from "@/lib/graph";
import { accent, gap as gapColor, ink, plexusGold } from "@/lib/theme";
import { heroNetwork, neighborIds, networkLinks, plexusCore, plexusDrift, plexusTint, type Star } from "./stars";

/** Nearly overhead so the XZ diagonal reads lower-left to upper-right, with a little parallax. */
const CAMERA_POS = new Vector3(0.2, 22.5, 2.8);
const CAMERA_FOV = 46;

const DRIFT = `
vec3 bandDrift(float phase) {
  return vec3(
    sin(uTime * 0.37 + phase) * 0.08,
    sin(uTime * 0.29 + phase * 1.7) * 0.045,
    cos(uTime * 0.33 + phase * 0.85) * 0.08
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
${DRIFT}
void main() {
  vec3 drifted = position + bandDrift(aPhase);
  vec4 world = modelMatrix * vec4(drifted, 1.0);
  gl_Position = projectionMatrix * viewMatrix * world;
  gl_PointSize = aSize;
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
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  float d = length(p);
  if (d > 1.0) discard;
  vec4 outc;
  if (vWash > 0.5) {
    float a = exp(-2.6 * d * d) * 0.075;
    outc = vec4(vTint, a);
  } else {
    float core = smoothstep(0.5, 0.08, d);
    float glow = exp(-4.4 * d * d) * 0.4;
    float tw = uMotion * vTwinkle * pow(max(sin(uTime * 1.7 + vPhase), 0.0), 28.0);
    float lit = clamp(vGlow, 0.0, 1.0);
    vec3 col = mix(vTint, vCore, 0.25 + 0.75 * core);
    col = mix(col, vec3(1.0), lit * 0.35 + tw);
    float alpha = max(core * (0.45 + 0.55 * vFade), glow * vFade);
    alpha = clamp(alpha * (1.0 + lit) + tw, 0.0, 1.0);
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
uniform float uTime;
uniform float uMotion;
${DRIFT}
void main() {
  vec3 drifted = position + bandDrift(aPhase);
  gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(drifted, 1.0);
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
void main() {
  gl_FragColor = vec4(vColor, clamp(vAlpha * (1.0 + vGlow * 1.5), 0.0, 0.8));
  #include <colorspace_fragment>
}
`;

function CameraRig({ look, reduce, controls }: { look: [number, number, number]; reduce: boolean; controls: React.RefObject<OrbitControlsImpl | null> }) {
  const { camera } = useThree();
  const intro = useRef(reduce ? 1 : 0.65);
  const from = useRef(new Vector3(0.2, 28, 4.2));
  const to = useRef(new Vector3());
  const lookV = useRef(new Vector3());
  useEffect(() => {
    lookV.current.set(look[0], look[1], look[2]);
    to.current.set(look[0] * 0.12 + CAMERA_POS.x, look[1] + CAMERA_POS.y, look[2] + CAMERA_POS.z);
    if (reduce) {
      camera.position.copy(to.current);
      if (controls.current) { controls.current.target.copy(lookV.current); controls.current.update(); }
    }
  }, [look, reduce, camera, controls]);
  useFrame((_, dt) => {
    if (reduce || document.hidden) return;
    intro.current = Math.min(1, intro.current + dt * 1.15);
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

function Field({ nodes: catalogue, showGaps, focus, highlight, reduce, onFocus, onHighlight, onPick }: Props & { reduce: boolean }) {
  const { camera, gl } = useThree();
  const controls = useRef<OrbitControlsImpl>(null);
  const spin = useRef<Group>(null);
  const [hover, setHover] = useState<number | null>(null);
  const time = useRef(0);
  const net = useMemo(() => heroNetwork(catalogue), [catalogue]);
  const nodes = net.nodes;
  const uniforms = useMemo(() => ({ uTime: { value: 0 }, uMotion: { value: reduce ? 0 : 1 } }), [reduce]);

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
    sizes[0] = 150;
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
      sizes[o] = 7.5;
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
    const pick = (ev: { clientX: number; clientY: number }) => {
      const rect = el.getBoundingClientRect();
      const px = ev.clientX - rect.left;
      const py = ev.clientY - rect.top;
      spin.current?.updateWorldMatrix(true, false);
      const v = new Vector3();
      const motion = reduce || document.hidden ? 0 : 1;
      let best = -1;
      let bestD = 15 * 15;
      nodes.forEach((node, i) => {
        const d = plexusDrift(node.phase, time.current, motion);
        v.set(node.pos[0] + d[0], node.pos[1] + d[1], node.pos[2] + d[2]);
        spin.current?.localToWorld(v);
        v.project(camera);
        const x = (v.x * 0.5 + 0.5) * rect.width;
        const y = (-v.y * 0.5 + 0.5) * rect.height;
        const dd = (x - px) ** 2 + (y - py) ** 2;
        if (dd < bestD) { bestD = dd; best = i; }
      });
      setHover(best >= 0 ? best : null);
    };
    const leave = () => setHover(null);
    const click = (ev: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const px = ev.clientX - rect.left;
      const py = ev.clientY - rect.top;
      spin.current?.updateWorldMatrix(true, false);
      const v = new Vector3();
      let best = -1;
      let bestD = 15 * 15;
      nodes.forEach((node, i) => {
        v.set(node.pos[0], node.pos[1], node.pos[2]);
        spin.current?.localToWorld(v);
        v.project(camera);
        const x = (v.x * 0.5 + 0.5) * rect.width;
        const y = (-v.y * 0.5 + 0.5) * rect.height;
        const dd = (x - px) ** 2 + (y - py) ** 2;
        if (dd < bestD) { bestD = dd; best = i; }
      });
      const node = best >= 0 ? nodes[best] : null;
      if (!node?.paper) return;
      onFocus?.(node.id);
      if (node.gap) onHighlight?.(node.cluster);
    };
    el.addEventListener("pointermove", pick);
    el.addEventListener("pointerleave", leave);
    el.addEventListener("click", click);
    return () => {
      el.removeEventListener("pointermove", pick);
      el.removeEventListener("pointerleave", leave);
      el.removeEventListener("click", click);
    };
  }, [camera, gl, nodes, onFocus, onHighlight, reduce]);

  useFrame((_, dt) => {
    if (document.hidden) return;
    time.current += Math.min(dt, 0.05);
    uniforms.uTime.value = time.current;
    uniforms.uMotion.value = reduce ? 0 : 1;
    if (!spin.current) return;
    if (reduce) {
      spin.current.rotation.set(0, 0, 0);
      return;
    }
    const t = time.current;
    spin.current.rotation.y = Math.sin(t * 0.16) * 0.2;
    spin.current.rotation.x = Math.sin(t * 0.12 + 0.7) * 0.045;
    spin.current.rotation.z = Math.sin(t * 0.1 + 1.4) * 0.03;
  });

  const look = useMemo(() => {
    const picked = highlight && highlight.size ? nodes.filter((n) => highlight.has(n.id)) : [];
    if (picked.length) return centroidOf(picked);
    const focused = nodes.find((n) => n.id === focus);
    return focused ? focused.pos : net.hub;
  }, [highlight, focus, nodes, net.hub]);

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
          <Html position={tip.pos} center zIndexRange={[12, 0]} style={{ pointerEvents: "auto" }}>
            <div className="glass w-48 p-2.5 text-left text-xs" onPointerDown={(e) => e.stopPropagation()}>
              <div className="font-medium text-white">{tip.id}</div>
              <p className="mt-0.5 text-mist">Paper{tip.cluster ? ` · topic cluster ${tip.cluster}` : ""}</p>
              {showGaps && tip.gap && <p className="text-gap">Research gap</p>}
              <button className="btn mt-2 w-full py-1" onClick={() => onPick?.(tip.id)}>Search this paper</button>
            </div>
          </Html>
        )}
      </group>
      <CameraRig look={look} reduce={reduce} controls={controls} />
      <OrbitControls ref={controls} enablePan={false} enableZoom minDistance={20} maxDistance={52} />
    </>
  );
}

function centroidOf(nodes: { pos: [number, number, number] }[]): [number, number, number] {
  const c = nodes.reduce((a, n) => [a[0] + n.pos[0], a[1] + n.pos[1], a[2] + n.pos[2]] as [number, number, number], [0, 0, 0]);
  return [c[0] / nodes.length, c[1] / nodes.length, c[2] / nodes.length];
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
}

export default function Galaxy3D(p: Props) {
  const reduce = usePrefersReduced();
  const hidden = usePageHidden();
  return (
    <Canvas
      frameloop={hidden ? "never" : "always"}
      camera={{ position: [CAMERA_POS.x, CAMERA_POS.y, CAMERA_POS.z], fov: CAMERA_FOV }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, toneMapping: NoToneMapping }}
    >
      <color attach="background" args={[ink]} />
      <Field {...p} reduce={reduce} />
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
