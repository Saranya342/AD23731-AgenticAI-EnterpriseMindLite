# """
# AGENT 2 — Organizational Reasoning Agent

# Input:
#     Agent 1's classification + customer name

# Process:
#     1. Query Neo4j for organizational relationships
#     2. Query PostgreSQL for historical incidents
#     3. Ask Gemini to reason over the evidence

# Output:
#     affected_service
#     responsible_department
#     responsible_employee
#     employee_available
#     historical_similar_incidents
#     is_recurring_issue
#     confidence
#     reason

# Run:
#     python agent2_organizational_reasoning.py
# """

# import os
# import json
# import time

# import psycopg2
# from dotenv import load_dotenv
# from neo4j import GraphDatabase
# from google import genai


# # ============================================================
# # LOAD ENVIRONMENT VARIABLES
# # ============================================================

# load_dotenv()

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# GEMINI_MODEL = os.getenv("GEMINI_MODEL")

# NEO4J_URI = os.getenv("NEO4J_URI")
# NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
# NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# DATABASE_URL = os.getenv("DATABASE_URL")


# # ============================================================
# # VALIDATE CONFIGURATION
# # ============================================================

# required_vars = {
#     "GEMINI_API_KEY": GEMINI_API_KEY,
#     "GEMINI_MODEL": GEMINI_MODEL,
#     "NEO4J_URI": NEO4J_URI,
#     "NEO4J_USERNAME": NEO4J_USERNAME,
#     "NEO4J_PASSWORD": NEO4J_PASSWORD,
#     "DATABASE_URL": DATABASE_URL,
# }

# missing = [name for name, value in required_vars.items() if not value]

# if missing:
#     raise ValueError(
#         f"Missing environment variables: {', '.join(missing)}"
#     )


# # ============================================================
# # GEMINI CLIENT
# # ============================================================

# client = genai.Client(
#     api_key=GEMINI_API_KEY
# )


# # ============================================================
# # NEO4J — ORGANIZATIONAL EVIDENCE
# # ============================================================

# def get_org_evidence(customer_name: str):
#     """
#     Pull the organizational ownership chain from Neo4j.

#     Customer
#         ↓ USES
#     Service
#         ↓ OWNS
#     Department

#     Employee
#         ↓ OWNS_SERVICE
#     Service
#     """

#     # Use neo4j+ssc for this environment because the original
#     # neo4j+s connection produced a certificate verification error.
#     neo4j_test_uri = NEO4J_URI.replace(
#         "neo4j+s://",
#         "neo4j+ssc://",
#         1
#     )

#     driver = GraphDatabase.driver(
#         neo4j_test_uri,
#         auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
#     )

#     try:
#         with driver.session() as session:

#             result = session.run(
#                 """
#                 MATCH (c:Customer {name: $name})-[:USES]->(s:Service)
#                       <-[:OWNS]-(d:Department)

#                 MATCH (e:Employee)-[:WORKS_IN]->(d)

#                 RETURN
#                     s.name AS service,
#                     s.service_id AS service_id,
#                     d.name AS department,
#                     e.name AS employee,
#                     e.availability AS available
#                 """,
#                 name=customer_name
#             )

#             records = [dict(record) for record in result]

#             return records

#     finally:
#         driver.close()


# # ============================================================
# # POSTGRESQL — HISTORICAL INCIDENTS
# # ============================================================
# def get_historical_incidents(service_id: str, exclude_incident_id: str = None):

#     conn = psycopg2.connect(DATABASE_URL)

#     try:
#         cur = conn.cursor()

#         cur.execute(
#             """
#             SELECT
#                 incident_id,
#                 title
#             FROM incidents
#             WHERE service_id = %s
#               AND incident_id != %s
#             ORDER BY created_at DESC
#             LIMIT 5
#             """,
#             (service_id, exclude_incident_id or '')
#         )
#         rows = cur.fetchall()

#         return [
#             {
#                 "incident_id": row[0],
#                 "title": row[1]
#             }
#             for row in rows
#         ]

#     finally:
#         cur.close()
#         conn.close()


# # ============================================================
# # GEMINI REASONING PROMPT
# # ============================================================

# REASONING_PROMPT = """
# You are an Organizational Reasoning Agent for an IT operations system.

# You are given:

# 1. An incident classification from Agent 1.
# 2. Organizational evidence from Neo4j:
#    - affected service
#    - owning department
#    - service owner
#    - employee availability
# 3. Historical incidents from PostgreSQL.

# Your job is NOT to simply repeat the database information.

# You must REASON over the evidence.

# Rules:

# - Identify the affected service.
# - Identify the department responsible for that service.
# - Identify the registered employee responsible for the service.
# - Check whether that employee is available.
# - If the employee is unavailable, explicitly mention this in the reason.
# - If the employee is unavailable, recommend department-level handling or reassignment.
# - Examine historical incidents.
# - Determine whether the issue appears to be recurring.
# - Use the historical incidents as evidence.
# - Do not invent historical incidents.
# - Do not invent organizational relationships.
# - Confidence must be between 0.0 and 1.0.

# Return ONLY valid JSON.

# The response must be syntactically valid JSON.
# Do not use single quotes.
# Do not put unescaped quotation marks inside string values.
# Do not add trailing commas.
# Return exactly one JSON object and nothing else.
# Keep the "reason" field concise, using no more than 2 sentences.

# Required JSON structure:

# {
#     "affected_service": string,
#     "responsible_department": string,
#     "responsible_employee": string,
#     "employee_available": boolean,
#     "historical_similar_incidents": [string],
#     "is_recurring_issue": boolean,
#     "confidence": number,
#     "reason": string
# }
# """


# # ============================================================
# # AGENT 2
# # ============================================================

# def reason_about_incident(
#     incident_classification: dict,
#     customer_name: str,
#     incident_id: str = None
# ) -> dict:

#     # --------------------------------------------------------
#     # STEP 1 — Get Neo4j evidence
#     # --------------------------------------------------------

#     evidence = get_org_evidence(customer_name)

#     if not evidence:
#         raise ValueError(
#             f"No organizational evidence found for customer: "
#             f"{customer_name}"
#         )

#     # For now, use the first matching service.
#     top_match = evidence[0]

#     # --------------------------------------------------------
#     # STEP 2 — Get PostgreSQL historical evidence
#     # --------------------------------------------------------

#     history = get_historical_incidents(
#         top_match["service_id"],
#         exclude_incident_id=incident_id
#     )

#     # --------------------------------------------------------
#     # STEP 3 — Build reasoning prompt
#     # --------------------------------------------------------

#     prompt = f"""
# {REASONING_PROMPT}

# Customer:
# {customer_name}

# Agent 1 Incident Classification:
# {json.dumps(incident_classification, indent=2)}

# Neo4j Organizational Evidence:
# {json.dumps(top_match, indent=2)}

# PostgreSQL Historical Incidents:
# {json.dumps(history, indent=2)}

# Now reason over all the evidence and return ONLY the JSON object.
# """

#     # --------------------------------------------------------
#     # STEP 4 + 5 — Ask Gemini and parse JSON
#     # --------------------------------------------------------

#     max_attempts = 3

#     for attempt in range(1, max_attempts + 1):

#         response = client.models.generate_content(
#             model=GEMINI_MODEL,
#             contents=prompt,
#             config={
#                 "response_mime_type": "application/json",
#                 "temperature": 0
#             }
#         )

#         raw_text = response.text.strip()

#         try:
#             return json.loads(raw_text)

#         except json.JSONDecodeError:

#             print(
#                 f"JSON parsing failed on attempt "
#                 f"{attempt}/{max_attempts}"
#             )

#             if attempt < max_attempts:
#                 time.sleep(1)
#                 continue

#             print("\nFAILED TO PARSE MODEL OUTPUT:")
#             print(raw_text)

#             raise


# # ============================================================
# # TEST
# # ============================================================

# if __name__ == "__main__":

#     # Agent 1's actual output
#     agent1_output = {
#         "incident_type": "Incident",
#         "category": "Payment Failure",
#         "priority": "Critical",
#         "severity": "Critical",
#         "business_impact": "Complete halt of retail transaction processing",
#         "reason": "Total outage of payment processing.",
#         "confidence": 0.95
#     }

#     result = reason_about_incident(
#         incident_classification=agent1_output,
#         customer_name="ABC Retail"
#     )

#     print("\nAGENT 2 OUTPUT")
#     print("=" * 60)
#     print(json.dumps(result, indent=2))

"""
AGENT 2 — Organizational Reasoning Agent

Input:
    Agent 1's classification + customer name

Process:
    1. Query Neo4j for organizational relationships
    2. Identify the service owner from the actual OWNS_SERVICE relationship
    3. Query PostgreSQL for historical incidents
    4. Ask Gemini to reason over the evidence

Output:
    affected_service
    responsible_department
    responsible_employee
    employee_available
    historical_similar_incidents
    is_recurring_issue
    confidence
    reason

Run:
    python agent2_organizational_reasoning.py
"""

import os
import json
import time

import psycopg2
from dotenv import load_dotenv
from neo4j import GraphDatabase
from google import genai


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

DATABASE_URL = os.getenv("DATABASE_URL")


# ============================================================
# VALIDATE CONFIGURATION
# ============================================================

required_vars = {
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "GEMINI_MODEL": GEMINI_MODEL,
    "NEO4J_URI": NEO4J_URI,
    "NEO4J_USERNAME": NEO4J_USERNAME,
    "NEO4J_PASSWORD": NEO4J_PASSWORD,
    "DATABASE_URL": DATABASE_URL,
}

missing = [name for name, value in required_vars.items() if not value]

if missing:
    raise ValueError(
        f"Missing environment variables: {', '.join(missing)}"
    )


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# NEO4J — ORGANIZATIONAL EVIDENCE
# ============================================================

def get_org_evidence(customer_name: str):
    """
    Pull the organizational ownership chain from Neo4j.

    Actual graph structure:

        Customer
            ↓ USES
        Service
            ↓ OWNS
        Department

        Service
            ↓ OWNS_SERVICE
        Employee

    Example:

        ABC Retail
            ↓ USES
        Payment Gateway
            ├── OWNS ──────────> Backend Engineering
            └── OWNS_SERVICE ──> Rahul
    """

    # Use neo4j+ssc for this environment because the original
    # neo4j+s connection produced a certificate verification error.
    neo4j_test_uri = NEO4J_URI.replace(
        "neo4j+s://",
        "neo4j+ssc://",
        1
    )

    driver = GraphDatabase.driver(
        neo4j_test_uri,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    try:
        with driver.session() as session:

            result = session.run(
                """
                MATCH (c:Customer {name: $name})-[:USES]->(s:Service)
                    <-[:OWNS]-(d:Department)

                OPTIONAL MATCH (s)-[:OWNS_SERVICE]->(e:Employee)

                RETURN
                    s.name AS service,
                    s.service_id AS service_id,
                    d.name AS department,
                    e.name AS employee,
                    e.availability AS available
                ORDER BY s.service_id
                """,
                name=customer_name
            )

            records = [dict(record) for record in result]

            return records

    finally:
        driver.close()


# ============================================================
# POSTGRESQL — HISTORICAL INCIDENTS
# ============================================================

def get_historical_incidents(
    service_id: str,
    exclude_incident_id: str = None
):

    conn = psycopg2.connect(DATABASE_URL)

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                incident_id,
                title
            FROM incidents
            WHERE service_id = %s
              AND incident_id != %s
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (
                service_id,
                exclude_incident_id or ''
            )
        )

        rows = cur.fetchall()

        return [
            {
                "incident_id": row[0],
                "title": row[1]
            }
            for row in rows
        ]

    finally:
        cur.close()
        conn.close()


# ============================================================
# GEMINI REASONING PROMPT
# ============================================================

REASONING_PROMPT = """
You are an Organizational Reasoning Agent for an IT operations system.

You are given:

1. An incident classification from Agent 1.
2. Organizational evidence from Neo4j.
3. Historical incidents from PostgreSQL.

Your job is to reason over the evidence while NEVER inventing
organizational information.

Rules:

- Identify the affected service from the provided organizational evidence
  and the Agent 1 incident classification.
- Identify the department responsible for that service.
- Identify the employee connected to the service through the
  OWNS_SERVICE relationship.
- employee_available MUST come directly from the Neo4j evidence.
- Do NOT select another employee from the same department.
- Do NOT replace an unavailable service owner with another employee.
- If the registered service owner is unavailable, explicitly mention this.
- If the registered service owner is unavailable, recommend
  department-level handling or reassignment.
- Examine historical incidents.
- Determine whether the issue appears to be recurring.
- Use historical incidents as evidence.
- Do not invent historical incidents.
- Do not invent organizational relationships.
- Do not invent employee availability.
- Confidence must be between 0.0 and 1.0.

Important:

The OWNS_SERVICE relationship is directional:

Service -[:OWNS_SERVICE]-> Employee

Therefore, the employee returned in the Neo4j evidence is the
registered service owner.

Return ONLY valid JSON.

The response must be syntactically valid JSON.
Do not use single quotes.
Do not put unescaped quotation marks inside string values.
Do not add trailing commas.
Return exactly one JSON object and nothing else.

Keep the "reason" field concise, using no more than 2 sentences.

Required JSON structure:

{
    "affected_service": string,
    "responsible_department": string,
    "responsible_employee": string,
    "employee_available": boolean,
    "historical_similar_incidents": [string],
    "is_recurring_issue": boolean,
    "confidence": number,
    "reason": string
}
"""


# ============================================================
# FIND BEST ORGANIZATIONAL MATCH
# ============================================================

def select_org_match(
    evidence: list,
    incident_classification: dict
) -> dict:

    if not evidence:
        raise ValueError("No organizational evidence available.")

    # If there is only one service, use it directly.
    if len(evidence) == 1:
        return evidence[0]

    # Give Gemini all available organizational evidence so that
    # service identification is based on actual graph evidence.
    selection_prompt = f"""
You are identifying the affected service for an IT incident.

Agent 1 classification:
{json.dumps(incident_classification, indent=2)}

Available organizational evidence from Neo4j:
{json.dumps(evidence, indent=2)}

Select the ONE service that best matches the incident.

Rules:
- Only select a service that exists in the provided evidence.
- Do not invent a service.
- Return the exact service_id from the evidence.
- Return ONLY valid JSON.

Required format:

{{
    "service_id": "string"
}}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=selection_prompt,
        config={
            "response_mime_type": "application/json",
            "temperature": 0
        }
    )

    try:
        selection = json.loads(response.text.strip())
    except json.JSONDecodeError:
        raise ValueError(
            "Gemini returned invalid service selection JSON."
        )

    selected_service_id = selection.get("service_id")

    if not selected_service_id:
        raise ValueError(
            "Gemini did not return a service_id."
        )

    for record in evidence:
        if record["service_id"] == selected_service_id:
            return record

    raise ValueError(
        f"Gemini selected service_id '{selected_service_id}', "
        "but that service was not present in Neo4j evidence."
    )


# ============================================================
# AGENT 2
# ============================================================

def reason_about_incident(
    incident_classification: dict,
    customer_name: str,
    incident_id: str = None
) -> dict:

    # --------------------------------------------------------
    # STEP 1 — Get Neo4j evidence
    # --------------------------------------------------------

    evidence = get_org_evidence(customer_name)

    if not evidence:
        raise ValueError(
            f"No organizational evidence found for customer: "
            f"{customer_name}"
        )

    # --------------------------------------------------------
    # STEP 2 — Identify affected service
    # --------------------------------------------------------

    selected_match = select_org_match(
        evidence,
        incident_classification
    )

    # --------------------------------------------------------
    # STEP 3 — Get PostgreSQL historical evidence
    # --------------------------------------------------------

    history = get_historical_incidents(
        selected_match["service_id"],
        exclude_incident_id=incident_id
    )

    # --------------------------------------------------------
    # STEP 4 — Build reasoning prompt
    # --------------------------------------------------------

    prompt = f"""
{REASONING_PROMPT}

Customer:
{customer_name}

Agent 1 Incident Classification:
{json.dumps(incident_classification, indent=2)}

Selected Neo4j Organizational Evidence:
{json.dumps(selected_match, indent=2)}

PostgreSQL Historical Incidents:
{json.dumps(history, indent=2)}

Now reason over all the evidence and return ONLY the JSON object.
"""

    # --------------------------------------------------------
    # STEP 5 — Ask Gemini and parse JSON
    # --------------------------------------------------------

    max_attempts = 3

    for attempt in range(1, max_attempts + 1):

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0
            }
        )

        raw_text = response.text.strip()

        try:
            result = json.loads(raw_text)

            # ------------------------------------------------
            # Deterministic validation
            # ------------------------------------------------
            # These fields come from Neo4j and must not be
            # changed by Gemini.

            result["affected_service"] = selected_match["service"]
            result["responsible_department"] = selected_match["department"]
            result["responsible_employee"] = selected_match["employee"]
            result["employee_available"] = bool(
                selected_match["available"]
            )

            # Historical incidents must come from PostgreSQL.
            result["historical_similar_incidents"] = [
                item["incident_id"]
                for item in history
            ]

            # Ensure recurring issue is based on actual history.
            result["is_recurring_issue"] = len(history) > 0

            # Ensure confidence is valid.
            try:
                confidence = float(result.get("confidence", 0))
            except (TypeError, ValueError):
                confidence = 0.0

            result["confidence"] = max(
                0.0,
                min(1.0, confidence)
            )

            return result

        except json.JSONDecodeError:

            print(
                f"JSON parsing failed on attempt "
                f"{attempt}/{max_attempts}"
            )

            if attempt < max_attempts:
                time.sleep(1)
                continue

            print("\nFAILED TO PARSE MODEL OUTPUT:")
            print(raw_text)

            raise


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    # Agent 1's actual output
    agent1_output = {
        "incident_type": "Incident",
        "category": "Payment Failure",
        "priority": "Critical",
        "severity": "Critical",
        "business_impact": "Complete halt of retail transaction processing",
        "reason": "Total outage of payment processing.",
        "confidence": 0.95
    }

    result = reason_about_incident(
        incident_classification=agent1_output,
        customer_name="ABC Retail"
    )

    print("\nAGENT 2 OUTPUT")
    print("=" * 60)
    print(json.dumps(result, indent=2))