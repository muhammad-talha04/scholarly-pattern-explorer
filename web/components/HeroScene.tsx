"use client";

import dynamic from "next/dynamic";

// WebGL must only run in the browser.
const PatternGalaxy = dynamic(() => import("./PatternGalaxy"), { ssr: false });

export default function HeroScene() {
  return <PatternGalaxy />;
}
