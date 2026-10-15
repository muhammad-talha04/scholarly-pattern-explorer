/**
 * Embedding Lens. Every color in the web app comes from this file.
 * Galaxy nodes use the amber `clusterColors`. Charts and the globe use `okabeIto`.
 */
export const ink = "#0B0F1A";
export const panel = "#141A2B";
export const text = "#F4F1EA";
export const mist = "#9AA3B5";
export const faint = "#6E7890";
/** Warm amber. Headline word, search button, focus ring, active nav, node glow. */
export const accent = "#F5A54A";
/** Brighter amber for the galaxy hub. */
export const hub = "#FFC56E";
/** Pale blue dust behind the nodes. */
export const dust = "#9EBFDE";
/** Research-gap mark. Separate from the amber nodes. */
export const gap = "#CC79A7";
export const up = "#009E73";
export const down = "#D55E00";
/** Filament color at a hub: bright yellow-amber. */
export const filamentHot = "#FFE08A";
/** Thin amber filaments between papers. */
export const linkAmber = "#F5A54A";
/** Filament tips, deep orange with a magenta tint. */
export const filamentTip = "#C4476A";
/** Grey for a galaxy cluster past the five amber tones. */
export const otherColor = "#6D7C96";

/** Fixed galaxy order, all warm amber and orange. */
export const clusterColors = ["#F5A54A", "#FFB15A", "#E8832A", "#FFC98A", "#C96A22"] as const;

/** Okabe–Ito. Charts and the globe only. */
export const okabeIto = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"] as const;

/** Resting nodes stay bright enough to read, with the halo carrying the glow. */
export const NODE_BRIGHTNESS = 0.9;

export function chartColor(index: number) {
  const n = okabeIto.length;
  return okabeIto[((index % n) + n) % n];
}

function clusterIndexFromId(id: string) {
  let h = 2166136261;
  const key = id || "";
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) % clusterColors.length;
}

/**
 * Galaxy swatch. `color_index` from /galaxy wins. Otherwise the cluster id
 * picks one of the five amber tones. An index outside 0–4 is the other grey.
 */
export function galaxyColor(colorIndex: number | null | undefined, clusterId: string) {
  const idx = colorIndex != null && Number.isFinite(colorIndex) ? Math.trunc(colorIndex) : clusterIndexFromId(clusterId);
  if (idx < 0 || idx >= clusterColors.length) return otherColor;
  return clusterColors[idx];
}

/** sRGB scale. 1 is the hex itself; NODE_BRIGHTNESS is the resting node. */
export function scaleHex(hex: string, amount: number) {
  const n = Number.parseInt(hex.slice(1), 16);
  const ch = (shift: number) => Math.max(0, Math.min(255, Math.round(((n >> shift) & 255) * amount)));
  return `#${[ch(16), ch(8), ch(0)].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

const line = "rgba(245, 165, 74, 0.22)";
const glassTop = "rgba(20, 26, 43, 0.82)";
const glassBot = "rgba(11, 15, 26, 0.72)";
const searchBg = "rgba(11, 15, 26, 0.82)";
const star = "rgba(158, 191, 222, 0.35)";
const wash = "rgba(245, 165, 74, 0.06)";

/** Injected on :root so stylesheets refer to variables and not hex values. */
export const paletteCss = `:root {
  color-scheme: dark;
  --bg: ${ink};
  --panel: ${panel};
  --text: ${text};
  --muted: ${mist};
  --faint: ${faint};
  --line: ${line};
  --accent: ${accent};
  --gap: ${gap};
  --up: ${up};
  --down: ${down};
  --glass-top: ${glassTop};
  --glass-bot: ${glassBot};
  --search-bg: ${searchBg};
  --star: ${star};
  --wash: ${wash};
  --glow: 0 0 28px -8px rgba(245, 165, 74, 0.45);
  --glow-strong: 0 0 36px -6px rgba(245, 165, 74, 0.62);
  --vignette: linear-gradient(90deg, rgba(11, 15, 26, 0.94) 0%, rgba(11, 15, 26, 0.55) 42%, transparent 68%);
}`;

export const glowShadow = "0 0 28px -8px rgba(245, 165, 74, 0.45)";
