import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import AnalyticalDashboard from "./AnalyticalDashboard";

vi.mock("./components", async (importOriginal) => {
  const original =
    await importOriginal<typeof import("./components")>();

  return {
    ...original,
    TrendChart: ({ data, ariaLabel }: {
      data: unknown[];
      ariaLabel: string;
    }) => (
      <pre data-testid={ariaLabel}>
        {JSON.stringify(data)}
      </pre>
    ),
  };
});

const actEnvironment = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean;
};
actEnvironment.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | undefined;
let container: HTMLDivElement | undefined;

afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount());
    root = undefined;
  }
  container?.remove();
  container = undefined;
  vi.unstubAllGlobals();
});

describe("analytical actual-versus-predicted chart", () => {
  it("matches district-month observations and preserves missing values", async () => {
    const forecasts = [
      {
        disease: "Dengue",
        district: "Ernakulam",
        model_name: "test_model",
        feature_set: "test_features",
        origin_period: "2023-12",
        target_period: "2024-01",
        horizon: 1,
        predictive_mean: 90,
        display_80_lower: 70,
        display_80_upper: 110,
        evidence_role: "development_retrospective",
        prediction_type: "backtest",
      },
      {
        disease: "Dengue",
        district: "Ernakulam",
        model_name: "test_model",
        feature_set: "test_features",
        origin_period: "2023-12",
        target_period: "2024-02",
        horizon: 2,
        predictive_mean: 95,
        display_80_lower: 75,
        display_80_upper: 115,
        evidence_role: "development_retrospective",
        prediction_type: "backtest",
      },
    ];

    const observations = [
      {
        disease: "Dengue",
        district: "Ernakulam",
        reporting_period: "2024-01",
        observed_count: 100,
        classification: "Confirmed",
        observation_type: "reported_observation",
      },
      {
        disease: "Dengue",
        district: "Kollam",
        reporting_period: "2024-02",
        observed_count: 500,
        classification: "Confirmed",
        observation_type: "reported_observation",
      },
    ];

    const fetchMock = vi.fn(async (input: string) => {
      const url = String(input);

      let data: unknown[] = [];

      if (url.includes("/api/v1/forecasts?")) {
        data = forecasts;
      } else if (
        url.includes("/api/v1/surveillance/observations?")
      ) {
        data = observations;
      }

      return {
        ok: true,
        status: 200,
        json: async () => ({
          data,
          meta: {
            schema_version: "1.0",
            status: "exploratory",
            limitations: [],
          },
        }),
      } as Response;
    });

    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<AnalyticalDashboard />);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    const chart = container.querySelector(
      '[data-testid="Dengue retrospective forecasts for Ernakulam"]',
    );

    expect(chart).not.toBeNull();

    const rows = JSON.parse(chart!.textContent || "[]");

    expect(rows).toHaveLength(2);

    expect(rows[0]).toMatchObject({
      period: "2024-01",
      actual: 100,
      prediction: 90,
      lower: 70,
      upper: 110,
    });

    expect(rows[1]).toMatchObject({
      period: "2024-02",
      actual: null,
      prediction: 95,
      lower: 75,
      upper: 115,
    });

    expect(container.textContent).toContain(
      "historical backtest predictions",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("source=district_dashboard"),
      expect.anything(),
    );
  });
});
