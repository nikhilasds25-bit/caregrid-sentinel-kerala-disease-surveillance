import { useEffect, useState } from "react";
import { apiGet, type Disease } from "./api";
import { ErrorState, LoadingState, Panel } from "./components";

interface ModelComparisonRecord {
  disease: Disease;
  model_name: string;
  feature_set: string;
  evidence_role: string;
  horizon_scope: string;
  n_forecasts: number;
  mae: number | null;
  rmse: number | null;
  coverage_80_original: number | null;
  coverage_80_display: number | null;
}

interface ApiResponse {
  data: ModelComparisonRecord[];
}

function formatMetric(value: number | null) {
  return value == null ? "Unavailable" : value.toFixed(2);
}

export default function ModelComparison({ disease }: { disease: Disease }) {
  const [records, setRecords] = useState<ModelComparisonRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError(null);

    apiGet<ApiResponse>(
      `/api/v1/model-comparisons?disease=${encodeURIComponent(disease)}`,
    )
      .then((response) => {
        if (active) {
          if (!Array.isArray(response?.data)) {
            setRecords([]);
            setError("Analytical data is unavailable or has an unexpected response format.");
          } else {
            setRecords(response.data);
          }
        }
      })
      .catch((err: unknown) => {
        if (active)
          setError(err instanceof Error ? err.message : "Unable to load model comparisons.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [disease]);

  return (
    <Panel
      title="Model comparison"
      subtitle="Exploratory historical evaluation; no operational model selection"
    >
      {loading && <LoadingState label="Loading model comparisons…" />}
      {error && <ErrorState message={error} />}

      {!loading && !error && (
        <>
          <div className="table-wrap">
            <table>
              <caption>{disease} retrospective model comparison</caption>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Features</th>
                  <th>Evaluation role</th>
                  <th>Horizon</th>
                  <th>Sample size</th>
                  <th>MAE</th>
                  <th>RMSE</th>
                  <th>Original 80% coverage</th>
                  <th>Display 80% coverage</th>
                </tr>
              </thead>
              <tbody>
                {records.map((row, index) => (
                  <tr key={`${row.model_name}-${row.feature_set}-${row.horizon_scope}-${index}`}>
                    <td>{row.model_name}</td>
                    <td>{row.feature_set}</td>
                    <td>{row.evidence_role}</td>
                    <td>{row.horizon_scope}</td>
                    <td>{row.n_forecasts}</td>
                    <td>{formatMetric(row.mae)}</td>
                    <td>{formatMetric(row.rmse)}</td>
                    <td>{formatMetric(row.coverage_80_original)}</td>
                    <td>{formatMetric(row.coverage_80_display)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="chart-caption">
            Coverage values are empirical proportions, not guarantees.
            Models and intervals remain exploratory; no model is designated best
            or operationally ready.
          </p>
        </>
      )}
    </Panel>
  );
}
