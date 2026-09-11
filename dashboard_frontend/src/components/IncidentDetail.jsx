import { useEffect, useState } from "react";
import { fetchIncidentDetail } from "../api";

function AgentDecisionCard({ decision }) {
  let parsedDecision = decision.decision;

  // Backend may return decision as a JSON string.
  if (typeof parsedDecision === "string") {
    try {
      parsedDecision = JSON.parse(parsedDecision);
    } catch {
      // Keep original string if it is not valid JSON.
    }
  }

  const isObject =
    typeof parsedDecision === "object" &&
    parsedDecision !== null;

  return (
    <div className="decision-card">
      <div className="decision-card-header">
        <strong>{decision.agent_name}</strong>

        {decision.timestamp && (
          <span className="timestamp">
            {new Date(decision.timestamp).toLocaleString()}
          </span>
        )}
      </div>

      {decision.reason && (
        <p className="decision-reason">
          {decision.reason}
        </p>
      )}

      {decision.confidence != null && (
        <p className="confidence-line">
          Confidence:{" "}
          <strong>{decision.confidence}</strong>
        </p>
      )}

      {isObject && (
        <details>
          <summary>View full AI output</summary>
          <pre>
            {JSON.stringify(parsedDecision, null, 2)}
          </pre>
        </details>
      )}

      {!isObject && parsedDecision && (
        <details>
          <summary>View full AI output</summary>
          <pre>{String(parsedDecision)}</pre>
        </details>
      )}
    </div>
  );
}

export default function IncidentDetail({
  incidentId,
  onBack,
}) {
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    fetchIncidentDetail(incidentId)
      .then((data) => {
        setIncident(data);
      })
      .catch((err) => {
        console.error(
          "Failed to load incident detail:",
          err
        );

        setError(
          err?.message ||
            "Failed to load incident details."
        );
      })
      .finally(() => {
        setLoading(false);
      });
  }, [incidentId]);

  if (loading) {
    return (
      <p className="status-text">
        Loading incident...
      </p>
    );
  }

  if (error) {
    return (
      <p className="status-text error">
        Error: {error}
      </p>
    );
  }

  if (!incident) {
    return (
      <p className="status-text">
        Incident not found.
      </p>
    );
  }

  const approval = incident.approval;

  return (
    <div>
      <button
        className="back-button"
        onClick={onBack}
      >
        &larr; Back to Overview
      </button>

      <h2>{incident.title}</h2>

      <p className="incident-meta">
        <strong>
          {incident.incident_id}
        </strong>{" "}
        &middot;{" "}
        {incident.customer_name ||
          "Unknown customer"}{" "}
        &middot;{" "}
        {incident.service_name ||
          "Unknown service"}
      </p>

      <p className="incident-meta">
        Priority:{" "}
        <strong>
          {incident.priority || "—"}
        </strong>{" "}
        &middot; Severity:{" "}
        <strong>
          {incident.severity || "—"}
        </strong>{" "}
        &middot; Status:{" "}
        <strong>
          {incident.status || "—"}
        </strong>
      </p>

      {incident.description && (
        <div
          style={{
            marginTop: "20px",
            marginBottom: "20px",
          }}
        >
          <h3>Description</h3>

          <p>
            {incident.description}
          </p>
        </div>
      )}

      {incident.jira_id && (
        <p className="jira-badge">
          Jira Ticket:{" "}
          <strong>
            {incident.jira_id}
          </strong>
        </p>
      )}

      {approval && (
        <div
          className="approval-card"
          style={{
            marginTop: "24px",
            marginBottom: "24px",
            padding: "20px",
            border: "1px solid #e5e7eb",
            borderRadius: "10px",
            background: "#ffffff",
          }}
        >
          <h3
            style={{
              marginTop: 0,
            }}
          >
            Human Approval
          </h3>

          <p>
            <strong>
              Approval Status:
            </strong>{" "}
            {approval.status || "Unknown"}
          </p>

          <p>
            <strong>
              Reviewer:
            </strong>{" "}
            {approval.reviewer || "—"}
          </p>

          {approval.created_at && (
            <p>
              <strong>
                Approval Requested:
              </strong>{" "}
              {new Date(
                approval.created_at
              ).toLocaleString()}
            </p>
          )}

          {approval.resolved_at && (
            <p>
              <strong>
                Approval Resolved:
              </strong>{" "}
              {new Date(
                approval.resolved_at
              ).toLocaleString()}
            </p>
          )}

          {approval.decision_payload && (
            <div
              style={{
                marginTop: "16px",
              }}
            >
              <h4>
                Approved Operational Decision
              </h4>

              <p>
                <strong>
                  Create Jira:
                </strong>{" "}
                {String(
                  approval.decision_payload
                    .create_jira ??
                    "Unknown"
                )}
              </p>

              <p>
                <strong>
                  Jira Priority:
                </strong>{" "}
                {approval.decision_payload
                  .jira_priority ||
                  "Unknown"}
              </p>

              <p>
                <strong>
                  Escalation Required:
                </strong>{" "}
                {String(
                  approval.decision_payload
                    .escalation_required ??
                    "Unknown"
                )}
              </p>

              <p>
                <strong>
                  Notify:
                </strong>{" "}
                {approval.decision_payload
                  .notify ||
                  "Unknown"}
              </p>

              {approval.decision_payload
                .recommended_response && (
                <p>
                  <strong>
                    Recommended Response:
                  </strong>
                  <br />
                  {
                    approval
                      .decision_payload
                      .recommended_response
                  }
                </p>
              )}

              {approval.decision_payload
                .reason && (
                <p>
                  <strong>
                    Approval Reason:
                  </strong>
                  <br />
                  {
                    approval
                      .decision_payload
                      .reason
                  }
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {!approval &&
        incident.status ===
          "pending_approval" && (
          <div
            style={{
              marginTop: "24px",
              marginBottom: "24px",
              padding: "20px",
              border:
                "1px solid #e5e7eb",
              borderRadius: "10px",
            }}
          >
            <h3>
              Human Approval
            </h3>

            <p>
              This incident is waiting
              for human approval.
            </p>
          </div>
        )}

      <h3>
        AI Reasoning Timeline
      </h3>

      <div className="decision-timeline">
        {(!incident.decisions ||
          incident.decisions.length ===
            0) && (
          <p className="status-text">
            No decisions logged yet for
            this incident.
          </p>
        )}

        {incident.decisions?.map(
          (decision, index) => (
            <AgentDecisionCard
              key={
                decision.decision_id ||
                `${decision.agent_name}-${index}`
              }
              decision={decision}
            />
          )
        )}
      </div>
    </div>
  );
}