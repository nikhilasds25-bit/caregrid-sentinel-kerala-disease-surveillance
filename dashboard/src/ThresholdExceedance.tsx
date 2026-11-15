import { useEffect, useMemo, useState } from "react";
import { apiGet, type Disease } from "./api";
import {
  ErrorState,
  FilterSelect,
  LoadingState,
  Panel,
  TrendChart,
} from "./components";

interface ExceedanceRecord {
  disease: Disease;
  district: string;
  model_name: string;
  validation_phase: string;
  origin_period: string;
  target_period: string;
  horizon: number;
  method: string;
  threshold_definition_id: string;
  threshold_label: string;
  reference_start: string;
  reference_end: string;
  n_reference_values: number | null;
  threshold: number | null;
  status: string;
  observed_exceedance: boolean | null;
  predicted_probability: number | null;
  calibration_status: string;
  evidence_role: string;
}

interface ApiResponse {
  data: ExceedanceRecord[];
}

export default function ThresholdExceedance({
  disease,
  district,
}: {
  disease: Disease;
  district: string;
}) {
  const [records, setRecords] = useState<ExceedanceRecord[]>([]);
  const [model, setModel] = useState("");
  const [method, setMethod] = useState("");
  const [origin, setOrigin] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError(null);

    const params = new URLSearchParams({ disease, district });

    apiGet<ApiResponse>(`/api/v1/exceedance/assessments?${params}`)
      .then((response) => {
        if (active) setRecords(response.data);
      })
      .catch((err: unknown) => {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load threshold-exceedance assessments.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [disease, district]);

  const models = useMemo(
    () => [...new Set(records.map((row) => row.model_name))].sort(),
    [records],
  );

  const selectedModel = models.includes(model) ? model : (models[0] ?? "");

  const modelRecords = records.filter(
    (row) => row.model_name === selectedModel,
  );

  const methods = [...new Set(modelRecords.map((row) => row.method))].sort();
  const selectedMethod = methods.includes(method) ? method : (methods[0] ?? "");

  const methodRecords = modelRecords.filter(
    (row) => row.method === selectedMethod,
  );

  const origins = [...new Set(methodRecords.map((row) => row.origin_period))].sort();
  const selectedOrigin = origins.includes(origin) ? origin : (origins[0] ?? "");

  const selectedRecords = methodRecords
    .filter((row) => row.origin_period === selectedOrigin)
    .sort(
      (a, b) =>
        a.target_period.localeCompare(b.target_period)
        || a.origin_period.localeCompare(b.origin_period)
        || a.horizon - b.horizon,
    );

  const chartData = selectedRecords.map((row) => ({
    period: `${row.target_period} · H${row.horizon}`,
    probability:
      row.predicted_probability == null
        ? null
        : row.predicted_probability * 100,
  }));

  const available = selectedRecords.filter(
    (row) => row.predicted_probability != null,
  );

  return (
    <Panel
      title="Threshold exceedance · exploratory Q90"
      subtitle="Estimated probability of exceeding a historical statistical threshold"
    >
      {loading && (
        <LoadingState label="Loading threshold-exceedance assessments…" />
      )}
      {error && <ErrorState message={error} />}

      {!loading && !error && (
        <>
          {models.length > 0 && (
            <FilterSelect
              label="Model"
              value={selectedModel}
              options={models.map((value) => ({
                value,
                label: value,
              }))}
              onChange={setModel}
            />
          )}

          {methods.length > 0 && (
            <FilterSelect
              label="Threshold method"
              value={selectedMethod}
              options={methods.map((value) => ({
                value,
                label: value,
              }))}
              onChange={setMethod}
            />
          )}

          {origins.length > 0 && (
            <FilterSelect
              label="Forecast origin"
              value={selectedOrigin}
              options={origins.map((value) => ({
                value,
                label: value,
              }))}
              onChange={setOrigin}
            />
          )}

          <p className="chart-caption">
            {disease} · {district} · {selectedModel || "No model available"} ·
            {` ${available.length} probability estimates available out of ${selectedRecords.length} assessments.`}
          </p>

          <TrendChart
            data={chartData}
            dataKeys={[
              { key: "probability", label: "Estimated exceedance probability (%)" },
            ]}
            ariaLabel={`${disease} exploratory threshold-exceedance probability estimates for ${district}`}
            height={300}
          />

          <div className="table-wrap">
            <table>
              <caption>Exploratory historical threshold assessments</caption>
              <thead>
                <tr>
                  <th scope="col">Origin</th>
                  <th scope="col">Target</th>
                  <th scope="col">Horizon</th>
                  <th scope="col">Threshold</th>
                  <th scope="col">Reference samples</th>
                  <th scope="col">Estimated probability</th>
                  <th scope="col">Status</th>
                  <th scope="col">Calibration</th>
                </tr>
              </thead>
              <tbody>
                {selectedRecords.map((row, index) => (
                  <tr key={`${row.origin_period}-${row.target_period}-${row.horizon}-${index}`}>
                    <td>{row.origin_period}</td>
                    <td>{row.target_period}</td>
                    <td>{row.horizon}</td>
                    <td>{row.threshold?.toFixed(2) ?? "Unavailable"}</td>
                    <td>{row.n_reference_values ?? "Unavailable"}</td>
                    <td>
                      {row.predicted_probability == null
                        ? "Unavailable"
                        : `${(row.predicted_probability * 100).toFixed(1)}%`}
                    </td>
                    <td>{row.status}</td>
                    <td>{row.calibration_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="chart-caption">
            Q90 represents an exploratory historical statistical threshold,
            not a validated epidemiological outbreak definition.
            These probabilities are not calibrated outbreak probabilities.
            Insufficient historical evidence is displayed as unavailable.
          </p>
        </>
      )}
    </Panel>
  );
}
