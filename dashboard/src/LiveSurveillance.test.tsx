import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import LiveSurveillancePage from "./LiveSurveillance";

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

describe("Live Kerala Health Monitor loading and unavailable states", () => {
  it("shows a loading status while the API request is pending", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root?.render(<LiveSurveillancePage />));

    expect(container.textContent).toContain("Loading the latest verified official report");
  });

  it("surfaces API failures instead of showing an empty success state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network unavailable")));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<LiveSurveillancePage />);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "Cannot reach the CareGrid API",
    );
  });

  it("labels the no-snapshot state as unavailable and does not substitute history", async () => {
    const emptyStatus = {
      status: "data_not_available",
      source_access_status: "not_retrieved",
      source_name: "Kerala Directorate of Health Services",
      source_index_url: "https://dhs.kerala.gov.in/en/data-on-communicable-diseases/",
      source_url: "https://dhs.kerala.gov.in/wp-content/uploads/2026/09/CD-Data-2025-Approved.pdf",
      snapshot_available: false,
      publication_date: null,
      publication_date_note: "No verified official-report snapshot is available.",
      last_successful_retrieval: null,
      last_attempt: null,
      missing_districts: [],
      freshness_rule: {},
      error: "No verified snapshot",
    };
    const emptySummary = {
      data_status: "data_not_available",
      snapshot_data_status: "data_not_available",
      is_live: false,
      current_2026_information_available: false,
      reporting_period_start: null,
      reporting_period_end: null,
      source_publication_date: null,
      source_publication_date_note: emptyStatus.publication_date_note,
      last_successful_retrieval: null,
      source_status: emptyStatus,
      verified_disease_count: 0,
      verified_monthly_series_count: 0,
      district_count: 0,
      expected_district_count: 14,
      missing_districts: [],
      disease_statistics: [],
      message: "Current official data unavailable. No snapshot has been imported.",
    };
    const sourceMetadata = {
      source_name: emptyStatus.source_name,
      retrieval_method: "No snapshot",
      reporting_frequency: "Annual report with monthly tables when published",
      available_variables: [],
      validation_status: "no verified snapshot available",
      validation_checks: [],
      limitations: ["Current official data unavailable."],
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/daily/")) return jsonResponse({ detail: "No daily data" }, 503);
      if (path.endsWith("/summary")) return jsonResponse(emptySummary);
      if (path.endsWith("/source")) return jsonResponse(sourceMetadata);
      return jsonResponse({ detail: "No verified snapshot" }, 503);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<LiveSurveillancePage />);
      await new Promise((resolve) => setTimeout(resolve, 0));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(container.textContent).toContain("Current official daily data unavailable");
    expect(container.textContent).toContain("No historical dataset has been substituted");
    expect(container.textContent).toContain("No verified disease records are currently available");
  });

  it("renders a verified delayed DHS value in the monthly summary and accessible trend table", async () => {
    const sourceStatus = {
      status: "official_delayed",
      source_access_status: "success",
      source_name: "Kerala Directorate of Health Services",
      source_index_url: "https://dhs.kerala.gov.in/en/data-on-communicable-diseases/",
      source_url: "https://dhs.kerala.gov.in/wp-content/uploads/2026/09/CD-Data-2025-Approved.pdf",
      snapshot_available: true,
      publication_date: null,
      publication_date_note: "Formal publication date not stated.",
      last_modified_date: "2026-09-23",
      reporting_period: "2025",
      reporting_period_start: "2025-01",
      reporting_period_end: "2025-12",
      frequency: "annual report with monthly statewide tables",
      last_successful_retrieval: "2026-11-02T11:13:51+00:00",
      last_attempt: null,
      dataset_version: "report-v3-sha256-c873a4266ee2ee88",
      reported_district_count: 13,
      expected_district_count: 14,
      missing_districts: ["Alappuzha"],
      statewide_district_reconciliation: [],
      freshness_rule: {},
      message: "Latest official report covers 2025, not current 2026 information.",
    };
    const statistic = {
      disease: "Dengue",
      classification: "Confirmed",
      source_label: "Con Dengue",
      latest_period: "2025-12",
      previous_comparable_period: "2025-11",
      cases: 633,
      previous_cases: 645,
      cases_change: -12,
      cases_change_percent: -1.86,
      deaths: 8,
      previous_deaths: 10,
      deaths_change: -2,
      change_interpretation: "Reported cases decreased compared with the previous comparable reporting period.",
      comparison_valid: true,
      source_name: sourceStatus.source_name,
      source_url: sourceStatus.source_url,
      data_status: "official_delayed",
      metric_unit: "reported cases",
    };
    const summary = {
      data_status: "official_delayed",
      snapshot_data_status: "official_delayed",
      is_live: false,
      current_2026_information_available: false,
      reporting_period_start: "2025-01",
      reporting_period_end: "2025-12",
      source_publication_date: null,
      source_publication_date_note: "Formal publication date not stated.",
      last_successful_retrieval: sourceStatus.last_successful_retrieval,
      source_status: sourceStatus,
      verified_disease_count: 22,
      verified_monthly_series_count: 27,
      district_count: 13,
      expected_district_count: 14,
      missing_districts: ["Alappuzha"],
      disease_statistics: [statistic],
    };
    const monthlyRecord = {
      period: "2025-12",
      disease: "Dengue",
      classification: "Confirmed",
      source_label: "Con Dengue",
      cases: 633,
      deaths: 8,
    };
    const sourceMetadata = {
      retrieval_method: "Manually imported official DHS report",
      reporting_frequency: "Annual report with monthly tables",
      available_variables: ["Monthly statewide cases and deaths"],
      validation_status: "passed",
      validation_checks: ["Monthly totals reconciled."],
      limitations: ["No current 2026 data."],
      dataset_version: sourceStatus.dataset_version,
      source_sha256: "c873a4266ee2ee8862575309477b12cd3a877a3a9ad0105f9373e3473b879554",
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/daily/")) return jsonResponse({ detail: "No daily data" }, 503);
      if (path.endsWith("/summary")) return jsonResponse(summary);
      if (path.includes("/trends")) {
        return jsonResponse({
          records: [monthlyRecord],
          disease_options: ["Dengue"],
          classification_options: ["Confirmed"],
          classification_options_by_disease: { Dengue: ["Confirmed"] },
        });
      }
      if (path.includes("/districts")) {
        return jsonResponse({
          data_status: "official_delayed",
          reporting_year: 2025,
          reporting_frequency: "Annual",
          temporal_granularity: "annual district records, not district-month",
          disease_options: ["Dengue"],
          classification_options: ["Confirmed"],
          classification_options_by_disease: { Dengue: ["Confirmed"] },
          records: [{
            district: "Thiruvananthapuram",
            disease: "Dengue",
            classification: "Confirmed",
            cases: 1493,
            deaths: 9,
            rank_by_reported_count: 1,
          }],
          reported_districts: ["Thiruvananthapuram"],
          missing_districts: ["Alappuzha"],
          expected_district_count: 14,
          comparison_note: "Sorted by reported absolute counts only.",
          source_url: sourceStatus.source_url,
        });
      }
      return jsonResponse(sourceMetadata);
    }));
    class ResizeObserverMock {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<LiveSurveillancePage />);
      await new Promise((resolve) => setTimeout(resolve, 0));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(container.textContent).toContain("Official but delayed");
    expect(container.textContent).toContain("December 2025");
    expect(container.textContent).toContain("633");
    expect(container.textContent).toContain("Reported cases decreased");
    expect(container.querySelector(".sr-only")?.textContent).toContain("2025-12");
    expect(container.querySelector(".sr-only")?.textContent).toContain("633");
  });
});
