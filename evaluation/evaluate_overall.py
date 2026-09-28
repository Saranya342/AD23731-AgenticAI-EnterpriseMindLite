
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

files=["agent1_metrics.json","agent2_metrics.json","agent3_metrics.json"]
missing=[x for x in files if not (RESULTS/x).exists()]
if missing:
    print("Missing:",", ".join(missing)); print("Run Agent 1, Agent 2 and Agent 3 evaluators first."); raise SystemExit(1)
a1=json.loads((RESULTS/files[0]).read_text()); a2=json.loads((RESULTS/files[1]).read_text()); a3=json.loads((RESULTS/files[2]).read_text())
# Composite is transparently defined as the mean of three representative subsystem scores.
component_scores=[a1["priority_macro_f1"],a2["service_accuracy"],a3["requirement_satisfaction_rate"]]
summary={"agent1_priority_macro_f1":a1["priority_macro_f1"],
"agent1_severity_macro_f1":a1["severity_macro_f1"],
"agent2_service_accuracy":a2["service_accuracy"],"agent2_department_accuracy":a2["department_accuracy"],
"agent2_employee_accuracy":a2["employee_accuracy"],"agent3_requirement_satisfaction_rate":a3["requirement_satisfaction_rate"],
"agent3_complete_task_success_rate":a3["complete_task_success_rate"],
"agent3_jira_decision_accuracy":a3["jira_decision_accuracy"],"agent3_approval_routing_accuracy":a3["approval_routing_accuracy"],
"composite_system_score":sum(component_scores)/len(component_scores),
"composite_definition":"Mean of Agent 1 priority Macro-F1, Agent 2 service accuracy, and Agent 3 requirement satisfaction rate."}
(RESULTS/"overall_metrics.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print("OVERALL EVALUATION SUMMARY"); print(json.dumps(summary,indent=2))
