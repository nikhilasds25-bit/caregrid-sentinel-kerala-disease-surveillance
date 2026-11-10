import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import ForecastingExperimentPage from "./ForecastingExperiment";

const actEnvironment = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean;
};
actEnvironment.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | undefined;
let container: HTMLDivElement | undefined;

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}

afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount());
    root = undefined;
  }
  container?.remove();
  container = undefined;
  vi.unstubAllGlobals();
});

describe("forecasting experiment dashboard", () => {
  it("shows loading and API error states", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => root?.render(<ForecastingExperimentPage />));
    expect(container.textContent).toContain("Loading forecasting readiness");

    await act(async () => root?.unmount());
    root = undefined;
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Experiment unavailable" }, 503)));
    root = createRoot(container);
    await act(async () => {
      root?.render(<ForecastingExperimentPage />);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("Experiment unavailable");
  });

  it("renders a validated retrospective baseline comparison, not a future forecast", async () => {
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      unobserve() {}
      disconnect() {}
    });
    const payload = {
      status: "experimental_baseline_hindcast",
      experiment_generated_at_utc: "2026-11-02T12:00:00+00:00",
      source_dataset: "data/processed/kerala_disease_monthly_2021_2024.csv",
      source_columns: ["period", "cases"],
      series: [{
        disease: "Dengue",
        classification: "Confirmed",
        valid_observations: 24,
        first_reporting_month: "2023-01",
        last_reporting_month: "2024-12",
        missing_months: [],
        duplicate_months: [],
        zero_observations: 0,
        source_change: true,
        source_files: ["2023.pdf", "2024.pdf"],
        outliers_for_review_iqr_rule: [],
      }],
      evaluation: {
        proposed_2021_2023_train_2024_test_feasible: false,
        proposed_split_reason: "Classifications differ.",
        confirmed_2023_train_2024_test: {
          Dengue: {
            eligible_for_limited_2024_holdout: true,
            observations: 24,
            training_period: ["2023-01", "2023-12"],
            test_period: ["2024-01", "2024-12"],
            reason: "Complete series.",
            source_files_by_year: {},
          },
          Leptospirosis: {
            eligible_for_limited_2024_holdout: false,
            observations: 0,
            training_period: null,
            test_period: null,
            reason: "Unavailable.",
            source_files_by_year: {},
          },
        },
        rolling_origin_12_month_horizon_feasible: false,
        rolling_origin_reason: "Only one origin is available.",
      },
      climate: {
        matched_confirmed_disease_months: 24,
        weather_scope: "Equal-weight proxy.",
        climate_model_evaluated: false,
        reason_not_evaluated: "Insufficient training history.",
      },
      evaluation_metrics: [{
        disease: "Dengue",
        classification: "Confirmed",
        model: "naive",
        mae: 10,
        rmse: 12,
        mase: null,
        test_observations: 12,
        training_observations: 12,
        training_start: "2023-01",
        training_end: "2023-12",
        test_start: "2024-01",
        test_end: "2024-12",
        mase_note: "Not estimable.",
      }],
      actual_vs_predicted: [{
        disease: "Dengue",
        classification: "Confirmed",
        period: "2024-01",
        model: "naive",
        actual_cases: 100,
        predicted_cases: 90,
        residual_actual_minus_predicted: 10,
      }],
      validity_checks_passed: true,
      future_forecasts_available: false,
      climate_features_improved_performance: null,
      climate_feature_comparison_status: "Not evaluated.",
    };
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(payload)));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(<ForecastingExperimentPage />);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(container.textContent).toContain("2024 historical holdout");
    expect(container.textContent).toContain("MAE");
    expect(container.textContent).toContain("100");
    expect(container.textContent).toContain("90");
    expect(container.textContent).toContain("Climate improvement: Not evaluated");
    expect(container.textContent).toContain("not yet scientifically justified");
  });
});
