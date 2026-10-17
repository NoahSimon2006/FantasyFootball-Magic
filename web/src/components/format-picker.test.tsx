import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_FORMAT } from "@/lib/league-format";

import { FormatPicker } from "./format-picker";

// The Next.js router at the boundary: a page at /rankings with other params in its URL.
const router = vi.hoisted(() => ({
  replace: vi.fn(),
  search: "",
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: router.replace }),
  usePathname: () => "/rankings",
  useSearchParams: () => new URLSearchParams(router.search),
}));

beforeEach(() => {
  router.replace.mockReset();
  router.search = "position=WR&page=2";
});

describe("FormatPicker", () => {
  it("shows the format it is given", () => {
    render(<FormatPicker format={{ teams: 8, ppr: 0, superflex: true }} />);

    expect(screen.getByLabelText("League size")).toHaveValue("8");
    expect(screen.getByLabelText("Scoring")).toHaveValue("0");
    expect(screen.getByRole("checkbox", { name: "Superflex" })).toBeChecked();
  });

  it("writes a new team count into the URL and keeps the other params", () => {
    render(<FormatPicker format={DEFAULT_FORMAT} />);

    fireEvent.change(screen.getByLabelText("League size"), {
      target: { value: "10" },
    });

    expect(router.replace).toHaveBeenCalledWith(
      "/rankings?position=WR&page=2&teams=10&ppr=1&superflex=false",
      { scroll: false },
    );
  });

  it("updates format params already in the URL in place, without duplicates", () => {
    router.search = "teams=14&position=RB&ppr=0.5";
    render(<FormatPicker format={{ teams: 14, ppr: 0.5, superflex: false }} />);

    fireEvent.click(screen.getByRole("checkbox", { name: "Superflex" }));

    expect(router.replace).toHaveBeenCalledWith(
      "/rankings?teams=14&position=RB&ppr=0.5&superflex=true",
      { scroll: false },
    );
  });

  it("writes the scoring setting as the API's ppr number", () => {
    render(<FormatPicker format={DEFAULT_FORMAT} />);

    fireEvent.change(screen.getByLabelText("Scoring"), {
      target: { value: "0.5" },
    });

    expect(router.replace).toHaveBeenCalledWith(
      "/rankings?position=WR&page=2&teams=12&ppr=0.5&superflex=false",
      { scroll: false },
    );
  });
});
