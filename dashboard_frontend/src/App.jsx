import { useState } from "react";
import IncidentOverview from "./components/IncidentOverview";
import IncidentDetail from "./components/IncidentDetail";
import DecisionTrail from "./components/DecisionTrail";
import Insights from "./components/Insights";

import {
  fetchPendingApprovals,
  approveIncident,
  rejectIncident,
} from "./api";

import "./App.css";

const TABS = [
  { id: "overview", label: "Incident Overview" },
  { id: "approvals", label: "Pending Approvals" },
  { id: "decisions", label: "Decision Trail" },
  { id: "insights", label: "Organizational Insights" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedIncidentId, setSelectedIncidentId] = useState(null);

  const [approvals, setApprovals] = useState([]);
  const [approvalsLoading, setApprovalsLoading] = useState(false);
  const [approvalError, setApprovalError] = useState("");
  const [processingApproval, setProcessingApproval] = useState(null);

  function handleSelectIncident(incidentId) {
    setSelectedIncidentId(incidentId);
  }

  function handleBackToOverview() {
    setSelectedIncidentId(null);
  }

  async function loadApprovals() {
    setApprovalsLoading(true);
    setApprovalError("");

    try {
      const data = await fetchPendingApprovals();

      if (Array.isArray(data)) {
        setApprovals(data);
      } else if (Array.isArray(data?.approvals)) {
        setApprovals(data.approvals);
      } else {
        setApprovals([]);
      }
    } catch (error) {
      console.error("Failed to load approvals:", error);
      setApprovalError(error.message);
    } finally {
      setApprovalsLoading(false);
    }
  }

  function handleTabClick(tabId) {
    setActiveTab(tabId);
    setSelectedIncidentId(null);

    if (tabId === "approvals") {
      loadApprovals();
    }
  }

  async function handleApprove(incidentId) {
    const confirmed = window.confirm(
      `Approve incident ${incidentId} and allow Jira execution?`
    );

    if (!confirmed) return;

    setProcessingApproval(incidentId);
    setApprovalError("");

    try {
      await approveIncident(incidentId);
      await loadApprovals();
    } catch (error) {
      console.error("Approval failed:", error);
      setApprovalError(error.message);
    } finally {
      setProcessingApproval(null);
    }
  }

  async function handleReject(incidentId) {
    const confirmed = window.confirm(
      `Reject incident ${incidentId}? No Jira ticket will be created.`
    );

    if (!confirmed) return;

    setProcessingApproval(incidentId);
    setApprovalError("");

    try {
      await rejectIncident(incidentId);
      await loadApprovals();
    } catch (error) {
      console.error("Rejection failed:", error);
      setApprovalError(error.message);
    } finally {
      setProcessingApproval(null);
    }
  }

  function renderApprovalQueue() {
    if (approvalsLoading) {
      return (
        <section className="approval-page">
          <div className="approval-page-header">
            <div>
              <h2>Pending Approvals</h2>
              <p>
                Human review is required before these operational decisions
                can be executed.
              </p>
            </div>
          </div>

          <div className="approval-loading">
            Loading pending approvals...
          </div>
        </section>
      );
    }

    return (
      <section className="approval-page">
        <div className="approval-page-header">
          <div>
            <h2>Pending Approvals</h2>
            <p>
              Human review is required before these operational decisions
              can be executed.
            </p>
          </div>

          <button
            className="refresh-button"
            onClick={loadApprovals}
          >
            ↻ Refresh
          </button>
        </div>

        {approvalError && (
          <div className="approval-error">
            {approvalError}
          </div>
        )}

        {approvals.length === 0 ? (
          <div className="approval-empty">
            <div className="approval-empty-icon">✓</div>

            <h3>No Pending Approvals</h3>

            <p>
              There are currently no incidents waiting for human approval.
            </p>
          </div>
        ) : (
          <div className="approval-list">
            {approvals.map((approval) => {
              const incidentId =
                approval.incident_id ||
                approval.incidentId;

              const payload =
                approval.decision_payload ||
                approval.decisionPayload ||
                {};

              const isProcessing =
                processingApproval === incidentId;

              return (
                <article
                  key={
                    approval.approval_id ||
                    incidentId
                  }
                  className="approval-card"
                >
                  <div className="approval-card-top">
                    <div>
                      <h3 className="approval-incident-id">
                        {incidentId}
                      </h3>

                      <div className="approval-status-row">
                        <span>Status:</span>

                        <span className="approval-status-badge">
                          {approval.status || "PENDING"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="approval-divider" />

                  <div className="decision-heading">
                    <div className="decision-heading-icon">
                      ▣
                    </div>

                    <h4>Operational Decision</h4>
                  </div>

                  <div className="decision-grid">
                    <div className="decision-row">
                      <div className="decision-label">
                        <span className="decision-icon blue">
                          ▧
                        </span>

                        <strong>Create Jira:</strong>
                      </div>

                      <span
                        className={
                          payload.create_jira
                            ? "value-success"
                            : "value-muted"
                        }
                      >
                        {String(
                          payload.create_jira ??
                            "Unknown"
                        )}
                      </span>
                    </div>

                    <div className="decision-row">
                      <div className="decision-label">
                        <span className="decision-icon purple">
                          !
                        </span>

                        <strong>Jira Priority:</strong>
                      </div>

                      <span
                        className={
                          payload.jira_priority ===
                          "Critical"
                            ? "value-critical"
                            : "value-normal"
                        }
                      >
                        {payload.jira_priority ||
                          "Unknown"}
                      </span>
                    </div>

                    <div className="decision-row">
                      <div className="decision-label">
                        <span className="decision-icon orange">
                          ↗
                        </span>

                        <strong>
                          Escalation Required:
                        </strong>
                      </div>

                      <span
                        className={
                          payload.escalation_required
                            ? "value-success"
                            : "value-muted"
                        }
                      >
                        {String(
                          payload.escalation_required ??
                            "Unknown"
                        )}
                      </span>
                    </div>

                    <div className="decision-row">
                      <div className="decision-label">
                        <span className="decision-icon blue">
                          ♢
                        </span>

                        <strong>Notify:</strong>
                      </div>

                      <span className="value-link">
                        {payload.notify ||
                          "Unknown"}
                      </span>
                    </div>

                    <div className="decision-row decision-row-large">
                      <div className="decision-label">
                        <span className="decision-icon green">
                          ▢
                        </span>

                        <strong>
                          Recommended Response:
                        </strong>
                      </div>

                      <div className="decision-text">
                        {payload.recommended_response ||
                          "No recommendation provided."}
                      </div>
                    </div>

                    <div className="decision-row decision-row-large">
                      <div className="decision-label">
                        <span className="decision-icon blue">
                          i
                        </span>

                        <strong>Reason:</strong>
                      </div>

                      <div className="decision-text">
                        {payload.reason ||
                          "No reason provided."}
                      </div>
                    </div>
                  </div>

                  <div className="approval-actions">
                    <button
                      className="approve-button"
                      onClick={() =>
                        handleApprove(incidentId)
                      }
                      disabled={isProcessing}
                    >
                      {isProcessing
                        ? "Processing..."
                        : "✓ Approve & Execute"}
                    </button>

                    <button
                      className="reject-button"
                      onClick={() =>
                        handleReject(incidentId)
                      }
                      disabled={isProcessing}
                    >
                      ✕ Reject
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-area">
          <h1>EnterpriseMind Lite</h1>
        </div>

        <nav className="tab-nav">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={
                activeTab === tab.id
                  ? "tab active"
                  : "tab"
              }
              onClick={() =>
                handleTabClick(tab.id)
              }
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="app-main">
        {activeTab === "overview" &&
          !selectedIncidentId && (
            <IncidentOverview
              onSelectIncident={
                handleSelectIncident
              }
            />
          )}

        {activeTab === "overview" &&
          selectedIncidentId && (
            <IncidentDetail
              incidentId={
                selectedIncidentId
              }
              onBack={
                handleBackToOverview
              }
            />
          )}

        {activeTab === "approvals" &&
          renderApprovalQueue()}

        {activeTab === "decisions" && (
          <DecisionTrail />
        )}

        {activeTab === "insights" && (
          <Insights />
        )}
      </main>
    </div>
  );
}