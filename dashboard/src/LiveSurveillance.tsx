import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  ArrowUpRightFromSquare,
  CheckCircle2,
  Clock3,
  Database,
  MapPinned,
  ShieldAlert,
  Stethoscope,
} from "lucide-react";
import { apiGet } from "./api";
import DailyIdspSurveillance from "./DailyIdspSurveillance";
import {
  EmptyState,
  ErrorState,
  FilterSelect,
  LoadingState,
  Notice,
  PageHeading,
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

interface SourceStatus {
  status: FreshnessStatus;
  source_access_status: string;
  source_name: string;
  source_index_url: string;
  source_url: string;
  snapshot_available: boolean;
  publication_date: string | null;
  publication_date_note: string;
  last_modified_date?: string | null;
  reporting_period?: string;
  reporting_period_start?: string;
  reporting_period_end?: string;
  frequency?: string;
  last_successful_retrieval: string | null;
  retrieval_timestamp_basis?: string;
  source_response_date?: string | null;
  last_attempt: { timestamp_utc: string; status: string; error?: string } | null;
  dataset_version?: string;
  reported_district_count?: number;
  expected_district_count?: number;
  missing_districts: string[];
  statewide_district_reconciliation?: Array<{
    disease: string;
    classification: string;
    case_difference_district_minus_statewide: number;
    death_difference_district_minus_statewide: number | null;
    reconciles: boolean;
  }>;
  freshness_rule: Record<string, string>;
  message?: string;
  error?: string;
}

interface DiseaseStatistic {
  disease: string;
  classification: string;
  source_label: string;
  latest_period: string;
  previous_comparable_period: string | null;
  cases: number;
  previous_cases: number | null;
  cases_change: number | null;
  cases_change_percent: number | null;
  deaths: number | null;
  previous_deaths: number | null;
  deaths_change: number | null;
  change_interpretation: string;
  comparison_valid: boolean;
  source_name: string;
  source_url: string;
  data_status: FreshnessStatus;
  metric_unit: string;
}

interface SummaryResponse {
  data_status: FreshnessStatus;
  snapshot_data_status: FreshnessStatus;
  is_live: false;
  current_2026_information_available: false;
  reporting_period_start: string | null;
  reporting_period_end: string | null;
  source_publication_date: string | null;
  source_publication_date_note: string;
  last_successful_retrieval: string | null;
  source_status: SourceStatus;
  verified_disease_count: number;
  verified_monthly_series_count: number;
  district_count: number;
  expected_district_count: number;
  missing_districts: string[];
  disease_statistics: DiseaseStatistic[];
  message?: string;
}

interface DistrictResponse {
  data_status: FreshnessStatus;
  reporting_year: number;
  reporting_frequency: string;
  temporal_granularity: string;
  disease_options: string[];
  classification_options: string[];
  classification_options_by_disease: Record<string, string[]>;
  records: Array<{
    district: string;
    disease: string;
    classification: string;
    cases: number;
    deaths: number | null;
    rank_by_reported_count: number;
  }>;
  reported_districts: string[];
  missing_districts: string[];
  expected_district_count: number;
  comparison_note: string;
  source_url: string;
}

interface TrendResponse {
  disease_options?: string[];
  classification_options?: string[];
  classification_options_by_disease?: Record<string, string[]>;
  records: Array<{
    period: string;
    disease: string;
    classification: string;
    source_label: string;
    cases: number;
    deaths: number | null;
  }>;
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
  return value == null ? "—" : new Intl.NumberFormat("en-IN").format(value);
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return "Not available";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
      }).format(parsed) + " UTC";
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

function freshnessTone(status: FreshnessStatus) {
  if (status === "verified_recent") return "recent";
  if (status === "official_delayed" || status === "historical") return "delayed";
  return "unavailable";
}

function formatPeriod(value: string | null | undefined) {
  if (!value) return "Not available";
  const [year, month] = value.split("-");
  const parsedMonth = Number(month);
  if (!year || !Number.isInteger(parsedMonth) || parsedMonth < 1 || parsedMonth > 12) return value;
  return new Intl.DateTimeFormat("en", { month: "long", year: "numeric" })
    .format(new Date(Number(year), parsedMonth - 1, 1));
}

function ChangeIcon({ change }: { change: number | null }) {
  if (change == null || change === 0) return null;
  return change > 0
    ? <ArrowUpRight size={14} aria-hidden="true" />
    : <ArrowDownRight size={14} aria-hidden="true" />;
}

function StatusPill({ status }: { status: FreshnessStatus }) {
  return (
    <span className={`freshness-pill ${freshnessTone(status)}`}>
      <span aria-hidden="true" />
      {freshnessLabel(status)}
    </span>
  );
}

function DiseaseCard({ statistic }: { statistic: DiseaseStatistic }) {
  const changeClass = statistic.cases_change == null
    ? "unchanged"
    : statistic.cases_change > 0
      ? "increased"
      : statistic.cases_change < 0
        ? "decreased"
        : "unchanged";

  return (
    <article className="live-disease-card">
      <div className="live-card-title">
        <div>
          <strong>{statistic.disease}</strong>
          <span>{statistic.classification}</span>
        </div>
        <StatusPill status={statistic.data_status} />
      </div>
      <div className="live-card-cases">
        <strong>{formatNumber(statistic.cases)}</strong>
        <span>{statistic.metric_unit}</span>
      </div>
      <dl className="live-card-details">
        <div><dt>Previous comparable month</dt><dd>{formatPeriod(statistic.previous_comparable_period)}</dd></div>
        <div>
          <dt>Change</dt>
          <dd className={changeClass}>
            <ChangeIcon change={statistic.cases_change} />
            {statistic.cases_change == null
              ? "Not comparable"
              : `${statistic.cases_change > 0 ? "+" : ""}${formatNumber(statistic.cases_change)} (${statistic.cases_change_percent == null ? "percentage n/a" : `${statistic.cases_change_percent}%`})`}
          </dd>
        </div>
        <div><dt>Reported deaths</dt><dd>{formatNumber(statistic.deaths)}</dd></div>
        <div><dt>Reporting period</dt><dd>{formatPeriod(statistic.latest_period)}</dd></div>
      </dl>
      <p className="live-card-interpretation">{statistic.change_interpretation}</p>
      <a href={statistic.source_url} target="_blank" rel="noreferrer">
        {statistic.source_name} <ArrowUpRightFromSquare size={12} />
      </a>
    </article>
  );
}

function HistoricalAnnualComparison() {
  const summary = useResource<SummaryResponse>("/api/live-surveillance/summary");
  const [districtDisease, setDistrictDisease] = useState("Dengue");
  const [districtClassification, setDistrictClassification] = useState("Confirmed");
  const [trendDisease, setTrendDisease] = useState("Dengue");
  const [trendClassification, setTrendClassification] = useState("Confirmed");
  const trendPath = `/api/live-surveillance/trends?disease=${encodeURIComponent(trendDisease)}&classification=${encodeURIComponent(trendClassification)}`;
  const districtPath = `/api/live-surveillance/districts?disease=${encodeURIComponent(districtDisease)}&classification=${encodeURIComponent(districtClassification)}`;
  const trends = useResource<TrendResponse>(trendPath);
  const districts = useResource<DistrictResponse>(districtPath);

  const diseaseCards = useMemo(() => {
    const records = summary.data?.disease_statistics ?? [];
    return [...records].sort((a, b) => {
      const priority = (name: string) => name === "Dengue" ? 0 : name === "Leptospirosis" ? 1 : 2;
      return priority(a.disease) - priority(b.disease)
        || a.disease.localeCompare(b.disease)
        || a.classification.localeCompare(b.classification);
    });
  }, [summary.data?.disease_statistics]);

  if (summary.loading) return <LoadingState label="Loading the latest verified official report…" />;
  if (summary.error || !summary.data) {
    return <ErrorState message={summary.error ?? "The public-health surveillance summary is unavailable."} />;
  }

  const data = summary.data;
  const sourceStatus = data.source_status;
  const chartRows = trends.data?.records ?? [];
  const trendDiseaseOptions = [...new Set(diseaseCards.map((row) => row.disease))];
  const trendClassificationOptions = [...new Set(diseaseCards
    .filter((row) => row.disease === trendDisease)
    .map((row) => row.classification))];
  const districtClassificationOptions = districts.data?.classification_options_by_disease[districtDisease] ?? ["Confirmed"];
  const chartPoints = chartRows.map((row) => ({
    period: row.period ?? "",
    cases: row.cases,
  }));
  const chartKeys = [{ key: "cases", label: `${trendDisease} · ${trendClassification}` }];

  return (
    <>
      <PageHeading
        eyebrow="D. HISTORICAL ANNUAL COMPARISON"
        title="2025 DHS annual report"
        description="Historical annual-report data with statewide monthly tables and annual district records. These figures are separate from the 2026 daily IDSP reports."
        action={<StatusPill status={data.data_status} />}
      />
      <Notice title="Historical 2025 report — not current daily surveillance" tone="neutral">
        The records below are from the DHS 2025 annual report. They are retained for historical comparison only and are not combined with the separate 2026 daily IDSP report.
      </Notice>

      <div className="live-status-banner">
        <div className="live-status-icon"><ShieldAlert size={20} /></div>
        <div className="live-status-copy">
          <strong>{data.message ?? sourceStatus.message ?? "Latest available official report is delayed."}</strong>
          <span>{sourceStatus.source_name} · reporting period {data.reporting_period_start ?? "not available"} to {data.reporting_period_end ?? "not available"}</span>
        </div>
        <StatusPill status={data.data_status} />
      </div>

      <div className="stats-grid live-overview-stats">
        <StatCard label="Latest reporting period" value={formatPeriod(data.reporting_period_end)} detail="Monthly records are statewide" icon={<Clock3 size={19} />} />
        <StatCard label="Formal publication date" value={data.source_publication_date ?? "Not stated"} detail={sourceStatus.last_modified_date ? `PDF server last modified ${sourceStatus.last_modified_date}; not a publication date` : data.source_publication_date_note} icon={<Database size={19} />} tone="blue" />
        <StatCard label="Last successful import" value={formatTimestamp(data.last_successful_retrieval)} detail="Timestamp for the retained report snapshot" icon={<CheckCircle2 size={19} />} tone="amber" />
        <StatCard label="Diseases with monthly data" value={formatNumber(data.verified_disease_count)} detail={`${formatNumber(data.verified_monthly_series_count)} separate source series · ${formatNumber(data.district_count)} of ${formatNumber(data.expected_district_count)} districts have annual tables`} icon={<MapPinned size={19} />} tone="violet" />
      </div>

      {sourceStatus.status === "source_unavailable" && (
        <Notice title="Official source currently unavailable; cached snapshot retained" tone="warning">
          {sourceStatus.last_attempt?.error ?? "The last retrieval attempt failed."} The displayed report remains the previously validated 2025 snapshot.
        </Notice>
      )}
      {sourceStatus.status === "data_not_available" && (
        <Notice title="Current official data unavailable" tone="neutral">
          No valid report snapshot is loaded. No historical dataset has been substituted for current surveillance.
        </Notice>
      )}

      <Panel
        title="2025 monthly reported disease counts"
        subtitle="December 2025 compared with November 2025, keeping source classifications and units separate"
        action={<span className="mini-tag">{diseaseCards.length} reported series</span>}
      >
        {diseaseCards.length === 0
          ? <EmptyState>No verified disease records are currently available.</EmptyState>
          : <div className="live-disease-grid">{diseaseCards.map((statistic) => (
            <DiseaseCard
              key={`${statistic.disease}-${statistic.classification}-${statistic.metric_unit}`}
              statistic={statistic}
            />
          ))}</div>}
      </Panel>

      <Panel
        title="Monthly trend analysis"
        subtitle="Statewide official monthly counts · 2025 only"
        action={<StatusPill status={data.snapshot_data_status} />}
      >
        {sourceStatus.snapshot_available ? (
          <>
            <div className="live-filter-row">
              <FilterSelect
                label="Disease"
                value={trendDisease}
                options={trendDiseaseOptions.map((value) => ({ value, label: value }))}
                onChange={(value) => {
                  setTrendDisease(value);
                  const classifications = [...new Set(diseaseCards
                    .filter((row) => row.disease === value)
                    .map((row) => row.classification))];
                  setTrendClassification(classifications[0] ?? "");
                }}
              />
              <FilterSelect
                label="Source classification"
                value={trendClassification}
                options={trendClassificationOptions.map((value) => ({ value, label: value }))}
                onChange={setTrendClassification}
              />
            </div>
            {trends.loading ? <LoadingState label="Loading observed monthly values…" /> : trends.error ? (
              <ErrorState message={trends.error} />
            ) : (
              <>
                <TrendChart
                  data={chartPoints}
                  dataKeys={chartKeys}
                  ariaLabel={`${trendDisease} monthly reported case counts, ${trendClassification}, 2025`}
                  height={270}
                />
                {chartRows.length > 0 && (
                  <div className="table-wrap live-trend-table">
                    <table>
                      <caption>{trendDisease} · {trendClassification} · reported monthly values</caption>
                      <thead><tr><th scope="col">Reporting month</th><th scope="col">Cases</th><th scope="col">Deaths</th><th scope="col">Source label</th></tr></thead>
                      <tbody>{chartRows.map((row) => (
                        <tr key={`${row.period}-${row.disease}-${row.classification}`}>
                          <td>{formatPeriod(row.period)}</td><td>{formatNumber(row.cases)}</td>
                          <td>{formatNumber(row.deaths)}</td><td>{row.source_label}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </>
        ) : <EmptyState>Monthly disease records are unavailable; no historical dataset is substituted.</EmptyState>}
        <div className="chart-caption">Monthly counts remain at statewide grain. Comparisons are descriptive and not outbreak determinations.</div>
      </Panel>

      <Panel
        title="District situation"
        subtitle="Annual district records from the 2025 DHS report; never district-month estimates"
        action={<span className="mini-tag">{districts.data?.reporting_year ?? "2025"} · annual</span>}
      >
        {sourceStatus.snapshot_available && <div className="live-filter-row">
          <FilterSelect
            label="Disease"
            value={districtDisease}
            options={districts.data?.disease_options.map((value) => ({ value, label: value })) ?? [{ value: "Dengue", label: "Dengue" }]}
            onChange={(value) => {
              setDistrictDisease(value);
              const nextClassifications = districts.data?.classification_options_by_disease[value] ?? [];
              setDistrictClassification(nextClassifications[0] ?? "");
            }}
          />
          <FilterSelect
            label="Source classification"
            value={districtClassification}
            options={districtClassificationOptions.map((value) => ({ value, label: value }))}
            onChange={setDistrictClassification}
          />
        </div>}
        {!sourceStatus.snapshot_available ? <EmptyState>Annual district records are unavailable; historical district records are not presented as current.</EmptyState> : districts.loading ? <LoadingState label="Loading annual district report rows…" /> : districts.error ? (
          <ErrorState message={districts.error} />
        ) : districts.data && (
          <>
            <Notice title="Reported counts are not district risk scores" tone="neutral">
              {districts.data.comparison_note} {districts.data.missing_districts.length
                ? `Missing district report: ${districts.data.missing_districts.join(", ")}. Missing values are not zero.`
                : "All districts are present in the report."}
            </Notice>
            {districts.data.records.length === 0 ? <EmptyState>No district records match this disease and source classification.</EmptyState> : (
              <div className="table-wrap">
                <table>
                  <caption>Annual reported counts by district, 2025 · {districtDisease} · {districtClassification}</caption>
                  <thead><tr><th scope="col">District</th><th scope="col">Reported cases</th><th scope="col">Reported deaths</th><th scope="col">Rank by reported count</th></tr></thead>
                  <tbody>{districts.data.records.map((row) => (
                    <tr key={`${row.district}-${row.disease}-${row.classification}`}>
                      <td>{row.district}</td><td>{formatNumber(row.cases)}</td>
                      <td>{formatNumber(row.deaths)}</td><td>{row.rank_by_reported_count}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </>
        )}
      </Panel>

      <Panel title="Data source and validation" subtitle="Inspect the DHS source, retrieval evidence and known limitations">
        <SourceMethodology status={sourceStatus} />
      </Panel>

    </>
  );
}

function SourceMethodology({ status }: { status: SourceStatus }) {
  const source = useResource<{
    retrieval_method: string;
    reporting_frequency: string;
    available_variables: string[];
    validation_status: string;
    validation_checks: string[];
    limitations: string[];
    dataset_version: string;
    source_sha256: string;
    retrieval_timestamp_basis?: string;
    source_response_date?: string | null;
    suspicious_value_flags?: Array<{ reason: string }>;
  }>("/api/live-surveillance/source");
  if (source.loading) return <LoadingState label="Loading source and validation metadata…" />;
  if (source.error || !source.data) return <ErrorState message={source.error ?? "Source metadata is unavailable."} />;
  const metadata = source.data;
  return (
    <div className="source-methodology">
      <div className="source-cards">
        <article className="source-card">
          <div className="source-card-icon"><Database size={18} /></div>
          <div className="source-card-body">
            <h3>{status.source_name}</h3>
            <div className="source-coverage">
              {status.reporting_period ?? "Reporting period unavailable"} <span>·</span> {status.frequency ?? metadata.reporting_frequency}
            </div>
            <p>{metadata.retrieval_method}</p>
            <p>{status.publication_date_note}</p>
            <div className="source-links">
              <a href={status.source_index_url} target="_blank" rel="noreferrer">Official DHS index <ArrowUpRightFromSquare size={12} /></a>
              <a href={status.source_url} target="_blank" rel="noreferrer">Original report PDF <ArrowUpRightFromSquare size={12} /></a>
            </div>
          </div>
        </article>
      </div>
      <div className="source-method-grid">
        <div>
          <h3>Retrieval and validation</h3>
          <p>Retrieval status: <strong>{status.source_access_status}</strong></p>
          <p>Last successful import: <strong>{formatTimestamp(status.last_successful_retrieval)}</strong></p>
          <p>Timestamp basis: <strong>{status.retrieval_timestamp_basis ?? "Not recorded"}</strong></p>
          <p>HTTP response date: <strong>{status.source_response_date ?? "Not recorded"}</strong></p>
          <p>Last modified HTTP date: <strong>{status.last_modified_date ?? "Not available"}</strong> (not a formal publication date)</p>
          <p>Validation: <strong>{metadata.validation_status}</strong></p>
          <p>Dataset version: <code>{metadata.dataset_version ?? "Unavailable"}</code></p>
          <p>PDF SHA-256: <code>{metadata.source_sha256 ?? "Unavailable"}</code></p>
          <ul>{(metadata.validation_checks ?? []).map((check) => <li key={check}>{check}</li>)}</ul>
          {(metadata.suspicious_value_flags ?? []).map((flag, index) => (
            <p className="reconciliation-note" key={`${flag.reason}-${index}`}>{flag.reason}</p>
          ))}
        </div>
        <div>
          <h3>Variables available</h3>
          <ul>{(metadata.available_variables ?? []).map((variable) => <li key={variable}>{variable}</li>)}</ul>
          <h3>Limitations</h3>
          <ul>{(metadata.limitations ?? []).map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
          {status.statewide_district_reconciliation && status.statewide_district_reconciliation.some((row) => !row.reconciles) && (
            <p className="reconciliation-note">
              District and statewide annual totals have unreconciled differences for {status.statewide_district_reconciliation.filter((row) => !row.reconciles).length} source disease/classification rows. The reported totals are not adjusted.
            </p>
          )}
        </div>
      </div>
      {status.last_attempt?.error && <Notice title="Last source retrieval attempt failed" tone="warning">{status.last_attempt.error}</Notice>}
    </div>
  );
}

export default function LiveSurveillancePage() {
  return (
    <>
      <PageHeading
        eyebrow="KERALA DAILY HEALTH SURVEILLANCE"
        title="Live Kerala Health Monitor"
        description="Latest retrieved official DHS IDSP report, with report date, retrieval time, provisional status and historical data kept distinct."
      />
      <DailyIdspSurveillance />
      <HistoricalAnnualComparison />
      <div className="live-health-disclaimer">
        <Stethoscope size={16} aria-hidden="true" />
        <span>This is a descriptive public-health reporting monitor. It does not provide diagnoses, individual risk scores, medical recommendations or real-time outbreak detection.</span>
      </div>
    </>
  );
}
