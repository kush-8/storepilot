import React from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Clock,
  PackageX,
  Sparkles,
} from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';
import { PRIORITY_CHART_DATA, CATEGORY_CHART_DATA } from '../data/mockData';

// Custom tooltip for Priority Chart
const CustomPieTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0];
    return (
      <div className="chart-tooltip">
        <p className="tooltip-title">{data.name}</p>
        <p className="tooltip-value">
          <span className="tooltip-dot" style={{ backgroundColor: data.payload.color }} />
          <strong>{data.value}</strong> active cases
        </p>
      </div>
    );
  }
  return null;
};

// Custom tooltip for Category Bar Chart
const CustomBarTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="chart-tooltip">
        <p className="tooltip-title">{label}</p>
        {payload.map((item, idx) => (
          <p key={idx} className="tooltip-value">
            <span className="tooltip-dot" style={{ backgroundColor: item.color }} />
            {item.name}: <strong>{item.value}</strong>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function DashboardView({
  supportCases,
  inventory,
  onTriageWithCopilot,
  onViewCase,
  selectedStore,
}) {
  // Compute dynamic stats from props
  const totalOpenCases = supportCases.filter((c) => c.status !== 'Resolved').length;
  const p1CriticalCases = supportCases.filter(
    (c) => c.priority === 'P1' && c.status !== 'Resolved'
  ).length;
  const p2HighCases = supportCases.filter(
    (c) => c.priority === 'P2' && c.status !== 'Resolved'
  ).length;
  const stockAlerts = inventory.filter(
    (item) => item.status === 'Out of Stock' || item.status === 'Low Stock'
  ).length;

  // Recent cases for the table
  const recentCases = supportCases.slice(0, 6);

  const getPriorityBadgeClass = (priority) => {
    switch (priority) {
      case 'P1':
        return 'badge-p1';
      case 'P2':
        return 'badge-p2';
      case 'P3':
        return 'badge-p3';
      case 'P4':
        return 'badge-p4';
      default:
        return 'badge-neutral';
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'Open':
        return 'status-open';
      case 'Investigating':
        return 'status-investigating';
      case 'Resolved':
        return 'status-resolved';
      default:
        return 'status-neutral';
    }
  };

  return (
    <div className="dashboard-container">
      {/* Sample Data Disclaimer Banner */}
      <div className="demo-notice-bar">
        <div className="notice-content">
          <span className="notice-icon">ℹ️</span>
          <div>
            <strong>Sample Enterprise Data:</strong> This dashboard displays simulated operational
            metrics for Punjab Sports Mart (Store {selectedStore} & Regional Hubs).
            It does not connect to live backend enterprise ERP systems.
          </div>
        </div>
        <div className="sample-tag">PROTOTYPE SANDBOX</div>
      </div>

      {/* Top Metric / KPI Cards */}
      <div className="kpi-grid">
        {/* Card 1: Total Open Cases */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">TOTAL OPEN CASES</span>
            <div className="kpi-icon-wrapper bg-blue-subtle">
              <Clock size={20} className="text-blue" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value">{totalOpenCases}</div>
            <div className="kpi-meta text-warning">
              <span>+3 reported today</span>
              <span className="meta-sub">across 4 retail hubs</span>
            </div>
          </div>
        </div>

        {/* Card 2: P1 Critical Cases */}
        <div className="kpi-card kpi-border-p1">
          <div className="kpi-header">
            <span className="kpi-label text-danger font-semibold">P1 CRITICAL CASES</span>
            <div className="kpi-icon-wrapper bg-red-subtle">
              <AlertCircle size={20} className="text-danger" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-danger">{p1CriticalCases}</div>
            <div className="kpi-meta text-danger">
              <span className="pulse-dot"></span>
              <span>Requires immediate escalation</span>
            </div>
          </div>
        </div>

        {/* Card 3: P2 High Priority */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">P2 HIGH PRIORITY</span>
            <div className="kpi-icon-wrapper bg-orange-subtle">
              <AlertTriangle size={20} className="text-orange" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-orange">{p2HighCases}</div>
            <div className="kpi-meta text-muted">
              <span>Manager review & vendor triage</span>
            </div>
          </div>
        </div>

        {/* Card 4: Inventory Alerts */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">INVENTORY STOCK ALERTS</span>
            <div className="kpi-icon-wrapper bg-amber-subtle">
              <PackageX size={20} className="text-amber" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-amber">{stockAlerts}</div>
            <div className="kpi-meta text-muted">
              <span>2 critical hero SKUs depleted</span>
            </div>
          </div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="charts-grid">
        {/* Chart 1: Priority Distribution Donut */}
        <div className="chart-card">
          <div className="chart-card-header">
            <div>
              <h3 className="chart-title">Case Priority Distribution</h3>
              <p className="chart-subtitle">Active incident breakdown by severity rating</p>
            </div>
            <span className="sample-badge">Sample Data</span>
          </div>
          <div className="chart-body" style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={PRIORITY_CHART_DATA}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {PRIORITY_CHART_DATA.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<CustomPieTooltip />} />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value) => <span className="chart-legend-text">{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Issue Category Distribution */}
        <div className="chart-card">
          <div className="chart-card-header">
            <div>
              <h3 className="chart-title">Incident Volume by Category</h3>
              <p className="chart-subtitle">Open vs Resolved tickets across store domains</p>
            </div>
            <span className="sample-badge">Sample Data</span>
          </div>
          <div className="chart-body" style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={CATEGORY_CHART_DATA}
                margin={{ top: 15, right: 15, left: -10, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis
                  dataKey="category"
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={{ stroke: '#cbd5e1' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<CustomBarTooltip />} />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value) => <span className="chart-legend-text">{value}</span>}
                />
                <Bar dataKey="open" name="Active Open" fill="#ef4444" radius={[4, 4, 0, 0]} />
                <Bar dataKey="resolved" name="Resolved (MTD)" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Support Cases Table */}
      <div className="dashboard-table-card">
        <div className="table-header-row">
          <div>
            <h3 className="table-title">Recent Operational Support Cases</h3>
            <p className="table-subtitle">
              Live queue of reported floor incidents, billing interruptions & inventory stockouts
            </p>
          </div>
          <div className="table-header-meta">
            <span className="sample-badge">Sample Table Data</span>
          </div>
        </div>

        <div className="table-responsive">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Case ID</th>
                <th>Issue Description</th>
                <th>Category</th>
                <th>Priority</th>
                <th>Store ID</th>
                <th>Status</th>
                <th>Logged</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {recentCases.map((c) => (
                <tr key={c.id}>
                  <td className="font-mono text-primary font-semibold">{c.id}</td>
                  <td className="cell-issue">
                    <span className="issue-title-text">{c.issue}</span>
                  </td>
                  <td>
                    <span className="category-pill">{c.category}</span>
                  </td>
                  <td>
                    <span className={`priority-badge ${getPriorityBadgeClass(c.priority)}`}>
                      {c.priority}
                    </span>
                  </td>
                  <td className="font-mono text-muted">{c.storeId}</td>
                  <td>
                    <span className={`status-pill ${getStatusBadgeClass(c.status)}`}>
                      {c.status}
                    </span>
                  </td>
                  <td className="text-muted text-sm">{c.createdAt}</td>
                  <td className="text-right">
                    <div className="table-actions">
                      <button
                        className="btn-table-action"
                        onClick={() => onTriageWithCopilot(c.issue)}
                        title="Triage this issue with AI Copilot"
                      >
                        <Sparkles size={14} />
                        <span>Copilot Triage</span>
                      </button>
                      <button
                        className="btn-table-action-secondary"
                        onClick={() => onViewCase(c)}
                        title="View case details"
                      >
                        <span>Details</span>
                      </button>
                    </div>
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
