/** Light-gold palette. Hex values match tailwind.config.ts and globals.css. */
export const ink = "#14110E";
export const panel = "#241C16";
/** Light gold. Headings, buttons, focus, search glow, active nav. */
export const accent = "#E8C873";
export const champagne = "#F3E3B5";
export const ivory = "#F8F6F2";
export const mist = "#D4CBBE";
/** Cluster swatches: champagne, ivory, muted teal, terracotta, soft slate blue. */
export const CLUSTER_COLORS = [champagne, ivory, "#5FB3A8", "#C4785A", "#7383C0"] as const;
export const teal = "#5FB3A8";
export const rose = "#C4785A";
/** Soft slate blue. Named dusk so it does not replace Tailwind's slate scale. */
export const dusk = "#7383C0";
/** Research-gap mark. Separate from the five cluster colors. */
export const gapColor = "#E04B9A";
export const linkColor = accent;

export function clusterColor(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h + name.charCodeAt(i) * 13) % CLUSTER_COLORS.length;
  return CLUSTER_COLORS[h];
}
