"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { useMotionPrefs } from "./MotionProvider";
import { SourceBadge } from "./SourceBadge";

const LINKS = [["/", "Galaxy"], ["/search", "Search"], ["/countries", "Countries"], ["/timeline", "Progress"], ["/patterns", "Patterns"]] as const;

export function Nav() {
  const path = usePathname();
  const { lowPower, setLowPower } = useMotionPrefs();
  return (
    <header className="fixed inset-x-0 top-0 z-40 border-b border-white/5 bg-ink/60 backdrop-blur-xl">
      <nav className="mx-auto flex max-w-7xl items-center gap-1 px-4 py-3">
        <Link href="/" className="mr-4 font-semibold tracking-tight"><span className="text-accent">◎</span> Scholarly Patterns</Link>
        {LINKS.map(([href, label]) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link key={href} href={href} className="relative rounded-lg px-3 py-1.5 text-sm text-slate-300 hover:text-white">
              {active && <motion.span layoutId="nav-pill" className="absolute inset-0 rounded-lg bg-white/10" transition={{ type: "spring", bounce: 0.2, duration: 0.5 }} />}
              <span className="relative">{label}</span>
            </Link>
          );
        })}
        <div className="ml-auto flex items-center gap-3">
          <SourceBadge />
          <button className="chip hover:text-white" onClick={() => setLowPower(!lowPower)} aria-pressed={lowPower} title="Toggle 2D low-power mode">
            {lowPower ? "2D mode" : "3D mode"}
          </button>
        </div>
      </nav>
    </header>
  );
}
