// All calls to the FastAPI dashboard backend go through here.
// Backend must be running (uvicorn main:app --port 8000) for any of this to work.

const API_BASE = "http://127.0.0.1:8000";

export async function fetchIncidents() {
  const res = await fetch(`${API_BASE}/api/incidents`);
  if (!res.ok) throw new Error(`Failed to fetch incidents (${res.status})`);
  return res.json();
}

export async function fetchIncidentDetail(incidentId) {
  const res = await fetch(`${API_BASE}/api/incidents/${incidentId}`);
  if (!res.ok) throw new Error(`Failed to fetch incident ${incidentId} (${res.status})`);
  return res.json();
}

export async function fetchDecisions(limit = 100) {
  const res = await fetch(`${API_BASE}/api/decisions?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch decisions (${res.status})`);
  return res.json();
}

export async function fetchInsights() {
  const res = await fetch(`${API_BASE}/api/insights`);
  if (!res.ok) throw new Error(`Failed to fetch insights (${res.status})`);
  return res.json();
}
