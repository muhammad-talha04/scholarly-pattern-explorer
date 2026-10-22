/**
 * Champagne & Platinum. Every color in the web app comes from this file.
 * Galaxy clusters use `clusterColors`. Charts and the globe use `okabeIto`.
 */
export const ink = "#121216";
export const panel = "#1B1B21";
export const text = "#F4F2F6";
export const mist = "#C9C7D0";
export const faint = "#9B99A3";
/** Champagne. Headline word, search button, focus ring, active nav. */
export const accent = "#F3E3B5";
/** Research-gap mark. Separate from the gold and silver cluster tones. */
export const gap = "#CC79A7";
export const up = "#009E73";
export const down = "#D55E00";
/** Very faint warm grey for galaxy links. */
export const linkGrey = "#A39890";
/** Grey for a galaxy cluster past the five named tones. */
export const otherColor = "#6E6E76";

/** Fixed galaxy order: champagne gold, platinum, antique gold, pewter, pale gold. */
export const clusterColors = ["#D9C28E", "#C7CCD4", "#BFA36A", "#9EA4AE", "#E6DCC0"] as const;

/** Okabe–Ito. Charts and the globe only. */
export const okabeIto = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"] as const;

/** Nodes sit a little under full brightness so they stay crisp without bloom. */
export const NODE_BRIGHTNESS = 0.875;

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
 * picks one of the five tones. An index outside 0–4 is the other grey.
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

const line = "rgba(243, 227, 181, 0.18)";
const glassTop = "rgba(27, 27, 33, 0.78)";
const glassBot = "rgba(18, 18, 22, 0.6)";
const searchBg = "rgba(18, 18, 22, 0.78)";
const star = "rgba(244, 242, 246, 0.45)";
const wash = "rgba(199, 204, 212, 0.06)";

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
  --glow: 0 0 26px -10px rgba(243, 227, 181, 0.28);
  --glow-strong: 0 0 32px -8px rgba(243, 227, 181, 0.45);
  --vignette: radial-gradient(ellipse 68% 46% at 50% 24%, rgba(18, 18, 22, 0.62) 0%, rgba(18, 18, 22, 0.3) 48%, transparent 74%);
}`;

export const glowShadow = "0 0 26px -10px rgba(243, 227, 181, 0.28)";
