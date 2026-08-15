"""
AGENT 1 — Incident Intelligence Agent

Input:
    raw incident report (subject + body + customer name)

Output:
    structured JSON:
    incident_type
    category
    priority
    severity
    business_impact
    reason
    confidence

Run:
    python agent1_incident_intelligence.py
"""

import os
import json

from dotenv import load_dotenv
from google import genai


# --------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# --------------------------------------------------

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in .env")


# --------------------------------------------------
# GEMINI CLIENT
# --------------------------------------------------

client = genai.Client(api_key=API_KEY)

MODEL_NAME = "gemini-3.5-flash"


# --------------------------------------------------
# SYSTEM PROMPT
# --------------------------------------------------

SYSTEM_PROMPT = """
You are an Incident Intelligence Agent for an IT operations system.

You will be given an incident report.

Your task is to classify the incident and return ONLY valid JSON.
Do not return markdown.
Do not use ```json fences.
Do not include explanation outside the JSON.

Required JSON shape:

{
  "incident_type": "string",
  "category": "string",
  "priority": "string",
  "severity": "string",
  "business_impact": "string",
  "reason": "string",
  "confidence": 0.0
}

Rules:

incident_type:
Examples:
- Incident
- Customer Request
- Security Concern

category:
Examples:
- Payment Failure
- Auth Issue
- Billing Query

priority:
Must be exactly one of:
- Low
- Medium
- High
- Critical

severity:
Must be exactly one of:
- Low
- Medium
- High
- Critical

business_impact:
Return a short phrase describing what is affected.

reason:
Provide a 1-2 sentence justification for the classification.

confidence:
Return a number between 0.0 and 1.0.
"""


# --------------------------------------------------
# INCIDENT CLASSIFICATION
# --------------------------------------------------

def classify_incident(
    subject: str,
    body: str,
    customer_name: str
) -> dict:

    prompt = f"""
{SYSTEM_PROMPT}

Customer: {customer_name}

Subject: {subject}

Body: {body}

Return the JSON now.
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    raw_text = response.text.strip()

    # --------------------------------------------------
    # DEFENSIVE JSON CLEANUP
    # --------------------------------------------------

    if raw_text.startswith("```"):
        raw_text = raw_text.replace("```json", "")
        raw_text = raw_text.replace("```", "")
        raw_text = raw_text.strip()

    # --------------------------------------------------
    # PARSE JSON
    # --------------------------------------------------

    try:
        result = json.loads(raw_text)

    except json.JSONDecodeError:
        print("FAILED TO PARSE MODEL OUTPUT:")
        print(raw_text)
        raise

    return result


# --------------------------------------------------
# TEST
# --------------------------------------------------

if __name__ == "__main__":

    result = classify_incident(
        subject="Cannot process payments",
        body=(
            "ABC Retail has been unable to process payments "
            "for the last 30 minutes."
        ),
        customer_name="ABC Retail"
    )

    print(json.dumps(result, indent=2))