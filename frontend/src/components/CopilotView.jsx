import React, { useState, useCallback } from 'react';
import {
  Bot,
  Sparkles,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  CheckCircle,
  Copy,
  PlusCircle,
  RefreshCw,
  FileCheck2,
  Lock,
  ArrowRight,
  Check,
} from 'lucide-react';
import { analyzeEmployeeIssue, EXAMPLE_PROMPTS } from '../services/copilotEngine';

export default function CopilotView({
  initialQuery = '',
  onCreateSupportCase,
  selectedStore = 'ST002',
}) {
  const defaultStartingPrompt = initialQuery || 'All registers cannot process card payments';

  const [inputText, setInputText] = useState(defaultStartingPrompt);
  const [isLoading, setIsLoading] = useState(false);
  const [activeAnalysis, setActiveAnalysis] = useState(() =>
    analyzeEmployeeIssue(defaultStartingPrompt)
  );
  const [copied, setCopied] = useState(false);
  const [actionChecked, setActionChecked] = useState({});
  const [ticketCreated, setTicketCreated] = useState(false);
  const [history, setHistory] = useState(() => [
    {
      prompt: defaultStartingPrompt,
      result: analyzeEmployeeIssue(defaultStartingPrompt),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const handleAnalyze = useCallback(
    (textToAnalyze) => {
      const query = (textToAnalyze ?? inputText ?? '').trim();
      if (!query) return;

      setIsLoading(true);
      setTicketCreated(false);
      setActionChecked({});

      setTimeout(() => {
        const result = analyzeEmployeeIssue(query);
        setActiveAnalysis(result);
        setIsLoading(false);
        setHistory((prev) => [
          {
            prompt: query,
            result,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
          ...prev.filter((h) => h.prompt !== query).slice(0, 5),
        ]);
      }, 600);
    },
    [inputText]
  );

  const handleExampleClick = (prompt) => {
    setInputText(prompt);
    handleAnalyze(prompt);
  };

  const handleCopyPlan = () => {
    if (!activeAnalysis) return;
    const textToCopy = `[PUNJAB SPORTS MART - OPS COPILOT TRIAGE]
Store: ${selectedStore}
Category: ${activeAnalysis.category}
Priority: ${activeAnalysis.priority}
Escalation: ${activeAnalysis.escalationStatus}

Reasoning:
${activeAnalysis.reasoning}

Recommended Actions:
${activeAnalysis.recommendedActions.map((a, i) => `${i + 1}. ${a}`).join('\n')}

Policy Reference:
${activeAnalysis.policyEvidence}`;

    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleToggleCheck = (index) => {
    setActionChecked((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
  };

  const handleCreateTicket = () => {
    if (!activeAnalysis) return;
    onCreateSupportCase({
      issue: inputText,
      category: activeAnalysis.category,
      priority: activeAnalysis.priority,
      storeId: selectedStore,
      status: activeAnalysis.priority === 'P1' ? 'Escalated' : 'Open',
      assignedTo: activeAnalysis.isSecurityRefusal
        ? 'Regional InfoSec Desk'
        : activeAnalysis.priority === 'P1'
        ? 'Regional IT On-Call'
        : 'Store Supervisor',
      details: activeAnalysis.reasoning,
    });
    setTicketCreated(true);
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

  const getEscalationStyle = (tone) => {
    switch (tone) {
      case 'danger':
        return 'escalation-danger';
      case 'warning':
        return 'escalation-warning';
      case 'info':
      default:
        return 'escalation-info';
    }
  };

  return (
    <div className="copilot-container">
      {/* Copilot Header & Responsible AI Safeguard Disclaimer */}
      <div className="copilot-top-banner">
        <div className="banner-info">
          <div className="banner-icon-box">
            <Sparkles size={22} className="text-blue" />
          </div>
          <div>
            <h3 className="banner-title">Punjab Sports Mart Operations Copilot</h3>
            <p className="banner-subtitle">
              Simulated Rule-Based AI Engine • Real-time operational triage, SOP lookup & escalation decision engine
            </p>
          </div>
        </div>
        <div className="banner-safeguards">
          <span className="safeguard-badge">
            <ShieldCheck size={14} /> Responsible AI Safeguards Active
          </span>
          <span className="safeguard-sub">PCI-DSS Tokenized • Demo Prototype Engine</span>
        </div>
      </div>

      <div className="copilot-workspace-grid">
        {/* Left Column: Input and Example Prompts */}
        <div className="copilot-input-column">
          <div className="input-card">
            <div className="input-card-header">
              <label htmlFor="employee-issue-input" className="input-label">
                Describe Employee Issue or Store Incident
              </label>
              <button
                className="btn-clear-input"
                onClick={() => setInputText('')}
                disabled={!inputText}
              >
                Clear
              </button>
            </div>

            <div className="textarea-wrapper">
              <textarea
                id="employee-issue-input"
                className="copilot-textarea"
                rows={4}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Example: English Willow cricket bat out of stock at ST002, or all registers cannot process card payments..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    handleAnalyze();
                  }
                }}
              />
            </div>

            <div className="input-action-bar">
              <span className="input-tip">
                Tip: Press <code>Ctrl + Enter</code> to analyze
              </span>
              <button
                className="btn-submit-copilot"
                onClick={() => handleAnalyze()}
                disabled={isLoading || !inputText.trim()}
              >
                {isLoading ? (
                  <>
                    <RefreshCw size={16} className="spin-icon" />
                    <span>Analyzing Issue...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    <span>Analyze with Copilot</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Example Prompt Chips */}
          <div className="example-prompts-card">
            <div className="examples-header">
              <span className="examples-title">CLICK AN EXAMPLE INCIDENT SCENARIO</span>
              <span className="examples-sub">Demonstrates SOP triage & guardrails</span>
            </div>
            <div className="prompt-buttons-list">
              {EXAMPLE_PROMPTS.map((prompt, idx) => {
                const isSecurityTest = prompt.toLowerCase().includes('password') || prompt.toLowerCase().includes('credit card');
                return (
                  <button
                    key={idx}
                    className={`btn-prompt-chip ${isSecurityTest ? 'chip-security' : ''}`}
                    onClick={() => handleExampleClick(prompt)}
                  >
                    {isSecurityTest ? (
                      <Lock size={14} className="chip-icon text-danger" />
                    ) : (
                      <ArrowRight size={14} className="chip-icon text-primary" />
                    )}
                    <span className="chip-text">{prompt}</span>
                    {isSecurityTest && <span className="chip-tag-refusal">Security Test</span>}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Recent Query History */}
          {history.length > 1 && (
            <div className="history-card">
              <div className="history-header">
                <span>RECENT SESSION TRIAGES</span>
              </div>
              <ul className="history-list">
                {history.map((h, i) => (
                  <li key={i} className="history-item">
                    <button
                      className="history-btn"
                      onClick={() => {
                        setInputText(h.prompt);
                        setActiveAnalysis(h.result);
                      }}
                    >
                      <span className={`priority-mini-pill ${getPriorityBadgeClass(h.result.priority)}`}>
                        {h.result.priority}
                      </span>
                      <span className="history-prompt-text">{h.prompt}</span>
                      <span className="history-time">{h.timestamp}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right Column: Structured AI Response Panel */}
        <div className="copilot-response-column">
          {isLoading ? (
            <div className="loading-state-card">
              <div className="loading-spinner-circle">
                <RefreshCw size={32} className="spin-icon text-primary" />
              </div>
              <h4 className="loading-title">Evaluating Operational Standard Operating Procedures...</h4>
              <p className="loading-desc">
                Analyzing issue context, checking store safety thresholds, referencing policy
                guidelines, and determining escalation level for Store {selectedStore}.
              </p>
            </div>
          ) : activeAnalysis ? (
            <div className="response-card">
              {/* Header: Category & Priority */}
              <div className="response-header">
                <div className="response-header-left">
                  <div className="category-meta">
                    <span className="category-tag-title">ISSUE CATEGORY</span>
                    <h3 className="category-tag-value">{activeAnalysis.category}</h3>
                  </div>
                </div>

                <div className="response-header-right">
                  <div className="confidence-pill" title="Local rule inference confidence">
                    <span className="confidence-label">Confidence:</span>
                    <strong className="confidence-value">{activeAnalysis.confidence}%</strong>
                  </div>
                  <div
                    className={`priority-badge-lg ${getPriorityBadgeClass(
                      activeAnalysis.priority
                    )}`}
                  >
                    {activeAnalysis.priorityLabel || activeAnalysis.priority}
                  </div>
                </div>
              </div>

              {/* Responsible AI Security Flag or Banner */}
              {activeAnalysis.isSecurityRefusal && (
                <div className="security-refusal-banner">
                  <div className="refusal-icon-col">
                    <ShieldAlert size={28} className="text-danger" />
                  </div>
                  <div className="refusal-body">
                    <h4 className="refusal-title">
                      RESPONSIBLE AI REFUSAL: SENSITIVE CREDENTIAL & PII PROTECTION
                    </h4>
                    <p className="refusal-text">
                      The Punjab Sports Mart Copilot has intercepted this query. In accordance with
                      PCI-DSS Requirement 3.4 and ISO/IEC 27001 data protection protocols, cardholder
                      numbers, CVVs, and system passwords are encrypted and strictly prohibited from
                      LLM extraction or retrieval.
                    </p>
                  </div>
                </div>
              )}

              {/* Escalation Status Callout Box */}
              <div
                className={`escalation-banner ${getEscalationStyle(
                  activeAnalysis.escalationTone
                )}`}
              >
                <div className="escalation-header">
                  <AlertTriangle size={18} />
                  <span className="escalation-label">ESCALATION PROTOCOL STATUS</span>
                </div>
                <div className="escalation-value">{activeAnalysis.escalationStatus}</div>
              </div>

              {/* Reasoning Section */}
              <div className="section-block">
                <h4 className="section-heading">Operational Reasoning & Impact Analysis</h4>
                <div className="reasoning-text-box">
                  <p>{activeAnalysis.reasoning}</p>
                </div>
              </div>

              {/* Recommended Next Actions Checklist */}
              <div className="section-block">
                <div className="actions-header-row">
                  <h4 className="section-heading">Recommended Next Actions</h4>
                  <span className="action-hint">Check off as steps are completed</span>
                </div>
                <div className="actions-checklist">
                  {activeAnalysis.recommendedActions.map((action, idx) => (
                    <div
                      key={idx}
                      className={`action-check-item ${actionChecked[idx] ? 'checked' : ''}`}
                      onClick={() => handleToggleCheck(idx)}
                    >
                      <div className="action-checkbox">
                        {actionChecked[idx] ? (
                          <Check size={14} className="check-icon" />
                        ) : (
                          <span className="action-num">{idx + 1}</span>
                        )}
                      </div>
                      <div className="action-text">{action}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Policy Evidence Placeholder */}
              <div className="section-block policy-section">
                <div className="policy-box">
                  <div className="policy-icon-col">
                    <FileCheck2 size={20} className="text-blue" />
                  </div>
                  <div className="policy-content">
                    <div className="policy-tag-row">
                      <span className="policy-label">POLICY EVIDENCE</span>
                      <span className="placeholder-tag">Placeholder SOP Citation</span>
                    </div>
                    <p className="policy-citation">{activeAnalysis.policyEvidence}</p>
                    <p className="policy-disclaimer">
                      * In a production deployment, this links directly to Punjab Sports Mart&apos;s
                      internal Confluence Knowledge Base and ERP rule repositories. Currently
                      operating as a simulated demonstration placeholder.
                    </p>
                  </div>
                </div>
              </div>

              {/* Action Buttons Toolbar */}
              <div className="response-actions-toolbar">
                <button
                  className={`btn-action-primary ${ticketCreated ? 'btn-ticket-created' : ''}`}
                  onClick={handleCreateTicket}
                  disabled={ticketCreated}
                >
                  {ticketCreated ? (
                    <>
                      <CheckCircle size={16} />
                      <span>Ticket Logged into Support Queue</span>
                    </>
                  ) : (
                    <>
                      <PlusCircle size={16} />
                      <span>Create Support Case from Analysis</span>
                    </>
                  )}
                </button>

                <button className="btn-action-secondary" onClick={handleCopyPlan}>
                  {copied ? (
                    <>
                      <Check size={16} className="text-success" />
                      <span>Action Plan Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy size={16} />
                      <span>Copy Action Plan</span>
                    </>
                  )}
                </button>
              </div>

              {/* Responsible AI Disclaimer Footer */}
              <div className="copilot-footer-note">
                <span className="footer-note-text">
                  <strong>Responsible AI Safeguard:</strong> This prototype runs on a local
                  deterministic rule model. It never queries live customer databases or exposes
                  sensitive banking credentials.
                </span>
              </div>
            </div>
          ) : (
            <div className="empty-response-card">
              <Bot size={48} className="empty-icon" />
              <h4 className="empty-title">Ready for Floor Incident Triage</h4>
              <p className="empty-desc">
                Select an example scenario from the left or enter any store issue to generate
                instant operational categorization, priority ratings, and SOP-backed next steps.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
