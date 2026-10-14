import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Understand the "@/..." import alias from tsconfig.json (built into Vite 8).
    tsconfigPaths: true,
  },
  test: {
    // A simulated browser DOM, so components can render inside Node.
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
  },
});
