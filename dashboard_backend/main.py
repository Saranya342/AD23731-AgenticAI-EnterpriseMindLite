# dashboard_backend/main.py

import os
import json
import traceback
import asyncio
from datetime import datetime
from typing import Optional
import json
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2

from .db import fetch_all, fetch_one, DATABASE_URL

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline import process_agents, execute_approved_incident


# ============================================================
# APP CONFIGURATION
# ============================================================

app = FastAPI(
    title="EnterpriseMind-Lite",
    description="AI-powered Enterprise Incident Intelligence and Automated Resolution System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class IncidentSubmission(BaseModel):
    subject: str
    body: str
    customer_name: Optional[str] = None
    customer_id: Optional[str] = None
    service_id: Optional[str] = None


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_db_connection():
    """
    Create a PostgreSQL connection.
    """

    import psycopg2

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    return psycopg2.connect(DATABASE_URL)


def safe_json(value):
    """
    Convert database / Python values into JSON-safe values.
    """

    if value is None:
        return None

    if isinstance(value, (dict, list, str, int, float, bool)):
        return value

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


def normalize_decision_payload(payload):
    """
    Ensure JSONB decision payload is returned as a dictionary.
    """

    if payload is None:
        return {}

    if isinstance(payload, dict):
        return payload

    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return {"raw": payload}

    return {"value": safe_json(payload)}


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "application": "EnterpriseMind-Lite",
        "status": "running",
        "message": "AI Incident Intelligence Platform",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "EnterpriseMind-Lite",
    }


# ============================================================
# INCIDENT LIST
# ============================================================

@app.get("/api/incidents")
def get_incidents():
    """
    Return all incidents for the dashboard.
    """

    query = """
        SELECT
            i.incident_id,
            i.title,
            i.description,
            i.priority,
            i.severity,
            i.status,
            i.created_at,
            c.customer_name AS customer_name,
            s.service_name AS service_name,

            (
                SELECT jt.jira_id
                FROM jira_tickets jt
                WHERE jt.incident_id = i.incident_id
                ORDER BY jt.created_at DESC
                LIMIT 1
            ) AS jira_id

        FROM incidents i

        LEFT JOIN customers c
            ON i.customer_id = c.customer_id

        LEFT JOIN services s
            ON i.service_id = s.service_id

        ORDER BY i.created_at DESC;
    """

    try:
        rows = fetch_all(query)

        return [
            {
                "incident_id": row.get("incident_id"),
                "title": row.get("title"),
                "description": row.get("description"),
                "priority": row.get("priority"),
                "severity": row.get("severity"),
                "status": row.get("status"),
                "created_at": safe_json(row.get("created_at")),
                "customer_name": row.get("customer_name"),
                "service_name": row.get("service_name"),
                "jira_id": row.get("jira_id"),
            }
            for row in rows
        ]

    except Exception as e:
        print("[GET INCIDENTS ERROR]", str(e))
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve incidents.",
        )


# ============================================================
# CREATE INCIDENT
# ============================================================

@app.post("/api/incidents")
def create_incident(
    incident: IncidentSubmission,
    background_tasks: BackgroundTasks,
):
    """
    Create a new incident and start the AI workflow.

    Workflow:

        Incident
            ↓
        Agent 1
            ↓
        Agent 2
            ↓
        Agent 3
            ↓
        Routing
    """

    incident_id = f"INC-{os.urandom(4).hex().upper()}"

    insert_query = """
        INSERT INTO incidents (
            incident_id,
            title,
            description,
            customer_id,
            service_id,
            status,
            created_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            NOW()
        )
        RETURNING incident_id;
    """

    try:
        connection = get_db_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    insert_query,
                    (
                        incident_id,
                        incident.subject,
                        incident.body,
                        incident.customer_id,
                        incident.service_id,
                        "processing",
                    ),
                )

                connection.commit()

        finally:
            connection.close()

        background_tasks.add_task(
            run_web_incident,
            incident_id,
            incident.subject,
            incident.body,
            incident.customer_name,
            incident.customer_id,
            incident.service_id,
        )

        return {
            "incident_id": incident_id,
            "status": "processing",
            "message": "Incident submitted successfully.",
        }

    except Exception as e:
        print("[CREATE INCIDENT ERROR]", str(e))
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# WEB INCIDENT WORKFLOW
# ============================================================

def run_web_incident(
    incident_id: str,
    subject: str,
    body: str,
    customer_name: Optional[str] = None,
    customer_id: Optional[str] = None,
    service_id: Optional[str] = None,
):
    """
    Main web workflow.

    Agent 1:
        Incident Intelligence

    Agent 2:
        Organizational Reasoning

    Agent 3:
        Operational Decision

    Routing:

        create_jira = False
                ↓
             REJECT
                ↓
              AUDIT

        create_jira = True
        approval_required = True
                ↓
         HUMAN APPROVAL
           ↙         ↘
       APPROVE      REJECT
          ↓            ↓
        JIRA         AUDIT
          ↓
        AUDIT

        create_jira = True
        approval_required = False
                ↓
          AUTO EXECUTE
                ↓
               JIRA
                ↓
              AUDIT
    """

    print("\n========================================")
    print("[WORKFLOW START]")
    print("Incident:", incident_id)
    print("========================================")

    try:

        # ----------------------------------------------------
        # PROCESSING STATUS
        # ----------------------------------------------------

        update_incident_status(
            incident_id,
            "processing",
        )

        # ----------------------------------------------------
        # AGENTS 1 → 2 → 3
        # ----------------------------------------------------

        print("[AGENT 1] Starting")
        print("[AGENT 2] Starting")
        print("[AGENT 3] Starting")

        # IMPORTANT:
        # process_agents() does NOT accept customer_id.
        a1, a2, a3 = process_agents(
            incident_id=incident_id,
            subject=subject,
            body=body,
            customer_name=customer_name,
        )
        # Save Agent 1 priority and severity into incidents table
        update_query = """
            UPDATE incidents
            SET
                priority = %s,
                severity = %s
            WHERE incident_id = %s;
        """

        connection = get_db_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    update_query,
                    (   
                        a1.get("priority"),
                        a1.get("severity"),
                        incident_id,
                    ),
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()
            print("[AGENTS COMPLETE]")

        # ----------------------------------------------------
        # NORMALIZE AGENT 3
        # ----------------------------------------------------

        agent3 = normalize_decision_payload(a3)

        create_jira = bool(
            agent3.get("create_jira", False)
        )

        approval_required = bool(
            agent3.get("approval_required", False)
        )

        escalation_required = bool(
            agent3.get("escalation_required", False)
        )

        print(
            f"[AGENT 3] create_jira={create_jira}, "
            f"approval_required={approval_required}, "
            f"escalation_required={escalation_required}"
        )

        # ----------------------------------------------------
        # PATH 1
        # create_jira = FALSE
        # ----------------------------------------------------

        if not create_jira:

            print("[ROUTE] REJECT → AUDIT")

            insert_human_audit(
                incident_id=incident_id,
                action="REJECTED",
                decision={
                    "reason": agent3.get(
                        "reason",
                        "Agent 3 decided that Jira creation is not required.",
                    ),
                    "create_jira": False,
                    "approval_required": approval_required,
                },
            )

            update_incident_status(
                incident_id,
                "rejected",
            )

            print("[WORKFLOW COMPLETE] Rejected")

            return

        # ----------------------------------------------------
        # PATH 2
        # create_jira = TRUE
        # approval_required = TRUE
        # ----------------------------------------------------

        if approval_required:

            print("[ROUTE] HUMAN APPROVAL REQUIRED")

            create_approval_record(
                incident_id=incident_id,
                decision_payload=agent3,
            )

            update_incident_status(
                incident_id,
                "pending_approval",
            )

            print(
                "[WORKFLOW PAUSED] Waiting for human approval"
            )

            return

        # ----------------------------------------------------
        # PATH 3
        # create_jira = TRUE
        # approval_required = FALSE
        # ----------------------------------------------------

        print("[ROUTE] AUTO EXECUTE → JIRA → AUDIT")

        update_incident_status(
            incident_id,
            "executing",
        )

        result = execute_approved_incident(
            incident_id=incident_id,
            customer_name=customer_name,
        )

        print("[JIRA RESULT]", result)

        jira_success = False

        if isinstance(result, dict):

            jira_success = bool(
                result.get("success", False)
            )

            if result.get("jira_id"):
                jira_success = True

        elif result:
            jira_success = True

        if jira_success:

            update_incident_status(
                incident_id,
                "executed",
            )

            print(
                "[WORKFLOW COMPLETE] Jira execution successful"
            )

        else:

            update_incident_status(
                incident_id,
                "failed",
            )

            print(
                "[WORKFLOW COMPLETE] Jira execution failed"
            )

    except Exception as e:

        print("\n========================================")
        print("[PIPELINE ERROR]")
        print("INCIDENT:", incident_id)
        print("TYPE:", type(e).__name__)
        print("MESSAGE:", str(e))
        print("========================================")

        traceback.print_exc()

        try:
            update_incident_status(
                incident_id,
                "failed",
            )
        except Exception as status_error:
            print(
                "[STATUS UPDATE ERROR]",
                str(status_error),
            )


# ============================================================
# UPDATE INCIDENT STATUS
# ============================================================

def update_incident_status(
    incident_id: str,
    status: str,
):
    """
    Safely update incident status.
    """

    query = """
        UPDATE incidents
        SET status = %s
        WHERE incident_id = %s;
    """

    connection = get_db_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                (
                    status,
                    incident_id,
                ),
            )

        connection.commit()

    finally:
        connection.close()


# ============================================================
# APPROVAL RECORD
# ============================================================

def create_approval_record(
    incident_id: str,
    decision_payload: dict,
):
    """
    Create a persistent human approval record.
    """

    query = """
        INSERT INTO approvals (
            incident_id,
            status,
            decision_payload,
            created_at
        )
        VALUES (
            %s,
            'PENDING',
            %s::jsonb,
            NOW()
        )
        ON CONFLICT (incident_id)
        DO UPDATE SET
            status = 'PENDING',
            decision_payload = EXCLUDED.decision_payload,
            created_at = NOW(),
            reviewer = NULL,
            resolved_at = NULL;
    """

    connection = get_db_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                (
                    incident_id,
                    json.dumps(decision_payload),
                ),
            )

        connection.commit()

    finally:
        connection.close()


# ============================================================
# GET APPROVALS
# ============================================================

@app.get("/api/approvals")
def get_approvals(
    status: str = "PENDING",
):
    """
    Return approval queue.

    Example:

        /api/approvals?status=PENDING
    """

    query = """
        SELECT
            a.approval_id,
            a.incident_id,
            a.status,
            a.decision_payload,
            a.reviewer,
            a.created_at,
            a.resolved_at,

            i.title,
            i.description,
            i.priority,
            i.severity,
            i.status AS incident_status,

            c.customer_name AS customer_name,
            s.service_name AS service_name

        FROM approvals a

        JOIN incidents i
            ON a.incident_id = i.incident_id

        LEFT JOIN customers c
            ON i.customer_id = c.customer_id

        LEFT JOIN services s
            ON i.service_id = s.service_id

        WHERE a.status = %s

        ORDER BY a.created_at ASC;
    """

    try:

        rows = fetch_all(
            query,
            (status.upper(),),
        )

        approvals = []

        for row in rows:

            approvals.append(
                {
                    "approval_id": row.get("approval_id"),
                    "incident_id": row.get("incident_id"),
                    "status": row.get("status"),
                    "decision_payload": normalize_decision_payload(
                        row.get("decision_payload")
                    ),
                    "reviewer": row.get("reviewer"),
                    "created_at": safe_json(
                        row.get("created_at")
                    ),
                    "resolved_at": safe_json(
                        row.get("resolved_at")
                    ),
                    "title": row.get("title"),
                    "description": row.get("description"),
                    "priority": row.get("priority"),
                    "severity": row.get("severity"),
                    "incident_status": row.get(
                        "incident_status"
                    ),
                    "customer_name": row.get(
                        "customer_name"
                    ),
                    "service_name": row.get(
                        "service_name"
                    ),
                }
            )

        return approvals

    except Exception as e:

        print("[GET APPROVALS ERROR]", str(e))
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve approvals.",
        )


# ============================================================
# APPROVE INCIDENT
# ============================================================

# 
@app.post("/api/approvals/{incident_id}/approve")
def approve_incident(
    incident_id: str,
):
    """
    Approve or retry execution of an approved incident.

    Flow:

        PENDING
           ↓
        APPROVED
           ↓
        EXECUTE JIRA
           ↓
        AUDIT

    If the approval is already APPROVED but the incident
    previously failed, execution can safely be retried.
    """

    print(
        f"[APPROVAL] Processing incident {incident_id}"
    )

    # ========================================================
    # STEP 1: LOCK AND CHECK APPROVAL
    # ========================================================

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    approval_id,
                    status,
                    decision_payload
                FROM approvals
                WHERE incident_id = %s
                FOR UPDATE;
                """,
                (incident_id,),
            )

            approval = cursor.fetchone()

            if not approval:
                connection.rollback()

                raise HTTPException(
                    status_code=404,
                    detail="Approval request not found.",
                )

            approval_id = approval[0]
            current_status = approval[1]
            decision_payload = approval[2]

            print(
                f"[APPROVAL] Current status: {current_status}"
            )

            # ------------------------------------------------
            # PENDING -> APPROVED
            # ------------------------------------------------

            if current_status == "PENDING":

                cursor.execute(
                    """
                    UPDATE approvals
                    SET
                        status = 'APPROVED',
                        reviewer = 'dashboard_user',
                        resolved_at = NOW()
                    WHERE approval_id = %s;
                    """,
                    (approval_id,),
                )

                connection.commit()

                print(
                    f"[APPROVAL] Incident {incident_id} approved"
                )

            # ------------------------------------------------
            # ALREADY APPROVED -> ALLOW RETRY
            # ------------------------------------------------

            elif current_status == "APPROVED":

                connection.commit()

                print(
                    f"[APPROVAL] Incident {incident_id} "
                    f"is already approved. Retrying execution."
                )

            # ------------------------------------------------
            # REJECTED / OTHER STATUS
            # ------------------------------------------------

            else:

                connection.rollback()

                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Approval cannot be executed because "
                        f"its status is {current_status}."
                    ),
                )

    finally:
        connection.close()

    # ========================================================
    # STEP 2: GET INCIDENT INFORMATION
    # ========================================================

    incident = fetch_one(
        """
        SELECT
            incident_id,
            customer_id,
            service_id,
            status
        FROM incidents
        WHERE incident_id = %s;
        """,
        (incident_id,),
    )

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found.",
        )

    # ========================================================
    # STEP 3: CHECK IF JIRA ALREADY EXISTS
    # ========================================================
    #
    # This prevents duplicate Jira tickets if a previous
    # execution created Jira but crashed afterwards.
    # ========================================================

    existing_jira = fetch_one(
        """
        SELECT
            jira_id
        FROM jira_tickets
        WHERE incident_id = %s
        ORDER BY created_at DESC
        LIMIT 1;
        """,
        (incident_id,),
    )

    if existing_jira and existing_jira.get("jira_id"):

        jira_id = existing_jira.get("jira_id")

        print(
            f"[APPROVAL] Jira already exists: {jira_id}"
        )

        update_incident_status(
            incident_id,
            "executed",
        )

        return {
            "incident_id": incident_id,
            "status": "executed",
            "jira_id": jira_id,
            "message": (
                "Incident was already approved and "
                "a Jira ticket already exists."
            ),
        }

    # ========================================================
    # STEP 4: GET CUSTOMER NAME
    # ========================================================

    customer = fetch_one(
        """
        SELECT
            customer_name
        FROM customers
        WHERE customer_id = %s;
        """,
        (incident.get("customer_id"),),
    )

    customer_name = (
        customer.get("customer_name")
        if customer
        else None
    )

    # ========================================================
    # STEP 5: EXECUTE APPROVED INCIDENT
    # ========================================================

    try:

        update_incident_status(
            incident_id,
            "executing",
        )

        print(
            f"[HITL] Executing approved incident {incident_id}"
        )

        result = execute_approved_incident(
            incident_id=incident_id,
            customer_name=customer_name,
        )

        print(
            "[APPROVAL JIRA RESULT]",
            result,
        )

        # ====================================================
        # STEP 6: INTERPRET EXECUTION RESULT
        # ====================================================

        jira_success = False
        jira_id = None

        # execute_approved_incident may return a dictionary
        if isinstance(result, dict):

            jira_id = (
                result.get("jira_id")
                or result.get("jira_key")
                or result.get("ticket_key")
            )

            jira_success = bool(
                result.get("success", False)
            )

            if jira_id:
                jira_success = True

        # Current pipeline normally returns Jira key as string
        elif result:

            jira_id = str(result)
            jira_success = True

        # ====================================================
        # STEP 7: SUCCESS
        # ====================================================

        if jira_success:

            update_incident_status(
                incident_id,
                "executed",
            )

            insert_human_audit(
                incident_id=incident_id,
                action="APPROVED_AND_EXECUTED",
                decision={
                    "approval": "APPROVED",
                    "jira_execution": "SUCCESS",
                    "jira_id": jira_id,
                    "reason": (
                        "Human approval completed and "
                        "Jira execution succeeded."
                    ),
                },
            )

            print(
                f"[APPROVAL] Execution successful. "
                f"Jira: {jira_id}"
            )

            return {
                "incident_id": incident_id,
                "status": "executed",
                "jira_id": jira_id,
                "message": (
                    "Incident approved and "
                    "executed successfully."
                ),
            }

        # ====================================================
        # STEP 8: EXECUTION RETURNED NO JIRA
        # ====================================================

        update_incident_status(
            incident_id,
            "failed",
        )

        insert_human_audit(
            incident_id=incident_id,
            action="APPROVED_BUT_EXECUTION_FAILED",
            decision={
                "approval": "APPROVED",
                "jira_execution": "FAILED",
                "result": safe_json(result),
                "reason": (
                    "Human approval succeeded but "
                    "Jira execution returned no Jira ticket."
                ),
            },
        )

        return {
            "incident_id": incident_id,
            "status": "failed",
            "jira_id": None,
            "message": (
                "Approval succeeded, but "
                "Jira execution failed."
            ),
        }

    # ========================================================
    # STEP 9: EXECUTION EXCEPTION
    # ========================================================

    except Exception as e:

        print(
            "[APPROVE EXECUTION ERROR]",
            str(e),
        )

        traceback.print_exc()

        update_incident_status(
            incident_id,
            "failed",
        )

        try:
            insert_human_audit(
                incident_id=incident_id,
                action="APPROVED_BUT_EXECUTION_FAILED",
                decision={
                    "approval": "APPROVED",
                    "jira_execution": "FAILED",
                    "error": str(e),
                    "reason": (
                        "Human approval succeeded but "
                        "Jira execution raised an exception."
                    ),
                },
            )

        except Exception as audit_error:

            print(
                "[AUDIT ERROR]",
                str(audit_error),
            )

        raise HTTPException(
            status_code=500,
            detail=(
                "Incident approved but "
                "Jira execution failed: "
                + str(e)
            ),
        )

@app.post("/api/approvals/{incident_id}/reject")
def reject_incident(
    incident_id: str,
):
    """
    Reject a pending approval.

    Flow:

        PENDING
           ↓
        REJECTED
           ↓
         AUDIT
    """

    print(
        f"[APPROVAL] Rejecting incident {incident_id}"
    )

    connection = get_db_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    approval_id,
                    status,
                    decision_payload
                FROM approvals
                WHERE incident_id = %s
                FOR UPDATE;
                """,
                (incident_id,),
            )

            approval = cursor.fetchone()

            if not approval:

                connection.rollback()

                raise HTTPException(
                    status_code=404,
                    detail="Approval request not found.",
                )

            approval_id = approval[0]
            current_status = approval[1]
            decision_payload = approval[2]

            if current_status != "PENDING":

                connection.rollback()

                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Approval is already "
                        f"{current_status}."
                    ),
                )

            cursor.execute(
                """
                UPDATE approvals
                SET
                    status = 'REJECTED',
                    reviewer = 'dashboard_user',
                    resolved_at = NOW()
                WHERE approval_id = %s;
                """,
                (approval_id,),
            )

            connection.commit()

    finally:
        connection.close()

    # --------------------------------------------------------
    # Audit rejection
    # --------------------------------------------------------

    try:

        insert_human_audit(
            incident_id=incident_id,
            action="HUMAN_REJECTED",
            decision={
                "human_decision": "REJECTED",
                "agent3_decision": normalize_decision_payload(
                    decision_payload
                ),
            },
        )

        update_incident_status(
            incident_id,
            "rejected",
        )

    except Exception as e:

        print(
            "[REJECTION AUDIT ERROR]",
            str(e),
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Approval was rejected, "
                "but audit/status update failed."
            ),
        )

    return {
        "incident_id": incident_id,
        "status": "rejected",
        "message": "Incident rejected and audited.",
    }


# ============================================================
# HUMAN AUDIT
# ============================================================

def insert_human_audit(
    incident_id: str,
    action: str,
    decision: dict,
):
    """
    Insert a human / routing audit entry.
    """

    query = """
        INSERT INTO decisions
        (
            incident_id,
            agent_name,
            decision,
            reason,
            confidence
        )
        VALUES (%s, %s, %s, %s, %s)
    """

    connection = get_db_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                (
                    incident_id,
                    "HumanApprovalGate",
                    json.dumps(decision),
                    decision.get("reason", "Human approval decision"),
                    None,
                ),
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ============================================================
# INCIDENT DETAIL
# ============================================================

@app.get("/api/incidents/{incident_id}")
def get_incident_detail(
    incident_id: str,
):
    """
    Return complete incident information including:

    - Incident
    - Customer
    - Service
    - Agent decisions
    - Jira execution
    - Approval state
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
            i.customer_id,
            i.service_id,

            c.customer_name AS customer_name,
            s.service_name AS service_name

        FROM incidents i

        LEFT JOIN customers c
            ON i.customer_id = c.customer_id

        LEFT JOIN services s
            ON i.service_id = s.service_id

        WHERE i.incident_id = %s;
        """,
        (incident_id,),
    )

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found.",
        )

    # --------------------------------------------------------
    # Agent decisions
    # --------------------------------------------------------

    decisions = fetch_all(
        """
        SELECT
            incident_id,
            agent_name,
            decision,
            reason,
            confidence
        FROM decisions
        WHERE incident_id = %s
        """,
        (incident_id,),
    )

    # --------------------------------------------------------
    # Jira
    # --------------------------------------------------------

    jira = fetch_one(
        """
        SELECT jira_id
        FROM jira_tickets
        WHERE incident_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (incident_id,),
    )

    # --------------------------------------------------------
    # Approval
    # --------------------------------------------------------

    approval = fetch_one(
        """
        SELECT
            approval_id,
            incident_id,
            status,
            decision_payload,
            reviewer,
            created_at,
            resolved_at
        FROM approvals
        WHERE incident_id = %s;
        """,
        (incident_id,),
    )

    return {
        "incident_id": incident.get("incident_id"),
        "title": incident.get("title"),
        "description": incident.get("description"),
        "priority": incident.get("priority"),
        "severity": incident.get("severity"),
        "status": incident.get("status"),
        "created_at": safe_json(
            incident.get("created_at")
        ),
        "customer_name": incident.get(
            "customer_name"
        ),
        "service_name": incident.get(
            "service_name"
        ),
        "jira_id": (
            jira.get("jira_id")
            if jira
            else None
        ),

        "decisions": [
            {
                key: safe_json(value)
                for key, value in row.items()
            }
            for row in decisions
        ],

        "approval": (
            {
                "approval_id": approval.get(
                    "approval_id"
                ),
                "status": approval.get(
                    "status"
                ),
                "decision_payload": normalize_decision_payload(
                    approval.get(
                        "decision_payload"
                    )
                ),
                "reviewer": approval.get(
                    "reviewer"
                ),
                "created_at": safe_json(
                    approval.get("created_at")
                ),
                "resolved_at": safe_json(
                    approval.get("resolved_at")
                ),
            }
            if approval
            else None
        ),
    }


# ============================================================
# DECISIONS
# ============================================================

@app.get("/api/decisions")
def list_decisions():
    """
    Return all agent decisions for the Decision Trail.
    """

    query = """
        SELECT
            incident_id,
            agent_name,
            decision,
            reason,
            confidence
        FROM decisions;
    """

    try:

        rows = fetch_all(query)

        return [
            {
                key: safe_json(value)
                for key, value in row.items()
            }
            for row in rows
        ]

    except Exception as e:

        print(
            "[GET DECISIONS ERROR]",
            str(e),
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve decisions.",
        )


# ============================================================
# INSIGHTS
# ============================================================

@app.get("/api/insights")
def get_insights():
    """
    Dashboard-level system insights and evaluation metrics.
    """

    try:

        total = fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM incidents;
            """
        )

        executed = fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM incidents
            WHERE status = 'executed';
            """
        )

        rejected = fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM incidents
            WHERE status = 'rejected';
            """
        )

        pending = fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM approvals
            WHERE status = 'PENDING';
            """
        )

        failed = fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM incidents
            WHERE status = 'failed';
            """
        )

        approval_stats = fetch_one(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved,
                COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected,
                COUNT(*) FILTER (
                    WHERE status IN ('APPROVED', 'REJECTED')
                ) AS resolved
            FROM approvals;
            """
        )

        confidence_stats = fetch_one(
            """
            SELECT
                AVG(confidence) AS average_confidence,
                COUNT(confidence) AS confidence_count
            FROM decisions
            WHERE confidence IS NOT NULL;
            """
        )

        total_count = (
            total.get("count", 0)
            if total
            else 0
        )

        executed_count = (
            executed.get("count", 0)
            if executed
            else 0
        )

        rejected_count = (
            rejected.get("count", 0)
            if rejected
            else 0
        )

        pending_count = (
            pending.get("count", 0)
            if pending
            else 0
        )

        failed_count = (
            failed.get("count", 0)
            if failed
            else 0
        )

        approved_approvals = (
            approval_stats.get("approved", 0)
            if approval_stats
            else 0
        )

        rejected_approvals = (
            approval_stats.get("rejected", 0)
            if approval_stats
            else 0
        )

        resolved_approvals = (
            approval_stats.get("resolved", 0)
            if approval_stats
            else 0
        )

        average_confidence_raw = (
            confidence_stats.get("average_confidence")
            if confidence_stats
            else None
        )

        confidence_count = (
            confidence_stats.get("confidence_count", 0)
            if confidence_stats
            else 0
        )

        execution_success_rate = (
            round((executed_count / total_count) * 100, 1)
            if total_count > 0
            else 0.0
        )

        rejection_rate = (
            round((rejected_count / total_count) * 100, 1)
            if total_count > 0
            else 0.0
        )

        failure_rate = (
            round((failed_count / total_count) * 100, 1)
            if total_count > 0
            else 0.0
        )

        approval_acceptance_rate = (
            round((approved_approvals / resolved_approvals) * 100, 1)
            if resolved_approvals > 0
            else 0.0
        )

        average_agent_confidence = (
            round(float(average_confidence_raw) * 100, 1)
            if average_confidence_raw is not None
            else 0.0
        )

        return {
            "total_incidents": total_count,
            "executed_incidents": executed_count,
            "rejected_incidents": rejected_count,
            "pending_approvals": pending_count,
            "failed_incidents": failed_count,

            "evaluation_metrics": {
                "execution_success_rate": execution_success_rate,
                "rejection_rate": rejection_rate,
                "failure_rate": failure_rate,
                "approval_acceptance_rate": approval_acceptance_rate,
                "average_agent_confidence": average_agent_confidence,
                "confidence_samples": confidence_count,
                "approved_approvals": approved_approvals,
                "rejected_approvals": rejected_approvals,
                "resolved_approvals": resolved_approvals,
            },
        }

    except Exception as e:

        print(
            "[GET INSIGHTS ERROR]",
            str(e),
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve insights.",
        )

# ============================================================
# EMAIL / EML UPLOAD
# ============================================================

@app.post("/api/incidents/upload")
async def upload_incident(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Upload an .eml or text incident.

    This is the current simulated inbound incident intake.
    Gmail SMTP remains the outbound notification mechanism.
    """

    try:

        content = await file.read()

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode(
                "latin-1",
                errors="ignore",
            )

        subject = file.filename or "Uploaded Incident"

        # ----------------------------------------------------
        # Try parsing email
        # ----------------------------------------------------

        if file.filename.lower().endswith(".eml"):

            try:

                from email import policy
                from email.parser import BytesParser

                message = BytesParser(
                    policy=policy.default
                ).parsebytes(content)

                subject = (
                    message.get("subject")
                    or subject
                )

                body = ""

                if message.is_multipart():

                    for part in message.walk():

                        if (
                            part.get_content_type()
                            == "text/plain"
                        ):

                            try:
                                body += (
                                    part.get_content()
                                    or ""
                                )
                            except Exception:
                                pass

                else:

                    try:
                        body = (
                            message.get_content()
                            or ""
                        )
                    except Exception:
                        body = text

            except Exception:

                body = text

        else:

            body = text

        # ----------------------------------------------------
        # Create incident
        # ----------------------------------------------------

        incident_id = f"INC-{os.urandom(4).hex().upper()}"

        connection = get_db_connection()

        try:

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    INSERT INTO incidents (
                        incident_id,
                        title,
                        description,
                        status,
                        created_at
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        NOW()
                    );
                    """,
                    (
                        incident_id,
                        subject,
                        body,
                        "processing",
                    ),
                )

            connection.commit()

        finally:
            connection.close()

        # ----------------------------------------------------
        # Start AI workflow
        # ----------------------------------------------------

        if background_tasks:

            background_tasks.add_task(
                run_web_incident,
                incident_id,
                subject,
                body,
                None,
                None,
                None,
            )

        else:

            asyncio.create_task(
                asyncio.to_thread(
                    run_web_incident,
                    incident_id,
                    subject,
                    body,
                    None,
                    None,
                    None,
                )
            )

        return {
            "incident_id": incident_id,
            "status": "processing",
            "filename": file.filename,
            "message": "Incident uploaded successfully.",
        }

    except Exception as e:

        print(
            "[UPLOAD ERROR]",
            str(e),
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# APPLICATION STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    print("\n========================================")
    print(" EnterpriseMind-Lite Backend")
    print("========================================")
    print("FastAPI server started")
    print("API: http://127.0.0.1:8000")
    print("Docs: http://127.0.0.1:8000/docs")
    print("========================================\n")


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )

@app.post("/api/customer-service")
def create_customer_service_query(payload: dict):
    """
    Store emails from unknown/new customers
    for Customer Service investigation.
    """

    sender_email = payload.get("sender_email")
    subject = payload.get("subject")
    body = payload.get("body")
    detected_customer_name = payload.get("detected_customer_name")

    if not subject or not body:
        raise HTTPException(
            status_code=400,
            detail="Subject and body are required"
        )

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO customer_service_queries
            (
                sender_email,
                subject,
                body,
                detected_customer_name,
                query_type,
                assigned_team,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING query_id;
            """,
            (
                sender_email,
                subject,
                body,
                detected_customer_name,
                "UNKNOWN_CUSTOMER",
                "Customer Service",
                "pending",
            ),
        )

        query_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "message": "Email assigned to Customer Service",
            "query_id": query_id,
            "assigned_team": "Customer Service",
            "status": "pending",
        }

    except Exception as exc:
        print(
            "[CUSTOMER SERVICE ERROR]",
            str(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc)

        )
@app.get("/api/customer-service")
def get_customer_service_queries():
    """
    Return Customer Service queries for the dashboard.
    """

    try:
        rows = fetch_all(
            """
            SELECT
                query_id,
                sender_email,
                subject,
                body,
                detected_customer_name,
                query_type,
                assigned_team,
                status,
                created_at,
                resolved_at
            FROM customer_service_queries
            ORDER BY created_at DESC;
            """
        )

        return rows

    except Exception as exc:
        print(
            "[CUSTOMER SERVICE ERROR]",
            str(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )

# ============================================================
# RESOLVE CUSTOMER SERVICE QUERY
# ============================================================

@app.post("/api/customer-service/{query_id}/resolve")
def resolve_customer_service_query(query_id: int):
    """
    Mark a Customer Service query as resolved.
    """

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE customer_service_queries
            SET
                status = 'resolved',
                resolved_at = NOW()
            WHERE query_id = %s
              AND status <> 'resolved'
            RETURNING
                query_id,
                status,
                resolved_at;
            """,
            (query_id,),
        )

        row = cursor.fetchone()

        if not row:
            cursor.execute(
                """
                SELECT
                    query_id,
                    status,
                    resolved_at
                FROM customer_service_queries
                WHERE query_id = %s;
                """,
                (query_id,),
            )

            existing = cursor.fetchone()

            if not existing:
                conn.rollback()
                raise HTTPException(
                    status_code=404,
                    detail="Customer Service query not found.",
                )

            conn.commit()

            return {
                "query_id": existing[0],
                "status": existing[1],
                "resolved_at": safe_json(existing[2]),
                "message": "Customer Service query is already resolved.",
            }

        conn.commit()

        return {
            "query_id": row[0],
            "status": row[1],
            "resolved_at": safe_json(row[2]),
            "message": "Customer Service query resolved successfully.",
        }

    except HTTPException:
        raise

    except Exception as exc:
        if conn:
            conn.rollback()

        print(
            "[CUSTOMER SERVICE RESOLVE ERROR]",
            str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()

