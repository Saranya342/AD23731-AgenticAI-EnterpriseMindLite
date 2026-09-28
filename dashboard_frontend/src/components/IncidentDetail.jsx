import { useEffect, useState } from "react";
import { fetchIncidentDetail } from "../api";

function parseDecision(value) {
  if (typeof value !== "string") return value;
  try { return JSON.parse(value); } catch { return value; }
}

function BoolBadge({ value }) {
  const yes = value === true;
  return <span className={`evidence-pill ${yes ? "positive" : "neutral"}`}>{value == null ? "Unknown" : yes ? "Yes" : "No"}</span>;
}

function ToolEvidence({ evaluation }) {
  if (!evaluation || typeof evaluation !== "object") return null;
  const tools = Array.isArray(evaluation.tool_results) ? evaluation.tool_results : [];
  return (
    <section className="evidence-panel">
      <div className="section-heading-row">
        <div><span className="eyebrow">Tool-augmented validation</span><h3>Diagnostic Evidence</h3></div>
        <span className={`risk-badge risk-${String(evaluation.technical_risk || "unknown").toLowerCase()}`}>{evaluation.technical_risk || "Unknown"} risk</span>
      </div>
      <div className="evidence-summary-grid">
        <div><span>Incident confirmed</span><BoolBadge value={evaluation.incident_confirmed} /></div>
        <div><span>Evidence supports Jira</span><BoolBadge value={evaluation.tool_evidence_supports_jira} /></div>
      </div>
      {evaluation.summary && <p className="evidence-summary">{evaluation.summary}</p>}
      {tools.length > 0 && <div className="tool-grid">{tools.map((tool, index) => (
        <article className="tool-card" key={`${tool.tool}-${index}`}>
          <div className="tool-card-head"><strong>{String(tool.tool || "Diagnostic").replaceAll("_", " ")}</strong><span className="source-badge">{tool.source || "source"}</span></div>
          <p>{tool.message || (tool.logs?.length ? `${tool.logs.length} recent log entries` : "Diagnostic completed.")}</p>
          {tool.status && <div className="tool-meta">Status <strong>{tool.status}</strong></div>}
          {tool.connected != null && <div className="tool-meta">Connected <strong>{String(tool.connected)}</strong></div>}
          {tool.response_time_ms != null && <div className="tool-meta">Response <strong>{tool.response_time_ms} ms</strong></div>}
          {tool.latency_ms != null && <div className="tool-meta">Latency <strong>{tool.latency_ms} ms</strong></div>}
          {tool.logs?.length > 0 && <ul className="log-list">{tool.logs.map((log, i) => <li key={i}><b>{log.level || "LOG"}</b> {log.message}</li>)}</ul>}
        </article>
      ))}</div>}
      {tools.some((tool) => tool.source === "demo") && <p className="demo-note">Diagnostic source: demo/simulated checks for project demonstration.</p>}
    </section>
  );
}

function RagEvidence({ documents }) {
  if (!Array.isArray(documents) || documents.length === 0) return null;
  return (
    <section className="evidence-panel">
      <div className="section-heading-row"><div><span className="eyebrow">Retrieval-augmented reasoning</span><h3>Retrieved Knowledge</h3></div><span className="count-badge">{documents.length} document{documents.length === 1 ? "" : "s"}</span></div>
      <div className="rag-list">{documents.map((doc, index) => (
        <article className="rag-card" key={doc.id || index}>
          <div><strong>{doc.title || "Knowledge document"}</strong><p>{doc.document_type || "Document"} · {doc.service || "General"}</p></div>
          {doc.similarity != null && <span className="similarity">{Math.round(Number(doc.similarity) * 100)}% match</span>}
        </article>
      ))}</div>
    </section>
  );
}

function AgentDecisionCard({ decision }) {
  const parsedDecision = parseDecision(decision.decision);
  const isObject = typeof parsedDecision === "object" && parsedDecision !== null;
  return (
    <div className="decision-card">
      <div className="decision-card-header"><strong>{decision.agent_name}</strong>{decision.timestamp && <span className="timestamp">{new Date(decision.timestamp).toLocaleString()}</span>}</div>
      {decision.reason && <p className="decision-reason">{decision.reason}</p>}
      {decision.confidence != null && <p className="confidence-line">Confidence <strong>{decision.confidence}</strong></p>}
      {isObject && <><RagEvidence documents={parsedDecision.rag_documents} /><ToolEvidence evaluation={parsedDecision.tool_evaluation} /></>}
      {parsedDecision && <details><summary>View full decision output</summary><pre>{isObject ? JSON.stringify(parsedDecision, null, 2) : String(parsedDecision)}</pre></details>}
    </div>
  );
}

export default function IncidentDetail({ incidentId, onBack }) {
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchIncidentDetail(incidentId).then(setIncident).catch((err) => setError(err?.message || "Failed to load incident details.")).finally(() => setLoading(false));
  }, [incidentId]);

  if (loading) return <p className="status-text">Loading incident...</p>;
  if (error) return <p className="status-text error">Error: {error}</p>;
  if (!incident) return <p className="status-text">Incident not found.</p>;

  const approval = incident.approval;
  const operational = incident.decisions?.map((d) => ({...d, parsed: parseDecision(d.decision)})).find((d) => d.agent_name === "OperationalDecisionAgent");
  const op = operational?.parsed && typeof operational.parsed === "object" ? operational.parsed : null;

  return <div className="page-stack">
    <button className="back-button" onClick={onBack}>← Back to overview</button>
    <section className="incident-hero">
      <div><span className="eyebrow">Incident detail</span><h2>{incident.title}</h2><p className="incident-meta"><strong>{incident.incident_id}</strong> · {incident.customer_name || "Unknown customer"} · {incident.service_name || "Unknown service"}</p></div>
      <div className="hero-badges"><span className="badge badge-outline">{incident.priority || "No priority"}</span><span className="badge badge-outline">{incident.status || "Unknown"}</span></div>
    </section>
    <div className="summary-grid">
      <div className="summary-card"><span>Priority</span><strong>{incident.priority || "—"}</strong></div>
      <div className="summary-card"><span>Severity</span><strong>{incident.severity || "—"}</strong></div>
      <div className="summary-card"><span>Jira</span><strong>{incident.jira_id || "Not created"}</strong></div>
      <div className="summary-card"><span>Approval</span><strong>{approval?.status || (incident.status === "pending_approval" ? "PENDING" : "Not required")}</strong></div>
    </div>
    {incident.description && <section className="content-panel"><h3>Description</h3><p>{incident.description}</p></section>}
    {op && <><RagEvidence documents={op.rag_documents} /><ToolEvidence evaluation={op.tool_evaluation} /></>}
    {approval && <section className="content-panel"><div className="section-heading-row"><div><span className="eyebrow">Human-in-the-loop</span><h3>Approval Record</h3></div><span className="approval-status-badge">{approval.status || "Unknown"}</span></div><div className="approval-meta-grid"><p><span>Reviewer</span><strong>{approval.reviewer || "—"}</strong></p><p><span>Requested</span><strong>{approval.created_at ? new Date(approval.created_at).toLocaleString() : "—"}</strong></p><p><span>Resolved</span><strong>{approval.resolved_at ? new Date(approval.resolved_at).toLocaleString() : "—"}</strong></p></div></section>}
    <section><div className="section-heading-row"><div><span className="eyebrow">Audit trail</span><h3>AI Reasoning Timeline</h3></div><span className="count-badge">{incident.decisions?.length || 0} entries</span></div><div className="decision-timeline">{(!incident.decisions || incident.decisions.length === 0) ? <p className="status-text">No decisions logged yet.</p> : incident.decisions.map((decision, index) => <AgentDecisionCard key={decision.decision_id || `${decision.agent_name}-${index}`} decision={decision} />)}</div></section>
  </div>;
}
