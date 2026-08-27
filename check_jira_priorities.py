"""
One-off diagnostic: lists the real priority names available on your Jira site.
Not part of the main pipeline - just run once to check, then this can be deleted.

Run: python check_jira_priorities.py
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {"Accept": "application/json"}

response = requests.get(f"{JIRA_URL}/rest/api/3/priority", headers=headers, auth=auth)
response.raise_for_status()

priorities = response.json()

print("Available priority names on your Jira site:")
for p in priorities:
    print(f"  - {p['name']}")
