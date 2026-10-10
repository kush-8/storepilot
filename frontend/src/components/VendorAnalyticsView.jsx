import React from 'react';
import {
  Truck,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Sparkles,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  AreaChart,
  Area,
} from 'recharts';
import { VENDOR_METRICS, VENDOR_TREND_DATA } from '../data/mockData';

const CustomVendorBarTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="chart-tooltip">
        <p className="tooltip-title">{label}</p>
        {payload.map((entry, idx) => (
          <p key={idx} className="tooltip-value">
            <span className="tooltip-dot" style={{ backgroundColor: entry.color }} />
            {entry.name}: <strong>{entry.value}%</strong>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const CustomTrendTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="chart-tooltip">
        <p className="tooltip-title">{label}</p>
        {payload.map((entry, idx) => (
          <p key={idx} className="tooltip-value">
            <span className="tooltip-dot" style={{ backgroundColor: entry.color }} />
            {entry.name}: <strong>{entry.value}%</strong>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function VendorAnalyticsView({ onTriageWithCopilot }) {
  const getGradeBadgeClass = (grade) => {
    if (grade.startsWith('A')) return 'grade-badge-a';
    if (grade.startsWith('B')) return 'grade-badge-b';
    return 'grade-badge-c';
  };

  const getStatusBadge = (status, color) => {
    switch (color) {
      case 'green':
        return <span className="status-badge-in">{status}</span>;
      case 'orange':
        return <span className="status-badge-low">{status}</span>;
      case 'red':
        return <span className="status-badge-out">{status}</span>;
      default:
        return <span className="status-badge-neutral">{status}</span>;
    }
  };

  return (
    <div className="vendor-container">
      {/* Disclaimer */}
      <div className="demo-notice-bar">
        <div className="notice-content">
          <span className="notice-icon">📊</span>
          <div>
            <strong>Vendor Performance Ledger:</strong> Benchmark analytics for Punjab Sports
            Mart suppliers. Metrics evaluate contract fill rates, consignment on-time SLAs, and
            lead time variability.
          </div>
        </div>
        <div className="sample-tag">Sample Data</div>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">AVERAGE FILL RATE</span>
            <div className="kpi-icon-wrapper bg-blue-subtle">
              <CheckCircle2 size={20} className="text-blue" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value">92.8%</div>
            <div className="kpi-meta text-success">
              <span>+1.4% vs last quarter</span>
              <span className="meta-sub">Target: 92.0%</span>
            </div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">ON-TIME DELIVERY SLA</span>
            <div className="kpi-icon-wrapper bg-green-subtle">
              <Truck size={20} className="text-success" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-success">90.6%</div>
            <div className="kpi-meta text-muted">
              <span>9 out of 10 consignments on schedule</span>
            </div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">AVG LEAD TIME</span>
            <div className="kpi-icon-wrapper bg-amber-subtle">
              <Clock size={20} className="text-amber" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-dark">5.6 Days</div>
            <div className="kpi-meta text-warning">
              <span>Gym equipment vendors averaging 13.8d</span>
            </div>
          </div>
        </div>

        <div className="kpi-card kpi-border-p1">
          <div className="kpi-header">
            <span className="kpi-label text-danger font-semibold">VENDORS UNDER REVIEW</span>
            <div className="kpi-icon-wrapper bg-red-subtle">
              <AlertTriangle size={20} className="text-danger" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-danger">2 Suppliers</div>
            <div className="kpi-meta text-danger">
              <span>SG Sports (Cricket) & Proline Fitness</span>
            </div>
          </div>
        </div>
      </div>

      {/* Recharts Analytics Section */}
      <div className="charts-grid">
        {/* Chart 1: Fill Rate & On-Time Comparison */}
        <div className="chart-card">
          <div className="chart-card-header">
            <div>
              <h3 className="chart-title">Supplier Fulfillment Scorecard</h3>
              <p className="chart-subtitle">Order Fill Rate vs On-Time Dispatch Rate (%)</p>
            </div>
            <span className="sample-badge">Comparative Bar</span>
          </div>
          <div className="chart-body" style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={VENDOR_METRICS}
                margin={{ top: 15, right: 15, left: -10, bottom: 25 }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fill: '#64748b' }}
                  angle={-15}
                  textAnchor="end"
                  interval={0}
                  axisLine={{ stroke: '#cbd5e1' }}
                  tickLine={false}
                />
                <YAxis
                  domain={[60, 100]}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<CustomVendorBarTooltip />} />
                <Legend
                  verticalAlign="top"
                  align="right"
                  height={32}
                  formatter={(val) => <span className="chart-legend-text">{val}</span>}
                />
                <Bar dataKey="fillRate" name="Fill Rate %" fill="#2563eb" radius={[4, 4, 0, 0]} />
                <Bar dataKey="onTimeRate" name="On-Time Rate %" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Monthly Trends */}
        <div className="chart-card">
          <div className="chart-card-header">
            <div>
              <h3 className="chart-title">6-Month Fulfillment Trend</h3>
              <p className="chart-subtitle">Historical supplier compliance vs 92% benchmark target</p>
            </div>
            <span className="sample-badge">Trend Area</span>
          </div>
          <div className="chart-body" style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={VENDOR_TREND_DATA}
                margin={{ top: 15, right: 15, left: -10, bottom: 5 }}
              >
                <defs>
                  <linearGradient id="colorFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563eb" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#2563eb" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorOnTime" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={{ stroke: '#cbd5e1' }}
                  tickLine={false}
                />
                <YAxis
                  domain={[80, 100]}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<CustomTrendTooltip />} />
                <Legend
                  verticalAlign="top"
                  align="right"
                  height={32}
                  formatter={(val) => <span className="chart-legend-text">{val}</span>}
                />
                <Area
                  type="monotone"
                  dataKey="avgFillRate"
                  name="Avg Fill Rate %"
                  stroke="#2563eb"
                  fillOpacity={1}
                  fill="url(#colorFill)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="avgOnTime"
                  name="Avg On-Time %"
                  stroke="#10b981"
                  fillOpacity={1}
                  fill="url(#colorOnTime)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Vendor Table */}
      <div className="dashboard-table-card">
        <div className="table-header-row">
          <div>
            <h3 className="table-title">Vendor SLA Performance Registry</h3>
            <p className="table-subtitle">
              Contract terms, lead times, and active reliability status for Punjab Sports Mart
            </p>
          </div>
          <span className="sample-badge">Supplier Directory</span>
        </div>

        <div className="table-responsive">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Vendor Name</th>
                <th>Category</th>
                <th className="text-center">Fill Rate</th>
                <th className="text-center">On-Time Rate</th>
                <th className="text-center">Avg Lead Time</th>
                <th className="text-center">Grade</th>
                <th>Status</th>
                <th>POC Contact</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {VENDOR_METRICS.map((v) => (
                <tr key={v.name}>
                  <td>
                    <div className="font-semibold text-dark">{v.name}</div>
                    <div className="text-xs text-muted">{v.totalOrders} POs processed</div>
                  </td>
                  <td>
                    <span className="category-pill">{v.category}</span>
                  </td>
                  <td className="text-center">
                    <span
                      className={`font-bold ${
                        v.fillRate >= 92 ? 'text-success' : v.fillRate >= 85 ? 'text-orange' : 'text-danger'
                      }`}
                    >
                      {v.fillRate}%
                    </span>
                  </td>
                  <td className="text-center">
                    <span
                      className={`font-bold ${
                        v.onTimeRate >= 92 ? 'text-success' : v.onTimeRate >= 85 ? 'text-orange' : 'text-danger'
                      }`}
                    >
                      {v.onTimeRate}%
                    </span>
                  </td>
                  <td className="text-center font-mono text-muted">{v.avgLeadTimeDays} days</td>
                  <td className="text-center">
                    <span className={`grade-badge ${getGradeBadgeClass(v.grade)}`}>{v.grade}</span>
                  </td>
                  <td>{getStatusBadge(v.status, v.statusColor)}</td>
                  <td className="text-muted text-xs font-mono">{v.primaryContact}</td>
                  <td className="text-right">
                    <button
                      className="btn-table-action"
                      onClick={() =>
                        onTriageWithCopilot(
                          `Vendor review for ${v.name}: Fill rate is ${v.fillRate}% and on-time delivery is ${v.onTimeRate}% with ${v.avgLeadTimeDays} days lead time`
                        )
                      }
                      title="Analyze vendor SLA with Copilot"
                    >
                      <Sparkles size={14} />
                      <span>Copilot Audit</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
