/** Aurora palette. Hex values match tailwind.config.ts and globals.css. */
export const ink = "#0B0720";
export const panel = "#16132F";
export const accent = "#9AD7FF";
export const mist = "#D5D0E8";

/** Cluster swatches: teal, violet, amber, coral, sky. Distinct in hue and lightness. */
export const CLUSTER_COLORS = ["#2EE6C7", "#D58BFF", "#F5C451", "#FF7A62", "#3E78FF"] as const;
export const violet = "#D58BFF";
export const coral = "#FF7A62";
export const gapColor = "#FF4FD8";
export const linkColor = accent;

export function clusterColor(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h + name.charCodeAt(i) * 13) % CLUSTER_COLORS.length;
  return CLUSTER_COLORS[h];
}
