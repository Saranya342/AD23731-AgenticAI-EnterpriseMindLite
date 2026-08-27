import { useState } from "react";
import IncidentOverview from "./components/IncidentOverview";
import IncidentDetail from "./components/IncidentDetail";
import DecisionTrail from "./components/DecisionTrail";
import Insights from "./components/Insights";
import "./App.css";

const TABS = [
  { id: "overview", label: "Incident Overview" },
  { id: "decisions", label: "Decision Trail" },
  { id: "insights", label: "Organizational Insights" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedIncidentId, setSelectedIncidentId] = useState(null);

  function handleSelectIncident(incidentId) {
    setSelectedIncidentId(incidentId);
  }

  function handleBackToOverview() {
    setSelectedIncidentId(null);
  }

  function handleTabClick(tabId) {
    setActiveTab(tabId);
    setSelectedIncidentId(null);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>EnterpriseMind Lite</h1>
        <nav className="tab-nav">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={activeTab === tab.id ? "tab active" : "tab"}
              onClick={() => handleTabClick(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="app-main">
        {activeTab === "overview" && !selectedIncidentId && (
          <IncidentOverview onSelectIncident={handleSelectIncident} />
        )}
        {activeTab === "overview" && selectedIncidentId && (
          <IncidentDetail incidentId={selectedIncidentId} onBack={handleBackToOverview} />
        )}
        {activeTab === "decisions" && <DecisionTrail />}
        {activeTab === "insights" && <Insights />}
      </main>
    </div>
  );
}
