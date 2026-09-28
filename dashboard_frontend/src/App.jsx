import {useEffect,useState} from "react";
import IncidentOverview from "./components/IncidentOverview";
import IncidentDetail from "./components/IncidentDetail";
import DecisionTrail from "./components/DecisionTrail";
import CustomerService from "./components/CustomerService";
import Insights from "./components/Insights";
import {fetchIncidents,fetchInsights,fetchPendingApprovals,approveIncident,rejectIncident} from "./api";
import "./App.css";

const NAV=[
  ["dashboard","⌂","Dashboard"],
  ["incidents","▤","Incidents"],
  ["approvals","✓","Approval Queue"],
  ["decisions","↳","Decision Trail"],
  ["customer-service","☏","Customer Service"],
  ["insights","▥","Analytics"]
];
const arr=(v,k)=>Array.isArray(v)?v:Array.isArray(v?.[k])?v[k]:[];

function Dashboard({incidents,insights,approvals,openIncident,navigate}){
 const total=insights?.total_incidents??incidents.length, executed=insights?.executed_incidents??0, pending=insights?.pending_approvals??approvals.length, failed=insights?.failed_incidents??0;
 const services={}; incidents.forEach(i=>{let s=i.service_name||"Unassigned";services[s]=(services[s]||0)+1}); const serviceRows=Object.entries(services).sort((a,b)=>b[1]-a[1]).slice(0,5);
 return <div>
  <div className="welcome"><div><span className="eyebrow">AI-POWERED INCIDENT OPERATIONS</span><h1>Smarter Decisions. Faster Resolutions.</h1><p>Understand, reason, retrieve and act — with human oversight when it matters.</p></div><span className="healthy">● All systems operational</span></div>
  <div className="metrics">{[["▤",total,"Total Incidents","blue"],["✓",executed,"Executed","green"],["◷",pending,"Pending Approval","amber"],["!",failed,"Failed","red"]].map(x=><div className={"metric "+x[3]} key={x[2]}><b className="metricIcon">{x[0]}</b><div><strong>{x[1]}</strong><span>{x[2]}</span><small>{x[2]=="Pending Approval"?"Requires your action":"Operational workflow"}</small></div></div>)}</div>
  <div className="grid topGrid">
   <section className="panel"><div className="panelHead"><div><span className="eyebrow">OPERATIONS</span><h2>Recent Incidents</h2></div><button onClick={()=>navigate("incidents")}>View all →</button></div><div className="tableWrap"><table><thead><tr><th>ID</th><th>Subject</th><th>Service</th><th>Priority</th><th>Status</th></tr></thead><tbody>{incidents.slice(0,6).map(i=><tr key={i.incident_id} onClick={()=>openIncident(i.incident_id)}><td className="id">{i.incident_id}</td><td>{i.title}</td><td>{i.service_name||"—"}</td><td><span className={"pill p-"+String(i.priority||"").toLowerCase()}>{i.priority||"—"}</span></td><td><span className="status">{i.status||"—"}</span></td></tr>)}</tbody></table></div></section>
   <section className="panel"><div className="panelHead"><div><span className="eyebrow">DISTRIBUTION</span><h2>Incidents by Service</h2></div></div><div className="serviceViz"><div className="donut"><div><b>{total}</b><span>Incidents</span></div></div><div className="legend">{serviceRows.map(([s,n],i)=><div key={s}><i className={"dot d"+i}/><span>{s}</span><b>{n}</b></div>)}</div></div></section>
  </div>
  <div className="grid bottomGrid">
   <section className="panel"><div className="panelHead"><div><span className="eyebrow">HUMAN-IN-THE-LOOP</span><h2>Approval Queue <em>{pending}</em></h2></div><button onClick={()=>navigate("approvals")}>View all →</button></div>{approvals.length?approvals.slice(0,3).map(a=><div className="miniApproval" key={a.approval_id||a.incident_id}><div><b>{a.incident_id}</b><span>Operational decision requires review</span></div><button onClick={()=>navigate("approvals")}>Review</button></div>):<p className="empty">✓ No incidents waiting for approval</p>}</section>
   <section className="panel"><div className="panelHead"><div><span className="eyebrow">LIVE REASONING</span><h2>AI Agent Flow</h2></div><span className="live">● Live</span></div><div className="flow">{[["1","Agent 1","Incident intelligence & classification"],["2","Agent 2 + Neo4j","Service ownership & organizational reasoning"],["R","RAG","Service-specific SOP retrieval"],["3","Agent 3 + Tools","Decision, diagnostics & Gemini evaluation"],["J","Execution","Human approval or automatic Jira"]].map(x=><div key={x[0]}><b>{x[0]}</b><p><strong>{x[1]}</strong><span>{x[2]}</span></p></div>)}</div></section>
   <section className="panel"><div className="panelHead"><div><span className="eyebrow">EVALUATION</span><h2>Operational Metrics</h2></div><button onClick={()=>navigate("insights")}>Details →</button></div><div className="progress">{[["Execution success",insights?.evaluation_metrics?.execution_success_rate??0],["Approval acceptance",insights?.evaluation_metrics?.approval_acceptance_rate??0],["Agent confidence",insights?.evaluation_metrics?.average_agent_confidence??0]].map(([l,v])=><div key={l}><p><span>{l}</span><b>{v}%</b></p><div><i style={{width:`${Math.min(100,Number(v)||0)}%`}}/></div></div>)}</div></section>
  </div>
  <div className="banner"><b>✦</b><div><strong>Powered by AI Agents, RAG, Organizational Knowledge and Tool Evidence</strong><span>EnterpriseMind-Lite combines autonomous reasoning with auditable human oversight.</span></div></div>
 </div>
}

export default function App(){
 const [active,setActive]=useState("dashboard"),[selected,setSelected]=useState(null),[incidents,setIncidents]=useState([]),[insights,setInsights]=useState(null),[approvals,setApprovals]=useState([]),[query,setQuery]=useState(""),[processing,setProcessing]=useState(null);
 const load=async()=>{const r=await Promise.allSettled([fetchIncidents(),fetchInsights(),fetchPendingApprovals()]);if(r[0].status==="fulfilled")setIncidents(arr(r[0].value,"incidents"));if(r[1].status==="fulfilled")setInsights(r[1].value);if(r[2].status==="fulfilled")setApprovals(arr(r[2].value,"approvals"))}; useEffect(()=>{load()},[]);
 const nav=x=>{setActive(x);setSelected(null);if(x==="dashboard"||x==="approvals")load()}; const open=id=>{setSelected(id);setActive("incidents")};
 const act=async(id,type)=>{if(!confirm(type==="approve"?`Approve ${id} and allow Jira execution?`:`Reject ${id}?`))return;setProcessing(id);try{type==="approve"?await approveIncident(id):await rejectIncident(id);await load()}finally{setProcessing(null)}};
 const filtered=incidents.filter(i=>!query||[i.incident_id,i.title,i.customer_name,i.service_name].some(v=>String(v||"").toLowerCase().includes(query.toLowerCase())));
 return <div className="app"><aside><div className="brand"><b>〽</b><div><strong>EnterpriseMind-Lite</strong><span>AI Agents for Smarter IT Operations</span></div></div><nav>{NAV.map(n=><button className={active===n[0]?"active":""} onClick={()=>nav(n[0])} key={n[0]}><i>{n[1]}</i>{n[2]}{n[0]==="approvals"&&approvals.length>0?<em>{approvals.length}</em>:null}</button>)}</nav><div className="sideCard"><strong>From Incidents<br/>to Intelligent Actions</strong><p>AI + RAG + Neo4j + Tool Evidence + Human Oversight</p><b>⌁⌁⌁</b></div></aside><div className="work"><header><label>⌕ <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search incidents, services, customers or keywords..."/></label><div className="profile"><b>EM</b><span>EnterpriseMind<small>IT Operations</small></span></div></header><main>
 {active==="dashboard"&&<Dashboard incidents={filtered} insights={insights} approvals={approvals} openIncident={open} navigate={nav}/>}
 {active==="incidents"&&!selected&&<IncidentOverview onSelectIncident={open} incidentsOverride={filtered}/>}
 {active==="incidents"&&selected&&<IncidentDetail incidentId={selected} onBack={()=>setSelected(null)}/>}
 {active==="approvals"&&<section><div className="pageTitle"><span className="eyebrow">HUMAN-IN-THE-LOOP</span><h1>Approval Queue</h1><p>Review high-impact operational decisions before Jira execution.</p></div><div className="approvalList">{approvals.length?approvals.map(a=>{let p=a.decision_payload||{},id=a.incident_id||a.incidentId;return <article className="panel approvalCard" key={a.approval_id||id}><div className="approvalHead"><div><span className="pill p-high">{p.jira_priority||"Review"}</span><h2>{id}</h2><p>{p.reason||"Human review required."}</p></div><span className="pending">{a.status||"PENDING"}</span></div><div className="facts"><div><span>Create Jira</span><b>{String(p.create_jira??"—")}</b></div><div><span>Notify</span><b>{p.notify||"—"}</b></div><div><span>Retrieved SOP</span><b>{p.rag_documents?.[0]?.title||"—"}</b></div><div><span>Technical Risk</span><b>{p.tool_evaluation?.technical_risk||"—"}</b></div></div>{p.tool_evaluation?.summary&&<p className="diag"><b>Diagnostic evidence</b>{p.tool_evaluation.summary}</p>}<div className="actions"><button className="approve" disabled={processing===id} onClick={()=>act(id,"approve")}>✓ Approve & Execute</button><button className="reject" disabled={processing===id} onClick={()=>act(id,"reject")}>✕ Reject</button></div></article>}):<div className="panel empty">✓ No pending approvals</div>}</div></section>}
 {active==="decisions"&&<DecisionTrail/>}
 {active==="customer-service"&&<CustomerService/>}
 {active==="insights"&&<Insights/>}
 </main></div></div>
}