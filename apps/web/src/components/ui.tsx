"use client";
import { motion } from "framer-motion";

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="font-display text-3xl font-medium tracking-tight text-white sm:text-4xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-mist">{subtitle}</p>}
      </div>
      {children}
    </motion.div>
  );
}
export function Spinner() {
  return <div role="status" aria-label="loading" className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-accent" />;
}
export function ErrorNote({ msg, onRetry }: { msg: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="glass border-down/40 p-4 text-sm text-down">
      <p className="font-medium">Something went wrong</p>
      <p className="mt-1 text-down/80">{msg}</p>
      {onRetry && <button className="btn mt-3" onClick={onRetry}>Try again</button>}
    </div>
  );
}
export function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="glass flex flex-col items-center px-6 py-12 text-center">
      <StarMark />
      <h2 className="mt-4 font-display text-2xl text-white">{title}</h2>
      <p className="mt-2 max-w-md text-sm text-mist">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
export function StarMark() {
  return (
    <div aria-hidden className="relative h-16 w-16">
      <span className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent shadow-glow" />
      <span className="absolute left-2 top-3 h-1.5 w-1.5 rounded-full bg-glow" />
      <span className="absolute bottom-3 right-2 h-1 w-1 rounded-full bg-gap" />
      <span className="absolute right-4 top-5 h-1 w-1 rounded-full bg-white" />
      <span className="absolute inset-0 rounded-full border border-white/15" />
      <span className="absolute inset-2 rounded-full border border-accent/30" />
    </div>
  );
}
export function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="glass px-4 py-3"><div className="text-xs uppercase tracking-wide text-mist">{label}</div><div className="mt-1 text-xl font-semibold text-white">{value}</div></div>;
}
export function LoadingBlock({ label }: { label: string }) {
  return (
    <div role="status" className="glass flex h-64 flex-col items-center justify-center gap-3 text-sm text-mist">
      <Spinner />
      {label}
    </div>
  );
}
