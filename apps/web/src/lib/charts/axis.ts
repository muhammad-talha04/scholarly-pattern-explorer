/** Calendar axis for the publication chart. Works in SVG user units, so a scaled-down mobile view keeps the same gaps. */

export const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const;

export function monthKey(year: number, monthIndex: number): string {
  return `${year}-${String(monthIndex + 1).padStart(2, "0")}`;
}

export function monthKeys(year: number): string[] {
  return MONTH_LABELS.map((_, i) => monthKey(year, i));
}

/** "2025" stays "2025". "2025-03" becomes "Mar". */
export function tickLabel(key: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(key);
  if (!m) return key;
  return MONTH_LABELS[Number(m[2]) - 1] ?? key;
}

export function isMonthKey(key: string): boolean {
  return /^(\d{4})-(\d{2})$/.test(key);
}

/**
 * Indexes whose labels can be drawn without their boxes touching.
 * The first label is always kept. The last is kept when it fits; interior
 * labels that would collide with it are dropped first.
 */
export function visibleTickIndexes(labels: string[], xs: number[], opts?: { charPx?: number; pad?: number }): number[] {
  const charPx = opts?.charPx ?? 6.8;
  const pad = opts?.pad ?? 8;
  const n = labels.length;
  if (n === 0) return [];
  const width = (i: number) => Math.max(1, labels[i].length) * charPx;
  const left = (i: number) => xs[i] - width(i) / 2;
  const right = (i: number) => xs[i] + width(i) / 2;
  const shown: number[] = [0];
  let last = 0;
  for (let i = 1; i < n - 1; i++) {
    if (left(i) >= right(last) + pad && right(i) + pad <= left(n - 1)) {
      shown.push(i);
      last = i;
    }
  }
  if (n === 1) return shown;
  while (shown.length > 1 && left(n - 1) < right(shown[shown.length - 1]) + pad) shown.pop();
  if (left(n - 1) >= right(shown[shown.length - 1]) + pad) shown.push(n - 1);
  return shown;
}

/** True when two shown labels would paint on top of each other. */
export function ticksOverlap(labels: string[], xs: number[], indexes: number[], opts?: { charPx?: number; pad?: number }): boolean {
  const charPx = opts?.charPx ?? 6.8;
  const pad = opts?.pad ?? 8;
  const width = (i: number) => Math.max(1, labels[i].length) * charPx;
  for (let a = 0; a < indexes.length; a++) {
    for (let b = a + 1; b < indexes.length; b++) {
      const i = indexes[a], j = indexes[b];
      const gap = Math.abs(xs[i] - xs[j]) - width(i) / 2 - width(j) / 2;
      if (gap < pad) return true;
    }
  }
  return false;
}

/** Axis text for large totals: 80000 → "80k", 15200 → "15.2k". */
export function compactCount(n: number): string {
  const sign = n < 0 ? "-" : "";
  const v = Math.abs(n);
  if (v < 1000) return `${sign}${Math.round(v)}`;
  const k = v / 1000;
  const text = k >= 100 || Math.abs(k - Math.round(k)) < 0.05 ? String(Math.round(k)) : (Math.round(k * 10) / 10).toString();
  return `${sign}${text}k`;
}

/** Spread `total` across `weights` as integers. Zero weights stay zero. The parts sum to `total`. */
export function distribute(total: number, weights: number[]): number[] {
  const whole = Math.max(0, Math.round(total));
  const sum = weights.reduce((s, w) => s + Math.max(0, w), 0);
  if (!weights.length) return [];
  if (sum <= 0 || whole === 0) return weights.map(() => 0);
  const raw = weights.map((w) => (whole * Math.max(0, w)) / sum);
  const floors = raw.map((n) => Math.floor(n));
  let left = whole - floors.reduce((s, n) => s + n, 0);
  const order = raw
    .map((n, i) => [n - floors[i], i] as const)
    .sort((a, b) => b[0] - a[0] || a[1] - b[1]);
  for (let k = 0; left > 0; k++, left--) floors[order[k % order.length][1]] += 1;
  return floors;
}
