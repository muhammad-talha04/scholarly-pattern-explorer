"use client";
import { motion } from "framer-motion";
export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="bg-gradient-to-r from-white via-sky-200 to-violet-300 bg-clip-text text-3xl font-semibold tracking-tight text-transparent">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
      </div>
      {children}
    </motion.div>
  );
}
export function Spinner() { return <div role="status" aria-label="loading" className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-accent" />; }
export function ErrorNote({ msg }: { msg: string }) { return <p className="glass p-4 text-sm text-rose-300">Something went wrong: {msg}</p>; }
export function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="glass px-4 py-3"><div className="text-xs uppercase tracking-wide text-slate-400">{label}</div><div className="mt-1 text-xl font-semibold">{value}</div></div>;
}
