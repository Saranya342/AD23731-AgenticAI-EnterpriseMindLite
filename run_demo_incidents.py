"""
Creates and processes 4 DIFFERENT demo incidents, across different
customers/services, so the dashboard's "Recurring Issue Rate" and
"Incident Overview" reflect real variety instead of one test case
run 17 times.

Run: python run_demo_incidents.py
"""

import os
import psycopg2
from dotenv import load_dotenv

from pipeline import run_pipeline

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

DEMO_INCIDENTS = [
    # {
    #     "incident_id": "INC-DEMO-01",
    #     "title": "Increased latency and intermittent 502 errors on API Gateway",
    #     "customer_id": "C2",   # TechNova Inc
    #     "service_id": "S8",    # API Gateway -> owned by Naveen (available)
    #     "customer_name": "TechNova Inc",
    #     "subject": "API Gateway returning intermittent errors",
    #     "body": "TechNova Inc is seeing increased latency and intermittent 502 errors when calling our API Gateway over the last hour."
    # },
    # {
    #     "incident_id": "INC-DEMO-02",
    #     "title": "SMS notifications failing to send for shipment updates",
    #     "customer_id": "C4",   # QuickShip Logistics
    #     "service_id": "S6",    # Notification Service -> owned by Vignesh (available)
    #     "customer_name": "QuickShip Logistics",
    #     "subject": "SMS shipment notifications not sending",
    #     "body": "QuickShip Logistics reports that SMS shipment update notifications have not been sending to customers since this morning."
    # },
    # {
    #     "incident_id": "INC-DEMO-03",
    #     "title": "Customers unable to log into Customer Portal",
    #     "customer_id": "C6",   # Sunrise Foods
    #     "service_id": "S5",    # Customer Portal -> owned by Anitha (available)
    #     "customer_name": "Sunrise Foods",
    #     "subject": "Customer Portal login failures",
    #     "body": "Sunrise Foods customers have been unable to log into the Customer Portal since this morning, blocking all account access."
    # },
    {
        "incident_id": "INC-DEMO-04",
        "title": "CI/CD deployment pipeline stuck, blocking releases",
        "customer_id": "C8",   # Nimbus Cloud Co
        "service_id": "S7",    # CI/CD Pipeline -> owned by Arun (available)
        "customer_name": "Nimbus Cloud Co",
        "subject": "Deployment pipeline stuck",
        "body": "Nimbus Cloud Co's deployment pipeline has been stuck for over 45 minutes, blocking all releases to production."
    },
]


def insert_incident_row(incident):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO incidents (incident_id, title, customer_id, service_id, status)
        VALUES (%s, %s, %s, %s, 'open')
        ON CONFLICT (incident_id) DO NOTHING
        """,
        (incident["incident_id"], incident["title"], incident["customer_id"], incident["service_id"])
    )
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    for incident in DEMO_INCIDENTS:
        print("\n" + "#" * 60)
        print(f"# Setting up {incident['incident_id']}")
        print("#" * 60)

        insert_incident_row(incident)

        run_pipeline(
            incident_id=incident["incident_id"],
            subject=incident["subject"],
            body=incident["body"],
            customer_name=incident["customer_name"]
        )
