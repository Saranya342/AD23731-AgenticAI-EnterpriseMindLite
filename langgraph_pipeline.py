"""
PHASE 6 — LangGraph Orchestration

Wraps Agent 1 -> Agent 2 -> Agent 3 -> Human Approval -> Jira Execution
as a proper LangGraph state machine with conditional routing, instead of
plain chained function calls.

Reuses the EXISTING, already-tested functions from pipeline.py:
    - log_decision()          (writes to the Postgres decisions table)
    - request_human_approval() (Phase 12 CLI approval gate)
    - execute_jira_decision()  (Phase 10 Jira creation + Phase 13 email)

This file only adds the graph/routing layer on top — none of the
underlying logic is duplicated or rewritten.

Run:
    python langgraph_pipeline.py
"""

import json
from typing import TypedDict, Optional, Literal

import psycopg2
from langgraph.graph import StateGraph, START, END

from agent1_incident_intelligence import classify_incident
from agent2_organizational_reasoning import reason_about_incident
from agent3_operational_decision import decide_operational_path

from pipeline import (
    DATABASE_URL,
    log_decision,
    request_human_approval,
    execute_jira_decision
)


# ============================================================
# STATE SCHEMA
# ============================================================

class PipelineState(TypedDict):
    incident_id: str
    subject: str
    body: str
    customer_name: str
    a1: dict
    a2: dict
    a3: dict
    approved: bool
    jira_key: Optional[str]


# ============================================================
# GRAPH BUILDER
# ============================================================
# conn is captured via closure so every node shares the same
# open Postgres connection for the duration of one pipeline run.

def build_graph(conn):

    def agent1_node(state: PipelineState) -> dict:

        print("\n[AGENT 1] Incident Intelligence")

        a1 = classify_incident(
            state["subject"],
            state["body"],
            state["customer_name"]
        )

        print(json.dumps(a1, indent=2))

        log_decision(conn, state["incident_id"], "IncidentIntelligenceAgent", a1)

        return {"a1": a1}


    def agent2_node(state: PipelineState) -> dict:

        print("\n[AGENT 2] Organizational Reasoning")

        a2 = reason_about_incident(
            state["a1"],
            state["customer_name"],
            incident_id=state["incident_id"]
    )

        print(json.dumps(a2, indent=2))

        log_decision(conn, state["incident_id"], "OrganizationalReasoningAgent", a2)

        return {"a2": a2}


    def agent3_node(state: PipelineState) -> dict:

        print("\n[AGENT 3] Operational Decision")

        a3 = decide_operational_path(
            state["a1"],
            state["a2"]
        )

        print(json.dumps(a3, indent=2))

        log_decision(conn, state["incident_id"], "OperationalDecisionAgent", a3)

        return {"a3": a3}


    def human_approval_node(state: PipelineState) -> dict:

        approved = request_human_approval(state["a3"])

        if not approved:
            log_decision(
                conn,
                state["incident_id"],
                "HumanApprovalGate",
                {"reason": "Rejected by human reviewer — Jira ticket not created."}
            )

        return {"approved": approved}


    def jira_execution_node(state: PipelineState) -> dict:

        print("\n[JIRA] Executing Operational Decision")

        jira_key = execute_jira_decision(
            conn=conn,
            incident_id=state["incident_id"],
            subject=state["subject"],
            customer_name=state["customer_name"],
            agent1_output=state["a1"],
            agent2_output=state["a2"],
            agent3_output=state["a3"]
        )

        return {"jira_key": jira_key}


    # --------------------------------------------------------
    # ROUTING FUNCTIONS
    # --------------------------------------------------------

    def route_after_agent3(state: PipelineState) -> Literal["skip", "needs_approval", "auto_proceed"]:

        a3 = state["a3"]

        if not a3.get("create_jira"):
            return "skip"

        if a3.get("approval_required"):
            return "needs_approval"

        return "auto_proceed"


    def route_after_approval(state: PipelineState) -> Literal["approved", "rejected"]:

        return "approved" if state.get("approved") else "rejected"


    # --------------------------------------------------------
    # ASSEMBLE THE GRAPH
    # --------------------------------------------------------

    graph = StateGraph(PipelineState)

    graph.add_node("agent1", agent1_node)
    graph.add_node("agent2", agent2_node)
    graph.add_node("agent3", agent3_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("jira_execution", jira_execution_node)

    graph.add_edge(START, "agent1")
    graph.add_edge("agent1", "agent2")
    graph.add_edge("agent2", "agent3")

    graph.add_conditional_edges(
        "agent3",
        route_after_agent3,
        {
            "skip": END,
            "needs_approval": "human_approval",
            "auto_proceed": "jira_execution"
        }
    )

    graph.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "approved": "jira_execution",
            "rejected": END
        }
    )

    graph.add_edge("jira_execution", END)

    return graph.compile()


# ============================================================
# ENTRY POINT
# ============================================================

def run_pipeline_langgraph(incident_id, subject, body, customer_name):

    conn = psycopg2.connect(DATABASE_URL)

    try:

        print("\n" + "=" * 60)
        print(f"PROCESSING INCIDENT (LangGraph): {incident_id}")
        print("=" * 60)

        app = build_graph(conn)

        initial_state: PipelineState = {
            "incident_id": incident_id,
            "subject": subject,
            "body": body,
            "customer_name": customer_name,
            "a1": {},
            "a2": {},
            "a3": {},
            "approved": False,
            "jira_key": None
        }

        final_state = app.invoke(initial_state)

        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE (LangGraph)")
        print("=" * 60)

        if final_state.get("jira_key"):
            print(f"JIRA TICKET CREATED: {final_state['jira_key']}")
        else:
            print("NO JIRA TICKET CREATED")

        return final_state

    finally:

        conn.close()


# ============================================================
# TEST RUN
# ============================================================

if __name__ == "__main__":

    run_pipeline_langgraph(
        incident_id="INC-TEST-01",
        subject="Cannot process payments",
        body="ABC Retail has been unable to process payments for the last 30 minutes.",
        customer_name="ABC Retail"
    )
