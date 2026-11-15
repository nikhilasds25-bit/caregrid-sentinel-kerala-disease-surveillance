import { useEffect, useMemo, useState } from "react";
import { apiGet, type Disease } from "./api";
import {
  ErrorState,
  FilterSelect,
  LoadingState,
  Panel,
  TrendChart,
} from "./components";

interface SignalRecord {
  detector_id: string;
  disease: Disease;
  district: string;
  period: string;
  observed_count: number | null;
  baseline: number | null;
  anomaly_score: number | null;
  unusual_activity_flag: boolean;
  evidence_role: string;
  signal_status: string;
  signal_type: string;
}

interface ApiResponse {
  data: SignalRecord[];
}

export default function UnusualActivity({
  disease,
  district,
}: {
  disease: Disease;
  district: string;
}) {
  const [records, setRecords] = useState<SignalRecord[]>([]);
  const [detector, setDetector] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError(null);

    const params = new URLSearchParams({ disease, district });

    apiGet<ApiResponse>(`/api/v1/detection/signals?${params}`)
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
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load unusual-activity signals.",
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

  const detectors = useMemo(
    () => [...new Set(records.map((row) => row.detector_id))].sort(),
    [records],
  );

  const selectedDetector = detectors.includes(detector)
    ? detector
    : (detectors[0] ?? "");

  const selectedRecords = useMemo(
    () =>
      records
        .filter((row) => row.detector_id === selectedDetector)
        .sort((a, b) => a.period.localeCompare(b.period)),
    [records, selectedDetector],
  );

  const chartData = selectedRecords.map((row) => ({
    period: row.period,
    observed: row.observed_count,
    baseline: row.baseline,
  }));

  const flagged = selectedRecords.filter((row) => row.unusual_activity_flag);

  return (
    <Panel
      title="Unusual activity · EWMA/CUSUM"
      subtitle="Exploratory retrospective statistical signals, not confirmed outbreaks"
    >
      {loading && <LoadingState label="Loading unusual-activity signals…" />}
      {error && <ErrorState message={error} />}

      {!loading && !error && (
        <>
          {detectors.length > 0 && (
            <FilterSelect
              label="Detection method"
              value={selectedDetector}
              options={detectors.map((value) => ({
                value,
                label: value,
              }))}
              onChange={setDetector}
            />
          )}

          <p className="chart-caption">
            {disease} · {district} · {selectedDetector || "No detector available"} ·
            {` ${flagged.length} flagged months out of ${selectedRecords.length} evaluated months.`}
          </p>

          <TrendChart
            data={chartData}
            dataKeys={[
              { key: "observed", label: "Observed cases" },
              { key: "baseline", label: "Statistical baseline" },
            ]}
            ariaLabel={`${disease} retrospective unusual-activity analysis for ${district}`}
            height={300}
          />

          <div className="table-wrap">
            <table>
              <caption>Months flagged for exploratory unusual activity</caption>
              <thead>
                <tr>
                  <th scope="col">Month</th>
                  <th scope="col">Detector</th>
                  <th scope="col">Observed count</th>
                  <th scope="col">Anomaly score</th>
                  <th scope="col">Signal status</th>
                </tr>
              </thead>
              <tbody>
                {flagged.map((row) => (
                  <tr key={`${row.detector_id}-${row.period}`}>
                    <td>{row.period}</td>
                    <td>{row.detector_id}</td>
                    <td>{row.observed_count ?? "Unavailable"}</td>
                    <td>{row.anomaly_score?.toFixed(2) ?? "Unavailable"}</td>
                    <td>{row.signal_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="chart-caption">
            EWMA and CUSUM identify deviations from a statistical baseline.
            These retrospective flags do not establish epidemiologically
            confirmed outbreaks. No validated outbreak labels are available.
          </p>
        </>
      )}
    </Panel>
  );
}
