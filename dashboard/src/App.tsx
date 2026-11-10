import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  ArrowUpRightFromSquare,
  BarChart3,
  Bed,
  BookOpenText,
  ChevronDown,
  CircleHelp,
  CloudRain,
  Download,
  FileSpreadsheet,
  LayoutDashboard,
  MapPinned,
  Menu,
  Shield,
  ShieldAlert,
  SlidersHorizontal,
  Stethoscope,
  Thermometer,
  X,
} from "lucide-react";
import LiveSurveillancePage from "./LiveSurveillance";
import ForecastingExperimentPage from "./ForecastingExperiment";
import {
  apiGet,
  downloadCsv,
  type ClimateResponse,
  type DistrictResponse,
  type Disease,
  type Methodology,
  type MonthlyResponse,
  type Overview,
  type RecordRow,
} from "./api";
import {
  DistrictChart,
  EmptyState,
  ErrorState,
  FilterSelect,
  LoadingState,
  Notice,
  PageHeading,
  Panel,
  StatCard,
  TrendChart,
  WeatherChart,
} from "./components";

type PageId =
  | "overview"
  | "surveillance"
  | "live-surveillance"
  | "districts"
  | "climate"
  | "forecasts"
  | "capacity"
  | "methodology";

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, group: "Workspace" },
  { id: "surveillance", label: "Disease surveillance", icon: Activity, group: "Workspace" },
  { id: "live-surveillance", label: "Live Kerala Health Monitor", icon: ShieldAlert, group: "Workspace" },
  { id: "districts", label: "District explorer", icon: MapPinned, group: "Workspace" },
  { id: "climate", label: "Climate insights", icon: CloudRain, group: "Workspace" },
  { id: "forecasts", label: "Forecasts & risk", icon: BarChart3, group: "Planning" },
  { id: "capacity", label: "Capacity simulator", icon: Bed, group: "Planning" },
  { id: "methodology", label: "Sources & methodology", icon: BookOpenText, group: "About" },
] as const;

const pageMeta: Record<PageId, { title: string; subtitle: string }> = {
  overview: { title: "Overview", subtitle: "Kerala public-health intelligence" },
  surveillance: { title: "Disease surveillance", subtitle: "Observed monthly statewide reports" },
  "live-surveillance": { title: "Live Kerala Health Monitor", subtitle: "Latest official report · not a live feed" },
  districts: { title: "District explorer", subtitle: "Annual district records · 2020–2024" },
  climate: { title: "Climate insights", subtitle: "Historical weather and reported disease series" },
  forecasts: { title: "Forecasts & risk assessment", subtitle: "Model readiness and evaluation status" },
  capacity: { title: "Hospital capacity simulator", subtitle: "Hypothetical planning scenarios only" },
  methodology: { title: "Sources & methodology", subtitle: "Data lineage, coverage and limitations" },
};

function useResource<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
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

function fmt(value: number) {
  return new Intl.NumberFormat("en-IN").format(value);
}

function monthLabel(value: string) {
  const [year, month] = value.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return new Intl.DateTimeFormat("en", { month: "short", year: "2-digit" }).format(date);
}

function makeClassSeries(rows: RecordRow[], metric: "cases" | "deaths") {
  const groups = new Map<string, { key: string; label: string }>();
  const data = new Map<string, Record<string, string | number | null>>();
  for (const row of rows) {
    if (!row.period) continue;
    const key = `y${row.year}_${row.classification.toLowerCase().replaceAll(/[^a-z0-9]+/g, "_")}`;
    groups.set(key, { key, label: `${row.year} · ${row.classification}` });
    const point = data.get(row.period) ?? { period: monthLabel(row.period) };
    point[key] = row[metric];
    data.set(row.period, point);
  }
  return {
    series: [...groups.values()],
    points: [...data.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, value]) => value),
  };
}

function formatClassification(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\bnot\b/, "not")
    .replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
}

function Shell({
  page,
  onNavigate,
  children,
}: {
  page: PageId;
  onNavigate: (page: PageId) => void;
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [health, setHealth] = useState<"available" | "degraded" | "checking">("checking");
  useEffect(() => {
    apiGet<{ status: "available" | "degraded" }>("/api/health")
      .then((result) => setHealth(result.status))
      .catch(() => setHealth("degraded"));
  }, []);

  const choosePage = (id: PageId) => {
    onNavigate(id);
    setMobileOpen(false);
  };

  return (
    <div className="app-shell">
      {mobileOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-symbol"><Shield size={22} strokeWidth={2.2} /></div>
          <div><strong>CareGrid</strong><span>SENTINEL</span></div>
          <button className="mobile-close" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button>
        </div>
        <div className="workspace-switch">
          <div className="workspace-mark">KL</div>
          <div className="workspace-copy"><strong>Kerala workspace</strong><span>Historical data</span></div>
          <ChevronDown size={16} />
        </div>
        {["Workspace", "Planning", "About"].map((group) => (
          <div className="nav-group" key={group}>
            <div className="nav-label">{group}</div>
            {navigation.filter((item) => item.group === group).map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`nav-item ${page === item.id ? "active" : ""}`}
                  onClick={() => choosePage(item.id)}
                  aria-current={page === item.id ? "page" : undefined}
                >
                  <Icon size={17} strokeWidth={1.8} /><span>{item.label}</span>
                  {item.id === "forecasts" && <span className="nav-pill">Hindcast</span>}
                </button>
              );
            })}
          </div>
        ))}
        <div className="sidebar-bottom">
          <div className="sidebar-status"><span className={`status-dot ${health}`} />{health === "available" ? "Data sources ready" : health === "degraded" ? "Data unavailable" : "Checking data…"}</div>
          <div className="sidebar-foot">CareGrid Sentinel <span>v1.0 · Kerala</span></div>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <button className="mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={20} /></button>
          <div className="breadcrumb"><span>CareGrid Sentinel</span><span className="crumb-slash">/</span><strong>{pageMeta[page].title}</strong></div>
          <div className="topbar-right">
            <span className="historical-badge"><span /> HISTORICAL DATA</span>
            <button className="help-button" aria-label="About this application" onClick={() => choosePage("methodology")}><CircleHelp size={18} /></button>
          </div>
        </header>
        <main className="content">{children}</main>
        <footer className="app-footer">
          <span>CareGrid Sentinel · Kerala</span>
          <span>Descriptive public-health data · Not for diagnosis or clinical decisions</span>
        </footer>
      </div>
    </div>
  );
}

function OverviewPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const overview = useResource<Overview>("/api/overview");
  const monthly = useResource<MonthlyResponse>("/api/disease/monthly");
  if (overview.loading || monthly.loading) return <LoadingState />;
  if (overview.error || monthly.error || !overview.data || !monthly.data)
    return <ErrorState message={overview.error ?? monthly.error ?? "Overview data is unavailable."} />;

  const { coverage } = overview.data;
  const dengue = makeClassSeries(monthly.data.records.filter((row) => row.disease === "Dengue"), "cases");
  const lepto = makeClassSeries(monthly.data.records.filter((row) => row.disease === "Leptospirosis"), "cases");
  const annualDengue = overview.data.annual_statewide_totals.filter((row) => row.disease === "Dengue");
  return (
    <>
      <PageHeading eyebrow="KERALA · HISTORICAL SURVEILLANCE" title="Public health, in context." description="A clear view of validated disease reporting and historical climate signals across Kerala." action={<span className="period-chip"><span className="period-dot" />{coverage.monthly_period_start} — {coverage.monthly_period_end}</span>} />
      <Notice title="Observed data only" tone="info">
        The dashboard summarizes reported records. No forecast, live alert, district-month estimate, or hospital status is generated.
      </Notice>
      <div className="stats-grid">
        <StatCard label="Monthly observations" value={fmt(coverage.monthly_records)} detail={`${coverage.monthly_periods} statewide reporting months`} icon={<Activity size={19} />} />
        <StatCard label="District-year records" value={fmt(coverage.annual_district_records)} detail={`${coverage.districts} districts · annual grain`} icon={<MapPinned size={19} />} tone="blue" />
        <StatCard label="Reporting period" value={`${coverage.annual_year_start}–${coverage.annual_year_end}`} detail="Annual district dataset" icon={<FileSpreadsheet size={19} />} tone="amber" />
        <StatCard label="Latest monthly data" value={coverage.latest_month} detail={`${coverage.latest_month_records} statewide disease rows`} icon={<CloudRain size={19} />} tone="violet" />
      </div>
      <div className="section-title-row"><div><h2>Surveillance overview</h2><p>Monthly reported cases · source categories kept distinct</p></div><button className="text-button" onClick={() => onNavigate("surveillance")}>Explore surveillance <ArrowUpRight size={15} /></button></div>
      <div className="grid-two">
        <Panel title="Dengue" subtitle="Kerala · reported cases per month" action={<span className="mini-tag">48 months</span>}>
          <TrendChart data={dengue.points} dataKeys={dengue.series} ariaLabel="Dengue monthly reported cases by year and source classification" height={260} />
          <div className="chart-caption">Each line represents a year and its original reporting category; categories are not harmonized.</div>
        </Panel>
        <Panel title="Leptospirosis" subtitle="Kerala · reported cases per month" action={<span className="mini-tag">48 months</span>}>
          <TrendChart data={lepto.points} dataKeys={lepto.series} ariaLabel="Leptospirosis monthly reported cases by year and source classification" height={260} />
          <div className="chart-caption">Each line represents a year and its original reporting category; categories are not harmonized.</div>
        </Panel>
      </div>
      <div className="grid-two overview-bottom">
        <Panel title="Annual dengue totals" subtitle="Statewide source totals · classifications shown separately" action={<span className="mini-tag">2021–2024</span>}>
          <div className="totals-list">
            {annualDengue.map((row) => (
              <div className="total-row" key={`${row.year}-${row.classification}`}>
                <span className="total-year">{row.year}</span>
                <span className="classification-chip">{formatClassification(row.classification)}</span>
                <strong>{fmt(row.cases)}</strong><span className="total-muted">cases</span>
                <span className="total-muted">{fmt(row.deaths)} deaths</span>
              </div>
            ))}
          </div>
          <div className="chart-caption">Monthly statewide totals; no classification harmonization is implied.</div>
        </Panel>
        <div className="insight-card">
          <div className="insight-icon"><ShieldAlert size={20} /></div>
          <div className="insight-kicker">READINESS CHECK</div>
          <h3>Forecasting remains unavailable</h3>
          <p>Four years of statewide monthly reports are not district-month observations and do not provide a defensible forecast evaluation.</p>
          <button className="text-button" onClick={() => onNavigate("forecasts")}>View model readiness <ArrowUpRight size={15} /></button>
        </div>
      </div>
    </>
  );
}

function SurveillancePage() {
  const [disease, setDisease] = useState("Dengue");
  const [year, setYear] = useState("2024");
  const [classification, setClassification] = useState("Confirmed");
  const [districtYear, setDistrictYear] = useState("2024");
  const [districtClassification, setDistrictClassification] = useState<"Confirmed" | "Probable">("Confirmed");
  const path = `/api/disease/monthly?disease=${disease}${year === "all" ? "" : `&year=${year}`}${classification === "all" ? "" : `&classification=${encodeURIComponent(classification)}`}`;
  const districtPath = `/api/districts?year=${districtYear}&disease=${disease}&classification=${districtClassification}`;
  const response = useResource<MonthlyResponse>(path);
  const districtResponse = useResource<DistrictResponse>(districtPath);
  if (response.loading || districtResponse.loading) return <LoadingState />;
  if (response.error || !response.data || districtResponse.error || !districtResponse.data)
    return <ErrorState message={response.error ?? districtResponse.error ?? "Surveillance data are unavailable."} />;
  const records = response.data.records;
  const districtRecords = districtResponse.data.records;
  const chart = makeClassSeries(records, "cases");
  const caseTotal = classification === "all" ? null : records.reduce((sum, row) => sum + row.cases, 0);
  const deathsTotal = classification === "all" ? null : records.reduce((sum, row) => sum + row.deaths, 0);
  const exportRows = records as unknown as Record<string, unknown>[];

  return (
    <>
      <PageHeading eyebrow="OBSERVED REPORTS" title="Disease surveillance" description="Explore statewide monthly cases and deaths while retaining the source's year-specific reporting classifications." action={<button className="button button-primary" disabled={!records.length} onClick={() => downloadCsv("caregrid-monthly-surveillance.csv", exportRows)}><Download size={16} /> Export CSV</button>} />
      <div className="filter-bar">
        <div className="filter-bar-title"><SlidersHorizontal size={17} /><span>Filters</span></div>
        <FilterSelect label="Disease" value={disease} options={[{ value: "Dengue", label: "Dengue" }, { value: "Leptospirosis", label: "Leptospirosis" }]} onChange={setDisease} />
        <FilterSelect label="Year" value={year} options={[{ value: "all", label: "All years" }, ...response.data.options.years.map((item) => ({ value: String(item), label: String(item) }))]} onChange={setYear} />
        <FilterSelect label="Source classification" value={classification} options={[{ value: "all", label: "All source labels" }, ...response.data.options.classifications.map((item) => ({ value: item, label: formatClassification(item) }))]} onChange={setClassification} />
      </div>
      <Notice title="Source classifications are not interchangeable">
        2021 does not split probable status, 2022 monthly values are reported as the non-probable category, and 2023–2024 are labelled Confirmed. Use the classification filter before comparing totals.
      </Notice>
      <div className="stats-grid stats-grid-three">
        <StatCard label="Displayed observations" value={fmt(records.length)} detail="Monthly statewide rows" icon={<Activity size={19} />} />
        <StatCard label="Reported cases" value={caseTotal === null ? "—" : fmt(caseTotal)} detail={caseTotal === null ? "Select one source label" : "Selected filters only"} icon={<Stethoscope size={19} />} tone="blue" />
        <StatCard label="Reported deaths" value={deathsTotal === null ? "—" : fmt(deathsTotal)} detail={deathsTotal === null ? "Select one source label" : "Selected filters only"} icon={<ShieldAlert size={19} />} tone="amber" />
      </div>
      <Panel title={`${disease} monthly cases`} subtitle="Statewide reports · observed values only" action={<span className="mini-tag">{records.length} records</span>}>
        <TrendChart data={chart.points} dataKeys={chart.series} ariaLabel={`${disease} monthly cases for selected source classifications`} height={315} />
        {records.length > 0 && <div className="chart-caption">The line series is separated by year and source classification; no values are filled for missing months.</div>}
      </Panel>
      <Panel title="Monthly records" subtitle="Source provenance retained in each exported row" className="table-panel">
        {records.length === 0 ? <EmptyState>No observations match the selected filters.</EmptyState> : (
          <div className="table-wrap">
            <table><thead><tr><th>Month</th><th>Year</th><th>Source classification</th><th>Cases</th><th>Deaths</th><th>Source document</th></tr></thead>
              <tbody>{records.map((row) => <tr key={`${row.period}-${row.disease}-${row.classification}`}><td className="strong-cell">{row.month_name} {row.year}</td><td>{row.year}</td><td><span className="classification-chip">{formatClassification(row.classification)}</span></td><td>{fmt(row.cases)}</td><td>{fmt(row.deaths)}</td><td>{row.source_url ? <a href={row.source_url} target="_blank" rel="noreferrer" className="source-link">{row.source_file} <ArrowUpRightFromSquare size={12} /></a> : "—"}</td></tr>)}</tbody>
            </table>
          </div>
        )}
      </Panel>
      <Panel
        title={`${disease} annual district comparison`}
        subtitle="Annual district workbooks · separate filters and source classifications"
        action={
          <div className="inline-filter-group">
            <FilterSelect label="District year" value={districtYear} options={[2020, 2021, 2022, 2023, 2024].map((item) => ({ value: String(item), label: String(item) }))} onChange={setDistrictYear} />
            <FilterSelect label="District classification" value={districtClassification} options={[{ value: "Confirmed", label: "Confirmed" }, { value: "Probable", label: "Probable" }]} onChange={(value) => setDistrictClassification(value as "Confirmed" | "Probable")} />
            <button className="button button-secondary" disabled={!districtRecords.length} onClick={() => downloadCsv("caregrid-annual-district-records.csv", districtRecords as unknown as Record<string, unknown>[])}><Download size={14} /> Export annual CSV</button>
          </div>
        }
      >
        <Notice title="Annual district records are not district-month observations" tone="warning">
          These values are kept separate from the monthly statewide series and its year-specific classification labels.
        </Notice>
        {districtRecords.length ? (
          <div className="district-inline-grid">
            <DistrictChart data={districtRecords.map((row) => ({ district: row.district ?? "", cases: row.cases }))} />
            <div className="table-wrap district-table-wrap">
              <table><thead><tr><th>District</th><th>Cases</th><th>Deaths</th></tr></thead>
                <tbody>{districtRecords.map((row) => <tr key={row.district_code}><td className="strong-cell">{row.district}</td><td>{fmt(row.cases)}</td><td>{fmt(row.deaths)}</td></tr>)}</tbody>
              </table>
            </div>
          </div>
        ) : <EmptyState>No annual district rows match these filters.</EmptyState>}
      </Panel>
    </>
  );
}

function DistrictPage() {
  const [year, setYear] = useState("2024");
  const [disease, setDisease] = useState<Disease>("Dengue");
  const [classification, setClassification] = useState<"Confirmed" | "Probable">("Confirmed");
  const path = `/api/districts?year=${year}&disease=${disease}&classification=${classification}`;
  const result = useResource<DistrictResponse>(path);
  if (result.loading) return <LoadingState />;
  if (result.error || !result.data) return <ErrorState message={result.error ?? "District records are unavailable."} />;
  const rows = result.data.records;
  return (
    <>
      <PageHeading eyebrow="ANNUAL DISTRICT DATA" title="District explorer" description="Compare reported annual counts across Kerala's 14 districts. No verified district-boundary dataset is available for mapping." action={<div className="heading-actions"><span className="mini-tag"><MapPinned size={13} /> Table view · no map boundaries</span><button className="button button-secondary" disabled={!rows.length} onClick={() => downloadCsv("caregrid-annual-district-records.csv", rows as unknown as Record<string, unknown>[])}><Download size={14} /> Export CSV</button></div>} />
      <div className="filter-bar">
        <div className="filter-bar-title"><SlidersHorizontal size={17} /><span>Compare</span></div>
        <FilterSelect label="Year" value={year} options={[2020, 2021, 2022, 2023, 2024].map((item) => ({ value: String(item), label: String(item) }))} onChange={setYear} />
        <FilterSelect label="Disease" value={disease} options={[{ value: "Dengue", label: "Dengue" }, { value: "Leptospirosis", label: "Leptospirosis" }]} onChange={(value) => setDisease(value as Disease)} />
        <FilterSelect label="Classification" value={classification} options={[{ value: "Confirmed", label: "Confirmed" }, { value: "Probable", label: "Probable" }]} onChange={(value) => setClassification(value as "Confirmed" | "Probable")} />
      </div>
      <Notice title="Annual—not monthly—district observations" tone="warning">
        These counts cannot be assigned to months or joined to monthly weather as district-level disease data. Values are raw counts, not population-adjusted rates.
      </Notice>
      <div className="stats-grid stats-grid-three">
        <StatCard label="Districts represented" value={fmt(rows.length)} detail={`${year} annual records`} icon={<MapPinned size={19} />} />
        <StatCard label="Reported cases" value={fmt(rows.reduce((sum, row) => sum + row.cases, 0))} detail={`${disease} · ${classification}`} icon={<Activity size={19} />} tone="blue" />
        <StatCard label="Reported deaths" value={fmt(rows.reduce((sum, row) => sum + row.deaths, 0))} detail="Annual source counts" icon={<ShieldAlert size={19} />} tone="amber" />
      </div>
      {rows.length ? (
        <div className="grid-two district-layout">
          <Panel title="District comparison" subtitle="Reported annual cases · sorted descending" action={<span className="mini-tag">{year}</span>}>
            <DistrictChart data={rows.map((row) => ({ district: row.district ?? "", cases: row.cases }))} />
          </Panel>
          <Panel title="District records" subtitle="Confirmed/probable categories remain separate">
            <div className="table-wrap district-table-wrap">
              <table><thead><tr><th>#</th><th>District</th><th>Cases</th><th>Deaths</th></tr></thead>
                <tbody>{rows.map((row, index) => <tr key={row.district_code}><td className="rank-cell">{String(index + 1).padStart(2, "0")}</td><td><span className="strong-cell">{row.district}</span><small>{row.district_code}</small></td><td>{fmt(row.cases)}</td><td>{fmt(row.deaths)}</td></tr>)}</tbody>
              </table>
            </div>
            <div className="chart-caption">Source: annual district workbooks. A missing map layer is not replaced with invented boundaries.</div>
          </Panel>
        </div>
      ) : <EmptyState>No annual district rows match these filters.</EmptyState>}
    </>
  );
}

function ClimatePage() {
  const [disease, setDisease] = useState<Disease>("Dengue");
  const [year, setYear] = useState("2024");
  const [classification, setClassification] = useState("Confirmed");
  const path = `/api/climate?disease=${disease}${classification === "all" ? "" : `&classification=${encodeURIComponent(classification)}`}`;
  const result = useResource<ClimateResponse>(path);
  if (result.loading) return <LoadingState />;
  if (result.error || !result.data) return <ErrorState message={result.error ?? "Climate data is unavailable."} />;
  const weather = result.data.weather.filter((row) => year === "all" || row.period.startsWith(`${year}-`));
  const diseaseRecords = result.data.disease_records.filter((row) => year === "all" || row.period?.startsWith(`${year}-`));
  const caseGroups = makeClassSeries(diseaseRecords, "cases");
  const seriesByYear = new Map<string, RecordRow[]>();
  for (const row of diseaseRecords) {
    const key = `${row.year} · ${row.classification}`;
    seriesByYear.set(key, [...(seriesByYear.get(key) ?? []), row]);
  }
  const firstClass = diseaseRecords[0]?.classification ?? classification;
  const yearTotal = classification === "all" ? null : diseaseRecords.reduce((sum, row) => sum + row.cases, 0);
  return (
    <>
      <PageHeading eyebrow="HISTORICAL WEATHER · EXPLORATORY" title="Climate insights" description="Compare validated weather summaries with compatible statewide monthly disease reports." action={<span className="proxy-badge"><CloudRain size={14} /> STATEWIDE PROXY</span>} />
      <Notice title="Weather is an equal-weight location-based proxy" tone="warning">
        Rainfall and temperature are averaged across 14 representative district locations. This is not an official or population-weighted statewide weather measure. Associations are descriptive, not causal.
      </Notice>
      <div className="filter-bar">
        <div className="filter-bar-title"><SlidersHorizontal size={17} /><span>View</span></div>
        <FilterSelect label="Disease" value={disease} options={[{ value: "Dengue", label: "Dengue" }, { value: "Leptospirosis", label: "Leptospirosis" }]} onChange={(value) => setDisease(value as Disease)} />
        <FilterSelect label="Year" value={year} options={[{ value: "all", label: "All years" }, ...[2021, 2022, 2023, 2024].map((item) => ({ value: String(item), label: String(item) }))]} onChange={setYear} />
        <FilterSelect label="Source classification" value={classification} options={[{ value: "all", label: "All source labels" }, ...result.data.classification_options.map((item) => ({ value: item, label: formatClassification(item) }))]} onChange={setClassification} />
      </div>
      <div className="climate-stats">
        <div className="climate-stat"><span className="climate-stat-icon rain"><CloudRain size={18} /></span><div><span>Mean rainfall in view</span><strong>{weather.length ? `${(weather.reduce((sum, row) => sum + row.precipitation_sum_mm, 0) / weather.length).toFixed(1)} <small>mm / month</small>` : "—"}</strong></div></div>
        <div className="climate-stat"><span className="climate-stat-icon temp"><Thermometer size={18} /></span><div><span>Mean temperature in view</span><strong>{weather.length ? `${(weather.reduce((sum, row) => sum + row.temperature_2m_mean_c, 0) / weather.length).toFixed(1)} <small>°C</small>` : "—"}</strong></div></div>
        <div className="climate-stat"><span className="climate-stat-icon cases"><Activity size={18} /></span><div><span>Reported cases · selected label</span><strong>{yearTotal === null ? "Choose one label" : fmt(yearTotal)}{yearTotal !== null && <small> cases</small>}</strong></div></div>
      </div>
      <div className="grid-two">
        <Panel title="Monthly precipitation" subtitle="Mean monthly sum across representative locations" action={<span className="unit-tag">mm / month</span>}>
          <WeatherChart data={weather} variable="precipitation_sum_mm" color="#438bb3" unit="mm" ariaLabel="Monthly precipitation in millimeters, equal-weight statewide proxy" />
        </Panel>
        <Panel title="Monthly mean temperature" subtitle="Mean of daily mean temperatures across locations" action={<span className="unit-tag">°C</span>}>
          <WeatherChart data={weather} variable="temperature_2m_mean_c" color="#d17859" unit="°C" ariaLabel="Monthly average temperature in Celsius, equal-weight statewide proxy" />
        </Panel>
      </div>
      <Panel title={`${disease} reported cases`} subtitle={`${year === "all" ? "All observed years" : year} · ${classification === "all" ? "original source categories shown separately" : formatClassification(firstClass)}`} action={<span className="mini-tag">{diseaseRecords.length} observed records</span>}>
        {diseaseRecords.length ? (
          <>
            <TrendChart data={caseGroups.points} dataKeys={caseGroups.series} ariaLabel={`${disease} observed monthly reported cases, separated by year and classification`} height={235} />
            <div className="classification-legend">{[...seriesByYear.keys()].map((item) => <span key={item}><i />{item}</span>)}</div>
          </>
        ) : <EmptyState>No compatible monthly disease rows are available for this selection.</EmptyState>}
        <div className="chart-caption">The weather and disease series share month keys. Year-specific reporting categories are preserved; no causal effect is inferred.</div>
      </Panel>
    </>
  );
}

function ForecastPage() {
  return <ForecastingExperimentPage />;
}

function CapacityPage() {
  const [capacity, setCapacity] = useState("");
  const [occupied, setOccupied] = useState("");
  const [surge, setSurge] = useState("");
  const numeric = [capacity, occupied, surge].map((value) => value === "" ? null : Number(value));
  const [beds, occupiedBeds, addedPatients] = numeric;
  const valid =
    beds !== null && occupiedBeds !== null && addedPatients !== null &&
    Number.isInteger(beds) && Number.isInteger(occupiedBeds) && Number.isInteger(addedPatients) &&
    beds > 0 && occupiedBeds >= 0 && occupiedBeds <= beds && addedPatients >= 0;
  const scenarioOccupancy = valid ? occupiedBeds + addedPatients : null;
  const scenarioPercent = valid ? (scenarioOccupancy! / beds!) * 100 : null;
  return (
    <>
      <PageHeading eyebrow="HYPOTHETICAL PLANNING TOOL" title="Hospital capacity simulator" description="Explore a user-defined capacity scenario. No hospital bed or occupancy data is connected." action={<span className="scenario-badge"><SlidersHorizontal size={14} /> SCENARIO ONLY</span>} />
      <Notice title="All inputs are hypothetical and supplied by you" tone="warning">
        Results are arithmetic scenarios—not real hospital status, occupancy, demand estimates, staffing guidance, or a recommendation.
      </Notice>
      <div className="capacity-layout">
        <Panel title="Scenario assumptions" subtitle="Enter hypothetical values to calculate an illustrative scenario">
          <div className="scenario-fields">
            <NumberField label="Hypothetical bed capacity" value={capacity} onChange={setCapacity} hint="Total beds in this example" />
            <NumberField label="Hypothetical occupied beds" value={occupied} onChange={setOccupied} hint="Must not exceed scenario capacity" />
            <NumberField label="Additional hypothetical patients" value={surge} onChange={setSurge} hint="Incremental admissions in this scenario" />
          </div>
          {occupiedBeds !== null && beds !== null && occupiedBeds > beds && <div className="field-error" role="alert">Scenario occupied beds cannot exceed the hypothetical capacity.</div>}
          <div className="scenario-reset"><button className="button button-secondary" onClick={() => { setCapacity(""); setOccupied(""); setSurge(""); }}>Clear scenario</button><span>Inputs are not stored or sent to the server.</span></div>
        </Panel>
        <Panel title="Illustrative scenario output" subtitle="Calculated only from the assumptions entered">
          {valid ? (
            <div className="scenario-output">
              <div className="scenario-gauge" style={{ "--scenario-value": `${Math.min(scenarioPercent!, 100)}%` } as React.CSSProperties}>
                <div><strong>{scenarioPercent!.toFixed(1)}%</strong><span>scenario occupancy</span></div>
              </div>
              <div className="scenario-results">
                <div><span>Scenario occupied beds</span><strong>{fmt(scenarioOccupancy!)}</strong></div>
                <div><span>Remaining hypothetical capacity</span><strong>{fmt(beds! - scenarioOccupancy!)}</strong></div>
                <div><span>Input capacity</span><strong>{fmt(beds!)}</strong></div>
              </div>
              <div className="scenario-disclaimer">Scenario output only. This is not actual hospital occupancy or an operational alert.</div>
            </div>
          ) : <EmptyState>Enter valid hypothetical integers in all three fields to see a scenario. No values are prefilled.</EmptyState>}
        </Panel>
      </div>
      <Notice title="No real hospital feeds" tone="neutral">
        This simulator does not use disease counts to infer admissions, occupied beds, or hospital stress. It performs only the arithmetic shown above.
      </Notice>
    </>
  );
}

function NumberField({ label, value, onChange, hint }: { label: string; value: string; onChange: (value: string) => void; hint: string }) {
  const id = `scenario-${label.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-")}`;
  return (
    <label className="number-field" htmlFor={id}>
      <span>{label}</span>
      <input id={id} type="number" min="0" step="1" inputMode="numeric" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Enter a value" />
      <small>{hint}</small>
    </label>
  );
}

function MethodologyPage() {
  const result = useResource<Methodology>("/api/methodology");
  if (result.loading) return <LoadingState />;
  if (result.error || !result.data) return <ErrorState message={result.error ?? "Methodology information is unavailable."} />;
  const data = result.data;
  return (
    <>
      <PageHeading eyebrow="TRANSPARENT BY DESIGN" title="Sources & methodology" description="Provenance, reporting coverage, weather aggregation and known limitations behind every view." />
      <Notice title="Source values are preserved as reported" tone="info">
        Original source files are read-only to this application. No missing disease months are filled and no district-month values are derived from annual totals.
      </Notice>
      <Panel title="Curated data sources" subtitle="Source lineage and temporal grain">
        <div className="source-cards">
          {data.sources.map((source) => (
            <article className="source-card" key={source.name}>
              <div className="source-card-icon"><FileSpreadsheet size={18} /></div>
              <div className="source-card-body"><h3>{source.name}</h3><div className="source-coverage">{source.coverage} <span>·</span> {fmt(source.records)} curated records</div><p>{source.grain}</p>
                {source.status && <p>Source status: <strong>{source.status.replaceAll("_", " ")}</strong>{source.report_date ? ` · report date ${source.report_date}` : ""}{source.source_published_at ? ` · source published ${source.source_published_at}` : ""}{source.last_retrieval ? ` · retrieved ${source.last_retrieval}` : ""}</p>}
                {source.reporting_frequency && <p>Reporting frequency: {source.reporting_frequency}</p>}
                {source.limitations?.map((limitation) => <p key={limitation}>{limitation}</p>)}
                <div className="source-links">{source.urls.map((url) => <a href={url} target="_blank" rel="noreferrer" key={url}>Open source <ArrowUpRightFromSquare size={12} /></a>)}{source.documentation && <a href={source.documentation} target="_blank" rel="noreferrer">API documentation <ArrowUpRightFromSquare size={12} /></a>}</div>
              </div>
            </article>
          ))}
        </div>
      </Panel>
      <div className="grid-two">
        <Panel title="Reporting classifications" subtitle="Monthly statewide category labels by source year">
          <div className="table-wrap">
            <table><thead><tr><th>Year</th><th>Source category</th><th>Rows</th></tr></thead><tbody>
              {data.classification_by_year.map((row) => <tr key={`${row.year}-${row.classification}`}><td className="strong-cell">{row.year}</td><td><span className="classification-chip">{formatClassification(row.classification)}</span></td><td>{row.records}</td></tr>)}
            </tbody></table>
          </div>
          <div className="chart-caption">Labels are shown as supplied. Matching words do not guarantee identical case definitions between source years.</div>
        </Panel>
        <Panel title="Known limitations" subtitle="Interpret results with care">
          <ul className="caveat-list">{data.caveats.map((caveat) => <li key={caveat}><span>•</span><p>{caveat}</p></li>)}</ul>
        </Panel>
      </div>
      <Panel title="Project quality reports" subtitle="Generated data-readiness and source-audit documentation">
        <div className="report-links">{data.reports.map((report) => <a href={`/api/reports/${encodeURIComponent(report.split("/").at(-1) ?? report)}`} target="_blank" rel="noreferrer" key={report}><FileSpreadsheet size={16} />{report}<ArrowUpRightFromSquare size={13} /></a>)}</div>
      </Panel>
      <div className="discrepancy-card">
        <div className="discrepancy-mark">!</div>
        <div><strong>Unresolved 2021 dengue discrepancy</strong><p>The statewide monthly dataset totals 3,251 dengue cases. The district annual confirmed records sum to 3,261—a difference of 10. The datasets remain unreconciled; no value is adjusted here.</p></div>
      </div>
    </>
  );
}

export default function App() {
  const [page, setPage] = useState<PageId>("overview");
  const content = useMemo(() => {
    switch (page) {
      case "overview": return <OverviewPage onNavigate={setPage} />;
      case "surveillance": return <SurveillancePage />;
      case "live-surveillance": return <LiveSurveillancePage />;
      case "districts": return <DistrictPage />;
      case "climate": return <ClimatePage />;
      case "forecasts": return <ForecastPage />;
      case "capacity": return <CapacityPage />;
      case "methodology": return <MethodologyPage />;
    }
  }, [page]);
  return <Shell page={page} onNavigate={setPage}>{content}</Shell>;
}
