import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""
SELECT incident_id, agent_name, confidence
FROM decisions
WHERE incident_id = 'INC-TEST-01'
""")

rows = cur.fetchall()

print("\nDATABASE AUDIT TRAIL")
print("=" * 70)

for row in rows:
    print(row)

cur.close()
conn.close()