"""
AGENT 3 — Operational Decision Agent

Input:
    Agent 1 classification
    Agent 2 organizational reasoning
    RAG knowledge (SOPs / past incidents)

Output:
    create_jira
    jira_priority
    approval_required
    escalation_required
    notify
    recommended_response
    reason

This agent DECIDES.
It does not create Jira tickets or send notifications.

Run:
    python agent3_operational_decision.py
"""

import os
import json
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from rag_service import retrieve_relevant_knowledge


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

missing = []

if not GEMINI_API_KEY:
    missing.append("GEMINI_API_KEY")

if not GEMINI_MODEL:
    missing.append("GEMINI_MODEL")

if missing:
    raise ValueError(
        f"Missing environment variables: {', '.join(missing)}"
    )


client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# DECISION PROMPT
# ============================================================

DECISION_PROMPT = """
You are an Operational Decision Agent for an IT operations system.

You receive:

1. Incident classification from Agent 1.
2. Organizational reasoning from Agent 2.
3. Relevant organizational knowledge retrieved using RAG.

The RAG knowledge may contain:
- Standard Operating Procedures (SOPs)
- troubleshooting guidance
- similar historical incidents
- previous resolutions

Use the retrieved knowledge as operational guidance.

Do NOT invent information that is not present in:
- Agent 1
- Agent 2
- Retrieved RAG knowledge

The deterministic operational rules below take priority over
recommendations found in RAG documents.

Apply these rules strictly:

RULE 1:
If severity is "Critical" or "High",
then create_jira must be true.

Otherwise:
create_jira must be false.

RULE 2:
If the responsible employee is NOT the registered primary owner
(i.e. a fallback assignment)
OR Agent 2 confidence is below 0.75,
then approval_required must be true.

Otherwise:
approval_required must be false.

RULE 3:
If is_recurring_issue is true AND severity is "Critical",
then escalation_required must be true.

Otherwise:
escalation_required must be false.

RULE 4:
Always specify who should be notified.

The notify field must contain either:
- a department name
- "Customer Support"
- another clearly relevant operational team

RULE 5:
jira_priority should reflect the incident priority.

RULE 6:
recommended_response should be a short operational recommendation
for what the operations team should do next.

When relevant, use the retrieved SOP or historical knowledge
to improve the recommended response.

RULE 7:
reason must explain the decision using evidence from Agent 1,
Agent 2, and relevant retrieved knowledge.

Do not invent facts.

RULE 8:
Retrieved SOP instructions are recommendations only.

Do not claim that a service health check, database check,
log inspection, restart, or any other technical operation
has actually been performed unless a tool result explicitly
states that it was performed.

JSON REQUIREMENTS:

Return ONLY one valid JSON object.

Do not write any text before the JSON.
Do not write any text after the JSON.
Do not use Markdown.
Do not use code fences.
Do not use single quotes.
Do not add trailing commas.
Do not add comments.
Do not put unescaped quotation marks inside string values.

Keep the "reason" field concise,
using no more than 2 sentences.

Keep the "recommended_response" field concise,
using no more than 1 sentence.

Required JSON structure:

{
  "create_jira": boolean,
  "jira_priority": string,
  "approval_required": boolean,
  "escalation_required": boolean,
  "notify": string,
  "recommended_response": string,
  "reason": string
}
"""


# ============================================================
# BUILD RAG SEARCH QUERY
# ============================================================

def build_rag_query(
    agent1_output: dict,
    agent2_output: dict,
    subject: str = "",
    body: str = ""
) -> str:

    query_parts = []

    if subject:
        query_parts.append(
            f"Incident subject: {subject}"
        )

    if body:
        query_parts.append(
            f"Incident description: {body}"
        )

    incident_type = agent1_output.get(
        "incident_type"
    )

    category = agent1_output.get(
        "category"
    )

    severity = agent1_output.get(
        "severity"
    )

    priority = agent1_output.get(
        "priority"
    )

    business_impact = agent1_output.get(
        "business_impact"
    )

    affected_service = agent2_output.get(
        "affected_service"
    )

    department = agent2_output.get(
        "responsible_department"
    )

    recurring = agent2_output.get(
        "is_recurring_issue"
    )

    if incident_type:
        query_parts.append(
            f"Incident type: {incident_type}"
        )

    if category:
        query_parts.append(
            f"Category: {category}"
        )

    if severity:
        query_parts.append(
            f"Severity: {severity}"
        )

    if priority:
        query_parts.append(
            f"Priority: {priority}"
        )

    if business_impact:
        query_parts.append(
            f"Business impact: {business_impact}"
        )

    if affected_service:
        query_parts.append(
            f"Affected service: {affected_service}"
        )

    if department:
        query_parts.append(
            f"Responsible department: {department}"
        )

    if recurring is not None:
        query_parts.append(
            f"Recurring issue: {recurring}"
        )

    return "\n".join(query_parts)


# ============================================================
# FORMAT RAG RESULTS
# ============================================================

def format_rag_context(
    rag_results: list
) -> str:

    if not rag_results:
        return (
            "No relevant organizational knowledge "
            "was retrieved."
        )

    sections = []

    for index, item in enumerate(
        rag_results,
        start=1
    ):

        similarity = item.get(
            "similarity"
        )

        if similarity is not None:
            similarity_text = (
                f"{float(similarity):.4f}"
            )
        else:
            similarity_text = "N/A"

        section = f"""
Retrieved Knowledge #{index}

Document Type:
{item.get("document_type", "Unknown")}

Title:
{item.get("title", "Unknown")}

Service:
{item.get("service", "Unknown")}

Similarity:
{similarity_text}

Content:
{item.get("content", "")}
""".strip()

        sections.append(section)

    return "\n\n".join(sections)


# ============================================================
# AGENT 3 FUNCTION
# ============================================================

def decide_operational_path(
    agent1_output: dict,
    agent2_output: dict,
    subject: str = "",
    body: str = ""
) -> dict:

    # --------------------------------------------------------
    # STEP 1 — Build RAG query
    # --------------------------------------------------------

    rag_query = build_rag_query(
        agent1_output=agent1_output,
        agent2_output=agent2_output,
        subject=subject,
        body=body
    )

    print()
    print("[AGENT 3] Retrieving relevant knowledge...")

    # --------------------------------------------------------
    # STEP 2 — Retrieve SOP / historical knowledge
    # --------------------------------------------------------

    try:

        affected_service = agent2_output.get(
            "affected_service"
        )

        print(
            f"[AGENT 3] Affected service sent to RAG: "
            f"{affected_service}"
        )

        rag_results = retrieve_relevant_knowledge(
            query_text=rag_query,
            limit=2,
            service=affected_service
        )

        print(
            f"[AGENT 3] Retrieved "
            f"{len(rag_results)} knowledge documents."
        )

        for item in rag_results:

            print(
                "[AGENT 3] RAG:",
                item.get("title"),
                "| similarity:",
                round(
                    float(
                        item.get(
                            "similarity",
                            0
                        )
                    ),
                    4
                )
            )

    except Exception as rag_error:

        print(
            "[AGENT 3] RAG retrieval failed:"
        )

        print(rag_error)

        # Agent 3 should still be able to operate
        # even if the RAG service temporarily fails.
        rag_results = []

    # --------------------------------------------------------
    # STEP 3 — Format retrieved knowledge
    # --------------------------------------------------------

    rag_context = format_rag_context(
        rag_results
    )

    # --------------------------------------------------------
    # STEP 4 — Build Gemini prompt
    # --------------------------------------------------------

    prompt = f"""
{DECISION_PROMPT}

Agent 1 — Incident Intelligence:

{json.dumps(agent1_output, indent=2)}

Agent 2 — Organizational Reasoning:

{json.dumps(agent2_output, indent=2)}

Retrieved RAG Knowledge:

{rag_context}

Return exactly one JSON object.
"""

    max_attempts = 3

    # --------------------------------------------------------
    # STEP 5 — Gemini decision
    # --------------------------------------------------------

    for attempt in range(
        1,
        max_attempts + 1
    ):

        try:

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0
                )
            )

        except genai_errors.APIError as api_error:

            print(
                f"\nAgent 3 API call failed "
                f"on attempt "
                f"{attempt}/{max_attempts}"
            )

            print(
                f"Reason: {api_error}"
            )

            if attempt < max_attempts:

                time.sleep(
                    2 * attempt
                )

                continue

            print(
                "\nAGENT 3 GAVE UP AFTER "
                "MAX ATTEMPTS (API ERROR)."
            )

            raise

        # ----------------------------------------------------
        # STEP 6 — Parse Gemini JSON
        # ----------------------------------------------------

        raw_text = response.text.strip()

        try:

            result = json.loads(
                raw_text
            )

            if not isinstance(
                result,
                dict
            ):
                raise ValueError(
                    "Gemini returned JSON, "
                    "but it was not a JSON object."
                )

            required_fields = {
                "create_jira",
                "jira_priority",
                "approval_required",
                "escalation_required",
                "notify",
                "recommended_response",
                "reason"
            }

            missing_fields = (
                required_fields
                - result.keys()
            )

            if missing_fields:

                raise ValueError(
                    f"Missing Agent 3 fields: "
                    f"{', '.join(sorted(missing_fields))}"
                )

            # ------------------------------------------------
            # Include retrieved RAG information in result
            # for debugging / dashboard usage.
            #
            # These extra fields do NOT change the existing
            # Agent 3 decision fields.
            # ------------------------------------------------

            result["rag_documents"] = [
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "document_type": item.get(
                        "document_type"
                    ),
                    "service": item.get(
                        "service"
                    ),
                    "similarity": (
                        float(
                            item["similarity"]
                        )
                        if item.get(
                            "similarity"
                        ) is not None
                        else None
                    )
                }
                for item in rag_results
            ]

            return result

        except (
            json.JSONDecodeError,
            ValueError
        ) as error:

            print(
                f"\nAgent 3 JSON validation failed "
                f"on attempt "
                f"{attempt}/{max_attempts}"
            )

            print(
                f"Reason: {error}"
            )

            if attempt < max_attempts:

                time.sleep(1)

                continue

            print(
                "\nFAILED TO PARSE MODEL OUTPUT:"
            )

            print(raw_text)

            raise


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_subject = (
        "Payment Gateway timeout "
        "affecting checkout"
    )

    test_body = """
ABC Retail is experiencing intermittent issues
with the Payment Gateway.

Several customers are reporting payment timeouts
during checkout.

Some transactions are failing and customers
have to retry their payments.
""".strip()

    agent1_output = {
        "incident_type": "Incident",
        "category": "Payment Failure",
        "priority": "Critical",
        "severity": "Critical",
        "business_impact":
            "Complete halt of retail transaction processing",
        "reason":
            "Total outage of payment processing.",
        "confidence": 0.95
    }

    agent2_output = {
        "affected_service":
            "Payment Gateway",
        "responsible_department":
            "Backend Engineering",
        "responsible_employee":
            "Rahul",
        "employee_available":
            True,
        "historical_similar_incidents": [
            "INC-121",
            "INC-103",
            "INC-102",
            "INC-101"
        ],
        "is_recurring_issue":
            True,
        "confidence":
            0.95,
        "reason":
            "Recurring payment gateway issue, "
            "assigned to available owner Rahul."
    }

    result = decide_operational_path(
        agent1_output=agent1_output,
        agent2_output=agent2_output,
        subject=test_subject,
        body=test_body
    )

    print()
    print("AGENT 3 OUTPUT")
    print("=" * 60)

    print(
        json.dumps(
            result,
            indent=2
        )
    )
