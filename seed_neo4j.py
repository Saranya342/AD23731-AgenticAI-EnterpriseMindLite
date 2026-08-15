"""
Seeds Neo4j Aura from org_data.json.
Creates nodes: Employee, Department, Service, Customer, Incident
Creates relationships:
  Employee -WORKS_IN-> Department
  Department -OWNS-> Service
  Employee -OWNS_SERVICE-> Service   (the primary owner, used by Agent 2)
  Customer -USES-> Service
  Service -HAD_INCIDENT-> Incident

Run: pip install neo4j
     python seed_neo4j.py
"""
import json
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")


def load_data():
    with open("org_data.json") as f:
        return json.load(f)

def seed(tx, data):
    # Departments
    for d in data["departments"]:
        tx.run(
            "MERGE (dept:Department {department_id: $id, name: $name})",
            id=d["department_id"], name=d["department_name"]
        )

    # Employees + WORKS_IN
    for e in data["employees"]:
        tx.run(
            """MERGE (emp:Employee {employee_id: $id, name: $name, availability: $avail})
               WITH emp
               MATCH (dept:Department {department_id: $dept_id})
               MERGE (emp)-[:WORKS_IN]->(dept)""",
            id=e["employee_id"], name=e["name"], avail=e["availability"], dept_id=e["department"]
        )

    # Services + OWNS (department) + OWNS_SERVICE (employee)
    employee_by_service = {
        e["primary_service"]: e["employee_id"]
        for e in data["employees"] if e["primary_service"] and e["is_primary_owner"]
    }
    for s in data["services"]:
        tx.run(
            """MERGE (svc:Service {service_id: $id, name: $name})
               WITH svc
               MATCH (dept:Department {department_id: $dept_id})
               MERGE (dept)-[:OWNS]->(svc)""",
            id=s["service_id"], name=s["service_name"], dept_id=s["department_owner"]
        )
        owner = employee_by_service.get(s["service_id"])
        if owner:
            tx.run(
                """MATCH (emp:Employee {employee_id: $emp_id})
                   MATCH (svc:Service {service_id: $svc_id})
                   MERGE (emp)-[:OWNS_SERVICE]->(svc)""",
                emp_id=owner, svc_id=s["service_id"]
            )

    # Customers + USES
    for c in data["customers"]:
        tx.run("MERGE (cust:Customer {customer_id: $id, name: $name})",
               id=c["customer_id"], name=c["customer_name"])
        for svc_id in c["uses_services"]:
            tx.run(
                """MATCH (cust:Customer {customer_id: $cust_id})
                   MATCH (svc:Service {service_id: $svc_id})
                   MERGE (cust)-[:USES]->(svc)""",
                cust_id=c["customer_id"], svc_id=svc_id
            )

    # Historical Incidents + HAD_INCIDENT
    for i in data["historical_incidents"]:
        tx.run(
            """MERGE (inc:Incident {incident_id: $id, title: $title, date: $date})
               WITH inc
               MATCH (svc:Service {service_id: $svc_id})
               MERGE (svc)-[:HAD_INCIDENT]->(inc)""",
            id=i["incident_id"], title=i["title"], date=i["date"], svc_id=i["service_id"]
        )

def main():
    data = load_data()
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    with driver.session() as session:
        session.execute_write(seed, data)
    driver.close()
    print("Neo4j seed complete.")

if __name__ == "__main__":
    main()
