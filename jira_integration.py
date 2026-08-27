"""
PHASE 10 — Jira Integration
Demonstrates: create ticket, assign, set priority, add comment, transition status.
Reads credentials from .env - variable names must match your .env file exactly.

Run: python jira_integration.py
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")
PROJECT_KEY = os.getenv("PROJECT_KEY")

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {"Accept": "application/json", "Content-Type": "application/json"}

# Agent 3 outputs priority language like "Critical", "High", "Medium", "Low" —
# but this Jira site's actual priority scheme (confirmed via
# check_jira_priorities.py) only has: Highest, High, Medium, Low, Lowest.
# This maps one to the other so ticket creation never sends an invalid name.
PRIORITY_MAP = {
    "Critical": "Highest",
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
}


def create_ticket(summary: str, description: str, priority: str = "High") -> str:
    jira_priority_name = PRIORITY_MAP.get(priority, "Medium")

    url = f"{JIRA_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": PROJECT_KEY},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": description}]}
                ]
            },
            "issuetype": {"name": "Task"},
            "priority": {"name": jira_priority_name}
        }
    }
    response = requests.post(url, headers=headers, auth=auth, json=payload)
    if response.status_code != 201:
        print("CREATE FAILED:", response.status_code, response.text)
        response.raise_for_status()
    issue_key = response.json()["key"]
    print(f"Created ticket: {issue_key}")
    return issue_key


def add_comment(issue_key: str, comment_text: str):
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": comment_text}]}
            ]
        }
    }
    response = requests.post(url, headers=headers, auth=auth, json=payload)
    if response.status_code not in (200, 201):
        print("COMMENT FAILED:", response.status_code, response.text)
        response.raise_for_status()
    print(f"Comment added to {issue_key}")


def get_transitions(issue_key: str):
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions"
    response = requests.get(url, headers=headers, auth=auth)
    response.raise_for_status()
    return response.json()["transitions"]


def transition_status(issue_key: str, target_status_name: str):
    transitions = get_transitions(issue_key)
    match = next((t for t in transitions if t["name"].lower() == target_status_name.lower()), None)
    if not match:
        available = [t["name"] for t in transitions]
        print(f"No transition named '{target_status_name}'. Available: {available}")
        return
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions"
    response = requests.post(url, headers=headers, auth=auth, json={"transition": {"id": match["id"]}})
    if response.status_code != 204:
        print("TRANSITION FAILED:", response.status_code, response.text)
        response.raise_for_status()
    print(f"{issue_key} moved to '{target_status_name}'")


if __name__ == "__main__":
    key = create_ticket(
        summary="[Critical] Payment Gateway outage - ABC Retail",
        description="Recurring Payment Gateway failure. Assigned to Rahul, Backend Engineering. "
                     "Historical incidents: INC-121, INC-103, INC-102, INC-101.",
        priority="Critical"
    )
    add_comment(key, "Auto-created by Operational Decision Agent. Escalation required: recurring issue.")
    transition_status(key, "In Progress")
