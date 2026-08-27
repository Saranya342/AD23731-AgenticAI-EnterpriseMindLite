import { useEffect, useState } from "react";
import { fetchIncidentDetail } from "../api";

function AgentDecisionCard({ decision }) {
  const d = decision.decision;
  const isObject = typeof d === "object" && d !== null;

  return (
    <div className="decision-card">
      <div className="decision-card-header">
        <strong>{decision.agent_name}</strong>
        <span className="timestamp">
          {new Date(decision.timestamp).toLocaleString()}
        </span>
      </div>

      <p className="decision-reason">{decision.reason}</p>

      {decision.confidence != null && (
        <p className="confidence-line">
          Confidence: <strong>{decision.confidence}</strong>
        </p>
      )}

      {isObject && (
        <details>
          <summary>View full AI output</summary>
          <pre>{JSON.stringify(d, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}

export default function IncidentDetail({ incidentId, onBack }) {
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchIncidentDetail(incidentId)
      .then(setIncident)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [incidentId]);

  if (loading) return <p className="status-text">Loading incident...</p>;
  if (error) return <p className="status-text error">Error: {error}</p>;
  if (!incident) return null;

  return (
    <div>
      <button className="back-button" onClick={onBack}>
        &larr; Back to Overview
      </button>

      <h2>{incident.title}</h2>

      <p className="incident-meta">
        <strong>{incident.incident_id}</strong> &middot;{" "}
        {incident.customer_name || "Unknown customer"} &middot;{" "}
        {incident.service_name || "Unknown service"}
      </p>

      <p className="incident-meta">
        Priority: <strong>{incident.priority || "—"}</strong> &middot; Severity:{" "}
        <strong>{incident.severity || "—"}</strong> &middot; Status:{" "}
        <strong>{incident.status}</strong>
      </p>

      {incident.jira_key && (
        <p className="jira-badge">
          Jira Ticket: <strong>{incident.jira_key}</strong>
        </p>
      )}

      <h3>AI Reasoning Timeline</h3>

      <div className="decision-timeline">
        {incident.decisions.length === 0 && (
          <p className="status-text">No decisions logged yet for this incident.</p>
        )}
        {incident.decisions.map((decision) => (
          <AgentDecisionCard key={decision.decision_id} decision={decision} />
        ))}
      </div>
    </div>
  );
}
