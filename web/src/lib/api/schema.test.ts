// @vitest-environment node
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, it } from "vitest";

const WEB_ROOT = fileURLToPath(new URL("../../../", import.meta.url));

// The TypeScript half of the drift guard. api/tests/test_openapi_contract.py proves
// openapi.json matches the API; this proves schema.d.ts matches openapi.json, by running
// the real `gen:api` command in --check mode (it compares instead of writing).
it("schema.d.ts is up to date with openapi.json", { timeout: 30_000 }, () => {
  const result = spawnSync("npm run gen:api -- --check", {
    cwd: WEB_ROOT,
    shell: true,
    encoding: "utf8",
  });

  expect(
    result.status,
    `src/lib/api/schema.d.ts is out of date. In web/, run: npm run gen:api\n${result.stderr}`,
  ).toBe(0);
});
