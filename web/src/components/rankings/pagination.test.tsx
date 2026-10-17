import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import { Pagination } from "./pagination";

function renderPage(props: Partial<ComponentProps<typeof Pagination>> = {}) {
  return render(
    <Pagination
      pathname="/rankings"
      search={{}}
      offset={50}
      count={50}
      total={312}
      pageSize={50}
      {...props}
    />,
  );
}

describe("Pagination", () => {
  it("says which players are on the page", () => {
    renderPage();

    expect(screen.getByText("Showing 51–100 of 312")).toBeInTheDocument();
  });

  it("links to the neighbouring pages and keeps the other params", () => {
    renderPage({ search: { position: "WR", offset: "50" } });

    expect(
      [
        screen.getByRole("link", { name: "Previous page" }),
        screen.getByRole("link", { name: "Next page" }),
      ].map((link) => link.getAttribute("href")),
    ).toEqual(["/rankings?position=WR", "/rankings?position=WR&offset=100"]);
  });

  it("has no previous link on the first page", () => {
    renderPage({ offset: 0 });

    expect(
      screen.queryByRole("link", { name: "Previous page" }),
    ).not.toBeInTheDocument();
  });

  it("has no next link on the last page", () => {
    renderPage({ offset: 300, count: 12 });

    expect(
      screen.queryByRole("link", { name: "Next page" }),
    ).not.toBeInTheDocument();
  });

  it("counts the last page up to the total", () => {
    renderPage({ offset: 300, count: 12 });

    expect(screen.getByText("Showing 301–312 of 312")).toBeInTheDocument();
  });

  it("has no page links when everything fits on one page", () => {
    renderPage({ offset: 0, count: 31, total: 31 });

    expect(screen.queryAllByRole("link")).toEqual([]);
  });

  it("groups thousands in the counts", () => {
    renderPage({ offset: 1000, count: 50, total: 1204 });

    expect(
      screen.getByText("Showing 1,001–1,050 of 1,204"),
    ).toBeInTheDocument();
  });
});
