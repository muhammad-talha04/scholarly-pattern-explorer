import type { Config } from "tailwindcss";
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: {
      ink: "#0B0720",
      panel: "#16132F",
      accent: "#9AD7FF",
      gap: "#FF4FD8",
      mist: "#D5D0E8",
      teal: "#2EE6C7",
      violet: "#D58BFF",
      amber: "#F5C451",
      coral: "#FF7A62",
    },
    fontFamily: {
      sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      display: ["var(--font-display)", "Georgia", "serif"],
    },
    boxShadow: {
      glow: "0 0 40px -8px rgba(46, 230, 199, 0.45)",
    },
  } },
  plugins: [],
} satisfies Config;
