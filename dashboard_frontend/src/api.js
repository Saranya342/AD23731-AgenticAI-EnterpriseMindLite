// // All calls to the FastAPI dashboard backend go through here.
// // Backend must be running (uvicorn main:app --port 8000) for any of this to work.

// const API_BASE = "http://127.0.0.1:8000";

// export async function fetchIncidents() {
//   const res = await fetch(`${API_BASE}/api/incidents`);
//   if (!res.ok) throw new Error(`Failed to fetch incidents (${res.status})`);
//   return res.json();
// }

// export async function fetchIncidentDetail(incidentId) {
//   const res = await fetch(`${API_BASE}/api/incidents/${incidentId}`);
//   if (!res.ok) throw new Error(`Failed to fetch incident ${incidentId} (${res.status})`);
//   return res.json();
// }

// export async function fetchDecisions(limit = 100) {
//   const res = await fetch(`${API_BASE}/api/decisions?limit=${limit}`);
//   if (!res.ok) throw new Error(`Failed to fetch decisions (${res.status})`);
//   return res.json();
// }

// export async function fetchInsights() {
//   const res = await fetch(`${API_BASE}/api/insights`);
//   if (!res.ok) throw new Error(`Failed to fetch insights (${res.status})`);
//   return res.json();
// }
// All calls to the FastAPI dashboard backend go through here.
// Backend must be running:
// uvicorn main:app --port 8000

// const API_BASE = "http://127.0.0.1:8000";
const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export async function fetchIncidents() {
  const res = await fetch(`${API_BASE}/api/incidents`);

  if (!res.ok) {
    throw new Error(`Failed to fetch incidents (${res.status})`);
  }

  return res.json();
}

export async function fetchIncidentDetail(incidentId) {
  const res = await fetch(
    `${API_BASE}/api/incidents/${incidentId}`
  );

  if (!res.ok) {
    throw new Error(
      `Failed to fetch incident ${incidentId} (${res.status})`
    );
  }

  return res.json();
}

export async function fetchDecisions(limit = 100) {
  const res = await fetch(
    `${API_BASE}/api/decisions?limit=${limit}`
  );

  if (!res.ok) {
    throw new Error(
      `Failed to fetch decisions (${res.status})`
    );
  }

  return res.json();
}

export async function fetchInsights() {
  const res = await fetch(
    `${API_BASE}/api/insights`
  );

  if (!res.ok) {
    throw new Error(
      `Failed to fetch insights (${res.status})`
    );
  }

  return res.json();
}


// ============================================================
// APPROVAL WORKFLOW
// ============================================================

export async function fetchPendingApprovals() {
  const res = await fetch(
    `${API_BASE}/api/approvals?status=PENDING`
  );

  if (!res.ok) {
    throw new Error(
      `Failed to fetch pending approvals (${res.status})`
    );
  }

  return res.json();
}


export async function approveIncident(incidentId) {
  const res = await fetch(
    `${API_BASE}/api/approvals/${incidentId}/approve`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!res.ok) {
    const errorText = await res.text();

    throw new Error(
      `Failed to approve incident ${incidentId}: ${errorText}`
    );
  }

  return res.json();
}


export async function rejectIncident(incidentId) {
  const res = await fetch(
    `${API_BASE}/api/approvals/${incidentId}/reject`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!res.ok) {
    const errorText = await res.text();

    throw new Error(
      `Failed to reject incident ${incidentId}: ${errorText}`
    );
  }

  return res.json();
}
// ============================================================
// CUSTOMER SERVICE
// ============================================================

export async function fetchCustomerServiceQueries() {
  const res = await fetch(
    `${API_BASE}/api/customer-service`
  );

  if (!res.ok) {
    throw new Error(
      `Failed to fetch customer service queries (${res.status})`
    );
  }

  return res.json();
}
export async function resolveCustomerServiceQuery(queryId) {
  const res = await fetch(
    `${API_BASE}/api/customer-service/${queryId}/resolve`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!res.ok) {
    const errorText = await res.text();

    throw new Error(
      `Failed to resolve customer query ${queryId}: ${errorText}`
    );
  }

  return res.json();
}
