
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

from agent1_incident_intelligence import classify_incident
try:
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report, confusion_matrix
except ImportError:
    print("Run: pip install scikit-learn"); raise SystemExit(1)
cases=load_cases(); rows=[]
labels=["Low","Medium","High","Critical"]
print("AGENT 1 EVALUATION - 10 CASES")
for i,t in enumerate(cases,1):
    print(f"[{i}/10] {t['test_id']} {t['subject']}")
    st=time.perf_counter(); err=""; p={}
    try: p=classify_incident(t["subject"],t["body"],t["customer_name"]) or {}
    except Exception as e: err=f"{type(e).__name__}: {e}"
    rows.append({**t,
      "predicted_incident_type":p.get("incident_type",""),"predicted_category":p.get("category",""),
      "predicted_priority":p.get("priority",""),"predicted_severity":p.get("severity",""),
      "confidence":p.get("confidence",""),"response_time_seconds":round(time.perf_counter()-st,3),"error":err})
out=RESULTS/"agent1_predictions.csv"
with out.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
valid=[r for r in rows if not r["error"]]
def met(field):
    y=[r["expected_"+field] for r in valid]; p=[r["predicted_"+field] for r in valid]
    a=accuracy_score(y,p); pr,re,f1,_=precision_recall_fscore_support(y,p,labels=labels,average="macro",zero_division=0)
    return y,p,a,pr,re,f1
py,pp,pa,ppr,pre,pf=met("priority"); sy,sp,sa,spr,sre,sf=met("severity")
m={"tests":len(cases),"successful":len(valid),"priority_accuracy":pa,"priority_macro_precision":ppr,
"priority_macro_recall":pre,"priority_macro_f1":pf,"severity_accuracy":sa,"severity_macro_f1":sf,
"incident_type_exact_accuracy":sum(norm(r["expected_incident_type"])==norm(r["predicted_incident_type"]) for r in valid)/len(valid),
"category_exact_accuracy":sum(norm(r["expected_category"])==norm(r["predicted_category"]) for r in valid)/len(valid),
"average_response_time_seconds":statistics.mean(float(r["response_time_seconds"]) for r in valid)}
(RESULTS/"agent1_metrics.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
print(json.dumps(m,indent=2))
