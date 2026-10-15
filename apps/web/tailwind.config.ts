import type { Config } from "tailwindcss";
import { accent, down, gap, glowShadow, ink, mist, panel, up } from "./src/lib/theme";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: { ink, panel, accent, gap, mist, up, down },
    fontFamily: {
      sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      display: ["var(--font-display)", "Georgia", "serif"],
    },
    boxShadow: { glow: glowShadow },
  } },
  plugins: [],
} satisfies Config;
