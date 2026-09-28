
from pathlib import Path
import sys, csv, json, time, statistics
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
HERE=Path(__file__).resolve().parent
RESULTS=HERE/"results"; RESULTS.mkdir(exist_ok=True)
def load_cases():
    with (HERE/"evaluation_test_cases.csv").open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def norm(x): return str(x or "").strip().lower()
def b(v): return str(v).strip().lower() in ("true","1","yes")

from agent2_organizational_reasoning import reason_about_incident
cases=load_cases(); rows=[]
print("AGENT 2 EVALUATION - 10 CASES")
for i,t in enumerate(cases,1):
    print(f"[{i}/10] {t['test_id']} expected service: {t['expected_service']}")
    a1={"incident_type":t["expected_incident_type"],"category":t["expected_category"],
        "priority":t["expected_priority"],"severity":t["expected_severity"],
        "business_impact":t["body"],"reason":"Ground-truth input for isolated Agent 2 evaluation","confidence":1.0}
    st=time.perf_counter(); err=""; p={}
    try: p=reason_about_incident(a1,t["customer_name"],subject=t["subject"],body=t["body"]) or {}
    except Exception as e: err=f"{type(e).__name__}: {e}"
    rows.append({**t,"predicted_service":p.get("affected_service",""),
      "predicted_department":p.get("responsible_department",""),"predicted_employee":p.get("responsible_employee",""),
      "employee_available":p.get("employee_available",""),"is_recurring_issue":p.get("is_recurring_issue",""),
      "confidence":p.get("confidence",""),"response_time_seconds":round(time.perf_counter()-st,3),"error":err})
with (RESULTS/"agent2_predictions.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
v=[r for r in rows if not r["error"]]
acc=lambda e,p: sum(norm(r[e])==norm(r[p]) for r in v)/len(v)
m={"tests":len(cases),"successful":len(v),"service_accuracy":acc("expected_service","predicted_service"),
   "department_accuracy":acc("expected_department","predicted_department"),
   "employee_accuracy":acc("expected_employee","predicted_employee"),
   "average_response_time_seconds":statistics.mean(float(r["response_time_seconds"]) for r in v)}
(RESULTS/"agent2_metrics.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
print(json.dumps(m,indent=2))
