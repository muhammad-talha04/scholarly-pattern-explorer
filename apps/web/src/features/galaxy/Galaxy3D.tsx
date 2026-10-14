"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, Line, OrbitControls, Stars } from "@react-three/drei";
import { useMemo, useRef, useState } from "react";
import type { Group } from "three";
import type { TopicLink, TopicNode } from "@/lib/graph";
import { linkPairs, positionNodes } from "./layout";

function Scene({ nodes, links, showGaps, onPick }: Props) {
  const g = useRef<Group>(null);
  const [hover, setHover] = useState<string | null>(null);
  const placed = useMemo(() => positionNodes(nodes), [nodes]);
  const pairs = useMemo(() => linkPairs(placed, links), [placed, links]);
  const maxS = Math.max(...nodes.map((n) => n.support), 0.01);
  useFrame((_, dt) => { if (g.current) g.current.rotation.y += dt * 0.05; });
  return (
    <group ref={g}>
      {pairs.map(({ a, b, w }, i) => (
        <Line key={i} points={[a.pos, b.pos]} color="#7dd3fc" lineWidth={0.5 + w * 6} transparent opacity={0.25} />
      ))}
      {placed.map((n) => {
        const s = 0.08 + 0.32 * Math.sqrt(n.support / maxS), isGap = showGaps && n.gap;
        const color = isGap ? "#f472b6" : "#a78bfa";
        return (
          <group key={n.id} position={n.pos}>
            <mesh onPointerOver={(e) => { e.stopPropagation(); setHover(n.id); }} onPointerOut={() => setHover(null)} onClick={() => onPick?.(n.id)} scale={hover === n.id ? 1.3 : 1}>
              <sphereGeometry args={[s, 32, 32]} />
              <meshStandardMaterial color={color} emissive={color} emissiveIntensity={isGap ? 2.4 : 1.4} toneMapped={false} />
            </mesh>
            {isGap && <mesh><sphereGeometry args={[s * 1.9, 24, 24]} /><meshBasicMaterial color="#f472b6" transparent opacity={0.12} /></mesh>}
            {(hover === n.id || isGap || n.support / maxS > 0.6) && (
              <Html center distanceFactor={12} position={[0, s + 0.35, 0]} style={{ pointerEvents: "none" }}>
                <div className={`whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] ${isGap ? "bg-pink-500/20 text-pink-200" : "bg-black/50 text-slate-200"}`}>{n.id}{isGap ? " · gap" : ""}</div>
              </Html>
            )}
          </group>
        );
      })}
    </group>
  );
}

interface Props { nodes: TopicNode[]; links: TopicLink[]; showGaps: boolean; onPick?: (id: string) => void }
export default function Galaxy3D(p: Props) {
  return (
    <Canvas camera={{ position: [0, 5, 11], fov: 55 }} dpr={[1, 2]} gl={{ antialias: true }}>
      <color attach="background" args={["#05060f"]} />
      <ambientLight intensity={0.3} />
      <pointLight position={[0, 0, 0]} intensity={30} color="#7dd3fc" />
      <Stars radius={60} depth={40} count={2500} factor={3} fade speed={0.6} />
      <Scene {...p} />
      <OrbitControls enablePan={false} enableZoom minDistance={5} maxDistance={20} autoRotate={false} />
    </Canvas>
  );
}
