"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { motion } from "framer-motion";
import { useMotionPrefs } from "./MotionProvider";
import { SourceBadge } from "./SourceBadge";
import { replayTour } from "./Tour";

const LINKS = [
  ["/", "Galaxy"],
  ["/search", "Search"],
  ["/countries", "Countries"],
  ["/timeline", "Progress"],
  ["/patterns", "Patterns"],
  ["/collections", "Saved"],
] as const;

export function Nav() {
  const path = usePathname();
  const { lowPower, setLowPower } = useMotionPrefs();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <header className="fixed inset-x-0 top-0 z-40 border-b border-white/10 bg-ink/80 backdrop-blur-xl">
      <a href="#content" className="skip-link">Skip to content</a>
      <nav aria-label="Primary" data-tour="nav" className="mx-auto flex max-w-7xl items-center gap-2 px-3 py-2.5 sm:px-4">
        <Link href="/" className="shrink-0 font-display text-lg tracking-tight text-white" onClick={close}>
          <span className="text-accent">◎</span> <span className="hidden min-[420px]:inline">Scholarly Patterns</span>
        </Link>
        <div className="ml-2 hidden items-center gap-0.5 lg:flex">
          {LINKS.map(([href, label]) => {
            const active = href === "/" ? path === "/" : path.startsWith(href);
            return (
              <Link key={href} href={href} data-tour={href === "/collections" ? "saved" : undefined} aria-current={active ? "page" : undefined}
                className="relative rounded-lg px-2.5 py-1.5 text-sm text-mist hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
                {active && <motion.span layoutId="nav-pill" className="absolute inset-0 rounded-lg bg-white/10" transition={{ type: "spring", bounce: 0.18, duration: 0.45 }} />}
                <span className="relative">{label}</span>
              </Link>
            );
          })}
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <SourceBadge />
          <button data-tour="power" className="chip hidden hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent sm:inline-flex" onClick={() => setLowPower(!lowPower)} aria-pressed={lowPower} title="Toggle the flat drawing used for reduced motion and low power">
            {lowPower ? "2D mode" : "3D mode"}
          </button>
          <button className="chip hidden hover:text-white lg:inline-flex" onClick={() => replayTour()}>Tour</button>
          <button className="btn shrink-0 px-3 py-1.5 lg:hidden" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen((v) => !v)}>
            {open ? "Close" : "Menu"}
          </button>
        </div>
      </nav>
      {open && (
        <div id="mobile-nav" className="space-y-1 border-t border-white/10 px-3 py-3 lg:hidden">
          {LINKS.map(([href, label]) => {
            const active = href === "/" ? path === "/" : path.startsWith(href);
            return (
              <Link key={href} href={href} onClick={close} aria-current={active ? "page" : undefined}
                className={`block rounded-xl px-3 py-2.5 text-sm ${active ? "bg-white/10 text-white" : "text-mist hover:bg-white/5 hover:text-white"}`}>
                {label}
              </Link>
            );
          })}
          <div className="flex flex-wrap gap-2 pt-2">
            <button className="chip hover:text-white sm:hidden" onClick={() => setLowPower(!lowPower)} aria-pressed={lowPower}>{lowPower ? "2D mode" : "3D mode"}</button>
            <button className="chip hover:text-white" onClick={() => { close(); replayTour(); }}>Replay tour</button>
          </div>
        </div>
      )}
    </header>
  );
}
