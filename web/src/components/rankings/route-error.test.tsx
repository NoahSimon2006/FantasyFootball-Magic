import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RouteError } from "./route-error";

describe("RouteError", () => {
  beforeEach(() => {
    // The boundary logs the error it caught; keep test output clean.
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps the page's heading above the error", () => {
    render(
      <RouteError
        pageTitle="Player rankings"
        error={new Error("boom")}
        retry={() => {}}
      />,
    );

    expect(
      screen.getByRole("heading", { level: 1, name: "Player rankings" }),
    ).toBeInTheDocument();
  });

  it("retries the page when asked", () => {
    const retry = vi.fn();
    render(
      <RouteError
        pageTitle="Player rankings"
        error={new Error("boom")}
        retry={retry}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(retry).toHaveBeenCalledOnce();
  });

  it("gives the server-log reference when there is one", () => {
    render(
      <RouteError
        pageTitle="Trending players"
        error={Object.assign(new Error("boom"), { digest: "abc123" })}
        retry={() => {}}
      />,
    );

    expect(screen.getByText(/reference abc123/)).toBeInTheDocument();
  });
});
