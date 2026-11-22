import coreWebVitals from "eslint-config-next/core-web-vitals";

export default [
  ...coreWebVitals,
  { ignores: [".next/**", "node_modules/**"] },
  {
    // New React Compiler checks in eslint-config-next 16. The flagged code predates them
    // and works; keep them visible as warnings until those components are refactored.
    rules: {
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/immutability": "warn",
    },
  },
];
