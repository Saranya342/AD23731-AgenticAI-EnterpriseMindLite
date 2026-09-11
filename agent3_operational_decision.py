"""
AGENT 3 — Operational Decision Agent
 
Input:
    Agent 1 classification + Agent 2 organizational reasoning
 
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
 
Your job is to decide the operational path.
 
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
 
RULE 7:
reason must explain the decision using evidence from Agent 1
and Agent 2. Do not invent facts.
 
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
Keep the "reason" field concise, using no more than 2 sentences.
Keep the "recommended_response" field concise, using no more than 1 sentence.
 
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
# AGENT 3 FUNCTION
# ============================================================
 
def decide_operational_path(
    agent1_output: dict,
    agent2_output: dict
) -> dict:
 
    prompt = f"""
{DECISION_PROMPT}
 
Agent 1 — Incident Intelligence:
 
{json.dumps(agent1_output, indent=2)}
 
Agent 2 — Organizational Reasoning:
 
{json.dumps(agent2_output, indent=2)}
 
Return exactly one JSON object.
"""
 
    max_attempts = 3
 
    for attempt in range(1, max_attempts + 1):
 
        # --------------------------------------------------------
        # STEP 1 — Call Gemini. This can fail with a transient
        # server-side error (503 UNAVAILABLE, 429 RESOURCE_EXHAUSTED,
        # network errors) - these are NOT JSON/validation problems,
        # so they need their own retry handling.
        # --------------------------------------------------------
 
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
                f"on attempt {attempt}/{max_attempts}"
            )
            print(f"Reason: {api_error}")
 
            if attempt < max_attempts:
                # Exponential backoff: 2s, then 4s
                time.sleep(2 * attempt)
                continue
 
            print("\nAGENT 3 GAVE UP AFTER MAX ATTEMPTS (API ERROR).")
            raise
 
        # --------------------------------------------------------
        # STEP 2 — Parse and validate the JSON response.
        # This is the original retry logic, unchanged.
        # --------------------------------------------------------
 
        raw_text = response.text.strip()
 
        try:
            result = json.loads(raw_text)
 
            if not isinstance(result, dict):
                raise ValueError(
                    "Gemini returned JSON, but it was not a JSON object."
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
 
            missing_fields = required_fields - result.keys()
 
            if missing_fields:
                raise ValueError(
                    f"Missing Agent 3 fields: "
                    f"{', '.join(sorted(missing_fields))}"
                )
 
            return result
 
        except (json.JSONDecodeError, ValueError) as error:
 
            print(
                f"\nAgent 3 JSON validation failed "
                f"on attempt {attempt}/{max_attempts}"
            )
            print(f"Reason: {error}")
 
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
 
    agent1_output = {
        "incident_type": "Incident",
        "category": "Payment Failure",
        "priority": "Critical",
        "severity": "Critical",
        "business_impact": "Complete halt of retail transaction processing",
        "reason": "Total outage of payment processing.",
        "confidence": 0.95
    }
 
    agent2_output = {
        "affected_service": "Payment Gateway",
        "responsible_department": "Backend Engineering",
        "responsible_employee": "Rahul",
        "employee_available": True,
        "historical_similar_incidents": [
            "INC-121",
            "INC-103",
            "INC-102",
            "INC-101"
        ],
        "is_recurring_issue": True,
        "confidence": 0.95,
        "reason": "Recurring payment gateway issue, assigned to available owner Rahul."
    }
 
    result = decide_operational_path(
        agent1_output=agent1_output,
        agent2_output=agent2_output
    )
 
    print("\nAGENT 3 OUTPUT")
    print("=" * 60)
    print(json.dumps(result, indent=2))
 