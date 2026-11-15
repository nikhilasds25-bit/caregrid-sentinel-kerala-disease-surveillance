import ThresholdExceedance from "./ThresholdExceedance";
import UnusualActivity from "./UnusualActivity";
import ModelComparison from "./ModelComparison";
import { useEffect, useMemo, useState } from "react";
import { apiGet, type Disease } from "./api";
import { ErrorState, FilterSelect, LoadingState, Notice, Panel, TrendChart } from "./components";

interface ForecastRecord {
  disease: Disease;
  district: string;
  model_name: string;
  feature_set: string;
  origin_period: string;
  target_period: string;
  horizon: number;
  predictive_mean: number | null;
  display_80_lower: number | null;
  display_80_upper: number | null;
  evidence_role: string;
  prediction_type: string;
}

interface ObservationRecord {
  disease: Disease;
  district: string;
  reporting_period: string;
  observed_count: number;
  classification: string;
  observation_type: string;
}

interface ApiResponse<T> {
  data: T[];
  meta: {
    schema_version: string;
    status: string;
    limitations: string[];
  };
}

export default function AnalyticalDashboard() {
  const [disease, setDisease] = useState<Disease>("Dengue");
  const [district, setDistrict] = useState("Ernakulam");
  const [forecasts, setForecasts] = useState<ForecastRecord[]>([]);
  const [observations, setObservations] = useState<ObservationRecord[]>([]);
  const [observationError, setObservationError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError(null);

    const params = new URLSearchParams({ disease, district });

    apiGet<ApiResponse<ForecastRecord>>(`/api/v1/forecasts?${params}`)
      .then((response) => {
        if (active) {
          if (!Array.isArray(response?.data)) {
            setForecasts([]);
            setError("Forecast data is unavailable or has an unexpected response format.");
          } else {
            setForecasts(response.data);
          }
        }
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load forecasts.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [disease, district]);

  useEffect(() => {
    let active = true;

    setObservations([]);
    setObservationError(null);

    const params = new URLSearchParams({
      source: "district_dashboard",
      disease,
      district,
      granularity: "monthly",
      classification: "Confirmed",
    });

    apiGet<ApiResponse<ObservationRecord>>(
      `/api/v1/surveillance/observations?${params}`,
    )
      .then((response) => {
        if (!active) return;

        if (!Array.isArray(response?.data)) {
          setObservationError(
            "Actual observations are unavailable or have an unexpected response format.",
          );
          return;
        }

        setObservations(response.data);
      })
      .catch((err: unknown) => {
        if (active) {
          setObservationError(
            err instanceof Error ? err.message : "Unable to load actual observations.",
          );
        }
      });

    return () => {
      active = false;
    };
  }, [disease, district]);

  const [model, setModel] = useState("");
  const [origin, setOrigin] = useState("");

  const models = useMemo(
    () => [...new Set(forecasts.map((row) => `${row.model_name}|${row.feature_set}`))].sort(),
    [forecasts],
  );

  const selectedModel = models.includes(model) ? model : (models[0] ?? "");
  const modelRows = forecasts.filter(
    (row) => `${row.model_name}|${row.feature_set}` === selectedModel,
  );

  const origins = [...new Set(modelRows.map((row) => row.origin_period))].sort();
  const selectedOrigin = origins.includes(origin) ? origin : (origins[0] ?? "");

  const chartRows = modelRows
    .filter((row) => row.origin_period === selectedOrigin)
    .sort((a, b) => a.horizon - b.horizon);

  const observationsByPeriod = new Map(
    observations
      .filter(
        (row) =>
          row.disease === disease &&
          row.district === district &&
          row.classification === "Confirmed" &&
          row.observation_type === "reported_observation",
      )
      .map((row) => [row.reporting_period, row.observed_count]),
  );

  const chartData = chartRows.map((row) => ({
    period: row.target_period,
    actual: observationsByPeriod.get(row.target_period) ?? null,
    prediction: row.predictive_mean,
    lower: row.display_80_lower,
    upper: row.display_80_upper,
  }));

  return (
    <section>
      <Notice title="Exploratory retrospective analysis" tone="warning">
        These are historical backtest predictions, not future forecasts or
        operational outbreak alerts. District-level analytical outputs must
        not be confused with the separate statewide forecasting experiment.
      </Notice>

      <Panel
        title="Retrospective forecasts"
        subtitle="Historical model predictions with exploratory uncertainty intervals"
      >
        <div className="filter-row">
          <FilterSelect
            label="Disease"
            value={disease}
            options={[
              { value: "Dengue", label: "Dengue" },
              { value: "Leptospirosis", label: "Leptospirosis" },
            ]}
            onChange={(value) => setDisease(value as Disease)}
          />

          <FilterSelect
            label="District"
            value={district}
            options={[
              "Alappuzha",
              "Ernakulam",
              "Idukki",
              "Kannur",
              "Kasaragod",
              "Kollam",
              "Kottayam",
              "Kozhikode",
              "Malappuram",
              "Palakkad",
              "Pathanamthitta",
              "Thiruvananthapuram",
              "Thrissur",
              "Wayanad",
            ].map((name) => ({ value: name, label: name }))}
            onChange={setDistrict}
          />

          {models.length > 0 && (
            <FilterSelect
              label="Model and features"
              value={selectedModel}
              options={models.map((value) => ({
                value,
                label: value.replace("|", " · "),
              }))}
              onChange={setModel}
            />
          )}

          {origins.length > 0 && (
            <FilterSelect
              label="Forecast origin"
              value={selectedOrigin}
              options={origins.map((value) => ({ value, label: value }))}
              onChange={setOrigin}
            />
          )}
        </div>

        {loading && <LoadingState label="Loading retrospective forecasts…" />}
        {error && <ErrorState message={error} />}
        {observationError && (
          <ErrorState message={`Actual observations: ${observationError}`} />
        )}

        {!loading && !error && (
          <>
            <p className="chart-caption">
              Prediction type: historical backtest · District: {district} ·
              Origin: {selectedOrigin || "Unavailable"} ·
              No prospective forecast is available.
            </p>

            <TrendChart
              data={chartData}
              dataKeys={[
                { key: "actual", label: "Actual Confirmed cases" },
                { key: "prediction", label: "Predicted cases" },
                { key: "lower", label: "80% interval lower bound" },
                { key: "upper", label: "80% interval upper bound" },
              ]}
              ariaLabel={`${disease} retrospective forecasts for ${district}`}
              height={300}
            />

            <p className="chart-caption">
              Actual values are source-reported district-month Confirmed counts.
              Missing observations are not replaced with zero.
              The 80% bounds are displayed as separate lines, not a shaded
              interval. Interval coverage may be inadequate, particularly
              for some models and longer horizons.
            </p>
          </>
        )}
      </Panel>

      <ModelComparison disease={disease} />
      <UnusualActivity disease={disease} district={district} />
      <ThresholdExceedance disease={disease} district={district} />
    </section>
  );
}
