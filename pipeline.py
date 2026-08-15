"""
END-TO-END PIPELINE — chains Agent 1 -> Agent 2 -> Agent 3

Also writes each agent's decision into the Postgres `decisions` table,
which is the audit trail used later by the dashboard.

Run:
    python pipeline.py
"""

import os
import json
import psycopg2
from dotenv import load_dotenv

from agent1_incident_intelligence import classify_incident
from agent2_organizational_reasoning import reason_about_incident
from agent3_operational_decision import decide_operational_path


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("Missing environment variable: DATABASE_URL")


# ============================================================
# AUDIT LOGGING
# ============================================================

def log_decision(conn, incident_id, agent_name, decision_dict):

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO decisions
        (
            incident_id,
            agent_name,
            decision,
            reason,
            confidence
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            incident_id,
            agent_name,
            json.dumps(decision_dict),
            decision_dict.get("reason", ""),
            decision_dict.get("confidence", None)
        )
    )

    conn.commit()
    cur.close()


# ============================================================
# END-TO-END PIPELINE
# ============================================================

def run_pipeline(
    incident_id,
    subject,
    body,
    customer_name
):

    conn = psycopg2.connect(DATABASE_URL)

    print(f"\n{'=' * 60}")
    print(f"PROCESSING INCIDENT: {incident_id}")
    print(f"{'=' * 60}")


    # --------------------------------------------------------
    # AGENT 1 — INCIDENT INTELLIGENCE
    # --------------------------------------------------------

    print("\n[AGENT 1] Incident Intelligence")

    a1 = classify_incident(
        subject,
        body,
        customer_name
    )

    print(json.dumps(a1, indent=2))

    log_decision(
        conn,
        incident_id,
        "IncidentIntelligenceAgent",
        a1
    )


    # --------------------------------------------------------
    # AGENT 2 — ORGANIZATIONAL REASONING
    # --------------------------------------------------------

    print("\n[AGENT 2] Organizational Reasoning")

    a2 = reason_about_incident(
        a1,
        customer_name
    )

    print(json.dumps(a2, indent=2))

    log_decision(
        conn,
        incident_id,
        "OrganizationalReasoningAgent",
        a2
    )


    # --------------------------------------------------------
    # AGENT 3 — OPERATIONAL DECISION
    # --------------------------------------------------------

    print("\n[AGENT 3] Operational Decision")

    a3 = decide_operational_path(
        a1,
        a2
    )

    print(json.dumps(a3, indent=2))

    log_decision(
        conn,
        incident_id,
        "OperationalDecisionAgent",
        a3
    )


    # --------------------------------------------------------
    # CLOSE DATABASE CONNECTION
    # --------------------------------------------------------

    conn.close()

    print(f"\n{'=' * 60}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 60}")

    return a1, a2, a3


# ============================================================
# TEST RUN
# ============================================================

if __name__ == "__main__":

    run_pipeline(
        incident_id="INC-TEST-01",
        subject="Cannot process payments",
        body="ABC Retail has been unable to process payments for the last 30 minutes.",
        customer_name="ABC Retail"
    )