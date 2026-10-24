"use client";
import { useEffect, useState } from "react";

const DONE = "spe-tour-done";
const listeners = new Set<() => void>();
export function replayTour() {
  localStorage.removeItem(DONE);
  listeners.forEach((l) => l());
}
const STEPS = [
  { title: "Welcome aboard", body: "Each dot in the galaxy is a paper. Colors and groups are topic clusters, so papers sit together by theme. This takes about a minute.", selector: "" },
  { title: "Five rooms, one sky", body: "Galaxy, Search, Countries, Progress and Patterns are always in the menu. Saved keeps collections on this device.", selector: "[data-tour=nav]" },
  { title: "Search papers", body: "Search by meaning. Open a result for the summary, a chat about that paper, and a map of related work.", selector: "[data-tour=search]" },
  { title: "A flatter sky", body: "3D mode draws the paper galaxy and the globe. 2D mode is the same papers, grouped by theme, as a flat picture. It turns on by itself if you prefer less motion.", selector: "[data-tour=power]" },
  { title: "Keep what you find", body: "Save a paper into a collection, or pin two papers and open Compare. Both stay in this browser. Nothing is sent to a server.", selector: "[data-tour=saved]" },
];

export function Tour() {
  const [step, setStep] = useState(0);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!localStorage.getItem(DONE)) setShown(true);
    const open = () => { setStep(0); setShown(true); };
    listeners.add(open);
    return () => { listeners.delete(open); };
  }, []);
  useEffect(() => {
    if (!shown) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
      if (e.key === "ArrowRight") setStep((s) => Math.min(STEPS.length - 1, s + 1));
      if (e.key === "ArrowLeft") setStep((s) => Math.max(0, s - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // finish closes over setState only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shown]);
  function finish() {
    localStorage.setItem(DONE, "1");
    setShown(false);
    setStep(0);
  }
  if (!shown) return null;
  const cur = STEPS[step];
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-3 sm:items-center" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      <button className="absolute inset-0 bg-black/55" aria-label="Close tour" onClick={finish} />
      <div className="glass relative z-10 w-full max-w-md p-5">
        <p className="text-xs uppercase tracking-widest text-accent">Tour {step + 1} / {STEPS.length}</p>
        <h2 id="tour-title" className="mt-1 font-display text-2xl text-white">{cur.title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-mist">{cur.body}</p>
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <button className="btn" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>Back</button>
          {step < STEPS.length - 1
            ? <button className="btn bg-accent/20" onClick={() => setStep((s) => s + 1)}>Next</button>
            : <button className="btn bg-accent/20" onClick={finish}>Done</button>}
          <button className="ml-auto text-sm text-mist underline-offset-2 hover:text-white hover:underline" onClick={finish}>Skip</button>
        </div>
      </div>
    </div>
  );
}

