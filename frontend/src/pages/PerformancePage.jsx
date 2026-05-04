import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import BASE from '../config/api';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, Cell,
} from 'recharts';

const COLORS = ['#0a66c2', '#057642', '#7c3aed', '#e68a00', '#cc1016', '#06b6d4', '#ec4899'];

const SCENARIOS = {
  'A-search': 'Job Search',
  'A-detail': 'Job Detail',
  'B-submit': 'Apply Submit',
};

export default function PerformancePage() {
  const authCfg = useMemo(() => ({ headers: { Authorization: 'Bearer ' + localStorage.getItem('access_token') } }), []);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    axios.post(`${BASE.analytics}/benchmarks/list`, {}, authCfg)
      .then(({ data }) => {
        setItems(data?.data?.items || []);
        setError(null);
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          setError('Recruiter access required to view benchmark results.');
        } else {
          setError('Could not load benchmark data. Make sure the analytics service is running.');
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const scenarios = useMemo(() => {
    const map = {};
    items.forEach((b) => {
      const s = b.scenario || 'unknown';
      if (!map[s]) map[s] = [];
      map[s].push(b);
    });
    return map;
  }, [items]);

  const variantLatency = useMemo(() => {
    const map = {};
    items.forEach((b) => {
      const v = b.variant || b.config || 'default';
      if (!map[v]) map[v] = { variant: v, latency_sum: 0, p95_sum: 0, throughput_sum: 0, count: 0 };
      map[v].latency_sum += b.latency_ms_avg || 0;
      map[v].p95_sum += b.latency_ms_p95 || 0;
      map[v].throughput_sum += b.throughput || 0;
      map[v].count += 1;
    });
    return Object.values(map).map((v) => ({
      variant: v.variant,
      avg_latency: +(v.latency_sum / v.count).toFixed(1),
      avg_p95: +(v.p95_sum / v.count).toFixed(1),
      avg_throughput: +(v.throughput_sum / v.count).toFixed(1),
    })).sort((a, b) => a.avg_latency - b.avg_latency);
  }, [items]);

  const scenarioChart = useMemo(() =>
    Object.entries(scenarios).map(([s, runs]) => {
      const avg = (fn) => +(runs.reduce((acc, r) => acc + (r[fn] || 0), 0) / runs.length).toFixed(1);
      return {
        scenario: SCENARIOS[s] || s,
        avg_ms: avg('latency_ms_avg'),
        p95_ms: avg('latency_ms_p95'),
        p99_ms: avg('latency_ms_p99'),
        throughput: avg('throughput'),
        error_pct: avg('error_rate_pct'),
      };
    }), [scenarios]);

  if (loading) return (
    <div className="li-card" style={{ padding: 60, textAlign: 'center', color: 'rgba(0,0,0,0.5)' }}>
      <div style={{ width: 32, height: 32, border: '3px solid #e5e7eb', borderTopColor: '#0a66c2', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 14px' }} />
      Loading performance benchmarks…
    </div>
  );

  if (error) return (
    <div className="li-card" style={{ padding: 48, textAlign: 'center' }}>
      <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
      <p style={{ fontSize: 17, fontWeight: 600, marginBottom: 8 }}>Performance Dashboard</p>
      <p style={{ color: 'rgba(0,0,0,0.5)', fontSize: 14 }}>{error}</p>
      {error.includes('Recruiter') && (
        <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.4)', marginTop: 8 }}>Sign in as a recruiter to view benchmark results.</p>
      )}
    </div>
  );

  if (items.length === 0) return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Performance Dashboard</h1>
        <p style={{ color: 'rgba(0,0,0,0.55)', fontSize: 15 }}>System throughput, latency, and error-rate benchmarks</p>
      </div>
      <div className="li-card" style={{ padding: 60, textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>⚡</div>
        <p style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>No benchmark data yet</p>
        <p style={{ color: 'rgba(0,0,0,0.55)', marginBottom: 12 }}>Run the performance benchmark script to populate this dashboard.</p>
        <code style={{ fontSize: 12, background: '#f4f4f4', padding: '10px 16px', borderRadius: 6, display: 'inline-block', color: '#333' }}>
          python scripts/run_performance_benchmarks.py
        </code>
      </div>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ marginBottom: 8 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Performance Dashboard</h1>
        <p style={{ color: 'rgba(0,0,0,0.55)', fontSize: 15 }}>
          System throughput, latency, and error-rate — {items.length} benchmark run{items.length !== 1 ? 's' : ''} recorded
        </p>
      </div>

      {/* Summary stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 12 }}>
        <StatCard label="Benchmark Runs" value={items.length} unit="runs" color="#0a66c2" />
        <StatCard label="Best Avg Latency" value={Math.min(...items.map(i => i.latency_ms_avg || 999)).toFixed(0)} unit="ms" color="#057642" />
        <StatCard label="Best P95" value={Math.min(...items.map(i => i.latency_ms_p95 || 999)).toFixed(0)} unit="ms" color="#7c3aed" />
        <StatCard label="Peak Throughput" value={Math.max(...items.map(i => i.throughput || 0)).toFixed(1)} unit="req/s" color="#e68a00" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Latency by scenario */}
        <div style={S.card}>
          <ChartHeader title="Avg Latency by Scenario" sub="Lower is better — aggregated over all runs" />
          {scenarioChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={scenarioChart} margin={{ bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="scenario" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} unit="ms" />
                <Tooltip formatter={(v) => [`${v} ms`, '']} />
                <Legend />
                <Bar dataKey="avg_ms" name="Avg (ms)" fill="#0a66c2" radius={[4, 4, 0, 0]} />
                <Bar dataKey="p95_ms" name="P95 (ms)" fill="#7c3aed" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="No scenario data." />}
        </div>

        {/* Throughput by scenario */}
        <div style={S.card}>
          <ChartHeader title="Throughput by Scenario" sub="Requests per second — higher is better" />
          {scenarioChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={scenarioChart} margin={{ bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="scenario" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} unit=" r/s" />
                <Tooltip formatter={(v) => [`${v} req/s`, 'Throughput']} />
                <Bar dataKey="throughput" name="Throughput (req/s)" radius={[4, 4, 0, 0]}>
                  {scenarioChart.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="No throughput data." />}
        </div>

        {/* Latency by variant/config */}
        {variantLatency.length > 1 && (
          <div style={S.card}>
            <ChartHeader title="Latency by Config Variant" sub="Comparing deployment configurations" />
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={variantLatency} margin={{ bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="variant" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit="ms" />
                <Tooltip formatter={(v) => [`${v} ms`, '']} />
                <Legend />
                <Bar dataKey="avg_latency" name="Avg (ms)" fill="#0a66c2" radius={[4, 4, 0, 0]} />
                <Bar dataKey="avg_p95" name="P95 (ms)" fill="#cc1016" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Throughput by variant */}
        {variantLatency.length > 1 && (
          <div style={S.card}>
            <ChartHeader title="Throughput by Config Variant" sub="Req/s across deployment configurations" />
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={variantLatency} margin={{ bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="variant" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit=" r/s" />
                <Tooltip formatter={(v) => [`${v} req/s`, 'Throughput']} />
                <Bar dataKey="avg_throughput" name="Throughput (req/s)" radius={[4, 4, 0, 0]}>
                  {variantLatency.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Error rate */}
        {scenarioChart.some(s => s.error_pct > 0) && (
          <div style={S.card}>
            <ChartHeader title="Error Rate by Scenario" sub="% of requests that returned 4xx/5xx" />
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={scenarioChart} margin={{ bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="scenario" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} unit="%" domain={[0, 100]} />
                <Tooltip formatter={(v) => [`${v}%`, 'Error rate']} />
                <Bar dataKey="error_pct" name="Error %" fill="#cc1016" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Raw results table */}
      <div style={S.card}>
        <ChartHeader title="All Benchmark Runs" sub="Most recent first — full raw results table" />
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f8f9fa' }}>
                {['Scenario', 'Variant', 'Avg ms', 'P50 ms', 'P95 ms', 'P99 ms', 'Req/s', 'Error %', 'Workers', 'Requests', 'Timestamp'].map((h) => (
                  <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 700, color: 'rgba(0,0,0,0.6)', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5, borderBottom: '2px solid rgba(0,0,0,0.08)', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((b, i) => (
                <tr key={b.benchmark_id || i} style={{ borderBottom: '1px solid rgba(0,0,0,0.06)', background: i % 2 === 0 ? '#fff' : '#fafafa' }}>
                  <td style={S.td}><span style={{ fontWeight: 600 }}>{b.scenario || '—'}</span></td>
                  <td style={S.td}><span style={{ background: '#eef3f8', borderRadius: 4, padding: '2px 7px', fontSize: 12 }}>{b.variant || b.config || '—'}</span></td>
                  <td style={{ ...S.td, color: '#0a66c2', fontWeight: 700 }}>{b.latency_ms_avg?.toFixed(1) ?? '—'}</td>
                  <td style={S.td}>{b.latency_ms_p50?.toFixed(1) ?? '—'}</td>
                  <td style={{ ...S.td, color: b.latency_ms_p95 > 500 ? '#cc1016' : '#057642', fontWeight: 600 }}>{b.latency_ms_p95?.toFixed(1) ?? '—'}</td>
                  <td style={S.td}>{b.latency_ms_p99?.toFixed(1) ?? '—'}</td>
                  <td style={{ ...S.td, color: '#057642', fontWeight: 700 }}>{b.throughput?.toFixed(1) ?? '—'}</td>
                  <td style={{ ...S.td, color: (b.error_rate_pct || 0) > 0 ? '#cc1016' : '#057642' }}>{b.error_rate_pct?.toFixed(1) ?? '0.0'}%</td>
                  <td style={S.td}>{b.workers ?? b.concurrency ?? '—'}</td>
                  <td style={S.td}>{b.total_requests ?? '—'}</td>
                  <td style={{ ...S.td, color: 'rgba(0,0,0,0.4)', fontSize: 11 }}>{b.timestamp ? new Date(b.timestamp).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, unit, color }) {
  return (
    <div style={{ background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px rgba(0,0,0,0.1)', padding: '16px 18px' }}>
      <p style={{ fontSize: 11, color: 'rgba(0,0,0,0.45)', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 6 }}>{label}</p>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span style={{ fontSize: 32, fontWeight: 800, color, lineHeight: 1 }}>{value}</span>
        <span style={{ fontSize: 13, color: 'rgba(0,0,0,0.4)' }}>{unit}</span>
      </div>
    </div>
  );
}

function ChartHeader({ title, sub }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 2, color: 'rgba(0,0,0,0.9)' }}>{title}</h2>
      {sub && <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', fontStyle: 'italic' }}>{sub}</p>}
    </div>
  );
}

function Empty({ text }) {
  return <p style={{ textAlign: 'center', color: 'rgba(0,0,0,0.4)', fontSize: 14, padding: '32px 0' }}>{text}</p>;
}

const S = {
  card: { background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px rgba(0,0,0,0.1)', padding: '18px 20px' },
  td: { padding: '9px 12px', color: 'rgba(0,0,0,0.8)' },
};
