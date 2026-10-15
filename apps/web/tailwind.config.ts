import type { Config } from "tailwindcss";
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: {
      ink: "#070814",
      panel: "#12162a",
      accent: "#7dd3fc",
      gap: "#f9a8d4",
      glow: "#c4b5fd",
      mist: "#c5d0e6",
    },
    fontFamily: {
      sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      display: ["var(--font-display)", "Georgia", "serif"],
    },
    boxShadow: {
      glow: "0 0 40px -8px rgba(125, 211, 252, 0.45)",
    },
  } },
  plugins: [],
} satisfies Config;
