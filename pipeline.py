"""
END-TO-END PIPELINE
Agent 1 -> Agent 2 -> Agent 3 -> Human Approval -> Jira Execution -> Notification

Flow:
    1. Agent 1 classifies the incident
    2. Agent 2 performs organizational reasoning
    3. Agent 3 decides the operational path
    4. Decisions are saved to PostgreSQL
    5. If approval is required:
         - Ask human for approval
         - If approved -> create Jira
         - If rejected -> do NOT create Jira
    6. If approval is NOT required:
         - Create Jira automatically
    7. Add comment and move Jira ticket to In Progress
    8. Send a real email notification about the outcome
"""

import os
import json
import psycopg2
from dotenv import load_dotenv

from agent1_incident_intelligence import classify_incident
from agent2_organizational_reasoning import reason_about_incident
from agent3_operational_decision import decide_operational_path

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
# HUMAN APPROVAL
# ============================================================

def request_human_approval(agent3_output):
    """
    Ask a human operator whether the Agent 3 decision
    should be executed.
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

        choice = input("\nEnter your choice (y/n): ").strip().lower()

        if choice == "y":

            print("\n[HITL] Human approved the operational decision.")

            return True

        if choice == "n":

            print("\n[HITL] Human rejected the operational decision.")

            return False

        print("Invalid choice. Please enter y or n.")


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

    create_jira = agent3_output.get(
        "create_jira",
        False
    )

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


    # --------------------------------------------------------
    # Prepare information
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Jira Summary
    # --------------------------------------------------------

    summary = (
        f"[{jira_priority}] "
        f"{subject} - {customer_name}"
    )


    # --------------------------------------------------------
    # Jira Description
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # CREATE JIRA TICKET
    # --------------------------------------------------------

    jira_key = create_ticket(
        summary=summary,
        description=description,
        priority=jira_priority
    )


    # --------------------------------------------------------
    # LOG TICKET CREATION TO DECISIONS TABLE (audit trail)
    # --------------------------------------------------------

    log_decision(
        conn,
        incident_id,
        "JiraExecutionAgent",
        {
            "ticket_key": jira_key,
            "reason": f"Jira ticket {jira_key} created and moved to In Progress."
        }
    )


    # --------------------------------------------------------
    # ADD COMMENT
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # MOVE TO IN PROGRESS
    # --------------------------------------------------------

    transition_status(
        jira_key,
        "In Progress"
    )


    # --------------------------------------------------------
    # SEND NOTIFICATION EMAIL (PHASE 13)
    # --------------------------------------------------------
    # Wrapped in try/except so a failed email never crashes an
    # otherwise-successful Jira ticket creation.

    email_subject = (
        f"[EnterpriseMind Lite] {jira_priority} incident "
        f"— {jira_key} created"
    )

    email_body = (
        f"A new incident has been processed and a Jira ticket created.\n\n"
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

        print(f"[EMAIL] Notification failed: {email_error}")


    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    print("\n[JIRA] EXECUTION COMPLETE")

    print(f"[JIRA] Ticket: {jira_key}")

    print(f"[JIRA] Priority: {jira_priority}")

    print("[JIRA] Status: In Progress")


    return jira_key


# ============================================================
# END-TO-END PIPELINE
# ============================================================

def run_pipeline(
    incident_id,
    subject,
    body,
    customer_name
):

    conn = psycopg2.connect(
        DATABASE_URL
    )

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
            customer_name
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
        # AGENT 3
        # ====================================================

        print(
            "\n[AGENT 3] Operational Decision"
        )

        a3 = decide_operational_path(
            a1,
            a2
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


        # ====================================================
        # HUMAN APPROVAL / HITL
        # ====================================================

        approval_required = a3.get(
            "approval_required",
            False
        )


        if approval_required:

            approved = request_human_approval(
                a3
            )

            if not approved:

                print("\n" + "=" * 60)
                print("HITL RESULT: REJECTED")
                print("=" * 60)

                print(
                    "\n[JIRA] No Jira ticket will be created."
                )

                print(
                    "\nPIPELINE STOPPED AFTER HUMAN REJECTION."
                )

                log_decision(
                    conn,
                    incident_id,
                    "HumanApprovalGate",
                    {"reason": "Rejected by human reviewer — Jira ticket not created."}
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


        # ====================================================
        # JIRA EXECUTION
        # ====================================================

        print(
            "\n[JIRA] Executing Operational Decision"
        )

        jira_key = execute_jira_decision(
            conn=conn,
            incident_id=incident_id,
            subject=subject,
            customer_name=customer_name,
            agent1_output=a1,
            agent2_output=a2,
            agent3_output=a3
        )


        # ====================================================
        # PIPELINE COMPLETE
        # ====================================================

        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE")
        print("=" * 60)

        if jira_key:

            print(
                f"JIRA TICKET CREATED: {jira_key}"
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


    finally:

        conn.close()


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
