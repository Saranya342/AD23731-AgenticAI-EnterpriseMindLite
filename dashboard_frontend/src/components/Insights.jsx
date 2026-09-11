import { useEffect, useState } from "react";
import { fetchInsights } from "../api";

export default function Insights() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchInsights()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="status-text">Loading insights...</p>;
  }

  if (error) {
    return (
      <p className="status-text error">
        Error: {error}
      </p>
    );
  }

  if (!data) {
    return <p className="status-text">No insights available.</p>;
  }

  const metrics = data.evaluation_metrics || {};

  return (
    <div>
      <h2>Organizational Insights</h2>

      <div className="insights-grid">
        <div className="insight-card">
          <h3>Total Incidents</h3>
          <p className="big-stat">{data.total_incidents ?? 0}</p>
        </div>

        <div className="insight-card">
          <h3>Executed Incidents</h3>
          <p className="big-stat">{data.executed_incidents ?? 0}</p>
        </div>

        <div className="insight-card">
          <h3>Pending Approvals</h3>
          <p className="big-stat">{data.pending_approvals ?? 0}</p>
        </div>

        <div className="insight-card">
          <h3>Rejected Incidents</h3>
          <p className="big-stat">{data.rejected_incidents ?? 0}</p>
        </div>

        <div className="insight-card">
          <h3>Failed Incidents</h3>
          <p className="big-stat">{data.failed_incidents ?? 0}</p>
        </div>
      </div>

      <h2 style={{ marginTop: "36px" }}>Evaluation Metrics</h2>

      <div className="insights-grid">
        <div className="insight-card">
          <h3>Execution Success Rate</h3>
          <p className="big-stat">
            {metrics.execution_success_rate ?? 0}%
          </p>
          <p className="status-text">
            Executed incidents out of all incidents
          </p>
        </div>

        <div className="insight-card">
          <h3>Approval Acceptance Rate</h3>
          <p className="big-stat">
            {metrics.approval_acceptance_rate ?? 0}%
          </p>
          <p className="status-text">
            Approved requests out of resolved approvals
          </p>
        </div>

        <div className="insight-card">
          <h3>Average Agent Confidence</h3>
          <p className="big-stat">
            {metrics.average_agent_confidence ?? 0}%
          </p>
          <p className="status-text">
            Based on {metrics.confidence_samples ?? 0} recorded confidence values
          </p>
        </div>

        <div className="insight-card">
          <h3>Rejection Rate</h3>
          <p className="big-stat">
            {metrics.rejection_rate ?? 0}%
          </p>
          <p className="status-text">
            Rejected incidents out of all incidents
          </p>
        </div>

        <div className="insight-card">
          <h3>Failure Rate</h3>
          <p className="big-stat">
            {metrics.failure_rate ?? 0}%
          </p>
          <p className="status-text">
            Failed incidents out of all incidents
          </p>
        </div>
      </div>
    </div>
  );
}
