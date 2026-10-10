import React from 'react';
import {
  X,
  Clock,
  Sparkles,
  Building,
  User,
  Tag,
} from 'lucide-react';

export default function CaseDetailModal({
  selectedCase,
  onClose,
  onTriageWithCopilot,
}) {
  if (!selectedCase) return null;

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
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog modal-case-detail" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-case-header-left">
            <span className="font-mono text-primary font-bold">{selectedCase.id}</span>
            <span className={`priority-badge ${getPriorityBadgeClass(selectedCase.priority)}`}>
              {selectedCase.priority}
            </span>
            <span className={`status-pill ${getStatusBadgeClass(selectedCase.status)}`}>
              {selectedCase.status}
            </span>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close dialog">
            <X size={20} />
          </button>
        </div>

        <div className="modal-case-body">
          <h3 className="modal-case-title">{selectedCase.issue}</h3>

          <div className="case-meta-grid">
            <div className="case-meta-item">
              <span className="meta-item-label">
                <Tag size={13} /> Category
              </span>
              <span className="meta-item-value">{selectedCase.category}</span>
            </div>

            <div className="case-meta-item">
              <span className="meta-item-label">
                <Building size={13} /> Store Location
              </span>
              <span className="meta-item-value font-mono">{selectedCase.storeId}</span>
            </div>

            <div className="case-meta-item">
              <span className="meta-item-label">
                <User size={13} /> Assigned Owner
              </span>
              <span className="meta-item-value">{selectedCase.assignedTo}</span>
            </div>

            <div className="case-meta-item">
              <span className="meta-item-label">
                <Clock size={13} /> Reported Time
              </span>
              <span className="meta-item-value">{selectedCase.createdAt}</span>
            </div>
          </div>

          <div className="case-description-box">
            <h4 className="box-title">Incident Details & Context</h4>
            <p className="box-text">{selectedCase.details || 'No additional technical notes provided.'}</p>
          </div>

          <div className="case-audit-trail">
            <h4 className="box-title">Simulated Audit Trail</h4>
            <div className="timeline-item">
              <div className="timeline-dot"></div>
              <div className="timeline-content">
                <span className="timeline-time">Reported ({selectedCase.createdAt})</span>
                <p className="timeline-text">
                  Incident logged into Punjab Sports Mart Operations Ledger for Store{' '}
                  {selectedCase.storeId}.
                </p>
              </div>
            </div>
            <div className="timeline-item">
              <div className="timeline-dot"></div>
              <div className="timeline-content">
                <span className="timeline-time">Triage Evaluation</span>
                <p className="timeline-text">
                  Classified severity as <strong>{selectedCase.priority}</strong> under standard
                  operating procedures. Assigned to {selectedCase.assignedTo}.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn-modal-cancel" onClick={onClose}>
            Close
          </button>
          <button
            className="btn-modal-copilot"
            onClick={() => {
              onTriageWithCopilot(selectedCase.issue);
              onClose();
            }}
          >
            <Sparkles size={16} />
            <span>Triage in AI Copilot</span>
          </button>
        </div>
      </div>
    </div>
  );
}
