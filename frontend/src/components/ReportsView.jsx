import React, { useState } from 'react';
import {
  FileText,
  Download,
  CheckCircle2,
  Clock,
  Building,
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
} from 'recharts';

const STORE_INCIDENT_DATA = [
  { store: 'ST001 Amritsar', p1: 1, p2: 3, p3: 4, p4: 2, total: 10 },
  { store: 'ST002 Jalandhar', p1: 2, p2: 4, p3: 5, p4: 2, total: 13 },
  { store: 'ST003 Ludhiana', p1: 0, p2: 2, p3: 4, p4: 3, total: 9 },
  { store: 'ST004 Mohali', p1: 0, p2: 1, p3: 3, p4: 2, total: 6 },
];

export default function ReportsView() {
  const [downloading, setDownloading] = useState(false);
  const [exportedMsg, setExportedMsg] = useState('');

  const handleExport = (reportType) => {
    setDownloading(true);
    setTimeout(() => {
      setDownloading(false);
      setExportedMsg(`Successfully generated "${reportType}" (CSV Export Simulated)`);
      setTimeout(() => setExportedMsg(''), 4000);
    }, 800);
  };

  return (
    <div className="reports-container">
      {/* Toast */}
      {exportedMsg && (
        <div className="inventory-toast-banner">
          <CheckCircle2 size={18} className="text-success" />
          <span>{exportedMsg}</span>
          <button className="toast-close" onClick={() => setExportedMsg('')}>
            ✕
          </button>
        </div>
      )}

      {/* Header bar */}
      <div className="reports-header-card">
        <div>
          <h3 className="reports-title">Punjab Sports Mart Operations Compliance Report</h3>
          <p className="reports-subtitle">
            Audited store reliability metrics, SLA adherence, and payment hardware uptime
          </p>
        </div>
        <div className="reports-actions">
          <button
            className="btn-export-csv"
            onClick={() => handleExport('October 2026 Executive Summary')}
            disabled={downloading}
          >
            <Download size={16} />
            <span>{downloading ? 'Exporting...' : 'Export Audit CSV'}</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">OVERALL SLA ADHERENCE</span>
            <div className="kpi-icon-wrapper bg-green-subtle">
              <CheckCircle2 size={20} className="text-success" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-success">96.4%</div>
            <div className="kpi-meta text-muted">Incident resolution within target SLA</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">P1 MEAN TIME TO RESOLVE</span>
            <div className="kpi-icon-wrapper bg-blue-subtle">
              <Clock size={20} className="text-blue" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-primary">22 mins</div>
            <div className="kpi-meta text-success">Target: 30 minutes</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">POS HARDWARE UPTIME</span>
            <div className="kpi-icon-wrapper bg-blue-subtle">
              <Building size={20} className="text-blue" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-dark">99.82%</div>
            <div className="kpi-meta text-muted">Across 24 checkout pin-pads</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">AUDIT COMPLIANCE SCORE</span>
            <div className="kpi-icon-wrapper bg-amber-subtle">
              <FileText size={20} className="text-amber" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-dark">98/100</div>
            <div className="kpi-meta text-success">PCI-DSS Level 1 Audit Ready</div>
          </div>
        </div>
      </div>

      {/* Recharts Store Incident Distribution */}
      <div className="chart-card">
        <div className="chart-card-header">
          <div>
            <h3 className="chart-title">Incident Frequency by Retail Location</h3>
            <p className="chart-subtitle">Breakdown of P1–P4 tickets logged per branch this month</p>
          </div>
          <span className="sample-badge">Store Comparison</span>
        </div>
        <div className="chart-body" style={{ height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={STORE_INCIDENT_DATA}
              margin={{ top: 15, right: 15, left: -10, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis
                dataKey="store"
                tick={{ fontSize: 11, fill: '#64748b' }}
                axisLine={{ stroke: '#cbd5e1' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#64748b' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip />
              <Legend
                verticalAlign="bottom"
                height={32}
                formatter={(val) => <span className="chart-legend-text">{val}</span>}
              />
              <Bar dataKey="p1" name="P1 Critical" fill="#ef4444" radius={[3, 3, 0, 0]} />
              <Bar dataKey="p2" name="P2 High" fill="#f97316" radius={[3, 3, 0, 0]} />
              <Bar dataKey="p3" name="P3 Medium" fill="#eab308" radius={[3, 3, 0, 0]} />
              <Bar dataKey="p4" name="P4 Low" fill="#3b82f6" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
