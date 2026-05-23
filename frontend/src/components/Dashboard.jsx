import React, { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { getDashboardStats, getDashboardLogs } from "../utils/api";

/**
 * Dashboard view: summary cards, latency + throughput charts, recent logs table.
 */
export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [s, l] = await Promise.all([
        getDashboardStats(hours),
        getDashboardLogs(50),
      ]);
      setStats(s);
      setLogs(l);
    } catch (err) {
      console.error("Dashboard fetch error:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15_000);
    return () => clearInterval(interval);
  }, [hours]);

  if (loading && !stats) {
    return (
      <div className="main-content">
        <div className="empty-state">
          <span className="spinner" /> Loading dashboard…
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="main-content">
        <div className="empty-state">No data available yet. Send some messages first.</div>
      </div>
    );
  }

  const errorRate =
    stats.total_requests > 0
      ? ((stats.error_count / stats.total_requests) * 100).toFixed(1)
      : "0.0";

  return (
    <div className="main-content">
      <div className="dashboard">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h2>Inference Dashboard</h2>
          <select
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            style={{
              padding: "6px 10px",
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              color: "var(--text)",
              fontSize: 12,
            }}
          >
            <option value={1}>Last 1 hour</option>
            <option value={6}>Last 6 hours</option>
            <option value={24}>Last 24 hours</option>
            <option value={168}>Last 7 days</option>
            <option value={720}>Last 30 days</option>
          </select>
        </div>

        {/* ── Summary cards ──────────────────────────────────── */}
        <div className="stats-grid">
          <StatCard label="Total Requests" value={stats.total_requests} />
          <StatCard label="Successful" value={stats.success_count} cls="success" />
          <StatCard label="Errors" value={stats.error_count} cls="error" />
          <StatCard label="Error Rate" value={`${errorRate}%`} cls={Number(errorRate) > 5 ? "error" : ""} />
          <StatCard label="Avg Latency" value={`${stats.avg_latency_ms.toFixed(0)} ms`} />
          <StatCard label="P95 Latency" value={`${stats.p95_latency_ms.toFixed(0)} ms`} />
          <StatCard label="Input Tokens" value={stats.total_input_tokens.toLocaleString()} />
          <StatCard label="Output Tokens" value={stats.total_output_tokens.toLocaleString()} />
        </div>

        {/* ── Latency chart ──────────────────────────────────── */}
        {stats.latency_over_time.length > 0 && (
          <div className="chart-section">
            <h3>Latency Over Time (ms)</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={stats.latency_over_time}>
                <CartesianGrid stroke="#2e3345" strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fill: "#8b8fa3", fontSize: 11 }} tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} />
                <YAxis tick={{ fill: "#8b8fa3", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#1a1d27", border: "1px solid #2e3345", borderRadius: 8, fontSize: 12 }} />
                <Legend />
                <Line type="monotone" dataKey="avg_ms" name="Avg" stroke="#6366f1" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="p95_ms" name="P95" stroke="#f59e0b" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* ── Throughput chart ────────────────────────────────── */}
        {stats.throughput_over_time.length > 0 && (
          <div className="chart-section">
            <h3>Throughput (Requests / Hour)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={stats.throughput_over_time}>
                <CartesianGrid stroke="#2e3345" strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fill: "#8b8fa3", fontSize: 11 }} tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} />
                <YAxis tick={{ fill: "#8b8fa3", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#1a1d27", border: "1px solid #2e3345", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="requests" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* ── Provider breakdown ──────────────────────────────── */}
        <div className="stats-grid">
          <div className="chart-section" style={{ marginBottom: 0 }}>
            <h3>Requests by Provider</h3>
            {Object.entries(stats.requests_per_provider).map(([p, c]) => (
              <div key={p} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: 13 }}>
                <span>{p}</span>
                <span style={{ fontWeight: 600 }}>{c}</span>
              </div>
            ))}
            {Object.keys(stats.requests_per_provider).length === 0 && (
              <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No data</div>
            )}
          </div>
          <div className="chart-section" style={{ marginBottom: 0 }}>
            <h3>Errors by Provider</h3>
            {Object.entries(stats.errors_per_provider).map(([p, c]) => (
              <div key={p} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: 13 }}>
                <span>{p}</span>
                <span style={{ fontWeight: 600, color: "var(--error)" }}>{c}</span>
              </div>
            ))}
            {Object.keys(stats.errors_per_provider).length === 0 && (
              <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No errors</div>
            )}
          </div>
        </div>

        {/* ── Recent logs table ──────────────────────────────── */}
        <div className="chart-section" style={{ marginTop: 20 }}>
          <h3>Recent Inference Logs</h3>
          {logs.length > 0 ? (
            <div style={{ overflowX: "auto" }}>
              <table className="log-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Provider</th>
                    <th>Model</th>
                    <th>Latency</th>
                    <th>Tokens (in/out)</th>
                    <th>Status</th>
                    <th>Input Preview</th>
                    <th>Output Preview</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id}>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td>{log.provider}</td>
                      <td>{log.model}</td>
                      <td>{log.latency_ms.toFixed(0)} ms</td>
                      <td>
                        {log.input_tokens ?? "–"} / {log.output_tokens ?? "–"}
                      </td>
                      <td>
                        <span className={`status-badge status-${log.status === "success" ? "active" : "cancelled"}`}>
                          {log.status}
                        </span>
                      </td>
                      <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {log.input_preview || "–"}
                      </td>
                      <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {log.output_preview || "–"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: 13, padding: 16, textAlign: "center" }}>
              No logs yet. Send some messages to see inference data.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, cls = "" }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className={`value ${cls}`}>{value}</div>
    </div>
  );
}
