"""
Diagnostic: lists every project this API token can see, with exact keys and IDs.
Reads credentials from .env - variable names must match your .env file exactly.
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")

if not JIRA_URL or not EMAIL or not API_TOKEN:
    raise ValueError(f"Missing from .env — JIRA_URL={bool(JIRA_URL)}, EMAIL={bool(EMAIL)}, JIRA_API_TOKEN={bool(API_TOKEN)}")

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {"Accept": "application/json"}

# Identity check first
url = f"{JIRA_URL}/rest/api/3/myself"
response = requests.get(url, headers=headers, auth=auth)
print("=== Identity check (/myself) ===")
print("Status:", response.status_code)
print("Body:", response.text)
print()

# Project list
url = f"{JIRA_URL}/rest/api/3/project/search"
response = requests.get(url, headers=headers, auth=auth)
print("=== Project search ===")
print("Status:", response.status_code)
if response.status_code == 200:
    projects = response.json()["values"]
    if not projects:
        print("No projects visible to this token/account at all.")
    for p in projects:
        print(f"key={p['key']}  id={p['id']}  name={p['name']}  type={p.get('projectTypeKey')}")
else:
    print("Response body:", response.text)
