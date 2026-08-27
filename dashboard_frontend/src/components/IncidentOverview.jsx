import { useEffect, useState } from "react";
import { fetchIncidents } from "../api";

function priorityColor(priority) {
  switch (priority) {
    case "Critical": return "#dc2626";
    case "High": return "#ea580c";
    case "Medium": return "#ca8a04";
    case "Low": return "#16a34a";
    default: return "#64748b";
  }
}

export default function IncidentOverview({ onSelectIncident }) {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchIncidents()
      .then(setIncidents)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="status-text">Loading incidents...</p>;
  if (error) return <p className="status-text error">Error: {error}</p>;

  return (
    <div>
      <h2>Incident Overview</h2>
      <p className="status-text">{incidents.length} incidents. Click a row for full AI reasoning.</p>

      <table className="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Title</th>
            <th>Customer</th>
            <th>Service</th>
            <th>Priority</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((incident) => (
            <tr
              key={incident.incident_id}
              onClick={() => onSelectIncident(incident.incident_id)}
              className="clickable-row"
            >
              <td>{incident.incident_id}</td>
              <td>{incident.title}</td>
              <td>{incident.customer_name || "—"}</td>
              <td>{incident.service_name || "—"}</td>
              <td>
                {incident.priority ? (
                  <span
                    className="badge"
                    style={{ backgroundColor: priorityColor(incident.priority) }}
                  >
                    {incident.priority}
                  </span>
                ) : (
                  "—"
                )}
              </td>
              <td>{incident.status}</td>
              <td>{new Date(incident.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
