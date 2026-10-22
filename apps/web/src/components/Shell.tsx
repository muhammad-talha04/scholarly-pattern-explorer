"use client";
import { Nav } from "./Nav";
import Link from "next/link";
import { Tour } from "./Tour";
import { CompareTray } from "./CompareTray";

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Nav />
      <main id="content" className="mx-auto max-w-7xl px-3 pb-24 pt-20 sm:px-4">{children}</main>
      <footer className="mx-auto max-w-7xl border-t border-white/10 px-3 py-6 text-xs text-slate-400 sm:px-4">
        A two-year sample of AI papers from OpenAlex. <Link href="/about" className="text-accent hover:underline">About the data</Link>
      </footer>
      <CompareTray />
      <Tour />
    </>
  );
}
