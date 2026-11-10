export type Disease = "Dengue" | "Leptospirosis";

export interface RecordRow {
  period?: string;
  year: number;
  month_num?: number;
  month_name?: string;
  district?: string;
  district_code?: string;
  disease: Disease;
  classification: string;
  classification_note?: string;
  source_file?: string;
  source_url?: string;
  cases: number;
  deaths: number;
  precipitation_sum_mm?: number;
  temperature_2m_mean_c?: number;
  temperature_2m_min_c?: number;
  temperature_2m_max_c?: number;
  weather_location_count?: number;
  weather_scope?: string;
  [key: string]: unknown;
}

export interface Overview {
  coverage: {
    monthly_period_start: string;
    monthly_period_end: string;
    monthly_periods: number;
    monthly_records: number;
    annual_year_start: number;
    annual_year_end: number;
    annual_district_records: number;
    districts: number;
    diseases: Disease[];
    latest_month: string;
    latest_month_records: number;
  };
  annual_statewide_totals: Array<{
    year: number;
    disease: Disease;
    classification: string;
    cases: number;
    deaths: number;
  }>;
  classification_by_year: Array<{
    year: number;
    classification: string;
    records: number;
  }>;
  forecasting_available: false;
}

export interface MonthlyResponse {
  options: { diseases: Disease[]; years: number[]; classifications: string[] };
  records: RecordRow[];
}

export interface DistrictResponse {
  records: RecordRow[];
  year: number;
  disease: Disease;
  classification: string;
  temporal_granularity: "annual";
}

export interface ClimateResponse {
  disease: Disease;
  classification: string | null;
  weather_scope: string;
  weather: Array<{
    period: string;
    precipitation_sum_mm: number;
    temperature_2m_mean_c: number;
    temperature_2m_min_c: number;
    temperature_2m_max_c: number;
    weather_location_count: number;
  }>;
  disease_records: RecordRow[];
  classification_options: string[];
}

export interface Methodology {
  sources: Array<{
    name: string;
    coverage: string;
    records: number;
    urls: string[];
    grain: string;
    documentation?: string;
    status?: string;
    report_date?: string | null;
    source_published_at?: string | null;
    last_retrieval?: string | null;
    reporting_frequency?: string;
    limitations?: string[];
  }>;
  classification_by_year: Array<{
    year: number;
    classification: string;
    records: number;
  }>;
  caveats: string[];
  reports: string[];
  forecasting_available: false;
  district_boundary_data_available: false;
}

export async function apiGet<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { headers: { Accept: "application/json" } });
  } catch {
    throw new Error("Cannot reach the CareGrid API. Start the FastAPI server and try again.");
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export function downloadCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return;
  const headers = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  const escape = (value: unknown) => {
    const text = value == null ? "" : String(value);
    return `"${text.replaceAll('"', '""')}"`;
  };
  const csv = [
    headers.map(escape).join(","),
    ...rows.map((row) => headers.map((header) => escape(row[header])).join(",")),
  ].join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
