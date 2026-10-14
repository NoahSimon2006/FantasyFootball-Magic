// Adds DOM matchers such as expect(element).toBeInTheDocument().
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Unmount whatever each test rendered, so tests can't see each other's DOM.
// Testing Library only does this automatically when Vitest globals are enabled.
afterEach(() => {
  cleanup();
});
