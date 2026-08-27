"""
PHASE 14 — Dashboard Backend (FastAPI)

Read-only API on top of the existing Postgres (Supabase) database.
Does NOT modify any existing agent/pipeline/jira_integration code —
this only reads data that's already being written by phases 1-13.

Endpoints:
    GET /api/incidents               -> Incident Overview (list)
    GET /api/incidents/{incident_id} -> Incident Details + AI reasoning
    GET /api/decisions               -> Decision Trail (full audit log)
    GET /api/insights                -> Organizational Insights

Note on Jira ticket info: the `jira_tickets` table exists but is never
written to by any current script — the real ticket key only exists inside
the JiraExecutionAgent row in `decisions.decision` (stored as a JSON
string). So incident details pull the ticket key from there instead of
from `jira_tickets`.

Run:
    cd dashboard_backend
    uvicorn main:app --reload --port 8000
"""

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import fetch_all, fetch_one

app = FastAPI(title="EnterpriseMind Lite Dashboard API")

# Allows the React dev server (Vite default port 5173) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def parse_decision(row: dict) -> dict:
    """
    decisions.decision is stored as TEXT containing a JSON string
    (see pipeline.py's log_decision -> json.dumps(decision_dict)).
    This turns it back into a real dict for the API response.
    """
    parsed = dict(row)
    raw = parsed.get("decision")

    try:
        parsed["decision"] = json.loads(raw)
    except (TypeError, ValueError):
        # Leave as-is if it isn't valid JSON for some reason —
        # better to show the raw text than crash the endpoint.
        pass

    return parsed


# ============================================================
# INCIDENT OVERVIEW
# ============================================================

@app.get("/api/incidents")
def list_incidents():
    """
    List every incident with its customer and service names.

    Note: incidents.priority / incidents.severity are never populated by
    the seed script — the real classification only exists inside each
    incident's latest IncidentIntelligenceAgent decision. So we pull it
    from there instead, and fall back to the (usually empty) table
    columns only if no such decision exists yet.
    """

    rows = fetch_all(
        """
        SELECT
            i.incident_id,
            i.title,
            i.priority AS table_priority,
            i.severity AS table_severity,
            i.status,
            i.created_at,
            c.customer_name,
            s.service_name
        FROM incidents i
        LEFT JOIN customers c ON i.customer_id = c.customer_id
        LEFT JOIN services s ON i.service_id = s.service_id
        ORDER BY i.created_at DESC
        """
    )

    latest_classifications = fetch_all(
        """
        SELECT DISTINCT ON (incident_id) incident_id, decision
        FROM decisions
        WHERE agent_name = 'IncidentIntelligenceAgent'
        ORDER BY incident_id, timestamp DESC
        """
    )

    classification_by_incident = {}

    for row in latest_classifications:
        try:
            parsed = json.loads(row["decision"])
            classification_by_incident[row["incident_id"]] = {
                "priority": parsed.get("priority"),
                "severity": parsed.get("severity"),
            }
        except (TypeError, ValueError):
            continue

    for incident in rows:
        classification = classification_by_incident.get(incident["incident_id"], {})
        incident["priority"] = classification.get("priority") or incident.pop("table_priority", None)
        incident["severity"] = classification.get("severity") or incident.pop("table_severity", None)
        incident.pop("table_priority", None)
        incident.pop("table_severity", None)

    return rows


# ============================================================
# INCIDENT DETAILS + AI REASONING (EXPLAINABILITY)
# ============================================================

@app.get("/api/incidents/{incident_id}")
def get_incident_detail(incident_id: str):
    """
    Full detail for one incident, plus every agent decision made
    about it, in order — this is the "explainability" view where
    you can see exactly what Agent 1, 2, 3 (and approval/Jira/email)
    each decided and why.
    """

    incident = fetch_one(
        """
        SELECT
            i.incident_id,
            i.title,
            i.description,
            i.priority,
            i.severity,
            i.status,
            i.created_at,
            c.customer_name,
            s.service_name
        FROM incidents i
        LEFT JOIN customers c ON i.customer_id = c.customer_id
        LEFT JOIN services s ON i.service_id = s.service_id
        WHERE i.incident_id = %s
        """,
        (incident_id,)
    )

    if not incident:
        raise HTTPException(
            status_code=404,
            detail=f"Incident '{incident_id}' not found"
        )

    decision_rows = fetch_all(
        """
        SELECT decision_id, incident_id, agent_name, decision, reason, confidence, timestamp
        FROM decisions
        WHERE incident_id = %s
        ORDER BY timestamp ASC
        """,
        (incident_id,)
    )

    decisions = [parse_decision(r) for r in decision_rows]

    # Pull the real Jira ticket key out of the JiraExecutionAgent row,
    # since the jira_tickets table itself is never populated.
    jira_key = None
    for d in decisions:
        if d["agent_name"] == "JiraExecutionAgent" and isinstance(d["decision"], dict):
            jira_key = d["decision"].get("ticket_key")

    incident["jira_key"] = jira_key
    incident["decisions"] = decisions

    return incident


# ============================================================
# DECISION TRAIL (FULL AUDIT LOG ACROSS ALL INCIDENTS)
# ============================================================

@app.get("/api/decisions")
def list_decisions(limit: int = 100):
    """Every decision ever logged, newest first, with the incident title attached."""

    rows = fetch_all(
        """
        SELECT
            d.decision_id,
            d.incident_id,
            i.title AS incident_title,
            d.agent_name,
            d.decision,
            d.reason,
            d.confidence,
            d.timestamp
        FROM decisions d
        LEFT JOIN incidents i ON d.incident_id = i.incident_id
        ORDER BY d.timestamp DESC
        LIMIT %s
        """,
        (limit,)
    )
    return [parse_decision(r) for r in rows]


# ============================================================
# ORGANIZATIONAL INSIGHTS
# ============================================================

@app.get("/api/insights")
def get_insights():
    """Aggregate stats: agent workload, incidents per service, employee availability."""

    agent_counts = fetch_all(
        """
        SELECT agent_name, COUNT(*) AS decision_count
        FROM decisions
        GROUP BY agent_name
        ORDER BY decision_count DESC
        """
    )

    incidents_per_service = fetch_all(
        """
        SELECT s.service_name, COUNT(i.incident_id) AS incident_count
        FROM services s
        LEFT JOIN incidents i ON i.service_id = s.service_id
        GROUP BY s.service_name
        ORDER BY incident_count DESC
        """
    )

    employees = fetch_all(
        """
        SELECT e.name, e.availability, d.department_name
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.department_id
        ORDER BY d.department_name, e.name
        """
    )

    # Recurring-issue rate, parsed out of Agent 2's decisions
    org_decisions = fetch_all(
        """
        SELECT decision
        FROM decisions
        WHERE agent_name = 'OrganizationalReasoningAgent'
        """
    )

    recurring_count = 0

    for row in org_decisions:
        try:
            parsed = json.loads(row["decision"])
            if parsed.get("is_recurring_issue"):
                recurring_count += 1
        except (TypeError, ValueError):
            continue

    return {
        "decisions_per_agent": agent_counts,
        "incidents_per_service": incidents_per_service,
        "employees": employees,
        "recurring_issue_rate": {
            "recurring": recurring_count,
            "total": len(org_decisions)
        }
    }


@app.get("/")
def root():
    return {"status": "EnterpriseMind Lite Dashboard API is running"}
