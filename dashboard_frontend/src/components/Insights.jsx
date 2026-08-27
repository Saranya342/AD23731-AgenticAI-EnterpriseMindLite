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

  if (loading) return <p className="status-text">Loading insights...</p>;
  if (error) return <p className="status-text error">Error: {error}</p>;
  if (!data) return null;

  const total = data.recurring_issue_rate.total;
  const recurring = data.recurring_issue_rate.recurring;
  const recurringPct = total > 0 ? Math.round((recurring / total) * 100) : 0;

  return (
    <div>
      <h2>Organizational Insights</h2>

      <div className="insights-grid">
        <div className="insight-card">
          <h3>Agent Workload</h3>
          <ul className="insight-list">
            {data.decisions_per_agent.map((row) => (
              <li key={row.agent_name}>
                <span>{row.agent_name}</span>
                <strong>{row.decision_count}</strong>
              </li>
            ))}
          </ul>
        </div>

        <div className="insight-card">
          <h3>Incidents per Service</h3>
          <ul className="insight-list">
            {data.incidents_per_service.map((row) => (
              <li key={row.service_name}>
                <span>{row.service_name}</span>
                <strong>{row.incident_count}</strong>
              </li>
            ))}
          </ul>
        </div>

        <div className="insight-card">
          <h3>Employee Availability</h3>
          <ul className="insight-list">
            {data.employees.map((emp) => (
              <li key={emp.name}>
                <span>
                  {emp.name} ({emp.department_name})
                </span>
                <strong className={emp.availability ? "available" : "unavailable"}>
                  {emp.availability ? "Available" : "Unavailable"}
                </strong>
              </li>
            ))}
          </ul>
        </div>

        <div className="insight-card">
          <h3>Recurring Issue Rate</h3>
          <p className="big-stat">{recurringPct}%</p>
          <p className="status-text">
            {recurring} of {total} classified incidents are recurring
          </p>
        </div>
      </div>
    </div>
  );
}
