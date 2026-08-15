"""
Seeds Postgres (Supabase) from org_data.json.
Insert order is fixed by foreign key dependencies:
departments -> employees -> services -> customers -> incidents -> jira_tickets -> decisions

Run: pip install psycopg2-binary --break-system-packages
     python seed_postgres.py
"""

import json
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# ---- CONFIG: replace with your Supabase connection string ----
CONN_STRING = os.getenv("DATABASE_URL")

def load_data():
    with open("org_data.json") as f:
        return json.load(f)

def seed():
    data = load_data()
    conn = psycopg2.connect(CONN_STRING)
    cur = conn.cursor()

    # 1. departments — no dependencies
    for d in data["departments"]:
        cur.execute(
            "INSERT INTO departments (department_id, department_name) VALUES (%s, %s)",
            (d["department_id"], d["department_name"])
        )

    # 2. employees — depends on departments
    for e in data["employees"]:
        cur.execute(
            """INSERT INTO employees (employee_id, name, department_id, availability)
               VALUES (%s, %s, %s, %s)""",
            (e["employee_id"], e["name"], e["department"], e["availability"])
        )

    # 3. services — depends on departments AND employees (owner_id)
    # owner_id = the employee whose primary_service matches this service
    employee_by_service = {
        e["primary_service"]: e["employee_id"]
        for e in data["employees"] if e["primary_service"] and e["is_primary_owner"]
    }
    for s in data["services"]:
        owner = employee_by_service.get(s["service_id"])
        cur.execute(
            """INSERT INTO services (service_id, service_name, department_id, owner_id)
               VALUES (%s, %s, %s, %s)""",
            (s["service_id"], s["service_name"], s["department_owner"], owner)
        )

    # 4. customers — depends on employees (account_owner). No owner assigned yet, so NULL for now.
    for c in data["customers"]:
        cur.execute(
            "INSERT INTO customers (customer_id, customer_name, account_owner) VALUES (%s, %s, %s)",
            (c["customer_id"], c["customer_name"], None)
        )

    # 5. incidents — depends on customers AND services
    # NOTE: our historical_incidents don't have customer_id yet — you'll assign that
    # when you build real incident records in Phase 7+. For now, historical incidents
    # are seeded with customer_id = NULL since they're background data, not live cases.
    for i in data["historical_incidents"]:
        cur.execute(
            """INSERT INTO incidents (incident_id, title, service_id, created_at)
               VALUES (%s, %s, %s, %s)""",
            (i["incident_id"], i["title"], i["service_id"], i["date"])
        )

    conn.commit()
    cur.close()
    conn.close()
    print("Seed complete.")

if __name__ == "__main__":
    seed()
