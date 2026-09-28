import os
import json

from dotenv import load_dotenv
from google import genai
from google.genai import types

from operational_tools import run_diagnostic_tools


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

client = genai.Client(
    api_key=GEMINI_API_KEY
)


EVALUATION_PROMPT = """
You are evaluating diagnostic tool results for an IT incident.

Your job is to decide whether the tool evidence confirms a real operational problem.

Rules:

1. Use only the provided tool results.
2. Do not invent checks that were not performed.
3. If service health is degraded or unavailable, consider the incident confirmed.
4. If recent error logs exist, increase technical risk.
5. Database connectivity being healthy does not cancel other failures.
6. Return only valid JSON.

Required JSON format:

{
  "incident_confirmed": boolean,
  "technical_risk": "low" | "medium" | "high",
  "tool_evidence_supports_jira": boolean,
  "summary": string
}
"""


def evaluate_tool_results(
    service_name: str
) -> dict:

    print()
    print(
        f"[EVALUATOR] Running tools for: "
        f"{service_name}"
    )

    tool_results = run_diagnostic_tools(
        service_name
    )

    print()
    print(
        "[EVALUATOR] Sending tool results "
        "to Gemini..."
    )

    prompt = f"""
{EVALUATION_PROMPT}

Service:
{service_name}

Tool Results:

{json.dumps(tool_results, indent=2)}

Return only JSON.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0
        )
    )

    result = json.loads(
        response.text
    )

    result["tool_results"] = tool_results

    return result


if __name__ == "__main__":

    result = evaluate_tool_results(
        "Payment Gateway"
    )

    print()
    print("=" * 60)
    print("TOOL EVALUATION RESULT")
    print("=" * 60)

    print(
        json.dumps(
            result,
            indent=2
        )
    )