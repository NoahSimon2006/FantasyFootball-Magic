// Regenerating API types: after any API change, run `uv run python -m app.export_openapi` in
// api/, then `npm run gen:api` in web/. Never hand-edit openapi.json or schema.d.ts; tests
// on both sides (api/tests/test_openapi_contract.py, schema.test.ts) fail while they're stale.
import createClient, { type Client, type ClientOptions } from "openapi-fetch";

import type { paths } from "./schema";

/** The local FastAPI server. 127.0.0.1, not "localhost", which hangs on this Windows setup. */
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

/** A client whose paths, parameters, and responses are all typed from the API's schema. */
export type ApiClient = Client<paths>;

export interface ApiClientOptions {
  /** Defaults to the server-side `API_BASE_URL` env var, then http://127.0.0.1:8000. */
  baseUrl?: string;
  /** Defaults to the global fetch. Tests pass a fake. */
  fetch?: ClientOptions["fetch"];
}

export function createApiClient({
  // `||`, not `??`, so an empty `API_BASE_URL=` line counts as unset.
  baseUrl = process.env.API_BASE_URL || DEFAULT_API_BASE_URL,
  // Look the global fetch up on each request rather than letting openapi-fetch capture it
  // once: Next.js swaps in its own instrumented fetch on the server, and a reference taken
  // before that swap would silently bypass it.
  fetch = (request: Request) => globalThis.fetch(request),
}: ApiClientOptions = {}): ApiClient {
  return createClient<paths>({ baseUrl, fetch });
}

/** The app's client, for server code: `API_BASE_URL` is not exposed to the browser. */
export const api = createApiClient();
