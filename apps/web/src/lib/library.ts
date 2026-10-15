"use client";
import { useSyncExternalStore } from "react";

export interface Collection { id: string; name: string; paperIds: string[]; createdAt: string }

const COL_KEY = "spe-collections";
const CMP_KEY = "spe-compare";
const colListeners = new Set<() => void>();
const cmpListeners = new Set<() => void>();
let collections: Collection[] | null = null;
let compare: string[] | null = null;

function readCollections(): Collection[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = JSON.parse(localStorage.getItem(COL_KEY) || "[]");
    if (!Array.isArray(raw)) return [];
    return raw.filter((c) => c && typeof c.id === "string" && typeof c.name === "string" && Array.isArray(c.paperIds));
  } catch { return []; }
}
function readCompare(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = JSON.parse(sessionStorage.getItem(CMP_KEY) || "[]");
    return Array.isArray(raw) ? raw.filter((id) => typeof id === "string").slice(0, 2) : [];
  } catch { return []; }
}
function cols(): Collection[] { return (collections ??= readCollections()); }
function cmps(): string[] { return (compare ??= readCompare()); }
function commitCols(next: Collection[]) { collections = next; localStorage.setItem(COL_KEY, JSON.stringify(next)); colListeners.forEach((l) => l()); }
function commitCmps(next: string[]) { compare = next; sessionStorage.setItem(CMP_KEY, JSON.stringify(next)); cmpListeners.forEach((l) => l()); }

export function getCollections() { return cols(); }
export function getCompare() { return cmps(); }

export function saveToCollection(name: string, paperId: string) {
  const trimmed = name.trim() || "Reading list";
  const list = cols().map((c) => ({ ...c, paperIds: [...c.paperIds] }));
  let col = list.find((c) => c.name.toLowerCase() === trimmed.toLowerCase());
  if (!col) {
    col = { id: `c${Date.now().toString(36)}`, name: trimmed, paperIds: [], createdAt: new Date().toISOString() };
    list.unshift(col);
  }
  if (!col.paperIds.includes(paperId)) col.paperIds.push(paperId);
  commitCols(list);
}
export function removePaper(collectionId: string, paperId: string) {
  commitCols(cols().map((c) => c.id === collectionId ? { ...c, paperIds: c.paperIds.filter((id) => id !== paperId) } : c));
}
export function removeCollection(id: string) {
  commitCols(cols().filter((c) => c.id !== id));
}
export function toggleCompare(id: string) {
  const cur = cmps();
  commitCmps(cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id].slice(-2));
}
export function clearCompare() { commitCmps([]); }
export function resetLibraryStore() { collections = null; compare = null; }

const EMPTY_COLS: Collection[] = [];
const EMPTY_CMP: string[] = [];
export function useCollections() {
  return useSyncExternalStore((l) => { colListeners.add(l); return () => colListeners.delete(l); }, getCollections, () => EMPTY_COLS);
}
export function useCompare() {
  return useSyncExternalStore((l) => { cmpListeners.add(l); return () => cmpListeners.delete(l); }, getCompare, () => EMPTY_CMP);
}
