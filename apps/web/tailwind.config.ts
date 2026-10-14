import type { Config } from "tailwindcss";
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: { ink: "#05060f", accent: "#7dd3fc", gap: "#f472b6", glow: "#a78bfa" },
    fontFamily: { sans: ["ui-sans-serif", "system-ui", "Inter", "sans-serif"] },
  } },
  plugins: [],
} satisfies Config;
