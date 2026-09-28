
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

from agent3_operational_decision import decide_operational_path
a2path=RESULTS/"agent2_predictions.csv"
if not a2path.exists():
    print("Run evaluate_agent2.py first."); raise SystemExit(1)
with a2path.open(encoding="utf-8-sig",newline="") as f: a2rows={r["test_id"]:r for r in csv.DictReader(f)}
cases=load_cases(); rows=[]
print("AGENT 3 RULE-COMPLIANCE EVALUATION - 10 CASES")
for i,t in enumerate(cases,1):
    r2=a2rows.get(t["test_id"],{})
    if r2.get("error"):
        rows.append({**t,"error":"Agent 2 failed; Agent 3 skipped"}); continue
    try: conf=float(r2.get("confidence") or 0)
    except: conf=0
    a1={"incident_type":t["expected_incident_type"],"category":t["expected_category"],
        "priority":t["expected_priority"],"severity":t["expected_severity"],
        "business_impact":t["body"],"reason":"Ground truth","confidence":1.0}
    a2={"affected_service":r2.get("predicted_service"),"responsible_department":r2.get("predicted_department"),
        "responsible_employee":r2.get("predicted_employee"),"employee_available":b(r2.get("employee_available")),
        "historical_similar_incidents":[],"is_recurring_issue":b(r2.get("is_recurring_issue")),
        "confidence":conf,"reason":"Agent 2 evaluation output"}
    exp_jira=t["expected_severity"] in ("High","Critical")
    exp_approval=(norm(r2.get("predicted_employee"))!=norm(t["expected_employee"])) or conf<0.75
    exp_escalation=b(r2.get("is_recurring_issue")) and t["expected_severity"]=="Critical"
    st=time.perf_counter(); err=""; p={}
    try: p=decide_operational_path(a1,a2,subject=t["subject"],body=t["body"]) or {}
    except Exception as e: err=f"{type(e).__name__}: {e}"
    checks={
      "jira_rule_correct":p.get("create_jira")==exp_jira,
      "priority_rule_correct":norm(p.get("jira_priority"))==norm(t["expected_priority"]),
      "approval_rule_correct":p.get("approval_required")==exp_approval,
      "escalation_rule_correct":p.get("escalation_required")==exp_escalation,
      "notify_present":bool(str(p.get("notify","")).strip()),
      "response_present":bool(str(p.get("recommended_response","")).strip()),
      "reason_present":bool(str(p.get("reason","")).strip())}
    rows.append({**t,"expected_create_jira":exp_jira,"expected_approval":exp_approval,
      "expected_escalation":exp_escalation,"predicted_create_jira":p.get("create_jira",""),
      "predicted_jira_priority":p.get("jira_priority",""),"predicted_approval":p.get("approval_required",""),
      "predicted_escalation":p.get("escalation_required",""),"notify":p.get("notify",""),
      **checks,"requirements_satisfied":sum(checks.values()),"requirements_total":len(checks),
      "response_time_seconds":round(time.perf_counter()-st,3),"error":err})
with (RESULTS/"agent3_predictions.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
v=[r for r in rows if not r.get("error")]
fields=["jira_rule_correct","priority_rule_correct","approval_rule_correct","escalation_rule_correct","notify_present","response_present","reason_present"]
rate=lambda fld: sum(b(r[fld]) for r in v)/len(v)
req=sum(int(r["requirements_satisfied"]) for r in v); total=sum(int(r["requirements_total"]) for r in v)
m={"tests":len(cases),"successful":len(v),"jira_decision_accuracy":rate("jira_rule_correct"),
   "jira_priority_accuracy":rate("priority_rule_correct"),"approval_routing_accuracy":rate("approval_rule_correct"),
   "escalation_accuracy":rate("escalation_rule_correct"),"requirement_satisfaction_rate":req/total,
   "complete_task_success_rate":sum(int(r["requirements_satisfied"])==int(r["requirements_total"]) for r in v)/len(v),
   "average_response_time_seconds":statistics.mean(float(r["response_time_seconds"]) for r in v)}
(RESULTS/"agent3_metrics.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
print(json.dumps(m,indent=2))
