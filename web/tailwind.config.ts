import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { ink: "#05060f", glow: "#7c5cff", aqua: "#2de2e6" },
    },
  },
  plugins: [],
};
export default config;
