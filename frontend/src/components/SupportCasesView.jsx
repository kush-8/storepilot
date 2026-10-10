import React, { useState, useMemo } from 'react';
import {
  Search,
  PlusCircle,
  Sparkles,
  Eye,
} from 'lucide-react';
import { STORES } from '../data/mockData';

export default function SupportCasesView({
  supportCases,
  setSupportCases,
  onTriageWithCopilot,
  onViewCase,
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [newCaseModalOpen, setNewCaseModalOpen] = useState(false);

  // New Case Form State
  const [newIssue, setNewIssue] = useState('');
  const [newCategory, setNewCategory] = useState('POS and Payments');
  const [newPriority, setNewPriority] = useState('P2');
  const [newStore, setNewStore] = useState('ST002');
  const [newDetails, setNewDetails] = useState('');

  // Extract categories for filter
  const categories = useMemo(() => {
    return Array.from(new Set(supportCases.map((c) => c.category)));
  }, [supportCases]);

  // Filtered Cases
  const filteredCases = useMemo(() => {
    return supportCases.filter((c) => {
      const matchesSearch =
        c.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.issue.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.assignedTo.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.storeId.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesPriority = priorityFilter === 'ALL' || c.priority === priorityFilter;
      const matchesStatus = statusFilter === 'ALL' || c.status === statusFilter;
      const matchesCategory = categoryFilter === 'ALL' || c.category === categoryFilter;

      return matchesSearch && matchesPriority && matchesStatus && matchesCategory;
    });
  }, [supportCases, searchQuery, priorityFilter, statusFilter, categoryFilter]);

  const handleToggleResolve = (caseId) => {
    setSupportCases((prev) =>
      prev.map((c) => {
        if (c.id === caseId) {
          const nextStatus = c.status === 'Resolved' ? 'Open' : 'Resolved';
          return { ...c, status: nextStatus };
        }
        return c;
      })
    );
  };

  const handleCreateNewCase = (e) => {
    e.preventDefault();
    if (!newIssue.trim()) return;

    const nextIdNumber = 4092 + supportCases.length;
    const newCase = {
      id: `CAS-${nextIdNumber}`,
      issue: newIssue.trim(),
      category: newCategory,
      priority: newPriority,
      storeId: newStore,
      status: 'Open',
      assignedTo: 'Store Duty Supervisor',
      createdAt: 'Just now',
      details: newDetails.trim() || 'Logged via Store Operations Desk.',
    };

    setSupportCases((prev) => [newCase, ...prev]);
    setNewIssue('');
    setNewDetails('');
    setNewCaseModalOpen(false);
  };

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
    <div className="cases-container">
      {/* Top Action & Search Bar */}
      <div className="cases-toolbar">
        <div className="search-input-wrapper">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search cases by ID, issue description, assignee, store..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="clear-search-btn" onClick={() => setSearchQuery('')}>
              ✕
            </button>
          )}
        </div>

        <div className="toolbar-actions">
          <button
            className="btn-create-case"
            onClick={() => setNewCaseModalOpen(true)}
          >
            <PlusCircle size={16} />
            <span>Report New Issue</span>
          </button>
        </div>
      </div>

      {/* Filter Chips Bar */}
      <div className="cases-filter-bar">
        <div className="filter-group">
          <span className="filter-label">Priority:</span>
          {['ALL', 'P1', 'P2', 'P3', 'P4'].map((p) => (
            <button
              key={p}
              className={`filter-chip ${priorityFilter === p ? 'active' : ''}`}
              onClick={() => setPriorityFilter(p)}
            >
              {p === 'ALL' ? 'All Priorities' : p}
            </button>
          ))}
        </div>

        <div className="filter-group">
          <span className="filter-label">Status:</span>
          {['ALL', 'Open', 'Investigating', 'Resolved'].map((s) => (
            <button
              key={s}
              className={`filter-chip ${statusFilter === s ? 'active' : ''}`}
              onClick={() => setStatusFilter(s)}
            >
              {s === 'ALL' ? 'All Statuses' : s}
            </button>
          ))}
        </div>

        <div className="filter-group">
          <span className="filter-label">Category:</span>
          <select
            className="filter-select"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="ALL">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Support Cases Table Card */}
      <div className="dashboard-table-card">
        <div className="table-header-row">
          <div>
            <h3 className="table-title">Retail Incident & Support Queue</h3>
            <p className="table-subtitle">
              Displaying {filteredCases.length} of {supportCases.length} operational cases
            </p>
          </div>
          <span className="sample-badge">Sample Ticketing Data</span>
        </div>

        <div className="table-responsive">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Case ID</th>
                <th>Issue Description</th>
                <th>Store ID</th>
                <th>Category</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Assigned To</th>
                <th>Reported</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredCases.length === 0 ? (
                <tr>
                  <td colSpan={9} className="empty-table-cell">
                    No support cases match the current filter criteria.
                  </td>
                </tr>
              ) : (
                filteredCases.map((c) => {
                  const isResolved = c.status === 'Resolved';

                  return (
                    <tr key={c.id} className={c.priority === 'P1' && !isResolved ? 'row-critical' : ''}>
                      <td className="font-mono text-primary font-semibold">{c.id}</td>
                      <td className="cell-issue">
                        <div className="issue-title-text font-medium">{c.issue}</div>
                        {c.details && (
                          <div className="text-xs text-muted truncate-text">{c.details}</div>
                        )}
                      </td>
                      <td>
                        <span className="store-pill font-mono">{c.storeId}</span>
                      </td>
                      <td>
                        <span className="category-pill">{c.category}</span>
                      </td>
                      <td>
                        <span className={`priority-badge ${getPriorityBadgeClass(c.priority)}`}>
                          {c.priority}
                        </span>
                      </td>
                      <td>
                        <span className={`status-pill ${getStatusBadgeClass(c.status)}`}>
                          {c.status}
                        </span>
                      </td>
                      <td className="text-muted text-sm">{c.assignedTo}</td>
                      <td className="text-muted text-xs">{c.createdAt}</td>
                      <td className="text-right">
                        <div className="table-actions">
                          {/* Copilot Action */}
                          <button
                            className="btn-table-action"
                            onClick={() => onTriageWithCopilot(c.issue)}
                            title="Triage this case in AI Copilot"
                          >
                            <Sparkles size={14} />
                            <span>Copilot</span>
                          </button>

                          {/* Details Modal */}
                          <button
                            className="btn-table-action-secondary"
                            onClick={() => onViewCase(c)}
                            title="View case details"
                          >
                            <Eye size={14} />
                          </button>

                          {/* Resolve / Re-open Toggle */}
                          <button
                            className={`btn-table-action-toggle ${isResolved ? 'btn-reopen' : 'btn-resolve'}`}
                            onClick={() => handleToggleResolve(c.id)}
                            title={isResolved ? 'Re-open case' : 'Mark as resolved'}
                          >
                            {isResolved ? 'Reopen' : 'Resolve'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Report New Support Case */}
      {newCaseModalOpen && (
        <div className="modal-backdrop" onClick={() => setNewCaseModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Log New Store Support Case</h3>
              <button
                className="modal-close-btn"
                onClick={() => setNewCaseModalOpen(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateNewCase} className="modal-form">
              <div className="form-group">
                <label className="form-label">Issue Summary / Title</label>
                <input
                  type="text"
                  className="form-input"
                  required
                  placeholder="e.g. Card reader offline at checkout 4"
                  value={newIssue}
                  onChange={(e) => setNewIssue(e.target.value)}
                />
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label className="form-label">Category</label>
                  <select
                    className="form-select"
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                  >
                    <option value="POS and Payments">POS and Payments</option>
                    <option value="Inventory and Replenishment">Inventory and Replenishment</option>
                    <option value="Pricing and Promotions">Pricing and Promotions</option>
                    <option value="Returns and Refunds">Returns and Refunds</option>
                    <option value="Facilities & Hardware">Facilities & Hardware</option>
                    <option value="Vendor & Logistics">Vendor & Logistics</option>
                  </select>
                </div>

                <div className="form-group flex-1">
                  <label className="form-label">Priority</label>
                  <select
                    className="form-select"
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value)}
                  >
                    <option value="P1">P1 - Critical (Outage)</option>
                    <option value="P2">P2 - High (Lost Sales / Review)</option>
                    <option value="P3">P3 - Medium (Localized Triage)</option>
                    <option value="P4">P4 - Low (Informational)</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label className="form-label">Store Location</label>
                  <select
                    className="form-select"
                    value={newStore}
                    onChange={(e) => setNewStore(e.target.value)}
                  >
                    {STORES.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.id} - {s.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Incident Details & Context</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="Describe observations, affected equipment, or customer interaction..."
                  value={newDetails}
                  onChange={(e) => setNewDetails(e.target.value)}
                />
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-modal-cancel"
                  onClick={() => setNewCaseModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-modal-submit">
                  Log Incident
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
