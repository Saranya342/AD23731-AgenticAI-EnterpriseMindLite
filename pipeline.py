"""
END-TO-END PIPELINE

Agent 1 -> Agent 2 -> Agent 3 -> Decision Routing -> Jira Execution -> Notification -> Audit

Flow:
    1. Agent 1 classifies the incident
    2. Agent 2 performs organizational reasoning
    3. Agent 3 decides the operational path
    4. Decisions are saved to PostgreSQL
    5. Agent 3 determines one of three paths:
         - create_jira=False -> Reject -> Audit
         - approval_required=True -> Human Approval -> Execute/Reject -> Audit
         - approval_required=False -> Auto Execute -> Jira -> Audit
"""

import os
import json
import psycopg2
from dotenv import load_dotenv

from agent1_incident_intelligence import classify_incident
from agent2_organizational_reasoning import reason_about_incident
from agent3_operational_decision import decide_operational_path
from tool_evaluator import evaluate_tool_results

from jira_integration import (
    create_ticket,
    add_comment,
    transition_status
)

from notification import send_notification


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("Missing environment variable: DATABASE_URL")


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=10
    )


# ============================================================
# AUDIT LOGGING
# ============================================================

def log_decision(
    conn,
    incident_id,
    agent_name,
    decision_dict
):
    """
    Store an agent decision in the decisions table.

    IMPORTANT:
    'JiraExecutionAgent' is an agent name.
    It is NOT a database table name.
    """

    cur = conn.cursor()

    try:
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
            VALUES (%s, %s, %s, %s, %s);
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

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()


# ============================================================
# LEGACY CLI HUMAN APPROVAL
# ============================================================

def request_human_approval(agent3_output):
    """
    Legacy CLI approval helper.

    IMPORTANT:
    The web/API workflow must NOT call this function because
    input() blocks the HTTP request.

    It is retained only for manual CLI testing.
    """

    print("\n" + "=" * 60)
    print("HUMAN APPROVAL REQUIRED")
    print("=" * 60)

    print("\nAgent 3 has requested approval before execution.")

    print("\nOperational Decision:")
    print(json.dumps(agent3_output, indent=2))

    print("\nPlease choose:")
    print("  y = Approve")
    print("  n = Reject")

    while True:

        choice = input(
            "\nEnter your choice (y/n): "
        ).strip().lower()

        if choice == "y":

            print(
                "\n[HITL] Human approved "
                "the operational decision."
            )

            return True

        if choice == "n":

            print(
                "\n[HITL] Human rejected "
                "the operational decision."
            )

            return False

        print(
            "Invalid choice. Please enter y or n."
        )


# ============================================================
# AGENT PROCESSING
# ============================================================

def process_agents(
    incident_id,
    subject,
    body,
    customer_name
):
    """
    Run Agent 1 -> Agent 2 -> RAG-enabled Agent 3 -> diagnostic tools -> Gemini tool evaluation.

    This function does NOT:
        - ask for terminal approval
        - create Jira
        - wait for human input

    This makes it safe to use from the FastAPI
    background workflow.
    """

    conn = get_db_connection()

    try:

        print("\n" + "=" * 60)
        print(
            f"PROCESSING INCIDENT: {incident_id}"
        )
        print("=" * 60)

        # ====================================================
        # AGENT 1
        # ====================================================

        print(
            "\n[AGENT 1] Incident Intelligence"
        )

        a1 = classify_incident(
            subject,
            body,
            customer_name
        )

        print(
            json.dumps(
                a1,
                indent=2
            )
        )

        log_decision(
            conn,
            incident_id,
            "IncidentIntelligenceAgent",
            a1
        )

        # ====================================================
        # AGENT 2
        # ====================================================

        print(
            "\n[AGENT 2] Organizational Reasoning"
        )

        a2 = reason_about_incident(
            a1,
            customer_name,
            incident_id=incident_id,
            subject=subject,
            body=body
        )

        print(
            json.dumps(
                a2,
                indent=2
            )
        )

        log_decision(
            conn,
            incident_id,
            "OrganizationalReasoningAgent",
            a2
        )

        # ====================================================
        # AGENT 3 + RAG
        # ====================================================

        print(
            "\n[AGENT 3] Operational Decision"
        )

        # Pass the original incident text as well so the
        # RAG query has the strongest possible context.
        a3 = decide_operational_path(
            a1,
            a2,
            subject=subject,
            body=body
        )

        print(
            json.dumps(
                a3,
                indent=2
            )
        )

        # ====================================================
        # DIAGNOSTIC TOOLS + GEMINI TOOL EVALUATION
        # ====================================================

        affected_service = a2.get(
            "affected_service"
        )

        tool_evaluation = None

        if affected_service:

            print(
                "\n[TOOLS] Diagnostic Evaluation"
            )

            try:

                tool_evaluation = evaluate_tool_results(
                    affected_service
                )

                print(
                    json.dumps(
                        tool_evaluation,
                        indent=2
                    )
                )

                # Save a separate audit entry for the tool
                # evaluation so the evidence is visible later.
                tool_audit = dict(
                    tool_evaluation
                )

                tool_audit["reason"] = (
                    tool_evaluation.get(
                        "summary",
                        "Diagnostic tool evaluation completed."
                    )
                )

                log_decision(
                    conn,
                    incident_id,
                    "DiagnosticToolEvaluationAgent",
                    tool_audit
                )

                # Attach the tool evidence to Agent 3's final
                # decision so routing and Jira execution can use it.
                a3["tool_evaluation"] = tool_evaluation

                incident_confirmed = bool(
                    tool_evaluation.get(
                        "incident_confirmed",
                        False
                    )
                )

                tool_supports_jira = bool(
                    tool_evaluation.get(
                        "tool_evidence_supports_jira",
                        False
                    )
                )

                # ------------------------------------------------
                # FINAL ROUTING SAFETY RULE
                #
                # Agent 3 remains the primary decision-maker.
                # The tools do NOT create Jira by themselves.
                #
                # If Agent 3 wants Jira but the diagnostic
                # evidence does not confirm/support it, require
                # human approval instead of auto-executing.
                # ------------------------------------------------

                if a3.get("create_jira", False):

                    if (
                        not incident_confirmed
                        or not tool_supports_jira
                    ):

                        a3["approval_required"] = True

                        existing_reason = a3.get(
                            "reason",
                            ""
                        )

                        evidence_reason = (
                            " Diagnostic tool evidence did not "
                            "fully confirm/support automatic Jira "
                            "execution, so human approval is required."
                        )

                        a3["reason"] = (
                            existing_reason
                            + evidence_reason
                        ).strip()

                    else:

                        print(
                            "[ROUTE] Tool evidence confirms the "
                            "incident and supports Jira."
                        )

            except Exception as tool_error:

                print(
                    f"[TOOLS] Diagnostic evaluation failed: "
                    f"{tool_error}"
                )

                # Fail safely. If Agent 3 requested Jira and the
                # diagnostics could not be evaluated, do not allow
                # silent automatic execution.
                if a3.get("create_jira", False):

                    a3["approval_required"] = True

                    existing_reason = a3.get(
                        "reason",
                        ""
                    )

                    a3["reason"] = (
                        existing_reason
                        + " Diagnostic evaluation was unavailable, "
                        "so human approval is required before Jira "
                        "execution."
                    ).strip()

                a3["tool_evaluation"] = {
                    "status": "unavailable",
                    "error": str(tool_error)
                }

        else:

            print(
                "[TOOLS] No affected service was identified. "
                "Skipping diagnostic tools."
            )

            a3["tool_evaluation"] = {
                "status": "skipped",
                "reason": (
                    "No affected service was identified."
                )
            }

            # If Jira is requested but no service is known,
            # require a human check before execution.
            if a3.get("create_jira", False):
                a3["approval_required"] = True

        # ====================================================
        # SAVE FINAL AGENT 3 DECISION
        # ====================================================

        print(
            "\n[AGENT 3] Final decision after tool evaluation"
        )

        print(
            json.dumps(
                a3,
                indent=2
            )
        )

        log_decision(
            conn,
            incident_id,
            "OperationalDecisionAgent",
            a3
        )

        return a1, a2, a3

    finally:

        conn.close()


# ============================================================
# JIRA EXECUTION
# ============================================================

def execute_jira_decision(
    conn,
    incident_id,
    subject,
    customer_name,
    agent1_output,
    agent2_output,
    agent3_output
):

    create_jira = bool(
        agent3_output.get(
            "create_jira",
            False
        )
    )

    # ========================================================
    # REJECT / NO JIRA
    # ========================================================

    if not create_jira:

        print(
            "\n[JIRA] Agent 3 decided "
            "NOT to create a Jira ticket."
        )

        return None

    print(
        "\n[JIRA] Agent 3 decided "
        "to CREATE a Jira ticket."
    )

    # ========================================================
    # PREPARE INFORMATION
    # ========================================================

    jira_priority = agent3_output.get(
        "jira_priority",
        agent1_output.get(
            "priority",
            "High"
        )
    )

    service = agent2_output.get(
        "affected_service",
        "Unknown Service"
    )

    department = agent2_output.get(
        "responsible_department",
        "Unknown Department"
    )

    employee = agent2_output.get(
        "responsible_employee",
        "Unassigned"
    )

    escalation_required = agent3_output.get(
        "escalation_required",
        False
    )

    notify = agent3_output.get(
        "notify",
        "Operations Team"
    )

    # ========================================================
    # JIRA SUMMARY
    # ========================================================

    summary = (
        f"[{jira_priority}] "
        f"{subject} - {customer_name}"
    )

    # ========================================================
    # JIRA DESCRIPTION
    # ========================================================

    description = (
        f"Incident ID: {incident_id}\n\n"
        f"Customer: {customer_name}\n"
        f"Incident: {subject}\n\n"

        f"Affected Service: {service}\n"
        f"Responsible Department: {department}\n"
        f"Responsible Employee: {employee}\n\n"

        f"Agent 1 Priority: "
        f"{agent1_output.get('priority', 'Unknown')}\n"

        f"Agent 1 Severity: "
        f"{agent1_output.get('severity', 'Unknown')}\n"

        f"Agent 1 Category: "
        f"{agent1_output.get('category', 'Unknown')}\n\n"

        f"Recurring Issue: "
        f"{agent2_output.get('is_recurring_issue', False)}\n"

        f"Agent 2 Confidence: "
        f"{agent2_output.get('confidence', 'Unknown')}\n\n"

        f"Escalation Required: "
        f"{escalation_required}\n"

        f"Notify: {notify}\n\n"

        f"Recommended Response:\n"
        f"{agent3_output.get('recommended_response', '')}"
    )

    # ========================================================
    # CREATE JIRA TICKET
    # ========================================================

    jira_key = create_ticket(
        summary=summary,
        description=description,
        priority=jira_priority
    )

    if not jira_key:
        raise RuntimeError(
            "Jira ticket creation returned no Jira ID."
        )

    print(
        f"[JIRA] Created ticket: {jira_key}"
    )

    # ========================================================
    # ADD COMMENT
    # ========================================================

    comment = (
        "Auto-created by Operational Decision Agent.\n"
        f"Incident: {incident_id}\n"
        f"Escalation required: {escalation_required}\n"
        f"Notify: {notify}\n"
        f"Responsible employee: {employee}\n"
        f"Responsible department: {department}"
    )

    add_comment(
        jira_key,
        comment
    )

    # ========================================================
    # MOVE TO IN PROGRESS
    # ========================================================

    transition_status(
        jira_key,
        "In Progress"
    )

    # ========================================================
    # SAVE JIRA TICKET TO POSTGRESQL
    # ========================================================

    jira_insert = """
        INSERT INTO jira_tickets
        (
            jira_id,
            incident_id,
            status,
            priority,
            assignee,
            created_at
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            NOW()
        );
    """

    cur = conn.cursor()

    try:

        cur.execute(
            jira_insert,
            (
                str(jira_key),
                incident_id,
                "In Progress",
                str(jira_priority),
                str(employee) if employee else None
            )
        )

        conn.commit()

        print(
            "[DATABASE] Jira ticket saved "
            "to jira_tickets."
        )

    except Exception:

        conn.rollback()

        print(
            "[DATABASE ERROR] Failed to save "
            "Jira ticket to jira_tickets."
        )

        raise

    finally:

        cur.close()

    # ========================================================
    # AUDIT JIRA CREATION
    # ========================================================

    log_decision(
        conn,
        incident_id,
        "JiraExecutionAgent",
        {
            "jira_id": str(jira_key),
            "ticket_key": str(jira_key),
            "status": "In Progress",
            "priority": jira_priority,
            "assignee": employee,
            "reason": (
                f"Jira ticket {jira_key} "
                f"created and moved to In Progress."
            )
        }
    )

    # ========================================================
    # SEND NOTIFICATION
    # ========================================================

    email_subject = (
        f"[EnterpriseMind Lite] "
        f"{jira_priority} incident "
        f"— {jira_key} created"
    )

    email_body = (
        f"A new incident has been processed "
        f"and a Jira ticket created.\n\n"

        f"Incident ID: {incident_id}\n"
        f"Jira Ticket: {jira_key}\n"
        f"Customer: {customer_name}\n"
        f"Priority: {jira_priority}\n\n"

        f"Notify: {notify}\n"
        f"Responsible Employee: {employee}\n"
        f"Responsible Department: {department}\n\n"

        f"Recommended Response:\n"
        f"{agent3_output.get('recommended_response', '')}"
    )

    try:

        send_notification(
            incident_id=incident_id,
            subject_line=email_subject,
            body_text=email_body
        )

    except Exception as email_error:

        print(
            f"[EMAIL] Notification failed: "
            f"{email_error}"
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print(
        "\n[JIRA] EXECUTION COMPLETE"
    )

    print(
        f"[JIRA] Ticket: {jira_key}"
    )

    print(
        f"[JIRA] Priority: {jira_priority}"
    )

    print(
        "[JIRA] Status: In Progress"
    )

    return str(jira_key)


# ============================================================
# EXECUTE APPROVED INCIDENT
# ============================================================

def execute_approved_incident(
    incident_id,
    subject=None,
    customer_name=None,
    agent1_output=None,
    agent2_output=None,
    agent3_output=None
):
    """
    Execute a previously approved incident.

    The web approval API may provide only incident_id
    and customer_name.

    In that case, the original incident information
    and Agent 1/2/3 decisions are recovered from
    PostgreSQL.
    """

    conn = get_db_connection()

    try:

        print(
            f"\n[HITL] Executing approved incident "
            f"{incident_id}"
        )

        # ====================================================
        # RECOVER INCIDENT INFORMATION
        # ====================================================

        incident_row = None

        if (
            subject is None
            or customer_name is None
        ):

            cur = conn.cursor()

            try:

                cur.execute(
                    """
                    SELECT
                        title,
                        customer_id
                    FROM incidents
                    WHERE incident_id = %s;
                    """,
                    (incident_id,)
                )

                incident_row = cur.fetchone()

            finally:

                cur.close()

        if subject is None:

            if incident_row:
                subject = incident_row[0]

            else:
                raise RuntimeError(
                    f"Incident {incident_id} "
                    f"was not found."
                )

        # ====================================================
        # RECOVER CUSTOMER NAME
        # ====================================================

        if customer_name is None:

            customer_id = (
                incident_row[1]
                if incident_row
                else None
            )

            if customer_id:

                cur = conn.cursor()

                try:

                    cur.execute(
                        """
                        SELECT customer_name
                        FROM customers
                        WHERE customer_id = %s;
                        """,
                        (customer_id,)
                    )

                    customer_row = cur.fetchone()

                finally:

                    cur.close()

                if customer_row:

                    customer_name = (
                        customer_row[0]
                    )

        if customer_name is None:

            customer_name = "Unknown Customer"

        # ====================================================
        # RECOVER AGENT DECISIONS
        # ====================================================

        if (
            agent1_output is None
            or agent2_output is None
            or agent3_output is None
        ):

            cur = conn.cursor()

            try:

                cur.execute(
                    """
                    SELECT
                        agent_name,
                        decision
                    FROM decisions
                    WHERE incident_id = %s;
                    """,
                    (incident_id,)
                )

                decision_rows = cur.fetchall()

            finally:

                cur.close()

            for agent_name, decision in decision_rows:

                if isinstance(decision, str):

                    try:
                        decision = json.loads(
                            decision
                        )

                    except Exception:

                        decision = {}

                if not isinstance(
                    decision,
                    dict
                ):
                    decision = {}

                if (
                    agent_name
                    == "IncidentIntelligenceAgent"
                ):
                    agent1_output = decision

                elif (
                    agent_name
                    == "OrganizationalReasoningAgent"
                ):
                    agent2_output = decision

                elif (
                    agent_name
                    == "OperationalDecisionAgent"
                ):
                    agent3_output = decision

        # ====================================================
        # VALIDATE RECOVERED DECISIONS
        # ====================================================

        if agent1_output is None:
            raise RuntimeError(
                "Agent 1 decision could not be recovered."
            )

        if agent2_output is None:
            raise RuntimeError(
                "Agent 2 decision could not be recovered."
            )

        if agent3_output is None:
            raise RuntimeError(
                "Agent 3 decision could not be recovered."
            )

        # ====================================================
        # EXECUTE JIRA
        # ====================================================

        jira_key = execute_jira_decision(
            conn=conn,
            incident_id=incident_id,
            subject=subject,
            customer_name=customer_name,
            agent1_output=agent1_output,
            agent2_output=agent2_output,
            agent3_output=agent3_output
        )

        return jira_key

    finally:

        conn.close()


# ============================================================
# LEGACY CLI END-TO-END PIPELINE
# ============================================================

def run_pipeline(
    incident_id,
    subject,
    body,
    customer_name
):
    """
    Legacy synchronous CLI pipeline.

    Use process_agents() +
    execute_approved_incident()
    for the web/API workflow.
    """

    a1, a2, a3 = process_agents(
        incident_id=incident_id,
        subject=subject,
        body=body,
        customer_name=customer_name
    )

    create_jira = bool(
        a3.get(
            "create_jira",
            False
        )
    )

    approval_required = bool(
        a3.get(
            "approval_required",
            False
        )
    )

    # ========================================================
    # PATH 1
    # NO JIRA
    # ========================================================

    if not create_jira:

        print(
            "\n[ROUTE] REJECT -> AUDIT"
        )

        conn = get_db_connection()

        try:

            log_decision(
                conn,
                incident_id,
                "HumanApprovalGate",
                {
                    "approved": False,
                    "reason": (
                        "Agent 3 decided that "
                        "Jira creation is not required."
                    )
                }
            )

        finally:

            conn.close()

        return (
            a1,
            a2,
            a3,
            None
        )

    # ========================================================
    # PATH 2
    # HUMAN APPROVAL
    # ========================================================

    if approval_required:

        approved = request_human_approval(
            a3
        )

        if not approved:

            conn = get_db_connection()

            try:

                log_decision(
                    conn,
                    incident_id,
                    "HumanApprovalGate",
                    {
                        "approved": False,
                        "reason": (
                            "Rejected by human reviewer — "
                            "Jira ticket not created."
                        )
                    }
                )

            finally:

                conn.close()

            print(
                "\nPIPELINE STOPPED "
                "AFTER HUMAN REJECTION."
            )

            return (
                a1,
                a2,
                a3,
                None
            )

    else:

        print(
            "\n[HITL] Approval not required."
        )

        print(
            "[HITL] Continuing automatically."
        )

    # ========================================================
    # JIRA EXECUTION
    # ========================================================

    jira_key = execute_approved_incident(
        incident_id=incident_id,
        subject=subject,
        customer_name=customer_name,
        agent1_output=a1,
        agent2_output=a2,
        agent3_output=a3
    )

    # ========================================================
    # PIPELINE COMPLETE
    # ========================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "PIPELINE COMPLETE"
    )

    print(
        "=" * 60
    )

    if jira_key:

        print(
            f"JIRA TICKET CREATED: "
            f"{jira_key}"
        )

    else:

        print(
            "NO JIRA TICKET CREATED"
        )

    return (
        a1,
        a2,
        a3,
        jira_key
    )


# ============================================================
# TEST RUN
# ============================================================

if __name__ == "__main__":

    run_pipeline(
        incident_id="INC-TEST-01",
        subject="Cannot process payments",
        body=(
            "ABC Retail has been unable to "
            "process payments for the last "
            "30 minutes."
        ),
        customer_name="ABC Retail"
    )