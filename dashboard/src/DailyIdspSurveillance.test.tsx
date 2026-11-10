import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import DailyIdspSurveillance from "./DailyIdspSurveillance";

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

describe("daily IDSP surveillance section", () => {
  it("renders verified daily and cumulative data as separate metrics", async () => {
    const report = {
      data_status: "verified_recent",
      report_date: "2026-11-01",
      source_post_published_at: "2026-11-02T05:15:09+00:00",
      retrieved_at_utc: "2026-11-02T11:59:43+00:00",
      source_name: "Kerala DHS IDSP",
      source_page_url: "https://dhs.kerala.gov.in/en/2026/11/02/01-11-2026/",
      source_url: "https://dhs.kerala.gov.in/wp-content/uploads/2026/11/DR-CD-01.11.2026sd.pdf",
      source_sha256: "1eaa3f8501cc8676",
      dataset_version: "idsp-v1-1eaa3f8501cc8676",
      provisional_warning: "Preliminary values may change after laboratory tests and death audits.",
      daily_district_report_available: true,
      reported_district_count: 14,
      expected_district_count: 14,
      statewide_records: [
        { disease: "Dengue", disease_subtype: null, source_label: "Dengue Fever" },
        { disease: "Leptospirosis", disease_subtype: null, source_label: "Leptospirosis" },
      ],
    };
    const dengue = {
      disease: "Dengue",
      disease_subtype: null,
      source_label: "Dengue Fever",
      suspected_cases: 105,
      suspected_deaths: null,
      confirmed_cases: 80,
      confirmed_deaths: null,
      source_value_status: {
        suspected_cases: "reported",
        suspected_deaths: "source_dash_uninterpreted",
        confirmed_cases: "reported",
        confirmed_deaths: "source_dash_uninterpreted",
      },
    };
    const cumulativeDengue = {
      ...dengue,
      suspected_cases: 35419,
      suspected_deaths: 35,
      confirmed_cases: 13244,
      confirmed_deaths: 44,
      source_value_status: {
        suspected_cases: "reported",
        suspected_deaths: "reported",
        confirmed_cases: "reported",
        confirmed_deaths: "reported",
      },
    };
    const sourceStatus = {
      status: "verified_recent",
      source_access_status: "success",
      source_name: "Kerala DHS IDSP",
      source_index_url: "https://dhs.kerala.gov.in/en/idsp-2/",
      source_page_url: report.source_page_url,
      source_url: report.source_url,
      snapshot_available: true,
      report_date: report.report_date,
      source_post_published_at: report.source_post_published_at,
      last_successful_retrieval: report.retrieved_at_utc,
      last_attempt: null,
      daily_district_report_available: true,
      reported_district_count: 14,
      expected_district_count: 14,
      freshness_rule: { verified_recent: "Report date is no more than 2 calendar days old." },
    };
    const sourceMetadata = {
      retrieval_method: "Discovered and fetched from the official DHS page.",
      reporting_frequency: "Daily IDSP report",
      available_variables: ["Suspected and confirmed cases and deaths"],
      validation_status: "passed",
      validation_checks: ["PDF date, disease table, and district codes validated."],
      limitations: ["Preliminary report"],
      hospital_capacity_data_connected: false,
      hospital_capacity_note: "No verified official hospital capacity feed is connected.",
    };
    const districtResponse = {
      report_date: report.report_date,
      metric_period: "Daily",
      district_report_available: true,
      expected_district_count: 14,
      reported_district_count: 14,
      missing_district_codes: [],
      records: [{
        district_code: "TVM",
        district: "Thiruvananthapuram",
        disease: "Dengue",
        source_label: "Dengue",
        metric_unit: "reported cases",
        suspected_cases: 18,
        confirmed_cases: 2,
        reported_deaths: 0,
      }],
      source_url: report.source_url,
      note: "Death category not assigned.",
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/daily/latest")) return jsonResponse(report);
      if (path.endsWith("/daily/source-status")) return jsonResponse(sourceStatus);
      if (path.endsWith("/daily/diseases/daily")) return jsonResponse({ report_date: report.report_date, records: [dengue] });
      if (path.endsWith("/daily/diseases/month-to-date")) return jsonResponse({ report_date: report.report_date, records: [dengue] });
      if (path.endsWith("/daily/cumulative")) return jsonResponse({ report_date: report.report_date, records: [cumulativeDengue] });
      if (path.includes("/daily/districts")) return jsonResponse(districtResponse);
      if (path.endsWith("/daily/source")) return jsonResponse(sourceMetadata);
      return jsonResponse({ detail: "Not found" }, 404);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DailyIdspSurveillance />);
      await new Promise((resolve) => setTimeout(resolve, 0));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(container.textContent).toContain("2026-11-01");
    expect(container.textContent).toContain("Source publication date");
    expect(container.textContent).toContain("2026-11-02");
    expect(container.textContent).toContain("105");
    expect(container.textContent).toContain("80");
    expect(container.textContent).toContain("- (source dash; meaning unspecified)");
    expect(container.textContent).toContain("35,419");
    expect(container.textContent).toContain("13,244");
    expect(container.textContent).toContain("Preliminary official data");
    expect(container.textContent).toContain("Cumulative 2026");
    expect(container.textContent).toContain("No verified official hospital capacity feed is connected.");
  });

  it("shows a clear unavailable state when the daily report endpoint fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/daily/source-status")) {
        return jsonResponse({
          status: "data_not_available",
          source_access_status: "not_retrieved",
          source_name: "Kerala DHS IDSP",
          source_index_url: "https://dhs.kerala.gov.in/en/idsp-2/",
          snapshot_available: false,
          last_successful_retrieval: null,
          last_attempt: null,
          daily_district_report_available: false,
          reported_district_count: 0,
          expected_district_count: 14,
          freshness_rule: {},
        });
      }
      return jsonResponse({ detail: "No daily IDSP snapshot is available." }, 503);
    }));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DailyIdspSurveillance />);
      await new Promise((resolve) => setTimeout(resolve, 0));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(container.textContent).toContain("Current official daily data unavailable");
    expect(container.textContent).toContain("No historical dataset has been substituted");
  });
});
