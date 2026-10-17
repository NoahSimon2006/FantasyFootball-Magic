import type { NextConfig } from "next";

// Where the FastAPI server runs; same default as src/lib/api/client.ts. `||` (not `??`) so an
// empty `API_BASE_URL=` line counts as unset; 127.0.0.1 because "localhost" hangs on this
// Windows setup. Trailing slashes are trimmed so the destination never has "//api".
const API_BASE_URL = (
  process.env.API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Browser code calls the API at the web app's own origin (`browserApi` in
  // src/lib/api/client.ts) and Next.js proxies those requests to FastAPI. Read when the
  // server starts (`next dev`) or at build time (`next build`).
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${API_BASE_URL}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
