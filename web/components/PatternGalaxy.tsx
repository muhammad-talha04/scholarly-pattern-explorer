"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";

const N_TOPICS = 140;
const N_LINKS = 220;

/** Deterministic PRNG so server and client agree and the scene is stable. */
function rng(seed: number) {
  return () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
}

function useGalaxy() {
  return useMemo(() => {
    const r = rng(42);
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i < N_TOPICS; i++) {
      const arm = i % 3;
      const t = r() * 4;
      const a = t * 1.4 + (arm * 2 * Math.PI) / 3;
      pts.push(new THREE.Vector3(Math.cos(a) * t * 1.3, (r() - 0.5) * 0.8, Math.sin(a) * t * 1.3));
    }
    const seg: number[] = [];
    for (let i = 0; i < N_LINKS; i++) {
      const a = Math.floor(r() * N_TOPICS);
      const b = (a + 1 + Math.floor(r() * 6)) % N_TOPICS;
      seg.push(...pts[a].toArray(), ...pts[b].toArray());
    }
    const sizes = pts.map(() => 0.04 + r() * 0.12);
    return { pts, links: new Float32Array(seg), sizes };
  }, []);
}

function Galaxy() {
  const group = useRef<THREE.Group>(null);
  const { pts, links, sizes } = useGalaxy();
  const mesh = useRef<THREE.InstancedMesh>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (group.current) group.current.rotation.y = t * 0.06;
    if (!mesh.current) return;
    const m = new THREE.Matrix4();
    pts.forEach((p, i) => {
      const pulse = 1 + 0.35 * Math.sin(t * 1.5 + i);
      m.compose(p, new THREE.Quaternion(), new THREE.Vector3().setScalar(sizes[i] * pulse));
      mesh.current!.setMatrixAt(i, m);
    });
    mesh.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <group ref={group}>
      <instancedMesh ref={mesh} args={[undefined, undefined, N_TOPICS]}>
        <sphereGeometry args={[1, 16, 16]} />
        <meshStandardMaterial color="#7c5cff" emissive="#2de2e6" emissiveIntensity={0.9} />
      </instancedMesh>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[links, 3]} />
        </bufferGeometry>
        <lineBasicMaterial color="#2de2e6" transparent opacity={0.18} />
      </lineSegments>
    </group>
  );
}

export default function PatternGalaxy() {
  return (
    <Canvas camera={{ position: [0, 3.5, 9], fov: 55 }} dpr={[1, 2]}>
      <color attach="background" args={["#05060f"]} />
      <ambientLight intensity={0.4} />
      <pointLight position={[0, 4, 0]} intensity={30} color="#7c5cff" />
      <Stars radius={60} depth={40} count={2500} factor={3} fade speed={0.6} />
      <Galaxy />
      <OrbitControls enablePan={false} enableZoom={false} autoRotate autoRotateSpeed={0.3} />
    </Canvas>
  );
}
