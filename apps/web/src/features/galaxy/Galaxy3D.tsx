"use client";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  BufferGeometry, Color, DoubleSide, Float32BufferAttribute, InstancedBufferAttribute, InstancedMesh, Matrix4, NoToneMapping,
  PlaneGeometry, SphereGeometry, Vector3,
} from "three";
import type { Group } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { TopicLink } from "@/lib/graph";
import { NODE_BRIGHTNESS, clusterColors, dust as dustColor, gap as gapColor, ink, linkAmber } from "@/lib/theme";
import { heroNetwork, neighborIds, networkLinks, nodeAmber, type Star } from "./stars";

/** Resting camera, above the disc so the spiral reads as a cluster rather than an edge-on line. At fov 46 and this distance a unit is ~38px on a 900px-tall pane, so a 0.16–0.30 sphere is about 6–12px. */
const CAMERA_POS = new Vector3(0.35, 26, 11);
const CAMERA_FOV = 46;

const NODE_VERT = `
attribute float aPhase;
attribute vec3 aColor;
attribute float aGlow;
attribute float aTwinkle;
attribute float aEmerging;
varying vec3 vColor;
varying float vGlow;
varying float vTwinkle;
varying float vEmerging;
varying float vPhase;
uniform float uTime;
uniform float uMotion;
void main() {
  float pulse = 1.0 + uMotion * sin(uTime * 1.5 + aPhase) * 0.045;
  vec4 world = modelMatrix * instanceMatrix * vec4(position * pulse, 1.0);
  gl_Position = projectionMatrix * viewMatrix * world;
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
  float pulse = uMotion * (0.5 + 0.5 * sin(uTime * 1.5 + vPhase)) * 0.06;
  float tw = uMotion * vTwinkle * exp(-uTime * 1.55) * (0.55 + 0.45 * sin(uTime * 16.0));
  float bright = min(1.0, base + pulse + tw * 0.16 + vEmerging * 0.08);
  vec3 srgb = pow(max(vColor, vec3(0.0)), vec3(0.454545));
  vec3 warm = pow(max(uWarm, vec3(0.0)), vec3(0.454545));
  vec3 mixed = mix(srgb, warm, clamp(vEmerging, 0.0, 1.0) * 0.35);
  vec3 outS = min(vec3(1.0), mixed * bright);
  gl_FragColor = vec4(pow(outS, vec3(2.2)), 1.0);
  #include <colorspace_fragment>
}
`;

const HALO_VERT = `
attribute float aPhase;
attribute vec3 aColor;
attribute float aGlow;
varying vec2 vUv;
varying vec3 vColor;
varying float vGlow;
uniform float uTime;
uniform float uMotion;
void main() {
  float pulse = 1.0 + uMotion * sin(uTime * 1.5 + aPhase) * 0.045;
  float s = length(instanceMatrix[0].xyz) * pulse;
  vec4 center = viewMatrix * modelMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);
  gl_Position = projectionMatrix * (center + vec4(position.xy * s, 0.0, 0.0));
  vUv = uv;
  vColor = aColor;
  vGlow = aGlow;
}
`;

const HALO_FRAG = `
precision highp float;
varying vec2 vUv;
varying vec3 vColor;
varying float vGlow;
void main() {
  float d = length(vUv * 2.0 - 1.0);
  if (d > 1.0) discard;
  float alpha = exp(-3.6 * d * d) * (0.11 + vGlow * 0.08);
  if (alpha < 0.012) discard;
  gl_FragColor = vec4(vColor, alpha);
  #include <colorspace_fragment>
}
`;

const LINK_VERT = `
attribute float aT;
attribute float aPulse;
attribute float aPhase;
attribute float aAlpha;
varying float vT;
varying float vPulse;
varying float vPhase;
varying float vAlpha;
void main() {
  vT = aT;
  vPulse = aPulse;
  vPhase = aPhase;
  vAlpha = aAlpha;
  gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(position, 1.0);
}
`;

const LINK_FRAG = `
precision highp float;
varying float vT;
varying float vPulse;
varying float vPhase;
varying float vAlpha;
uniform vec3 uColor;
uniform float uTime;
uniform float uMotion;
void main() {
  float phase = fract(uTime * 0.16 + vPhase);
  float spark = uMotion * vPulse * exp(-pow((vT - phase) * 7.5, 2.0));
  gl_FragColor = vec4(uColor, min(0.8, vAlpha + spark * 0.5));
  #include <colorspace_fragment>
}
`;

const DUST_VERT = `
attribute float aSize;
void main() {
  vec4 mv = viewMatrix * modelMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = aSize;
}
`;

const DUST_FRAG = `
precision highp float;
uniform vec3 uColor;
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  float d = dot(p, p);
  if (d > 1.0) discard;
  gl_FragColor = vec4(uColor, 0.92 * (1.0 - d * 0.35));
  #include <colorspace_fragment>
}
`;

function phaseOf(id: string) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i) * 17) % 628;
  return h / 100;
}

function CameraRig({ look, reduce, controls }: { look: [number, number, number]; reduce: boolean; controls: React.RefObject<OrbitControlsImpl | null> }) {
  const { camera } = useThree();
  const intro = useRef(reduce ? 1 : 0.65);
  const from = useRef(new Vector3(0.35, 32, 14));
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

function nodeRadius(support: number, maxS: number, secondary: boolean) {
  if (secondary) return 0.3;
  return 0.15 + 0.1 * Math.sqrt(Math.max(support, 0) / maxS);
}

function Field({ nodes: catalogue, showGaps, focus, highlight, reduce, onFocus, onHighlight, onPick }: Props & { reduce: boolean }) {
  const controls = useRef<OrbitControlsImpl>(null);
  const spin = useRef<Group>(null);
  const nodesRef = useRef<InstancedMesh>(null);
  const haloRef = useRef<InstancedMesh>(null);
  const glowAttr = useRef<InstancedBufferAttribute | null>(null);
  const haloGlowAttr = useRef<InstancedBufferAttribute | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const net = useMemo(() => heroNetwork(catalogue), [catalogue]);
  const nodes = net.nodes;
  const maxS = Math.max(...nodes.map((n) => n.support), 0.01);
  const sphere = useMemo(() => new SphereGeometry(1, 28, 20), []);
  const haloPlane = useMemo(() => new PlaneGeometry(2, 2), []);
  const hub = net.hub;
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uMotion: { value: reduce ? 0 : 1 },
    uBrightness: { value: NODE_BRIGHTNESS },
    uWarm: { value: new Color(clusterColors[2]) },
  }), [reduce]);
  const haloUniforms = useMemo(() => ({
    uTime: uniforms.uTime,
    uMotion: uniforms.uMotion,
  }), [uniforms]);
  const linkUniforms = useMemo(() => ({
    uColor: { value: new Color(linkAmber) },
    uTime: uniforms.uTime,
    uMotion: uniforms.uMotion,
  }), [uniforms]);
  const dustUniforms = useMemo(() => ({ uColor: { value: new Color(dustColor) } }), []);

  const spokes = useMemo(() => {
    const pos: number[] = [];
    const t: number[] = [];
    const pulse: number[] = [];
    const phase: number[] = [];
    const alpha: number[] = [];
    const opacity = { near: 0.14, hub: 0.22 };
    let sparkN = 0;
    for (const edge of net.edges) {
      pos.push(edge.a[0], edge.a[1], edge.a[2], edge.b[0], edge.b[1], edge.b[2]);
      t.push(0, 1);
      const fire = edge.kind === "hub";
      const offset = fire ? (sparkN * 0.17) % 1 : 0;
      if (fire) sparkN++;
      pulse.push(fire ? 1 : 0, fire ? 1 : 0);
      phase.push(offset, offset);
      alpha.push(opacity[edge.kind], opacity[edge.kind]);
    }
    const geo = new BufferGeometry();
    geo.setAttribute("position", new Float32BufferAttribute(pos, 3));
    geo.setAttribute("aT", new Float32BufferAttribute(t, 1));
    geo.setAttribute("aPulse", new Float32BufferAttribute(pulse, 1));
    geo.setAttribute("aPhase", new Float32BufferAttribute(phase, 1));
    geo.setAttribute("aAlpha", new Float32BufferAttribute(alpha, 1));
    return geo;
  }, [net.edges]);

  const dustGeo = useMemo(() => {
    const count = 720;
    const pos = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    let seed = 17;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };
    for (let i = 0; i < count; i++) {
      const r = 0.6 + Math.pow(rand(), 0.7) * 8.6;
      const a = rand() * Math.PI * 2;
      const y = (rand() - 0.5) * 3.4;
      pos[i * 3] = Math.cos(a) * r;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = Math.sin(a) * r;
      sizes[i] = 2.3 + rand() * 2.0;
    }
    const geo = new BufferGeometry();
    geo.setAttribute("position", new Float32BufferAttribute(pos, 3));
    geo.setAttribute("aSize", new Float32BufferAttribute(sizes, 1));
    return geo;
  }, []);

  useLayoutEffect(() => {
    const mesh = nodesRef.current;
    const halo = haloRef.current;
    if (!mesh || !halo) return;
    const dummy = new Matrix4();
    const color = new Color();
    const n = nodes.length;
    const phases = new Float32Array(n);
    const colors = new Float32Array(n * 3);
    const twinkle = new Float32Array(n);
    const emerging = new Float32Array(n);
    const glow = new Float32Array(n);
    const m = new Matrix4();
    nodes.forEach((node, i) => {
      const s = nodeRadius(node.support, maxS, node.role === "secondary");
      m.makeTranslation(node.pos[0], node.pos[1], node.pos[2]);
      dummy.makeScale(s, s, s);
      m.multiply(dummy);
      mesh.setMatrixAt(i, m);
      const haloScale = s * 2.5;
      const haloM = new Matrix4().makeTranslation(node.pos[0], node.pos[1], node.pos[2]);
      haloM.multiply(new Matrix4().makeScale(haloScale, haloScale, haloScale));
      halo.setMatrixAt(i, haloM);
      const hex = showGaps && node.gap ? gapColor : nodeAmber(node.colorIndex, node.clusterId, node.id);
      color.set(hex);
      colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b;
      phases[i] = phaseOf(node.id);
      twinkle[i] = node.fresh ? 1 : 0;
      emerging[i] = node.gap ? 0 : node.emerging;
      glow[i] = 0;
    });
    mesh.instanceMatrix.needsUpdate = true;
    halo.instanceMatrix.needsUpdate = true;
    mesh.count = n;
    halo.count = n;
    const put = (target: InstancedMesh, name: string, data: Float32Array, size: number) => {
      const attr = new InstancedBufferAttribute(data, size);
      target.geometry.setAttribute(name, attr);
      return attr;
    };
    put(mesh, "aPhase", phases, 1);
    put(mesh, "aColor", colors, 3);
    put(mesh, "aTwinkle", twinkle, 1);
    put(mesh, "aEmerging", emerging, 1);
    glowAttr.current = put(mesh, "aGlow", glow, 1);
    put(halo, "aPhase", phases.slice(), 1);
    put(halo, "aColor", colors.slice(), 3);
    haloGlowAttr.current = put(halo, "aGlow", glow.slice(), 1);
    mesh.frustumCulled = false;
    halo.frustumCulled = false;
  }, [nodes, showGaps, maxS]);

  useEffect(() => {
    const attrs = [glowAttr.current, haloGlowAttr.current];
    if (attrs.some((attr) => !attr)) return;
    const hoverId = hover == null ? null : nodes[hover]?.id;
    const near = hoverId ? neighborIds(hoverId, networkLinks(net.edges)) : new Set<string>();
    for (const attr of attrs) {
      const arr = attr!.array as Float32Array;
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        let g = 0;
        if (highlight?.has(n.id)) g = 0.62;
        if (near.has(n.id)) g = 0.55;
        if (n.id === hoverId || n.id === focus) g = 1;
        arr[i] = g;
      }
      attr!.needsUpdate = true;
    }
  }, [hover, focus, highlight, nodes, net.edges]);

  useFrame((_, dt) => {
    if (document.hidden) return;
    uniforms.uTime.value += Math.min(dt, 0.05);
    uniforms.uMotion.value = reduce ? 0 : 1;
    if (spin.current) spin.current.rotation.y = reduce ? 0 : uniforms.uTime.value * 0.16;
  });

  const look = useMemo(() => {
    const picked = highlight && highlight.size ? nodes.filter((n) => highlight.has(n.id)) : [];
    if (picked.length) {
      const c = picked.reduce((a, n) => [a[0] + n.center[0], a[1] + n.center[1], a[2] + n.center[2]] as [number, number, number], [0, 0, 0]);
      return [c[0] / picked.length, c[1] / picked.length, c[2] / picked.length] as [number, number, number];
    }
    const focused = nodes.find((n) => n.id === focus);
    return focused ? focused.pos : hub;
  }, [highlight, focus, nodes, hub]);

  return (
    <>
      <group ref={spin}>
        <points geometry={dustGeo} frustumCulled={false} raycast={() => null}>
          <shaderMaterial args={[{ uniforms: dustUniforms, vertexShader: DUST_VERT, fragmentShader: DUST_FRAG, transparent: true, depthWrite: false, toneMapped: false }]} />
        </points>
        <lineSegments geometry={spokes} frustumCulled={false} raycast={() => null}>
          <shaderMaterial args={[{ uniforms: linkUniforms, vertexShader: LINK_VERT, fragmentShader: LINK_FRAG, transparent: true, depthWrite: false, toneMapped: false }]} />
        </lineSegments>
        <instancedMesh
          ref={nodesRef}
          args={[sphere, undefined, Math.max(nodes.length, 1)]}
          frustumCulled={false}
          renderOrder={2}
          onPointerOver={(e) => { e.stopPropagation(); if (e.instanceId != null) setHover(e.instanceId); }}
          onPointerOut={() => setHover(null)}
          onClick={(e) => {
            e.stopPropagation();
            if (e.instanceId == null) return;
            const n = nodes[e.instanceId];
            onFocus?.(n.id);
            if (n.gap) onHighlight?.(n.cluster);
          }}
        >
          <shaderMaterial args={[{ uniforms, vertexShader: NODE_VERT, fragmentShader: NODE_FRAG, toneMapped: false }]} />
        </instancedMesh>
        <instancedMesh ref={haloRef} args={[haloPlane, undefined, Math.max(nodes.length, 1)]} renderOrder={3} frustumCulled={false} raycast={() => null}>
          <shaderMaterial args={[{ uniforms: haloUniforms, vertexShader: HALO_VERT, fragmentShader: HALO_FRAG, transparent: true, depthWrite: false, depthTest: true, side: DoubleSide, toneMapped: false }]} />
        </instancedMesh>
        {hover != null && nodes[hover] && (
          <Html position={nodes[hover].pos} center zIndexRange={[12, 0]} style={{ pointerEvents: "auto" }}>
            <div className="glass w-48 p-2.5 text-left text-xs" onPointerDown={(e) => e.stopPropagation()}>
              <div className="font-medium text-white">{nodes[hover].id}</div>
              <p className="mt-0.5 text-mist">Paper{nodes[hover].cluster ? ` · topic cluster ${nodes[hover].cluster}` : ""}</p>
              {showGaps && nodes[hover].gap && <p className="text-gap">Research gap</p>}
              <button className="btn mt-2 w-full py-1" onClick={() => onPick?.(nodes[hover].id)}>Search this paper</button>
            </div>
          </Html>
        )}
      </group>
      <CameraRig look={look} reduce={reduce} controls={controls} />
      <OrbitControls ref={controls} enablePan={false} enableZoom minDistance={20} maxDistance={52} />
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
