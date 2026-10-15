import type { Config } from "tailwindcss";
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: {
      ink: "#14110E",
      panel: "#241C16",
      accent: "#E8C873",
      champagne: "#F3E3B5",
      ivory: "#F8F6F2",
      gap: "#E04B9A",
      mist: "#D4CBBE",
      teal: "#5FB3A8",
      rose: "#C4785A",
      dusk: "#7383C0",
    },
    fontFamily: {
      sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      display: ["var(--font-display)", "Georgia", "serif"],
    },
    boxShadow: {
      glow: "0 0 40px -8px rgba(232, 200, 115, 0.45)",
    },
  } },
  plugins: [],
} satisfies Config;
