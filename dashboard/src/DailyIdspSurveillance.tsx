import { useEffect, useMemo, useState } from "react";
import { ArrowUpRightFromSquare, Clock3, Database, MapPinned } from "lucide-react";
import { apiGet } from "./api";
import {
  EmptyState,
  ErrorState,
  FilterSelect,
  LoadingState,
  Notice,
  Panel,
  StatCard,
  TrendChart,
} from "./components";

type FreshnessStatus =
  | "verified_recent"
  | "official_delayed"
  | "historical"
  | "source_unavailable"
  | "data_not_available";

interface DailyRecord {
  disease: string;
  disease_subtype: string | null;
  source_label: string;
  suspected_cases: number | null;
  suspected_deaths: number | null;
  confirmed_cases: number | null;
  confirmed_deaths: number | null;
  source_values: Record<string, string>;
  source_value_status: Record<string, string>;
}

interface LatestReport {
  data_status: FreshnessStatus;
  report_date: string;
  source_post_published_at: string | null;
  retrieved_at_utc: string;
  source_name: string;
  source_page_url: string;
  source_url: string;
  source_sha256: string;
  dataset_version: string;
  provisional_warning: string;
  daily_district_report_available: boolean;
  reported_district_count: number;
  expected_district_count: number;
  statewide_records: DailyRecord[];
}

interface SourceStatus {
  status: FreshnessStatus;
  source_access_status: string;
  source_name: string;
  source_index_url: string;
  source_page_url?: string;
  source_url?: string;
  snapshot_available: boolean;
  report_date?: string;
  source_post_published_at?: string | null;
  last_successful_retrieval: string | null;
  last_attempt: { timestamp_utc: string; status: string; error?: string } | null;
  daily_district_report_available: boolean;
  reported_district_count: number;
  expected_district_count: number;
  freshness_rule: Record<string, string>;
  error?: string;
}

interface DistrictRecord {
  district_code: string;
  district: string;
  disease: string;
  disease_subtype: string | null;
  source_label: string;
  metric_unit: string;
  suspected_cases: number | null;
  confirmed_cases: number | null;
  reported_cases: number | null;
  reported_deaths: number | null;
  field_source_status: Record<string, string>;
}

interface DistrictResponse {
  report_date: string;
  metric_period: string;
  district_report_available: boolean;
  expected_district_count: number;
  reported_district_count: number;
  missing_district_codes: string[];
  disease_options: string[];
  records: DistrictRecord[];
  source_url: string;
  note: string;
}

interface SourceMetadata {
  retrieval_method: string;
  reporting_frequency: string;
  available_variables: string[];
  validation_status: string;
  validation_checks: string[];
  quality_flags?: Array<{ reason: string }>;
  limitations: string[];
  hospital_capacity_data_connected: boolean;
  hospital_capacity_note: string;
  count_dash_policy: string;
  backfill_status?: {
    discovered_2026_post_count: number;
    imported_date_count: number;
    discovered_report_dates: string[];
    imported_distinct_report_dates: string[];
    missing_from_discovered_posts: string[];
    calendar_dates_not_listed_by_index: string[];
    failed_discovered_dates: Array<{ report_date: string; error: string }>;
  } | null;
}

interface TrendsResponse {
  disease: string;
  reporting_period_start: string;
  reporting_period_end: string;
  report_count: number;
  calendar_dates_in_range: number;
  missing_report_dates: string[];
  missing_report_date_count: number;
  records: Array<{
    report_date: string;
    suspected_cases: number | null;
    suspected_deaths: number | null;
    confirmed_cases: number | null;
    confirmed_deaths: number | null;
    source_values: Record<string, string>;
    source_value_status: Record<string, string>;
  }>;
  summaries: Record<string, {
    current_period_start: string;
    current_period_end: string;
    previous_period_start: string;
    previous_period_end: string;
    metrics: Record<string, {
      current: {
        complete: boolean;
        reported_total: number | null;
        reports_received: number;
        expected_report_dates: number;
        missing_report_dates: string[];
        missing_numeric_value_dates: string[];
        comparison?: {
          absolute_change?: number;
          percentage_change?: number | null;
          interpretation?: string;
          reason?: string;
          available?: boolean;
        };
      };
      previous: { complete: boolean; reported_total: number | null };
    }>;
    adequacy_rule: string;
  }>;
  note: string;
  adequacy_rule?: string;
  provisional_warning?: string;
}

function useResource<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setData(null);
    setLoading(true);
    setError(null);
    apiGet<T>(path)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          setData(null);
          setError(reason instanceof Error ? reason.message : "The request failed unexpectedly.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path]);

  return { data, error, loading };
}

function formatNumber(value: number | null | undefined) {
  return value == null ? "Not reported" : new Intl.NumberFormat("en-IN").format(value);
}

function formatSourceValue(
  value: number | null | undefined,
  status: string | null | undefined,
) {
  if (status === "source_dash_uninterpreted") return "- (source dash; meaning unspecified)";
  if (status === "not_reported") return "Not reported";
  if (status === "unavailable" || status === "unavailable_in_source_format") return "Unavailable in source format";
  return formatNumber(value);
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return "Not available";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : `${new Intl.DateTimeFormat("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
      }).format(parsed)} UTC`;
}

function freshnessLabel(status: FreshnessStatus) {
  switch (status) {
    case "verified_recent": return "Verified and recent";
    case "official_delayed": return "Official but delayed";
    case "historical": return "Historical";
    case "source_unavailable": return "Source unavailable";
    case "data_not_available": return "Data not available";
  }
}

function DailyStatus({ status }: { status: FreshnessStatus }) {
  return <span className={`freshness-pill ${status === "verified_recent" ? "recent" : status === "official_delayed" || status === "historical" ? "delayed" : "unavailable"}`}>
    <span aria-hidden="true" />
    {freshnessLabel(status)}
  </span>;
}

export default function DailyIdspSurveillance() {
  const latest = useResource<LatestReport>("/api/live-surveillance/daily/latest");
  const sourceStatus = useResource<SourceStatus>("/api/live-surveillance/daily/source-status");
  const daily = useResource<{ report_date: string; records: DailyRecord[] }>(
    "/api/live-surveillance/daily/diseases/daily",
  );
  const monthToDate = useResource<{ report_date: string; records: DailyRecord[] }>(
    "/api/live-surveillance/daily/diseases/month-to-date",
  );
  const cumulative = useResource<{ report_date: string; records: DailyRecord[] }>(
    "/api/live-surveillance/daily/cumulative",
  );
  const source = useResource<SourceMetadata>("/api/live-surveillance/daily/source");
  const [districtDisease, setDistrictDisease] = useState("Dengue");
  const [trendDisease, setTrendDisease] = useState<"Dengue" | "Leptospirosis">("Dengue");
  const trends = useResource<TrendsResponse>(
    `/api/live-surveillance/daily/trends?disease=${trendDisease}`,
  );
  const districts = useResource<DistrictResponse>(
    `/api/live-surveillance/daily/districts?disease=${encodeURIComponent(districtDisease)}`,
  );

  const diseaseCount = useMemo(
    () => new Set((latest.data?.statewide_records ?? []).map((row) => row.disease)).size,
    [latest.data?.statewide_records],
  );
  const cumulativeRows = cumulative.data?.records ?? [];
  const dailyRows = daily.data?.records ?? [];
  const monthRows = monthToDate.data?.records ?? [];
  const districtRows = districts.data?.records ?? [];
  const highestSuspected = Math.max(0, ...districtRows.map((row) => row.suspected_cases ?? 0));
  const highestConfirmed = Math.max(0, ...districtRows.map((row) => row.confirmed_cases ?? 0));
  const highestOtherReported = Math.max(0, ...districtRows.map((row) => row.reported_cases ?? 0));
  const districtDiseaseOptions = districts.data?.disease_options?.length
    ? districts.data.disease_options
    : ["Dengue"];

  return (
    <div className="daily-idsp-sections">
      <Panel
        title="A. Latest Daily Surveillance"
        subtitle="Latest successfully imported daily DHS IDSP report. This is a retrieved snapshot, not a real-time feed."
        action={latest.data ? <DailyStatus status={latest.data.data_status} /> : undefined}
      >
        {latest.loading ? <LoadingState label="Loading the latest daily IDSP report…" /> : latest.error || !latest.data ? (
          <div className="daily-idsp-unavailable">
            <Notice title="Current official daily data unavailable" tone="warning">
              {latest.error ?? "No validated daily report snapshot is available. The separate historical reports are not substituted."}
              {" "}No historical dataset has been substituted for a current report.
            </Notice>
          </div>
        ) : (
          <>
            <div className="stats-grid daily-status-stats">
              <StatCard label="Report date" value={latest.data.report_date} detail="Date printed on the DHS report" icon={<Clock3 size={19} />} />
              <StatCard label="Source publication date" value={latest.data.source_post_published_at?.slice(0, 10) ?? "Not stated"} detail={formatTimestamp(latest.data.source_post_published_at)} icon={<Database size={19} />} tone="blue" />
              <StatCard label="Last successful retrieval" value={formatTimestamp(latest.data.retrieved_at_utc)} detail="UTC retrieval timestamp; distinct from publication" icon={<Database size={19} />} tone="amber" />
              <StatCard label="Diseases with reported rows" value={String(diseaseCount)} detail="Distinct source disease labels in this report" icon={<Database size={19} />} tone="amber" />
              <StatCard label="Districts covered" value={`${latest.data.reported_district_count}/${latest.data.expected_district_count}`} detail="Daily district table only" icon={<MapPinned size={19} />} tone="violet" />
            </div>
            <Notice title="Preliminary official data" tone="warning">{latest.data.provisional_warning}</Notice>
            {sourceStatus.data?.status === "source_unavailable" && (
              <Notice title="Latest retrieval failed; validated snapshot retained" tone="warning">
                {sourceStatus.data.last_attempt?.error ?? "The latest source retrieval failed."} The displayed report remains dated {latest.data.report_date}.
              </Notice>
            )}
            {daily.loading ? <LoadingState label="Loading source-reported daily values…" /> : daily.error ? (
              <ErrorState message={daily.error} />
            ) : (
              <div className="table-wrap">
                <table>
                  <caption>Daily reported cases and deaths · report dated {latest.data.report_date}</caption>
                  <thead><tr><th scope="col">Disease / source label</th><th scope="col">Suspected cases</th><th scope="col">Suspected deaths</th><th scope="col">Confirmed cases</th><th scope="col">Confirmed deaths</th></tr></thead>
                  <tbody>{dailyRows.map((row, index) => (
                    <tr key={`${row.disease}-${row.disease_subtype ?? ""}-${index}`}>
                      <td>{row.source_label}{row.disease_subtype ? ` · ${row.disease_subtype}` : ""}</td>
                      <td>{formatSourceValue(row.suspected_cases, row.source_value_status.suspected_cases)}</td>
                      <td>{formatSourceValue(row.suspected_deaths, row.source_value_status.suspected_deaths)}</td>
                      <td>{formatSourceValue(row.confirmed_cases, row.source_value_status.confirmed_cases)}</td>
                      <td>{formatSourceValue(row.confirmed_deaths, row.source_value_status.confirmed_deaths)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
            <p className="daily-idsp-footnote">
              A single report does not establish a change or an outbreak. The source's provisional figures may change after laboratory tests and death audits.
            </p>
          </>
        )}
      </Panel>

      <Panel
        title="B. 2026 Cumulative Disease Burden"
        subtitle="Cumulative 2026 values are running totals as printed by DHS—not daily counts and not sums across report dates."
        action={cumulative.data && <span className="mini-tag">As of {cumulative.data.report_date}</span>}
      >
        {cumulative.loading ? <LoadingState label="Loading cumulative 2026 source values…" /> : cumulative.error ? (
          <ErrorState message={cumulative.error} />
        ) : cumulativeRows.length === 0 ? <EmptyState>Cumulative 2026 disease statistics are unavailable.</EmptyState> : (
          <div className="table-wrap">
            <table>
              <caption>Cumulative reported cases and deaths · {cumulative.data?.report_date}</caption>
              <thead><tr><th scope="col">Disease</th><th scope="col">Suspected cases</th><th scope="col">Suspected deaths</th><th scope="col">Confirmed cases</th><th scope="col">Confirmed deaths</th></tr></thead>
              <tbody>{cumulativeRows.map((row) => (
                <tr key={`${row.disease}-${row.disease_subtype ?? ""}`}>
                  <td>{row.source_label}</td>
                  <td>{formatSourceValue(row.suspected_cases, row.source_value_status.suspected_cases)}</td>
                  <td>{formatSourceValue(row.suspected_deaths, row.source_value_status.suspected_deaths)}</td>
                  <td>{formatSourceValue(row.confirmed_cases, row.source_value_status.confirmed_cases)}</td>
                  <td>{formatSourceValue(row.confirmed_deaths, row.source_value_status.confirmed_deaths)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        <div className="daily-idsp-secondary">
          <h3>Present-month reported values</h3>
          {monthToDate.loading ? <LoadingState label="Loading present-month values…" /> : monthToDate.error ? (
            <ErrorState message={monthToDate.error} />
          ) : (
            <div className="table-wrap">
              <table>
                <caption>Present-month source values · {monthToDate.data?.report_date}</caption>
                <thead><tr><th scope="col">Disease / source label</th><th scope="col">Suspected cases</th><th scope="col">Suspected deaths</th><th scope="col">Confirmed cases</th><th scope="col">Confirmed deaths</th></tr></thead>
                <tbody>{monthRows.map((row, index) => (
                  <tr key={`${row.disease}-${row.disease_subtype ?? ""}-${index}`}>
                    <td>{row.source_label}{row.disease_subtype ? ` · ${row.disease_subtype}` : ""}</td>
                    <td>{formatSourceValue(row.suspected_cases, row.source_value_status.suspected_cases)}</td>
                    <td>{formatSourceValue(row.suspected_deaths, row.source_value_status.suspected_deaths)}</td>
                    <td>{formatSourceValue(row.confirmed_cases, row.source_value_status.confirmed_cases)}</td>
                    <td>{formatSourceValue(row.confirmed_deaths, row.source_value_status.confirmed_deaths)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </div>
      </Panel>

      <Panel
        title="C. District-wise Daily Reporting"
        subtitle="Daily district records from the latest validated DHS report. Counts are not normalized by population and do not indicate district risk."
        action={districts.data && <span className="mini-tag">{districts.data.reported_district_count}/{districts.data.expected_district_count} districts</span>}
      >
        <div className="live-filter-row">
          <FilterSelect
            label="Disease"
            value={districtDisease}
            options={districtDiseaseOptions.map((value) => ({ value, label: value }))}
            onChange={setDistrictDisease}
          />
        </div>
        {districts.loading ? <LoadingState label="Loading official district daily rows…" /> : districts.error ? (
          <ErrorState message={districts.error} />
        ) : !districts.data?.district_report_available ? (
          <>
            {districts.data?.missing_district_codes?.length ? (
              <Notice title="District reports unavailable" tone="warning">
                The daily report does not include usable rows for district codes: {districts.data.missing_district_codes.join(", ")}.
              </Notice>
            ) : null}
            <EmptyState>Daily district-level information is unavailable in this validated snapshot. No annual district totals are used as a substitute.</EmptyState>
          </>
        ) : (
          <>
            {districts.data.missing_district_codes.length > 0 && (
              <Notice title="District reports are missing" tone="warning">
                Missing district codes: {districts.data.missing_district_codes.join(", ")}. Missing reports are not treated as zero.
              </Notice>
            )}
            <Notice title="Counts are not risk classifications" tone="neutral">
              The districts with the highest reported counts are highlighted only for navigation. Absolute counts alone do not measure incidence or risk. {districts.data.note}
            </Notice>
            <div className="table-wrap">
              <table>
                <caption>{districtDisease} daily district counts · {districts.data.report_date}</caption>
                <thead><tr><th scope="col">District</th><th scope="col">Official code</th><th scope="col">Source metric / subtype</th><th scope="col">Suspected cases</th><th scope="col">Confirmed cases</th><th scope="col">Other source value</th><th scope="col">Reported deaths*</th></tr></thead>
                <tbody>{[...districtRows].sort((a, b) =>
                  Math.max(b.suspected_cases ?? -1, b.confirmed_cases ?? -1, b.reported_cases ?? -1)
                    - Math.max(a.suspected_cases ?? -1, a.confirmed_cases ?? -1, a.reported_cases ?? -1)
                  || a.district.localeCompare(b.district),
                ).map((row) => (
                  <tr key={`${row.district_code}-${row.disease}-${row.disease_subtype ?? ""}-${row.source_label}`}>
                    <td>{row.district}{(
                      (highestSuspected > 0 && row.suspected_cases === highestSuspected)
                      || (highestConfirmed > 0 && row.confirmed_cases === highestConfirmed)
                      || (highestOtherReported > 0 && row.reported_cases === highestOtherReported)
                    ) && <span className="daily-top-count">Highest reported</span>}</td>
                    <td>{row.district_code}</td>
                    <td>{row.source_label}{row.disease_subtype ? ` · ${row.disease_subtype}` : ""} · {row.metric_unit}</td>
                    <td>{formatSourceValue(row.suspected_cases, row.field_source_status?.suspected_cases ?? "unavailable_in_source_format")}</td>
                    <td>{formatSourceValue(row.confirmed_cases, row.field_source_status?.confirmed_cases ?? "unavailable_in_source_format")}</td>
                    <td>{formatSourceValue(row.reported_cases, row.field_source_status?.reported_cases ?? "unavailable_in_source_format")}</td>
                    <td>{formatSourceValue(row.reported_deaths, row.field_source_status?.reported_deaths ?? "unavailable_in_source_format")}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <p className="daily-idsp-footnote">*The district report provides one death field without suspected/confirmed classification. It is shown separately. Printed dashes are normalized to zero in numeric fields; blank source cells remain unavailable.</p>
          </>
        )}
      </Panel>

      <Panel
        title="D. Historical Daily Time Series and Period Summaries"
        subtitle="Daily observations from distinct imported 2026 report dates. Gaps and source-dash values are not treated as zero."
      >
        <div className="live-filter-row">
          <FilterSelect
            label="Disease"
            value={trendDisease}
            options={[
              { value: "Dengue", label: "Dengue" },
              { value: "Leptospirosis", label: "Leptospirosis" },
            ]}
            onChange={(value) => setTrendDisease(value as "Dengue" | "Leptospirosis")}
          />
        </div>
        {trends.loading ? <LoadingState label="Loading imported daily IDSP history…" /> : trends.error ? (
          <ErrorState message={trends.error} />
        ) : trends.data ? (
          <>
            <Notice title="Reporting completeness and provisional values" tone="warning">
              {trends.data.note} The source marks daily counts provisional. The chart contains reported dates only; missing dates are not interpolated.
            </Notice>
            <p className="daily-idsp-footnote">
              Imported report dates: {trends.data.report_count}; calendar dates in covered interval: {trends.data.calendar_dates_in_range}; absent report dates: {trends.data.missing_report_date_count}.
            </p>
            {trends.data.missing_report_dates.length > 0 && (
              <p className="daily-idsp-footnote">
                Missing report dates: {trends.data.missing_report_dates.join(", ")}
              </p>
            )}
            <TrendChart
              data={trends.data.records.map((row) => ({
                period: row.report_date,
                suspected_cases: row.suspected_cases,
                confirmed_cases: row.confirmed_cases,
              }))}
              dataKeys={[
                { key: "suspected_cases", label: "Suspected cases · daily" },
                { key: "confirmed_cases", label: "Confirmed cases · daily" },
              ]}
              ariaLabel={`${trendDisease} daily suspected and confirmed reported cases across imported DHS report dates`}
              height={290}
            />
            <div className="daily-summary-grid">
              {(["7_day", "30_day"] as const).map((window) => {
                const summary = trends.data?.summaries[window];
                if (!summary) return null;
                return (
                  <article className="daily-summary-card" key={window}>
                    <h3>{window === "7_day" ? "7-day" : "30-day"} reported totals</h3>
                    <p className="daily-idsp-footnote">
                      Current {summary.current_period_start} to {summary.current_period_end}; previous equivalent {summary.previous_period_start} to {summary.previous_period_end}.
                    </p>
                    <div className="table-wrap">
                      <table>
                        <thead><tr><th scope="col">Metric</th><th scope="col">Current</th><th scope="col">Previous</th><th scope="col">Comparison</th></tr></thead>
                        <tbody>{Object.entries(summary.metrics).map(([metric, periods]) => (
                          <tr key={metric}>
                            <th scope="row">{metric.replaceAll("_", " ")}</th>
                            <td>{periods.current.complete ? formatNumber(periods.current.reported_total) : `Incomplete (${periods.current.reports_received}/${periods.current.expected_report_dates} dates)`}</td>
                            <td>{periods.previous.complete ? formatNumber(periods.previous.reported_total) : "Incomplete"}</td>
                            <td>
                              {periods.current.comparison?.interpretation
                                ? `${periods.current.comparison.interpretation} Change: ${formatNumber(periods.current.comparison.absolute_change)}; percentage: ${periods.current.comparison.percentage_change == null ? "not defined" : `${periods.current.comparison.percentage_change}%`}.`
                                : periods.current.comparison?.reason ?? "Not comparable: incomplete reports/source values"}
                            </td>
                          </tr>
                        ))}</tbody>
                      </table>
                    </div>
                    <p className="daily-idsp-footnote">{summary.adequacy_rule}</p>
                  </article>
                );
              })}
            </div>
            <div className="table-wrap daily-history-table">
              <table>
                <caption>{trendDisease} daily source observations by actual report date</caption>
                <thead><tr><th scope="col">Report date</th><th scope="col">Suspected cases</th><th scope="col">Suspected deaths</th><th scope="col">Confirmed cases</th><th scope="col">Confirmed deaths</th></tr></thead>
                <tbody>{trends.data.records.map((row) => (
                  <tr key={row.report_date}>
                    <td>{row.report_date}</td>
                    <td>{formatSourceValue(row.suspected_cases, row.source_value_status.suspected_cases)}</td>
                    <td>{formatSourceValue(row.suspected_deaths, row.source_value_status.suspected_deaths)}</td>
                    <td>{formatSourceValue(row.confirmed_cases, row.source_value_status.confirmed_cases)}</td>
                    <td>{formatSourceValue(row.confirmed_deaths, row.source_value_status.confirmed_deaths)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </>
        ) : <EmptyState>No validated daily history is available.</EmptyState>}
      </Panel>

      <Panel title="E. Data Sources and Reliability" subtitle="Inspect the official source, retrieval evidence, validation and limitations">
        {source.loading ? <LoadingState label="Loading daily source metadata…" /> : source.error || !source.data ? (
          <ErrorState message={source.error ?? "Daily source metadata is unavailable."} />
        ) : (
          <>
            <div className="daily-source-links">
              <a href={sourceStatus.data?.source_index_url} target="_blank" rel="noreferrer">Official DHS IDSP index <ArrowUpRightFromSquare size={13} /></a>
              {latest.data && <a href={latest.data.source_page_url} target="_blank" rel="noreferrer">Report post · {latest.data.report_date} <ArrowUpRightFromSquare size={13} /></a>}
              {latest.data && <a href={latest.data.source_url} target="_blank" rel="noreferrer">Original daily report PDF <ArrowUpRightFromSquare size={13} /></a>}
            </div>
            <div className="daily-source-grid">
              <div>
                <h3>Retrieval and freshness</h3>
                <p>Source: <strong>{sourceStatus.data?.source_name ?? "Kerala DHS IDSP"}</strong></p>
                <p>Reporting frequency: <strong>{source.data.reporting_frequency}</strong></p>
                <p>Access status: <strong>{sourceStatus.data?.source_access_status ?? "Unavailable"}</strong></p>
                <p>Freshness status: <strong>{sourceStatus.data ? freshnessLabel(sourceStatus.data.status) : "Unavailable"}</strong></p>
                <p>DHS post publication timestamp: <strong>{formatTimestamp(sourceStatus.data?.source_post_published_at)}</strong></p>
                <p>Last successful retrieval: <strong>{formatTimestamp(sourceStatus.data?.last_successful_retrieval)}</strong></p>
                <p>Validation: <strong>{source.data.validation_status}</strong></p>
                <p>Source extraction method: {source.data.retrieval_method}</p>
              </div>
              <Notice title="Printed hyphen interpretation" tone="warning">
                {source.data.count_dash_policy}
              </Notice>
              {source.data.backfill_status && (
                <div className="daily-backfill-status">
                  <strong>2026 backfill status:</strong> {source.data.backfill_status.imported_date_count} distinct report dates retained from {source.data.backfill_status.discovered_2026_post_count} dated posts linked on the fetched index page.
                  {source.data.backfill_status.missing_from_discovered_posts.length > 0 && (
                    <p>Discovered but not imported: {source.data.backfill_status.missing_from_discovered_posts.join(", ")}</p>
                  )}
                  {source.data.backfill_status.calendar_dates_not_listed_by_index.length > 0 && (
                    <details>
                      <summary>Calendar dates not listed on the current index ({source.data.backfill_status.calendar_dates_not_listed_by_index.length})</summary>
                      <p>{source.data.backfill_status.calendar_dates_not_listed_by_index.join(", ")}</p>
                    </details>
                  )}
                </div>
              )}
              <div>
                <h3>Variables and checks</h3>
                <ul>{source.data.available_variables.map((value) => <li key={value}>{value}</li>)}</ul>
                <ul>{source.data.validation_checks.map((value) => <li key={value}>{value}</li>)}</ul>
              </div>
            </div>
            {sourceStatus.data && Object.entries(sourceStatus.data.freshness_rule ?? {}).map(([key, value]) => (
              <p className="daily-freshness-rule" key={key}><strong>{key.replaceAll("_", " ")}:</strong> {value}</p>
            ))}
            <ul>{source.data.limitations.map((value) => <li key={value}>{value}</li>)}</ul>
            {source.data.quality_flags?.map((flag, index) => (
              <p className="daily-freshness-rule" key={`${flag.reason}-${index}`}>{flag.reason}</p>
            ))}
            <Notice title="Hospital capacity is not connected" tone="neutral">
              {source.data.hospital_capacity_note}
            </Notice>
            <p className="daily-idsp-footnote">
              Daily trend comparisons require multiple compatible report snapshots. Cumulative totals are never added across dates. The daily IDSP series is kept separate from historical monthly disease datasets and the 2025 annual report.
            </p>
          </>
        )}
      </Panel>
    </div>
  );
}
