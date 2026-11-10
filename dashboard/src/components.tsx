import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ReactNode } from "react";

export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="heading-action">{action}</div>}
    </div>
  );
}

export function StatCard({
  label,
  value,
  detail,
  icon,
  tone = "mint",
}: {
  label: string;
  value: string;
  detail: string;
  icon: ReactNode;
  tone?: "mint" | "blue" | "amber" | "violet";
}) {
  return (
    <article className="stat-card">
      <div className={`stat-icon ${tone}`}>{icon}</div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-detail">{detail}</div>
    </article>
  );
}

export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warning" | "neutral";
  title: string;
  children: ReactNode;
}) {
  return (
    <div className={`notice ${tone}`} role="note">
      <div className="notice-mark" aria-hidden="true">
        {tone === "warning" ? "!" : "i"}
      </div>
      <div>
        <strong>{title}</strong>
        <div>{children}</div>
      </div>
    </div>
  );
}

export function LoadingState({ label = "Loading validated project data…" }: { label?: string }) {
  return (
    <div className="state-card" role="status">
      <span className="spinner" />
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state-card error-state" role="alert">
      <strong>Data unavailable</strong>
      <span>{message}</span>
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

export function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  const id = `filter-${label.toLowerCase().replaceAll(" ", "-")}`;
  return (
    <label className="filter-field" htmlFor={id}>
      <span>{label}</span>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option value={option.value} key={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

const tooltipStyle = {
  border: "1px solid #e1e9e5",
  borderRadius: 12,
  boxShadow: "0 8px 26px rgba(26, 51, 41, .12)",
  fontSize: 12,
};

const axisProps = {
  tick: { fill: "#82918a", fontSize: 11 },
  axisLine: false,
  tickLine: false,
};

export function TrendChart({
  data,
  dataKeys,
  ariaLabel,
  height = 270,
  colors = ["#227d67", "#e7a74f", "#7288ce"],
}: {
  data: Array<Record<string, string | number | null>>;
  dataKeys: Array<{ key: string; label: string }>;
  ariaLabel: string;
  height?: number;
  colors?: string[];
}) {
  if (!data.length) return <EmptyState>No records match these filters.</EmptyState>;
  return (
    <div className="chart" role="group" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
          <CartesianGrid stroke="#edf1ee" vertical={false} />
          <XAxis dataKey="period" {...axisProps} tickMargin={10} minTickGap={24} />
          <YAxis {...axisProps} width={48} />
          <Tooltip contentStyle={tooltipStyle} />
          {dataKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />}
          {dataKeys.map((series, index) => (
            <Line
              key={series.key}
              type="monotone"
              dataKey={series.key}
              name={series.label}
              stroke={colors[index % colors.length]}
              strokeWidth={2.5}
              dot={{ r: 2.5, strokeWidth: 0 }}
              activeDot={{ r: 5 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <div className="sr-only">
        <table>
          <caption>{ariaLabel}</caption>
          <thead><tr><th>Month</th>{dataKeys.map((series) => <th key={series.key}>{series.label}</th>)}</tr></thead>
          <tbody>{data.map((row, index) => <tr key={`${String(row.period)}-${index}`}><th>{String(row.period)}</th>{dataKeys.map((series) => <td key={series.key}>{row[series.key] ?? "No observation"}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

export function WeatherChart({
  data,
  variable,
  color,
  unit,
  ariaLabel,
}: {
  data: Array<Record<string, string | number>>;
  variable: string;
  color: string;
  unit: string;
  ariaLabel: string;
}) {
  if (!data.length) return <EmptyState>No weather records are available.</EmptyState>;
  return (
    <div className="chart" role="group" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height={230}>
        {variable === "precipitation_sum_mm" ? (
          <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#edf1ee" vertical={false} />
            <XAxis dataKey="period" {...axisProps} tickMargin={10} minTickGap={24} />
            <YAxis {...axisProps} width={48} />
            <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value} ${unit}`, ""]} />
            <Bar dataKey={variable} name={unit} fill={color} radius={[5, 5, 0, 0]} isAnimationActive={false} />
          </BarChart>
        ) : (
          <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#edf1ee" vertical={false} />
            <XAxis dataKey="period" {...axisProps} tickMargin={10} minTickGap={24} />
            <YAxis {...axisProps} width={48} />
            <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value} ${unit}`, ""]} />
            <Area
              type="monotone"
              dataKey={variable}
              name={unit}
              stroke={color}
              fill={color}
              fillOpacity={0.12}
              strokeWidth={2.5}
              isAnimationActive={false}
            />
          </AreaChart>
        )}
      </ResponsiveContainer>
      <div className="sr-only">
        <table>
          <caption>{ariaLabel}</caption>
          <thead><tr><th>Month</th><th>{variable}</th></tr></thead>
          <tbody>{data.map((row) => <tr key={String(row.period)}><th>{String(row.period)}</th><td>{String(row[variable] ?? "No observation")}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

export function DistrictChart({ data }: { data: Array<{ district: string; cases: number }> }) {
  return (
    <div className="chart" role="group" aria-label="Annual reported cases by Kerala district, sorted highest to lowest">
      <ResponsiveContainer width="100%" height={360}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 22 }}>
          <CartesianGrid stroke="#edf1ee" horizontal={false} />
          <XAxis type="number" {...axisProps} />
          <YAxis type="category" dataKey="district" {...axisProps} width={126} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="cases" name="Reported cases" fill="#227d67" radius={[0, 5, 5, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
