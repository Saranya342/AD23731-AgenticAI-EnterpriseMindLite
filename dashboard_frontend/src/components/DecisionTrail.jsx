import { useEffect, useState } from "react";
import { fetchDecisions } from "../api";

export default function DecisionTrail() {
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDecisions(100)
      .then(setDecisions)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="status-text">Loading decision trail...</p>;
  if (error) return <p className="status-text error">Error: {error}</p>;

  return (
    <div>
      <h2>Decision Trail</h2>
      <p className="status-text">
        Full audit log across every incident, most recent first ({decisions.length} entries).
      </p>

      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Incident</th>
            <th>Agent</th>
            <th>Reason</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {decisions.map((d) => (
            <tr key={d.decision_id}>
              <td className="nowrap">{new Date(d.timestamp).toLocaleString()}</td>
              <td>{d.incident_title || d.incident_id}</td>
              <td>{d.agent_name}</td>
              <td className="reason-cell">{d.reason}</td>
              <td>{d.confidence != null ? d.confidence : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
