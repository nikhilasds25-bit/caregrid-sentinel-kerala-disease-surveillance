import { useEffect, useMemo, useState } from "react";
import { apiGet, type Disease } from "./api";
import {
  EmptyState,
  ErrorState,
  FilterSelect,
  LoadingState,
  Notice,
  PageHeading,
  Panel,
  TrendChart,
} from "./components";

interface ForecastSeriesReadiness {
  disease: Disease;
  classification: string;
  valid_observations: number;
  first_reporting_month: string;
  last_reporting_month: string;
  missing_months: string[];
  duplicate_months: string[];
  zero_observations: number;
  source_change: boolean;
  source_files: string[];
  outliers_for_review_iqr_rule: Array<{ period: string; cases: number }>;
}

interface ForecastMetric {
  disease: Disease;
  classification: string;
  model: string;
  mae: number;
  rmse: number;
  mase: number | null;
  test_observations: number;
  training_observations: number;
  training_start: string;
  training_end: string;
  test_start: string;
  test_end: string;
  mase_note: string;
}

interface ForecastObservation {
  disease: Disease;
  classification: string;
  period: string;
  model: string;
  actual_cases: number;
  predicted_cases: number;
  residual_actual_minus_predicted: number;
}

interface ForecastExperiment {
  status: string;
  experiment_generated_at_utc: string;
  source_dataset: string;
  source_columns: string[];
  series: ForecastSeriesReadiness[];
  evaluation: {
    proposed_2021_2023_train_2024_test_feasible: boolean;
    proposed_split_reason: string;
    confirmed_2023_train_2024_test: Record<Disease, {
      eligible_for_limited_2024_holdout: boolean;
      observations: number;
      training_period: string[] | null;
      test_period: string[] | null;
      reason: string;
      source_files_by_year: Record<string, string[]>;
    }>;
    rolling_origin_12_month_horizon_feasible: boolean;
    rolling_origin_reason: string;
  };
  climate: {
    matched_confirmed_disease_months: number;
    weather_scope: string;
    climate_model_evaluated: boolean;
    reason_not_evaluated: string;
  };
  evaluation_metrics: ForecastMetric[];
  actual_vs_predicted: ForecastObservation[];
  validity_checks_passed: boolean;
  future_forecasts_available: boolean;
  climate_features_improved_performance: boolean | null;
  climate_feature_comparison_status: string;
}

function useForecastExperiment() {
  const [data, setData] = useState<ForecastExperiment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    apiGet<ForecastExperiment>("/api/forecasting/experiment")
      .then((result) => {
        if (active) setData(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          setData(null);
          setError(reason instanceof Error ? reason.message : "The experiment could not be loaded.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return { data, error, loading };
}

function formatNumber(value: number | null) {
  return value == null
    ? "Not estimable"
    : new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);
}

export default function ForecastingExperimentPage() {
  const { data, error, loading } = useForecastExperiment();
  const [disease, setDisease] = useState<Disease>("Dengue");
  const eligible = data?.evaluation.confirmed_2023_train_2024_test[disease];
  const visible = Boolean(
    data?.validity_checks_passed
      && eligible?.eligible_for_limited_2024_holdout
      && data.actual_vs_predicted.some((row) => row.disease === disease),
  );
  const metrics = (data?.evaluation_metrics ?? []).filter((row) => row.disease === disease);
  const rows = (data?.actual_vs_predicted ?? []).filter((row) => row.disease === disease);
  const chartData = useMemo(() => {
    const points = new Map<string, Record<string, string | number | null>>();
    for (const row of rows) {
      const point = points.get(row.period) ?? { period: row.period, actual_cases: row.actual_cases };
      point[row.model] = row.predicted_cases;
      points.set(row.period, point);
    }
    return [...points.values()];
  }, [rows]);
  const confirmedSeries = (data?.series ?? []).filter(
    (row) => row.classification === "Confirmed",
  );

  return (
    <>
      <PageHeading
        eyebrow="EXPERIMENTAL RETROSPECTIVE"
        title="Forecasts & risk assessment"
        description="A baseline-only chronological hindcast. No future predictions, risk scores, or public-health alerts are generated."
      />
      {loading ? <LoadingState label="Loading forecasting readiness and experiment results…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {data && (
        <>
          <Notice title="Experimental results only · not an official alert" tone="warning">
            These values compare baseline predictions against the 2024 historical holdout. They are not forecasts of future cases and are not an operational or clinical decision tool.
          </Notice>
          <div className="forecast-hero">
            <div className="forecast-kicker">FORECASTING READINESS</div>
            <h2>Future forecasting is not yet scientifically justified.</h2>
            <p>
              Evaluation is limited to 2023 training and a single 2024 holdout for the explicitly Confirmed category.
              The 2021–2023 proposed training period combines incompatible source classifications.
            </p>
            <span className="disabled-chip"><span /> Historical baseline experiment only</span>
          </div>
          <div className="grid-two forecast-grid">
            <Panel title="Compatible series coverage" subtitle="Historical monthly observations, source classifications kept separate">
              <div className="table-wrap">
                <table>
                  <caption>Readiness by disease and source classification</caption>
                  <thead><tr><th scope="col">Disease</th><th scope="col">Classification</th><th scope="col">Valid months</th><th scope="col">Coverage</th><th scope="col">Missing months</th><th scope="col">Duplicates</th><th scope="col">Zeros</th><th scope="col">Source transition</th></tr></thead>
                  <tbody>{(data.series ?? []).map((series) => (
                    <tr key={`${series.disease}-${series.classification}`}>
                      <td>{series.disease}</td>
                      <td>{series.classification}</td>
                      <td>{series.valid_observations}</td>
                      <td>{series.first_reporting_month} – {series.last_reporting_month}</td>
                      <td>{series.missing_months.length ? series.missing_months.join(", ") : "None"}</td>
                      <td>{series.duplicate_months.length ? series.duplicate_months.join(", ") : "None"}</td>
                      <td>{series.zero_observations}</td>
                      <td>{series.source_change ? "Yes" : "No"}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <p className="chart-caption">
                Dataset: {data.source_dataset}. The 2021 and 2022 categories are not merged with Confirmed.
                Annual district data and 2025 annual reports are excluded.
              </p>
            </Panel>
            <Panel title="Validation scope" subtitle="Chronological split; no random shuffling">
              <ul className="check-list">
                <li><span className="check-x">×</span><div><strong>Proposed 2021–2023 training unavailable</strong><p>{data.evaluation.proposed_split_reason}</p></div></li>
                <li><span className="check-x">×</span><div><strong>Rolling-origin 12-month horizon unavailable</strong><p>{data.evaluation.rolling_origin_reason}</p></div></li>
                <li><span className="check-x">×</span><div><strong>Climate model not evaluated</strong><p>{data.climate.reason_not_evaluated}</p></div></li>
              </ul>
            </Panel>
          </div>
          <Panel title="Baseline performance · 2024 historical holdout" subtitle="Select a disease; forecasts shown here are retrospective experimental predictions only.">
            <FilterSelect
              label="Disease"
              value={disease}
              options={[
                { value: "Dengue", label: "Dengue" },
                { value: "Leptospirosis", label: "Leptospirosis" },
              ]}
              onChange={(value) => setDisease(value as Disease)}
            />
            {!visible ? (
              <EmptyState>No experimental hindcast passed the documented validity checks for this selection.</EmptyState>
            ) : (
              <>
                <p className="chart-caption">
                  Classification: Confirmed · Train: January–December 2023 · Test: January–December 2024 ·
                  {eligible?.observations} total monthly observations.
                </p>
                <TrendChart
                  data={chartData}
                  dataKeys={[
                    { key: "actual_cases", label: "Observed cases" },
                    { key: "naive", label: "Naïve baseline" },
                    { key: "seasonal_naive", label: "Seasonal-naïve baseline" },
                  ]}
                  ariaLabel={`${disease} confirmed 2024 observed cases compared with naive and seasonal naive retrospective baseline predictions`}
                  height={300}
                />
                <div className="table-wrap">
                  <table>
                    <caption>{disease} confirmed actual versus predicted monthly reported cases</caption>
                    <thead><tr><th scope="col">Month</th><th scope="col">Model</th><th scope="col">Observed cases</th><th scope="col">Predicted cases</th><th scope="col">Residual (observed − predicted)</th></tr></thead>
                    <tbody>{rows.map((row) => (
                      <tr key={`${row.period}-${row.model}`}>
                        <td>{row.period}</td><td>{row.model === "naive" ? "Naïve" : "Seasonal naïve"}</td>
                        <td>{formatNumber(row.actual_cases)}</td><td>{formatNumber(row.predicted_cases)}</td>
                        <td>{formatNumber(row.residual_actual_minus_predicted)}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
                <div className="table-wrap">
                  <table>
                    <caption>2024 holdout error metrics · reported cases</caption>
                    <thead><tr><th scope="col">Baseline</th><th scope="col">Test months</th><th scope="col">MAE</th><th scope="col">RMSE</th><th scope="col">Seasonal MASE</th></tr></thead>
                    <tbody>{metrics.map((metric) => (
                      <tr key={metric.model}>
                        <td>{metric.model === "naive" ? "Naïve" : "Seasonal naïve"}</td>
                        <td>{metric.test_observations}</td>
                        <td>{formatNumber(metric.mae)}</td><td>{formatNumber(metric.rmse)}</td>
                        <td>{formatNumber(metric.mase)}<br /><small>{metric.mase_note}</small></td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              </>
            )}
          </Panel>
          <div className="grid-two forecast-grid">
            <Panel title="Climate feature assessment" subtitle="Alignment is not evidence that climate improves forecasting">
              <p>{data.climate.matched_confirmed_disease_months} confirmed disease-month records align with historical weather.</p>
              <p>{data.climate.weather_scope}</p>
              <p>{data.climate.climate_model_evaluated ? "A climate-feature comparison was evaluated." : data.climate.reason_not_evaluated}</p>
              <p>Climate improvement: {data.climate_features_improved_performance == null ? "Not evaluated" : data.climate_features_improved_performance ? "Improved" : "No improvement"}</p>
            </Panel>
            <Panel title="Data review flags" subtitle="Outlier screening does not remove source values">
              <div className="table-wrap">
                <table>
                  <caption>IQR screening flags for selected Confirmed series</caption>
                  <thead><tr><th scope="col">Disease</th><th scope="col">Flagged months</th></tr></thead>
                  <tbody>{confirmedSeries.map((series) => (
                    <tr key={series.disease}>
                      <td>{series.disease}</td>
                      <td>{series.outliers_for_review_iqr_rule.length
                        ? series.outliers_for_review_iqr_rule.map((item) => `${item.period}: ${item.cases}`).join("; ")
                        : "None flagged"}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <p className="chart-caption">IQR flags are screening indicators, not errors or reasons to exclude observations.</p>
            </Panel>
          </div>
          <Notice title="Interpretation and limitations" tone="neutral">
            One 12-month test year and a one-season training set cannot establish stable future performance. The source documents change between 2023 and 2024. The seasonal MASE scale is unavailable because training has no pairs 12 months apart. No causal weather claims, outbreak detection, future prediction, or hospital-capacity inference is made.
          </Notice>
        </>
      )}
    </>
  );
}
