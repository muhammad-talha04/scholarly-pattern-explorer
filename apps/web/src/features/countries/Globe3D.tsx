"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, OrbitControls, QuadraticBezierLine, Stars } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import { BufferGeometry, Float32BufferAttribute, Vector3, type Group } from "three";
import type { Collaboration, CountryStats } from "@/lib/api/types";
import { CENTROIDS, latLngToVec } from "@/lib/geo";
import { borderPositions } from "@/lib/world";
import { chartColor, panel } from "@/lib/theme";

const R = 2;

function Outlines() {
  const geo = useMemo(() => {
    const g = new BufferGeometry();
    g.setAttribute("position", new Float32BufferAttribute(borderPositions(R * 1.012), 3));
    return g;
  }, []);
  return (
    <lineSegments geometry={geo}>
      <lineBasicMaterial color={chartColor(4)} transparent opacity={0.75} />
    </lineSegments>
  );
}

function Globe({ countries, collabs, selected, onSelect }: Props) {
  const g = useRef<Group>(null);
  const [hover, setHover] = useState<string | null>(null);
  useFrame((_, dt) => {
    if (!g.current || selected || document.hidden) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    g.current.rotation.y += dt * 0.05;
  });
  const max = Math.max(...countries.map((c) => c.papers), 1);
  const maxC = Math.max(...collabs.map((c) => c.papers), 1);
  const arcs = useMemo(() => collabs.flatMap((c) => {
    const a = CENTROIDS[c.source], b = CENTROIDS[c.target]; if (!a || !b) return [];
    const va = new Vector3(...latLngToVec(a[0], a[1], R + 0.02)), vb = new Vector3(...latLngToVec(b[0], b[1], R + 0.02));
    const mid = va.clone().add(vb).multiplyScalar(0.5).normalize().multiplyScalar(R + va.distanceTo(vb) * 0.45);
    return [{ ...c, va, vb, mid }];
  }), [collabs]);
  const tip = countries.find((c) => c.code === hover);
  const tipLl = tip ? CENTROIDS[tip.code] : null;
  return (
    <group ref={g}>
      <mesh>
        <sphereGeometry args={[R, 64, 64]} />
        <meshStandardMaterial color={panel} roughness={0.85} metalness={0.05} />
      </mesh>
      <mesh>
        <sphereGeometry args={[R * 1.08, 48, 48]} />
        <meshBasicMaterial color={chartColor(1)} transparent opacity={0.05} />
      </mesh>
      <Outlines />
      {countries.map((c) => {
        const ll = CENTROIDS[c.code]; if (!ll) return null;
        const h = 0.05 + 1.1 * Math.sqrt(c.papers / max);
        const pos = new Vector3(...latLngToVec(ll[0], ll[1], R + h / 2));
        const sel = selected === c.code;
        return (
          <mesh key={c.code} position={pos} onUpdate={(m) => m.lookAt(0, 0, 0)}
            onPointerOver={(e) => { e.stopPropagation(); setHover(c.code); }}
            onPointerOut={() => setHover((hvr) => (hvr === c.code ? null : hvr))}
            onClick={(e) => { e.stopPropagation(); onSelect(c.code); }}>
            <boxGeometry args={[0.055, 0.055, h]} />
            <meshStandardMaterial color={sel ? chartColor(0) : chartColor(1)} roughness={0.55} metalness={0.05} />
          </mesh>
        );
      })}
      {tip && tipLl && (
        <Html position={new Vector3(...latLngToVec(tipLl[0], tipLl[1], R + 0.55))} center zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
          <div className="glass whitespace-nowrap px-2 py-1 text-[11px] text-white">{tip.name} · {tip.papers.toLocaleString(undefined, { maximumFractionDigits: 1 })}</div>
        </Html>
      )}
      {arcs.map((a, i) => (
        <QuadraticBezierLine key={i} start={a.va} end={a.vb} mid={a.mid} color={selected && (a.source === selected || a.target === selected) ? chartColor(5) : chartColor(2)}
          lineWidth={0.6 + 2.4 * (a.papers / maxC)} transparent opacity={selected && a.source !== selected && a.target !== selected ? 0.1 : 0.75} />
      ))}
    </group>
  );
}
interface Props { countries: CountryStats[]; collabs: Collaboration[]; selected: string | null; onSelect: (c: string) => void }
export default function Globe3D(p: Props) {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    const apply = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", apply);
    return () => document.removeEventListener("visibilitychange", apply);
  }, []);
  return (
    <Canvas frameloop={hidden ? "never" : "always"} camera={{ position: [0, 1.4, 6.2], fov: 45 }} dpr={[1, 1.5]}>
      <ambientLight intensity={0.55} />
      <pointLight position={[6, 4, 6]} intensity={28} />
      <Stars radius={50} count={1200} factor={2} fade />
      <Globe {...p} />
      <OrbitControls enablePan={false} minDistance={3.4} maxDistance={10} />
    </Canvas>
  );
}
