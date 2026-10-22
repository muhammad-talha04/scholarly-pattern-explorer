"use client";
import { MotionConfig } from "framer-motion";
import { createContext, useContext, useEffect, useState } from "react";

interface MotionPrefs { lowPower: boolean; setLowPower: (v: boolean) => void }
const Ctx = createContext<MotionPrefs>({ lowPower: false, setLowPower: () => {} });
export const useMotionPrefs = () => useContext(Ctx);

/** Detects prefers-reduced-motion, missing WebGL, or a saved low-power choice. The galaxy stays 3D and holds still; the globe uses its flat map. */
export function detectLowPower(): boolean {
  if (typeof window === "undefined") return false;
  if (localStorage.getItem("spe-low-power") === "1") return true;
  if (localStorage.getItem("spe-low-power") === "0") return false;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return true;
  try { const c = document.createElement("canvas"); return !(c.getContext("webgl2") || c.getContext("webgl")); } catch { return true; }
}

export function MotionProvider({ children }: { children: React.ReactNode }) {
  const [lowPower, setLP] = useState(false);
  useEffect(() => setLP(detectLowPower()), []);
  const setLowPower = (v: boolean) => { localStorage.setItem("spe-low-power", v ? "1" : "0"); setLP(v); };
  return (
    <Ctx.Provider value={{ lowPower, setLowPower }}>
      <MotionConfig reducedMotion={lowPower ? "always" : "user"}>{children}</MotionConfig>
    </Ctx.Provider>
  );
}
