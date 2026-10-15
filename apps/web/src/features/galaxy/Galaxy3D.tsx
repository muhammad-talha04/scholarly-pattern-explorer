"use client";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls, Stars } from "@react-three/drei";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  CircleGeometry, Color, InstancedBufferAttribute, InstancedMesh, Matrix4, NoToneMapping,
  SphereGeometry, Vector3,
} from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { TopicLink } from "@/lib/graph";
import { NODE_BRIGHTNESS, clusterColors, gap as gapColor, galaxyColor, ink, linkGrey } from "@/lib/theme";
import { neighborIds, type Star } from "./stars";

const NODE_VERT = `
attribute vec3 aCenter;
attribute float aPhase;
attribute vec3 aColor;
attribute float aGlow;
attribute float aTwinkle;
attribute float aEmerging;
varying vec3 vColor;
varying vec3 vNormalV;
varying float vGlow;
varying float vTwinkle;
varying float vEmerging;
uniform float uTime;
uniform float uMotion;
void main() {
  vec3 rest = (instanceMatrix * vec4(position, 1.0)).xyz;
  vec3 arm = rest - aCenter;
  float ang = uMotion * uTime * 0.15;
  float c = cos(ang);
  float s = sin(ang);
  vec3 spun = vec3(arm.x * c - arm.z * s, arm.y, arm.x * s + arm.z * c);
  spun.y += uMotion * sin(uTime * 0.35 + aPhase) * 0.045;
  vec4 viewPos = viewMatrix * vec4(aCenter + spun, 1.0);
  gl_Position = projectionMatrix * viewPos;
  vNormalV = normalize(mat3(viewMatrix) * mat3(instanceMatrix) * normal);
  vColor = aColor;
  vGlow = aGlow;
  vTwinkle = aTwinkle;
  vEmerging = aEmerging;
}
`;

const NODE_FRAG = `
precision highp float;
varying vec3 vColor;
varying vec3 vNormalV;
varying float vGlow;
varying float vTwinkle;
varying float vEmerging;
uniform float uTime;
uniform float uMotion;
uniform float uBrightness;
uniform vec3 uWarm;
void main() {
  float base = mix(uBrightness, 1.0, clamp(vGlow, 0.0, 1.0));
  float tw = uMotion * vTwinkle * exp(-uTime * 1.55) * (0.55 + 0.45 * sin(uTime * 16.0));
  float bright = min(1.0, base + tw * 0.16 + vEmerging * 0.08);
  vec3 srgb = pow(max(vColor, vec3(0.0)), vec3(0.454545));
  vec3 warm = pow(max(uWarm, vec3(0.0)), vec3(0.454545));
  vec3 mixed = mix(srgb, warm, clamp(vEmerging, 0.0, 1.0) * 0.4);
  float rim = pow(1.0 - abs(dot(normalize(vNormalV), vec3(0.0, 0.0, 1.0))), 3.0);
  vec3 outS = min(vec3(1.0), mixed * bright + rim * 0.045);
  gl_FragColor = vec4(pow(outS, vec3(2.2)), 1.0);
  #include <colorspace_fragment>
}
`;

const SHADOW_VERT = `
attribute vec3 aCenter;
attribute float aPhase;
varying vec2 vUv;
uniform float uTime;
uniform float uMotion;
void main() {
  vUv = uv;
  vec3 rest = (instanceMatrix * vec4(position, 1.0)).xyz;
  vec3 arm = rest - aCenter;
  float ang = uMotion * uTime * 0.15;
  float c = cos(ang);
  float s = sin(ang);
  vec3 spun = vec3(arm.x * c - arm.z * s, arm.y, arm.x * s + arm.z * c);
  spun.y += uMotion * sin(uTime * 0.35 + aPhase) * 0.045;
  vec3 pos = aCenter + spun + vec3(0.04, -0.1, 0.02);
  gl_Position = projectionMatrix * viewMatrix * vec4(pos, 1.0);
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

const LINK_VERT = `
attribute vec3 aCenter;
attribute float aPhase;
uniform float uTime;
uniform float uMotion;
void main() {
  vec3 arm = position - aCenter;
  float ang = uMotion * uTime * 0.15;
  float c = cos(ang);
  float s = sin(ang);
  vec3 spun = vec3(arm.x * c - arm.z * s, arm.y, arm.x * s + arm.z * c);
  spun.y += uMotion * sin(uTime * 0.35 + aPhase) * 0.045;
  gl_Position = projectionMatrix * viewMatrix * vec4(aCenter + spun, 1.0);
}
`;

const LINK_FRAG = `
precision highp float;
uniform vec3 uColor;
void main() {
  gl_FragColor = vec4(uColor, 0.2);
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
  const intro = useRef(reduce ? 1 : 0);
  const from = useRef(new Vector3(0, 5.8, 16));
  const to = useRef(new Vector3());
  const lookV = useRef(new Vector3());
  useEffect(() => {
    lookV.current.set(look[0], look[1], look[2]);
    to.current.set(look[0] * 0.25 + 0.4, look[1] + 2.4, look[2] + 7.2);
    if (reduce) {
      camera.position.copy(to.current);
      if (controls.current) { controls.current.target.copy(lookV.current); controls.current.update(); }
    }
  }, [look, reduce, camera, controls]);
  useFrame((_, dt) => {
    if (reduce || document.hidden) return;
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

function Field({ nodes, links, showGaps, focus, highlight, reduce, onFocus, onHighlight, onPick }: Props & { reduce: boolean }) {
  const controls = useRef<OrbitControlsImpl>(null);
  const nodesRef = useRef<InstancedMesh>(null);
  const shadowRef = useRef<InstancedMesh>(null);
  const glowAttr = useRef<InstancedBufferAttribute | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const maxS = Math.max(...nodes.map((n) => n.support), 0.01);
  const sphere = useMemo(() => new SphereGeometry(1, 28, 20), []);
  const disc = useMemo(() => { const g = new CircleGeometry(0.55, 24); g.rotateX(-Math.PI / 2); return g; }, []);
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uMotion: { value: reduce ? 0 : 1 },
    uBrightness: { value: NODE_BRIGHTNESS },
    uWarm: { value: new Color(clusterColors[2]) },
  }), [reduce]);
  const linkUniforms = useMemo(() => ({
    uTime: uniforms.uTime,
    uMotion: uniforms.uMotion,
    uColor: { value: new Color(linkGrey) },
  }), [uniforms]);
  const shadowUniforms = useMemo(() => ({ uTime: uniforms.uTime, uMotion: uniforms.uMotion }), [uniforms]);

  const linkGeo = useMemo(() => {
    const by = new Map(nodes.map((n) => [n.id, n]));
    const pos: number[] = [];
    const center: number[] = [];
    const phase: number[] = [];
    for (const link of links) {
      const a = by.get(link.source), b = by.get(link.target);
      if (!a?.pos || !b?.pos) continue;
      for (const n of [a, b]) {
        pos.push(n.pos[0], n.pos[1], n.pos[2]);
        center.push(n.center[0], n.center[1], n.center[2]);
        phase.push(phaseOf(n.clusterId));
      }
    }
    return { pos: new Float32Array(pos), center: new Float32Array(center), phase: new Float32Array(phase), count: pos.length / 3 };
  }, [nodes, links]);

  useLayoutEffect(() => {
    const mesh = nodesRef.current;
    const shadow = shadowRef.current;
    if (!mesh || !shadow) return;
    const dummy = new Matrix4();
    const color = new Color();
    const n = nodes.length;
    const centers = new Float32Array(n * 3);
    const phases = new Float32Array(n);
    const colors = new Float32Array(n * 3);
    const twinkle = new Float32Array(n);
    const emerging = new Float32Array(n);
    const glow = new Float32Array(n);
    const m = new Matrix4();
    nodes.forEach((node, i) => {
      const s = 0.09 + 0.32 * Math.sqrt(node.support / maxS);
      m.makeTranslation(node.pos[0], node.pos[1], node.pos[2]);
      dummy.makeScale(s, s, s);
      m.multiply(dummy);
      mesh.setMatrixAt(i, m);
      const shadowM = new Matrix4().makeTranslation(node.pos[0], node.pos[1], node.pos[2]);
      shadowM.multiply(new Matrix4().makeScale(s, s, s));
      shadow.setMatrixAt(i, shadowM);
      const hex = showGaps && node.gap ? gapColor : galaxyColor(node.colorIndex, node.clusterId);
      color.set(hex);
      colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b;
      centers[i * 3] = node.center[0]; centers[i * 3 + 1] = node.center[1]; centers[i * 3 + 2] = node.center[2];
      phases[i] = phaseOf(node.clusterId);
      twinkle[i] = node.fresh ? 1 : 0;
      emerging[i] = node.gap ? 0 : node.emerging;
      glow[i] = 0;
    });
    mesh.instanceMatrix.needsUpdate = true;
    shadow.instanceMatrix.needsUpdate = true;
    const put = (target: InstancedMesh, name: string, data: Float32Array, size: number) => {
      const attr = new InstancedBufferAttribute(data, size);
      target.geometry.setAttribute(name, attr);
      return attr;
    };
    put(mesh, "aCenter", centers, 3);
    put(mesh, "aPhase", phases, 1);
    put(mesh, "aColor", colors, 3);
    put(mesh, "aTwinkle", twinkle, 1);
    put(mesh, "aEmerging", emerging, 1);
    glowAttr.current = put(mesh, "aGlow", glow, 1);
    put(shadow, "aCenter", centers, 3);
    put(shadow, "aPhase", phases, 1);
    mesh.frustumCulled = false;
    shadow.frustumCulled = false;
  }, [nodes, showGaps, maxS]);

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
    uniforms.uTime.value += Math.min(dt, 0.05);
    uniforms.uMotion.value = reduce ? 0 : 1;
  });

  const look = useMemo(() => {
    const picked = highlight && highlight.size ? nodes.filter((n) => highlight.has(n.id)) : [];
    if (picked.length) {
      const c = picked.reduce((a, n) => [a[0] + n.center[0], a[1] + n.center[1], a[2] + n.center[2]] as [number, number, number], [0, 0, 0]);
      return [c[0] / picked.length, c[1] / picked.length, c[2] / picked.length] as [number, number, number];
    }
    const focused = nodes.find((n) => n.id === focus);
    return focused ? focused.pos : [0, 0, 0] as [number, number, number];
  }, [highlight, focus, nodes]);

  return (
    <>
      <instancedMesh
        ref={shadowRef}
        args={[disc, undefined, nodes.length]}
        renderOrder={0}
        frustumCulled={false}
      >
        <shaderMaterial args={[{ uniforms: shadowUniforms, vertexShader: SHADOW_VERT, fragmentShader: SHADOW_FRAG, transparent: true, depthWrite: false, toneMapped: false }]} />
      </instancedMesh>
      <instancedMesh
        ref={nodesRef}
        args={[sphere, undefined, nodes.length]}
        frustumCulled={false}
        renderOrder={1}
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
      {linkGeo.count > 0 && (
        <lineSegments frustumCulled={false}>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[linkGeo.pos, 3]} />
            <bufferAttribute attach="attributes-aCenter" args={[linkGeo.center, 3]} />
            <bufferAttribute attach="attributes-aPhase" args={[linkGeo.phase, 1]} />
          </bufferGeometry>
          <shaderMaterial args={[{ uniforms: linkUniforms, vertexShader: LINK_VERT, fragmentShader: LINK_FRAG, transparent: true, depthWrite: false, toneMapped: false }]} />
        </lineSegments>
      )}
      <CameraRig look={look} reduce={reduce} controls={controls} />
      <OrbitControls ref={controls} enablePan={false} enableZoom minDistance={4} maxDistance={22} />
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
      camera={{ position: [0, 4.2, 12], fov: 52 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, toneMapping: NoToneMapping }}
    >
      <color attach="background" args={[ink]} />
      <Stars radius={70} depth={40} count={1600} factor={2} fade speed={reduce ? 0 : 0.25} />
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
