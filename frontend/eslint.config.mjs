import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // The pilot UI loads remote data from effects. React's new optimization
      // rule is intentionally disabled until these pages move to a shared data
      // fetching abstraction. Correctness is still enforced by TypeScript/build.
      "react-hooks/set-state-in-effect": "off",
      // Legacy starter screens still contain a small number of untyped API
      // payloads. Keep them visible in CI without blocking the pilot import.
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
  globalIgnores([".next/**", "out/**"]),
]);
