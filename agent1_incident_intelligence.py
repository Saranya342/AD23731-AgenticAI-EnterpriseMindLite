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
import time
 
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
 
 
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
 
MODEL_NAME = os.getenv("GEMINI_MODEL")
 
 
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
 
    max_attempts = 3
 
    for attempt in range(1, max_attempts + 1):
 
        # ----------------------------------------------------
        # STEP 1 — Call Gemini. Retry on transient server
        # errors (503 UNAVAILABLE, 429 RESOURCE_EXHAUSTED, etc.)
        # ----------------------------------------------------
 
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
 
        except genai_errors.APIError as api_error:
 
            print(
                f"\nAgent 1 API call failed "
                f"on attempt {attempt}/{max_attempts}"
            )
            print(f"Reason: {api_error}")
 
            if attempt < max_attempts:
                time.sleep(2 * attempt)  # 2s, then 4s
                continue
 
            print("\nAGENT 1 GAVE UP AFTER MAX ATTEMPTS (API ERROR).")
            raise
 
        raw_text = response.text.strip()
 
        # ----------------------------------------------------
        # STEP 2 — Defensive JSON cleanup
        # ----------------------------------------------------
 
        if raw_text.startswith("```"):
            raw_text = raw_text.replace("```json", "")
            raw_text = raw_text.replace("```", "")
            raw_text = raw_text.strip()
 
        # ----------------------------------------------------
        # STEP 3 — Parse JSON, retry on failure too
        # ----------------------------------------------------
 
        try:
            result = json.loads(raw_text)
            return result
 
        except json.JSONDecodeError:
 
            print(
                f"\nAgent 1 JSON parsing failed "
                f"on attempt {attempt}/{max_attempts}"
            )
 
            if attempt < max_attempts:
                time.sleep(1)
                continue
 
            print("FAILED TO PARSE MODEL OUTPUT:")
            print(raw_text)
            raise
 
 
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
 