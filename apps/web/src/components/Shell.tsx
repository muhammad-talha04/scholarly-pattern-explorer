"use client";
import { Nav } from "./Nav";
import { Tour } from "./Tour";
import { CompareTray } from "./CompareTray";

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Nav />
      <main id="content" className="mx-auto max-w-7xl px-3 pb-24 pt-20 sm:px-4">{children}</main>
      <CompareTray />
      <Tour />
    </>
  );
}
