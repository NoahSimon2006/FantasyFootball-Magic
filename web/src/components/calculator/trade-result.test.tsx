import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { makeEvaluation } from "./test-factories";
import { TradeResult, verdictSummary } from "./trade-result";

describe("TradeResult", () => {
  it.each([
    ["a", "Team A wins", "value points ahead"],
    ["b", "Team B wins", "value points ahead"],
    ["even", "Too close to call", "value points apart"],
  ] as const)(
    "shows verdict %s as “%s” with the margin in points and percent",
    (verdict, headline, marginLabel) => {
      render(
        <TradeResult
          evaluation={makeEvaluation({
            verdict,
            margin: 10.5,
            margin_share: 0.1736,
          })}
        />,
      );

      expect(
        screen.getByRole("heading", { level: 2, name: headline }),
      ).toBeInTheDocument();
      expect(screen.getByText("10.5")).toBeInTheDocument();
      expect(
        screen.getByText(`${marginLabel} · 17.4% of the larger side`),
      ).toBeInTheDocument();
    },
  );

  it("gives each side's share of the adjusted value as text", () => {
    render(<TradeResult evaluation={makeEvaluation()} />);

    // 60.5 vs 50 adjusted points: 54.8% and 45.2%.
    expect(screen.getByRole("figure")).toHaveTextContent(
      "Team A 54.8% · 60.5 points",
    );
    expect(screen.getByRole("figure")).toHaveTextContent(
      "Team B 45.2% · 50.0 points",
    );
  });

  it("shows value gaps and depth discounts as different chips, with their reasons", () => {
    render(
      <TradeResult
        evaluation={makeEvaluation({
          drivers: [
            {
              kind: "value_gap",
              side: "a",
              amount: 10.5,
              label: "Team A receives 10.5 more value points",
            },
            {
              kind: "depth_adjustment",
              side: "b",
              amount: 4.2,
              label: "Team B's 2 players are discounted by 4.2 points",
            },
          ],
        })}
      />,
    );

    const why = screen.getByRole("region", { name: "Why" });
    expect(within(why).getByText("Value gap 10.5")).toBeInTheDocument();
    expect(
      within(why).getByText("Depth discount · Team B −4.2"),
    ).toBeInTheDocument();
    expect(
      within(why).getByText("Team B's 2 players are discounted by 4.2 points"),
    ).toBeInTheDocument();
  });

  it("lists each side's players with projected points, value and rank, plus totals", () => {
    render(<TradeResult evaluation={makeEvaluation()} />);

    const teamA = screen.getByRole("table", { name: "Team A receives" });
    const row = within(teamA).getByRole("row", { name: /Ja'Marr Chase/ });
    expect(row).toHaveTextContent("180.2");
    expect(row).toHaveTextContent("60.5");
    expect(row).toHaveTextContent("#3");
    expect(
      within(teamA).getByRole("row", { name: /Adjusted total/ }),
    ).toHaveTextContent("60.5");
  });

  it("explains the v0 method in plain English and dates the snapshot", () => {
    render(<TradeResult evaluation={makeEvaluation()} />);

    expect(
      screen.getByText(
        /uses projections only, with no evidence from real trades/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Oct 14, 2026")).toHaveAttribute(
      "dateTime",
      "2026-10-14",
    );
  });
});

describe("verdictSummary", () => {
  it("reads a win and a draw as one sentence each", () => {
    expect(verdictSummary(makeEvaluation({ verdict: "b", margin: 3 }))).toBe(
      "Team B wins by 3.0 value points.",
    );
    expect(
      verdictSummary(makeEvaluation({ verdict: "even", margin: 1.25 })),
    ).toBe("Too close to call: the sides are 1.3 value points apart.");
  });
});
