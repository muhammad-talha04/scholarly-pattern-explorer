"use client";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, Line, OrbitControls, Stars } from "@react-three/drei";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef, useState } from "react";
import { Vector3, type Group } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { TopicLink, TopicNode } from "@/lib/graph";
import { linkPairs, positionNodes, type Positioned } from "./layout";

const PALETTE = ["#7dd3fc", "#c4b5fd", "#6ee7b7", "#fcd34d", "#fb923c", "#f9a8d4"];
function colorFor(n: Positioned, showGaps: boolean) {
  if (showGaps && n.gap) return "#f9a8d4";
  const key = n.cluster ?? n.id;
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h + key.charCodeAt(i) * 13) % PALETTE.length;
  return PALETTE[h];
}

function CameraRig({ focus, controls }: { focus: [number, number, number] | null; controls: React.RefObject<OrbitControlsImpl | null> }) {
  const { camera } = useThree();
  const anim = useRef({ t: 1, fromP: new Vector3(0, 4.2, 12), toP: new Vector3(0, 4.2, 12), fromT: new Vector3(), toT: new Vector3() });
  useEffect(() => {
    const a = anim.current;
    a.fromP.copy(camera.position);
    a.fromT.copy(controls.current?.target ?? new Vector3());
    if (focus) {
      a.toT.set(focus[0], focus[1], focus[2]);
      a.toP.set(focus[0] * 0.35 + 0.8, focus[1] + 2.2, focus[2] + 6.5);
    } else {
      a.toT.set(0, 0, 0);
      a.toP.set(0, 4.2, 12);
    }
    a.t = 0;
  }, [focus, camera, controls]);
  useFrame(() => {
    const a = anim.current;
    if (a.t >= 1) return;
    a.t = Math.min(1, a.t + 0.04);
    const e = 1 - (1 - a.t) ** 3;
    camera.position.lerpVectors(a.fromP, a.toP, e);
    if (controls.current) {
      controls.current.target.lerpVectors(a.fromT, a.toT, e);
      controls.current.update();
    }
  });
  return null;
}

function Scene({ nodes, links, showGaps, focus, onFocus, onPick }: Props) {
  const g = useRef<Group>(null);
  const controls = useRef<OrbitControlsImpl>(null);
  const [hover, setHover] = useState<string | null>(null);
  const placed = useMemo(() => nodes.some((n) => n.pos) ? nodes as Positioned[] : positionNodes(nodes), [nodes]);
  const pairs = useMemo(() => linkPairs(placed, links), [placed, links]);
  const maxS = Math.max(...nodes.map((n) => n.support), 0.01);
  const focusPos = placed.find((n) => n.id === focus)?.pos ?? null;
  useFrame((_, dt) => { if (g.current && !focus) g.current.rotation.y += dt * 0.04; });
  return (
    <>
      <group ref={g}>
        {pairs.map(({ a, b, w }, i) => (
          <Line key={i} points={[a.pos, b.pos]} color="#9bd7ff" lineWidth={0.6 + w * 5} transparent opacity={0.28} />
        ))}
        {placed.map((n) => {
          const s = 0.09 + 0.34 * Math.sqrt(n.support / maxS);
          const hot = hover === n.id || focus === n.id;
          const color = colorFor(n, showGaps);
          return (
            <group key={n.id} position={n.pos}>
              <mesh
                onPointerOver={(e) => { e.stopPropagation(); setHover(n.id); }}
                onPointerOut={() => setHover((h) => (h === n.id ? null : h))}
                onClick={(e) => { e.stopPropagation(); onFocus?.(n.id); }}
                scale={hot ? 1.28 : 1}
              >
                <sphereGeometry args={[s, 32, 32]} />
                <meshStandardMaterial color={color} emissive={color} emissiveIntensity={hot ? 2.6 : 1.7} toneMapped={false} />
              </mesh>
              {(showGaps && n.gap) && <mesh><sphereGeometry args={[s * 1.85, 24, 24]} /><meshBasicMaterial color="#f9a8d4" transparent opacity={0.14} /></mesh>}
              {hot && (
                <Html center position={[0, s + 0.45, 0]} zIndexRange={[30, 0]} style={{ pointerEvents: "auto" }}>
                  <div className="glass w-48 p-2.5 text-left text-xs shadow-glow" onPointerDown={(e) => e.stopPropagation()}>
                    <div className="font-medium text-white">{n.id}</div>
                    <p className="mt-0.5 text-mist">Support {n.support.toFixed(2)}{n.cluster ? ` · ${n.cluster}` : ""}</p>
                    {showGaps && n.gap && <p className="text-pink-200">Research gap{n.gapScore != null ? ` · ${n.gapScore.toFixed(2)}` : ""}</p>}
                    <button className="btn mt-2 w-full py-1" onClick={() => onPick?.(n.id)}>Search this topic</button>
                  </div>
                </Html>
              )}
            </group>
          );
        })}
      </group>
      <CameraRig focus={focusPos} controls={controls} />
      <OrbitControls ref={controls} enablePan={false} enableZoom minDistance={4} maxDistance={22} />
    </>
  );
}

interface Props { nodes: (TopicNode & { pos?: [number, number, number] })[]; links: TopicLink[]; showGaps: boolean; focus: string | null; onFocus?: (id: string) => void; onPick?: (id: string) => void }
export default function Galaxy3D(p: Props) {
  return (
    <Canvas camera={{ position: [0, 4.2, 12], fov: 52 }} dpr={[1, 1.7]} gl={{ antialias: true }}>
      <color attach="background" args={["#070814"]} />
      <ambientLight intensity={0.35} />
      <pointLight position={[0, 0, 0]} intensity={24} color="#7dd3fc" />
      <pointLight position={[8, 6, 4]} intensity={18} color="#c4b5fd" />
      <Stars radius={70} depth={40} count={2800} factor={3} fade speed={0.4} />
      <Scene {...p} />
      <EffectComposer multisampling={0}>
        <Bloom luminanceThreshold={0.18} mipmapBlur intensity={1.15} radius={0.65} />
      </EffectComposer>
    </Canvas>
  );
}
