"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, QuadraticBezierLine, Stars } from "@react-three/drei";
import { useMemo, useRef } from "react";
import { Vector3, type Group } from "three";
import type { Collaboration, CountryStats } from "@/lib/api/types";
import { CENTROIDS, latLngToVec } from "@/lib/geo";

const R = 2;
function Globe({ countries, collabs, selected, onSelect }: Props) {
  const g = useRef<Group>(null);
  useFrame((_, dt) => { if (g.current && !selected) g.current.rotation.y += dt * 0.06; });
  const max = Math.max(...countries.map((c) => c.papers), 1);
  const maxC = Math.max(...collabs.map((c) => c.papers), 1);
  const arcs = useMemo(() => collabs.flatMap((c) => {
    const a = CENTROIDS[c.source], b = CENTROIDS[c.target]; if (!a || !b) return [];
    const va = new Vector3(...latLngToVec(a[0], a[1], R)), vb = new Vector3(...latLngToVec(b[0], b[1], R));
    const mid = va.clone().add(vb).multiplyScalar(0.5).normalize().multiplyScalar(R + va.distanceTo(vb) * 0.45);
    return [{ ...c, va, vb, mid }];
  }), [collabs]);
  return (
    <group ref={g}>
      <mesh><sphereGeometry args={[R, 64, 64]} /><meshStandardMaterial color="#0b1230" emissive="#0b1a40" roughness={0.9} /></mesh>
      <mesh><sphereGeometry args={[R * 1.002, 36, 18]} /><meshBasicMaterial color="#7dd3fc" wireframe transparent opacity={0.07} /></mesh>
      <mesh><sphereGeometry args={[R * 1.12, 48, 48]} /><meshBasicMaterial color="#38bdf8" transparent opacity={0.05} /></mesh>
      {countries.map((c) => {
        const ll = CENTROIDS[c.code]; if (!ll) return null;
        const h = 0.05 + 1.1 * (c.papers / max), pos = new Vector3(...latLngToVec(ll[0], ll[1], R + h / 2));
        const sel = selected === c.code;
        return (
          <mesh key={c.code} position={pos} onUpdate={(m) => m.lookAt(0, 0, 0)} onClick={(e) => { e.stopPropagation(); onSelect(c.code); }}>
            <boxGeometry args={[0.06, 0.06, h]} />
            <meshStandardMaterial color={sel ? "#f472b6" : "#7dd3fc"} emissive={sel ? "#f472b6" : "#38bdf8"} emissiveIntensity={1.6} toneMapped={false} />
          </mesh>
        );
      })}
      {arcs.map((a, i) => (
        <QuadraticBezierLine key={i} start={a.va} end={a.vb} mid={a.mid} color={selected && (a.source === selected || a.target === selected) ? "#f472b6" : "#a78bfa"}
          lineWidth={0.6 + 2.5 * (a.papers / maxC)} transparent opacity={selected && a.source !== selected && a.target !== selected ? 0.12 : 0.7} />
      ))}
    </group>
  );
}
interface Props { countries: CountryStats[]; collabs: Collaboration[]; selected: string | null; onSelect: (c: string) => void }
export default function Globe3D(p: Props) {
  return (
    <Canvas camera={{ position: [0, 1.5, 6], fov: 45 }} dpr={[1, 2]}>
      <ambientLight intensity={0.5} /><pointLight position={[6, 4, 6]} intensity={60} />
      <Stars radius={50} count={1500} factor={2} fade />
      <Globe {...p} />
      <OrbitControls enablePan={false} minDistance={3.5} maxDistance={10} />
    </Canvas>
  );
}
