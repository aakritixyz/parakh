import React, {
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type ReactNode
} from "react";
import { createRoot } from "react-dom/client";
import { loadDashboard, type DashboardData } from "./api";
import type { EventItem, GraphEdge, GraphNode } from "./types";
import "./styles.css";

type Tab =
  | "Dashboard"
  | "AI Leads"
  | "Timeline"
  | "Graph"
  | "Map"
  | "Gallery"
  | "Persons"
  | "Emails"
  | "Communications"
  | "Identifiers"
  | "Authenticity"
  | "Fraud"
  | "Reconstruction"
  | "Assistant";

const tabs: Tab[] = [
  "Dashboard",
  "AI Leads",
  "Timeline",
  "Graph",
  "Map",
  "Gallery",
  "Persons",
  "Emails",
  "Communications",
  "Identifiers",
  "Authenticity",
  "Fraud",
  "Reconstruction",
  "Assistant"
];

type RailItem =
  | "Active Cases"
  | "Inactive Cases"
  | "Public Report"
  | "Private Report"
  | "System Jobs"
  | "Identifier Search"
  | "Generated Reports"
  | "Settings";

const railItems: RailItem[] = [
  "Active Cases",
  "Inactive Cases",
  "Public Report",
  "Private Report",
  "System Jobs",
  "Identifier Search",
  "Generated Reports",
  "Settings"
];

const railTabMap: Partial<Record<RailItem, Tab>> = {
  "Active Cases": "Dashboard",
  "Identifier Search": "Identifiers",
  "Generated Reports": "Reconstruction",
  "Public Report": "Reconstruction",
  "Private Report": "Reconstruction",
  "System Jobs": "AI Leads"
};

type InputChangeEvent = { target: { value: string; checked: boolean } };
type SelectChangeEvent = { target: { value: string } };
type SimpleKeyboardEvent = { key: string };

function App() {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    loadDashboard().then(setData);
  }, []);

  if (!data) {
    return (
      <main className="loading">
        <div className="brand-mark">P</div>
        <p>Preparing Parakh investigation workspace...</p>
      </main>
    );
  }

  return <InvestigationWorkspace data={data} />;
}

function InvestigationWorkspace({ data }: { data: DashboardData }) {
  const [activeTab, setActiveTab] = useState<Tab>("Dashboard");
  const [activeRail, setActiveRail] = useState<RailItem>("Active Cases");
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(data.timeline[0] ?? null);
  const [detailsTab, setDetailsTab] = useState<"event" | "adjacent">("event");
  const [showFilters, setShowFilters] = useState(true);
  const [notice, setNotice] = useState("Workspace ready");
  const people = usePeople(data);
  const [selectedPerson, setSelectedPerson] = useState(people[0] ?? "Primary Owner");
  const selectedEvidence = data.evidence[0];
  const riskScore = useRiskScore(data);
  const selectedView = `${activeRail} / ${activeTab}`;

  function navigateTab(tab: Tab) {
    setActiveTab(tab);
    setActiveRail(tab === "Identifiers" ? "Identifier Search" : "Active Cases");
    setNotice(`${tab} view opened`);
  }

  function navigateRail(item: RailItem) {
    setActiveRail(item);
    const nextTab = railTabMap[item];
    if (nextTab) setActiveTab(nextTab);
    setNotice(`${item} opened`);
  }

  return (
    <div className="suite-shell">
      <aside className="case-rail">
        <div className="product-lockup">
          <div className="brand-mark">P</div>
          <div>
            <strong>Parakh</strong>
            <span>Forensic Intelligence</span>
          </div>
        </div>
        {railItems.map((item) => (
          <button className={item === activeRail ? "rail-active" : ""} key={item} onClick={() => navigateRail(item)}>
            {item}
          </button>
        ))}
      </aside>

      <main className="investigation">
        <header className="suite-topbar">
          <button className="hamburger" aria-label="Open navigation">
            <span />
            <span />
            <span />
          </button>
          <div className="case-title">
            <span className="case-icon">▣</span>
            <div>
              <strong>{activeRail === "Inactive Cases" ? "Archived Case Browser" : "UPI Investment Scam Demo"}</strong>
          <small>{data.online ? "Backend connected" : "Demo data mode"} · Offline-ready · IST workspace</small>
            </div>
          </div>
          <nav className="tab-strip" aria-label="Investigation views">
            {tabs.map((tab) => (
              <button className={tab === activeTab ? "tab-active" : ""} key={tab} onClick={() => navigateTab(tab)}>
                {tab}
              </button>
            ))}
          </nav>
          <div className="top-actions">
            <button title="Generate report" onClick={() => navigateRail("Generated Reports")}>▤</button>
            <button title="User profile" onClick={() => setNotice("Profile controls opened")}>◯</button>
          </div>
        </header>

        <section className="workbench">
          <FacetPanel
            data={data}
            people={people}
            selectedPerson={selectedPerson}
            showFilters={showFilters}
            onSelectPerson={(person) => {
              setSelectedPerson(person);
              setNotice(`${person} selected`);
            }}
            onToggleFilters={() => setShowFilters((current) => !current)}
            onQuickReport={() => navigateRail("Generated Reports")}
          />

          <section className="stage">
            <FilterBar
              activeTab={activeTab}
              total={data.summary?.event_count ?? data.timeline.length}
              notice={notice}
              selectedView={selectedView}
              onClear={() => {
                setShowFilters(true);
                setNotice("Filters cleared");
              }}
              onSave={() => setNotice("Current workspace view saved")}
              onLoad={() => setNotice("Saved view loaded")}
            />
            <ViewSwitch
              activeTab={activeTab}
              activeRail={activeRail}
              data={data}
              people={people}
              selectedPerson={selectedPerson}
              riskScore={riskScore}
              onSelectEvent={setSelectedEvent}
              onSelectPerson={(person) => {
                setSelectedPerson(person);
                setNotice(`${person} selected`);
              }}
            />
          </section>

          <DetailsPane
            activeTab={activeTab}
            data={data}
            event={selectedEvent}
            evidenceName={selectedEvidence?.filename ?? "No evidence selected"}
            detailsTab={detailsTab}
            onDetailsTabChange={setDetailsTab}
          />
        </section>
      </main>
    </div>
  );
}

function FilterBar({
  activeTab,
  total,
  notice,
  selectedView,
  onClear,
  onSave,
  onLoad
}: {
  activeTab: Tab;
  total: number;
  notice: string;
  selectedView: string;
  onClear: () => void;
  onSave: () => void;
  onLoad: () => void;
}) {
  const [query, setQuery] = useState("");
  const [regex, setRegex] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [groupDuplicates, setGroupDuplicates] = useState(true);
  return (
    <div className="filter-bar">
      <div className="search-group">
        <button className="blue-button" onClick={() => setQuery((current) => current || activeTab.toLowerCase())}>Search</button>
        <button className={regex ? "pressed" : ""} onClick={() => setRegex((current) => !current)}>Regex</button>
        <input placeholder={`Search ${activeTab.toLowerCase()}...`} value={query} onChange={(event: InputChangeEvent) => setQuery(event.target.value)} />
        <button className={advanced ? "pressed" : ""} onClick={() => setAdvanced((current) => !current)}>Advanced</button>
      </div>
      <div className="chips">
        <span>{total.toLocaleString("en-IN")} events</span>
        <span>{selectedView}</span>
        {query && <span>Query: {query}</span>}
        {advanced && <span>Advanced open</span>}
        <label>
          <input checked={groupDuplicates} type="checkbox" onChange={(event: InputChangeEvent) => setGroupDuplicates(event.target.checked)} />
          Group duplicates
        </label>
        <span>{notice}</span>
      </div>
      <div className="mini-actions">
        <button onClick={() => {
          setQuery("");
          setRegex(false);
          setAdvanced(false);
          onClear();
        }}>Clear</button>
        <button onClick={onSave}>Save</button>
        <button onClick={onLoad}>Load</button>
      </div>
    </div>
  );
}

function FacetPanel({
  data,
  people,
  selectedPerson,
  showFilters,
  onSelectPerson,
  onToggleFilters,
  onQuickReport
}: {
  data: DashboardData;
  people: string[];
  selectedPerson: string;
  showFilters: boolean;
  onSelectPerson: (person: string) => void;
  onToggleFilters: () => void;
  onQuickReport: () => void;
}) {
  const sources = Object.entries(data.summary?.source_counts ?? {});
  return (
    <aside className="facet-panel">
      <div className="facet-heading">
        <strong>Faceted filters 21/21</strong>
        <button onClick={onToggleFilters}>{showFilters ? "Hide ‹" : "Show ›"}</button>
      </div>
      {showFilters && (
        <>
          <FacetGroup title="Owners" count={people.length || 3} items={people.length ? people : ["Victim", "Suspect", "Mule"]} selected={selectedPerson} onSelect={onSelectPerson} />
          <FacetGroup
            title="Data sources"
            count={sources.length || 7}
            items={sources.length ? sources.map(([name, count]) => `${pretty(name)} ${count}`) : ["WhatsApp", "UPI CSV", "GPS", "PDF"]}
          />
          <FacetGroup
            title="Types"
            count={7}
            items={["Messages 1,107", "Transactions 18", "Image files 76", "Locations 42", "Calls 12"]}
            initiallyOpen
          />
          <FacetGroup title="Parties" count={62} items={["Colin DaCopps 1,099", "Riya 576", "Agent Arjun 232", "Cashout UPI 137"]} initiallyOpen />
          <FacetGroup title="Identifiers" count={775} items={["+91 phones", "UPI IDs", "PAN patterns", "IFSC codes"]} />
          <FacetGroup title="Entities" count={11} items={["People", "Organizations", "Locations", "URLs"]} />
        </>
      )}
      <button className="report-fab" title="Quick report" onClick={onQuickReport}>
        ▣
      </button>
    </aside>
  );
}

function FacetGroup({
  title,
  count,
  items,
  initiallyOpen = false,
  selected,
  onSelect
}: {
  title: string;
  count: number;
  items: string[];
  initiallyOpen?: boolean;
  selected?: string;
  onSelect?: (item: string) => void;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  const [checked, setChecked] = useState(() => new Set(items.slice(0, 2)));
  const allChecked = checked.size === items.length;

  function toggleItem(item: string) {
    setChecked((current) => {
      const next = new Set(current);
      if (next.has(item)) next.delete(item);
      else next.add(item);
      return next;
    });
    onSelect?.(item.replace(/\s+\d[\d,]*$/, ""));
  }

  return (
    <section className="facet-group">
      <header role="button" tabIndex={0} onClick={() => setOpen((current) => !current)} onKeyDown={(event: SimpleKeyboardEvent) => {
        if (event.key === "Enter" || event.key === " ") setOpen((current) => !current);
      }}>
        <span>{open ? "⌄" : "›"} {title}</span>
        <strong>{count}</strong>
      </header>
      {open && (
        <div className="facet-items">
          <label>
            <input
              checked={allChecked}
              type="checkbox"
              onChange={(event: InputChangeEvent) => setChecked(event.target.checked ? new Set(items) : new Set())}
            />
            All
          </label>
          {items.map((item, index) => (
            <label className={selected && item.startsWith(selected) ? "selected-filter" : ""} key={item}>
              <input checked={checked.has(item)} type="checkbox" onChange={() => toggleItem(item)} />
              {item}
            </label>
          ))}
        </div>
      )}
    </section>
  );
}

function ViewSwitch({
  activeTab,
  activeRail,
  data,
  people,
  selectedPerson,
  riskScore,
  onSelectEvent,
  onSelectPerson
}: {
  activeTab: Tab;
  activeRail: RailItem;
  data: DashboardData;
  people: string[];
  selectedPerson: string;
  riskScore: number;
  onSelectEvent: (event: EventItem) => void;
  onSelectPerson: (person: string) => void;
}) {
  if (activeRail === "Inactive Cases") return <CasesView status="Inactive" data={data} />;
  if (activeRail === "System Jobs") return <SystemJobsView data={data} />;
  if (activeRail === "Public Report" || activeRail === "Private Report" || activeRail === "Generated Reports") {
    return <ReportsView data={data} reportType={activeRail} />;
  }
  if (activeRail === "Settings") return <SettingsView />;
  if (activeTab === "AI Leads") return <AILeadsView data={data} riskScore={riskScore} />;
  if (activeTab === "Timeline") return <TimelineView data={data} onSelectEvent={onSelectEvent} />;
  if (activeTab === "Graph") return <GraphView nodes={data.graph.nodes} edges={data.graph.edges} />;
  if (activeTab === "Map") return <MapView />;
  if (activeTab === "Gallery") return <GalleryView data={data} />;
  if (activeTab === "Persons") return <PersonsView data={data} people={people} />;
  if (activeTab === "Emails") return <MessageTable title="Email messages" rows={["Fake investment agreement sent", "Payment receipt shared", "KYC reminder"]} />;
  if (activeTab === "Communications") return <CommunicationsView data={data} />;
  if (activeTab === "Identifiers") return <IdentifiersView />;
  if (activeTab === "Authenticity") return <AuthenticityView data={data} />;
  if (activeTab === "Fraud") return <FraudView data={data} riskScore={riskScore} />;
  if (activeTab === "Reconstruction") return <ReconstructionView data={data} />;
  if (activeTab === "Assistant") return <AssistantView data={data} />;
  return <DashboardView data={data} people={people} selectedPerson={selectedPerson} riskScore={riskScore} onSelectPerson={onSelectPerson} />;
}

function CasesView({ status, data }: { status: "Inactive"; data: DashboardData }) {
  return (
    <div className="table-view">
      <header><h2>{status} Cases</h2></header>
      <p>Archived cases remain searchable for cross-case identifiers and report review.</p>
      <table>
        <thead><tr><th>Case</th><th>Status</th><th>Evidence</th><th>Events</th><th>Last activity</th></tr></thead>
        <tbody>
          {["Investment scam archive", "UPI mule review", "Recovered handset export"].map((name, index) => (
            <tr key={name}><td>{name}</td><td>Inactive</td><td>{data.evidence.length + index}</td><td>{data.timeline.length + index * 12}</td><td>{["Oct 1, 2026", "Sep 27, 2026", "Sep 18, 2026"][index]}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReportsView({ data, reportType }: { data: DashboardData; reportType: RailItem }) {
  return (
    <div className="reconstruction-view">
      <WorkspaceCard title={reportType} className="wide">
        <p>{data.reconstruction.narrative}</p>
        <div className="phase-row">
          <span>Evidence manifest ready</span>
          <span>Hash chain verified</span>
          <span>Section 63 draft marked for legal review</span>
        </div>
      </WorkspaceCard>
      <WorkspaceCard title="Report sections">
        <ul>
          <li>Case summary and source manifest</li>
          <li>Authenticity findings and anomalies</li>
          <li>Timeline, graph and incident reconstruction</li>
        </ul>
      </WorkspaceCard>
      <WorkspaceCard title="Export status">
        <Metric label="Court bundle" value="Ready" hint={`${data.evidence.length} evidence items`} />
      </WorkspaceCard>
    </div>
  );
}

function SystemJobsView({ data }: { data: DashboardData }) {
  return (
    <div className="table-view">
      <header><h2>System Jobs</h2></header>
      <p>Background jobs for parsing, authenticity, graph analysis and report exports.</p>
      <table>
        <thead><tr><th>Job</th><th>Status</th><th>Source</th><th>Records</th><th>Updated</th></tr></thead>
        <tbody>
          {["Parser registry scan", "Entity extraction", "Fraud rules", "Report bundle"].map((job, index) => (
            <tr key={job}><td>{job}</td><td>{index === 3 ? "Queued" : "Complete"}</td><td>Local</td><td>{data.timeline.length + index * 3}</td><td>Just now</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SettingsView() {
  return (
    <div className="card-grid">
      <WorkspaceCard title="Local-first settings">
        <ul>
          <li>Telemetry disabled</li>
          <li>Offline AI provider enabled</li>
          <li>Retention policy configurable</li>
        </ul>
      </WorkspaceCard>
      <WorkspaceCard title="Security">
        <ul>
          <li>JWT login and case membership checks</li>
          <li>Immutable evidence storage</li>
          <li>Hash-chained audit log</li>
        </ul>
      </WorkspaceCard>
    </div>
  );
}

function DashboardView({
  data,
  people,
  selectedPerson,
  riskScore,
  onSelectPerson
}: {
  data: DashboardData;
  people: string[];
  selectedPerson: string;
  riskScore: number;
  onSelectPerson?: (person: string) => void;
}) {
  return (
    <div className="dashboard-grid">
      <OwnerList people={people} selectedPerson={selectedPerson} onSelectPerson={onSelectPerson ?? (() => undefined)} />
      <WorkspaceCard title={`${selectedPerson} · Case Overview`} className="wide">
        <div className="metric-grid">
          <Metric label="Evidence" value={data.summary?.evidence_count ?? data.evidence.length} hint="immutable originals" />
          <Metric label="Events" value={data.summary?.event_count ?? data.timeline.length} hint="normalized records" />
          <Metric label="Risk" value={`${riskScore}%`} hint="fraud + anomaly" danger />
          <Metric label="Custody" value={data.audit?.valid ?? data.summary?.audit_chain_valid ? "Valid" : "Review"} hint="hash chain" />
        </div>
        <AICommandDeck riskScore={riskScore} />
      </WorkspaceCard>
      <WorkspaceCard title="AI media classification">
        <CategoryGrid />
      </WorkspaceCard>
      <WorkspaceCard title="Top connected parties">
        <BarList items={["Agent Arjun", "Riya", "arjun@upi", "cashout@upi", "+91 suspect"]} />
      </WorkspaceCard>
      <WorkspaceCard title="Location interest">
        <MiniMap />
      </WorkspaceCard>
      <WorkspaceCard title="Languages">
        <BarList items={["Hinglish", "Hindi", "English", "Marathi", "Gujarati"]} compact />
      </WorkspaceCard>
    </div>
  );
}

function AICommandDeck({ riskScore }: { riskScore: number }) {
  return (
    <section className="ai-command-deck" aria-label="AI investigation capabilities">
      <article>
        <span>01</span>
        <strong>Natural-language evidence search</strong>
        <p>“Show messages where victim was pushed to share OTP before UPI transfer.”</p>
      </article>
      <article>
        <span>02</span>
        <strong>Citation-locked insights</strong>
        <p>AI answers stay tied to exact evidence and event IDs before report export.</p>
      </article>
      <article>
        <span>03</span>
        <strong>Offline copilot</strong>
        <p>Local model mode keeps case data on the investigator machine.</p>
      </article>
      <article>
        <span>{riskScore}%</span>
        <strong>Investigation priority</strong>
        <p>Fraud rules, anomalies, authenticity and graph signals combined.</p>
      </article>
    </section>
  );
}

function AILeadsView({ data, riskScore }: { data: DashboardData; riskScore: number }) {
  const leads = [
    {
      title: "High-pressure investment pitch",
      signal: "Scam language + communication burst",
      detail: "Repeated urgency words appear before the first debit and match known investment-fraud phrasing.",
      citation: "evidence #1 · event #10"
    },
    {
      title: "Rapid UPI pass-through",
      signal: "Mule account flow",
      detail: "Money enters a beneficiary and moves onward quickly, making the beneficiary worth deeper review.",
      citation: "evidence #2 · event #22"
    },
    {
      title: "Authenticity review needed",
      signal: "Document metadata mismatch",
      detail: "One report/receipt has weaker provenance and should be verified before it is used as an exhibit.",
      citation: `evidence #${data.authenticity[0]?.evidence_id ?? 4}`
    }
  ];

  return (
    <div className="ai-leads-view">
      <WorkspaceCard title="Parakh AI command center" className="wide">
        <div className="lead-hero">
          <div>
            <span className="eyebrow">Built for truth · designed for review</span>
            <h1>Move from scattered evidence to cited understanding.</h1>
            <p>
              Parakh surfaces hidden links across chats, money trails, locations and documents while keeping every
              AI finding tied to verifiable case evidence.
            </p>
          </div>
          <Metric label="AI priority" value={`${riskScore}%`} hint="explainable and cited" danger />
        </div>
      </WorkspaceCard>

      <WorkspaceCard title="Intelligent search">
        <div className="query-box">
          <strong>Ask in normal language</strong>
          <p>Find all Hinglish chats where return, OTP, KYC or urgent payment appears near a transaction.</p>
          <div className="citation-strip"><span>messages</span><span>UPI</span><span>Hindi/Hinglish</span></div>
        </div>
      </WorkspaceCard>

      <WorkspaceCard title="Structured insights">
        <div className="lead-list">
          {leads.map((lead) => (
            <article key={lead.title}>
              <strong>{lead.title}</strong>
              <small>{lead.signal}</small>
              <p>{lead.detail}</p>
              <span>{lead.citation}</span>
            </article>
          ))}
        </div>
      </WorkspaceCard>

      <WorkspaceCard title="Responsible AI controls">
        <ul className="control-list">
          <li>Unsupported claims are blocked before report generation.</li>
          <li>Investigator accepts or rejects AI leads with reasons.</li>
          <li>No mandatory cloud calls; local LLM and embeddings can be used.</li>
          <li>Aadhaar patterns are masked before storage and display.</li>
        </ul>
      </WorkspaceCard>
    </div>
  );
}

function OwnerList({ people, selectedPerson, onSelectPerson }: { people: string[]; selectedPerson: string; onSelectPerson: (person: string) => void }) {
  const rows = people.length ? people : ["Riya", "Agent Arjun", "Mule Account"];
  return (
    <aside className="owner-list">
      <p>Select an owner to view their data</p>
      <input placeholder="Start typing to find an owner..." />
      {rows.slice(0, 5).map((person, index) => (
        <button className={`owner-row ${person === selectedPerson ? "selected" : ""}`} key={person} onClick={() => onSelectPerson(person)}>
          <span className="avatar">{person[0]?.toUpperCase()}</span>
          <div>
            <strong>{person}</strong>
            <small>{identifier(index)}</small>
          </div>
          <span className="review-link">Review</span>
        </button>
      ))}
    </aside>
  );
}

function TimelineView({ data, onSelectEvent }: { data: DashboardData; onSelectEvent: (event: EventItem) => void }) {
  return (
    <div className="timeline-view">
      <Histogram />
      <p className="result-line">{data.timeline.length.toLocaleString("en-IN")} events shown · 0 deleted · grouped duplicates on</p>
      <div className="event-list">
        {data.timeline.map((event, index) => (
          <button className="event-row" key={`${event.event_id ?? event.id ?? index}`} onClick={() => onSelectEvent(event)}>
            <input type="checkbox" />
            <span className="event-type">▣</span>
            <span>
              <small>From: Owner</small>
              {event.action}
            </span>
            <strong>{event.summary ?? event.content ?? "Empty"}</strong>
            <time>{formatTime(event.timestamp_utc)}</time>
          </button>
        ))}
      </div>
    </div>
  );
}

function GraphView({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const [showVolume, setShowVolume] = useState(false);
  const [sizeByDegree, setSizeByDegree] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const graphNodes = nodes.length ? nodes : fallbackNodes;
  const graphEdges = edges.length ? edges : fallbackEdges;
  const positioned = graphNodes.slice(0, 14).map((node, index) => {
    const angle = (index / Math.max(1, graphNodes.length)) * Math.PI * 2;
    const radius = index === 0 ? 0 : 190 + (index % 3) * 32;
    return {
          ...node,
          x: 410 + Math.cos(angle) * radius,
      y: 260 + Math.sin(angle) * radius,
      radius: 34 + node.centrality * (sizeByDegree ? 28 : 18)
    };
  });
  const byId = new Map(positioned.map((node) => [node.id, node]));

  return (
    <div className="graph-view">
      <div className="graph-toolbar">
        <input placeholder="Search by name" />
        <button className={filterOpen ? "pressed" : ""} onClick={() => setFilterOpen((current) => !current)}>Filters</button>
        <label><input checked={showVolume} type="checkbox" onChange={(event: InputChangeEvent) => setShowVolume(event.target.checked)} /> Show volume</label>
        <label><input checked={sizeByDegree} type="checkbox" onChange={(event: InputChangeEvent) => setSizeByDegree(event.target.checked)} /> Node size by degree</label>
        {filterOpen && <span className="inline-status">Message and party filters active</span>}
      </div>
      <svg viewBox="0 0 900 560" role="img" aria-label="Entity relationship graph">
        {graphEdges.map((edge, index) => {
          const source = byId.get(edge.source);
          const target = byId.get(edge.target);
          if (!source || !target) return null;
          return (
            <g key={`${edge.source}-${edge.target}-${index}`}>
              <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} />
              <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2}>{edge.weight}</text>
            </g>
          );
        })}
        {positioned.map((node, index) => (
          <g className={index === 0 ? "hot-node" : ""} key={node.id}>
            <circle cx={node.x} cy={node.y} r={node.radius} />
            <text x={node.x} y={node.y + 6}>{shortName(node.id)}</text>
            <text className="node-label" x={node.x} y={node.y + 58}>{node.id}</text>
            {showVolume && <text className="node-volume" x={node.x} y={node.y - 46}>{Math.round(node.centrality * 100)}</text>}
          </g>
        ))}
      </svg>
    </div>
  );
}

function MapView() {
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState("x2");
  return (
    <div className="map-view">
      <Histogram />
      <div className="map-toolbar">
        <button className={playing ? "pressed" : ""} onClick={() => setPlaying(true)}>▶</button>
        <button onClick={() => setPlaying(false)}>■</button>
        <label>speed <select value={speed} onChange={(event: SelectChangeEvent) => setSpeed(event.target.value)}><option>x2</option><option>x4</option></select></label>
        <span className="inline-status">{playing ? `Playback running at ${speed}` : "Playback stopped"}</span>
      </div>
      <MiniMap large />
    </div>
  );
}

function GalleryView({ data }: { data: DashboardData }) {
  const media = data.evidence.length ? data.evidence : [];
  return (
    <div className="gallery-view">
      <p className="result-line">81,196 media events · duplicates grouped · image search available</p>
      <div className="media-grid">
        {media.concat(media).slice(0, 8).map((item, index) => (
          <article className="media-card" key={`${item.id}-${index}`}>
            <div className="media-thumb">▧</div>
            <span className="avatar red">{index % 2 ? "A" : "R"}</span>
            <strong>{item.filename}</strong>
            <small>{formatBytes(item.size_bytes)} · {item.source_type}</small>
          </article>
        ))}
      </div>
    </div>
  );
}

function PersonsView({ data, people }: { data: DashboardData; people: string[] }) {
  return (
    <div className="table-view">
      <table>
        <thead><tr><th>Person</th><th>Aliases</th><th>Events</th><th>Risk</th><th>Labels</th></tr></thead>
        <tbody>
          {(people.length ? people : ["Riya", "Agent Arjun", "Mule Account"]).map((person, index) => (
            <tr key={person}>
              <td>{person}</td>
              <td>{identifier(index)}</td>
              <td>{Math.max(4, data.timeline.length - index * 2)}</td>
              <td>{index === 1 ? "High" : "Medium"}</td>
              <td>chat · transaction · India</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CommunicationsView({ data }: { data: DashboardData }) {
  return <MessageTable title="Communications" rows={data.timeline.map((event) => event.summary ?? event.content ?? event.action)} />;
}

function MessageTable({ title, rows }: { title: string; rows: string[] }) {
  return (
    <div className="table-view">
      <h2>{title}</h2>
      <table>
        <thead><tr><th>From</th><th>To</th><th>Application</th><th>Content</th><th>Time</th></tr></thead>
        <tbody>
          {rows.slice(0, 12).map((row, index) => (
            <tr key={`${row}-${index}`}>
              <td>Owner</td>
              <td>Suspect</td>
              <td>{index % 2 ? "Email" : "WhatsApp"}</td>
              <td>{row || "Empty"}</td>
              <td>Dec {29 - index}, 2026</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IdentifiersView() {
  return (
    <div className="table-view identifier-view">
      <header>
        <h2>Identifier Search</h2>
        <button className="blue-button">Sync</button>
        <button className="blue-button">Export</button>
      </header>
      <p>Select cross-case identifiers such as phones, UPI IDs, emails, IFSC and masked Aadhaar patterns.</p>
      <table>
        <thead><tr><th><input type="checkbox" /></th><th>Identifier</th><th>Aliases</th><th>Cases</th><th>Total events</th><th>Labels</th><th>Last discovered</th></tr></thead>
        <tbody>
          {["+919876543210", "arjun@upi", "HDFC0001234", "riya@example.com", "Aadhaar ****1234"].map((id, index) => (
            <tr key={id}><td><input type="checkbox" /></td><td>{id}</td><td>+{index + 2}</td><td>{index + 1}</td><td>{(index + 1) * 73}</td><td>India · scam</td><td>Oct 1, 2026</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuthenticityView({ data }: { data: DashboardData }) {
  return (
    <div className="card-grid">
      {data.authenticity.map((item) => (
        <WorkspaceCard title={`Evidence #${item.evidence_id}`} key={item.evidence_id}>
          <div className="auth-row">
            <div className="score-ring" style={{ "--score": `${item.score}%` } as CSSProperties}>{item.score}</div>
            <div>
              <strong>{item.score >= 75 ? "Likely authentic" : "Needs review"}</strong>
              <p>{item.findings[0]?.explanation ?? "No major finding detected."}</p>
              <small>{item.findings[0]?.signal ?? "hash_verified"}</small>
            </div>
          </div>
        </WorkspaceCard>
      ))}
    </div>
  );
}

function FraudView({ data, riskScore }: { data: DashboardData; riskScore: number }) {
  return (
    <div className="card-grid">
      <WorkspaceCard title="Fraud Risk">
        <Metric label="Composite risk" value={`${riskScore}%`} hint="rule engine + anomalies" danger />
      </WorkspaceCard>
      {[...data.fraud, ...data.anomalies].map((item, index) => (
        <WorkspaceCard title={pretty(String(item.type ?? "AI lead"))} key={index}>
          <p>{String(item.explanation ?? JSON.stringify(item.features ?? item))}</p>
          <small>Source traceability required before report export</small>
        </WorkspaceCard>
      ))}
    </div>
  );
}

function ReconstructionView({ data }: { data: DashboardData }) {
  return (
    <div className="reconstruction-view">
      <WorkspaceCard title="Incident reconstruction" className="wide">
        <p>{data.reconstruction.narrative}</p>
        <div className="phase-row">
          {data.reconstruction.phases.map((phase) => <span key={phase}>{pretty(phase)}</span>)}
        </div>
      </WorkspaceCard>
      <WorkspaceCard title="Contradictions and gaps">
        <ul>
          {data.reconstruction.gaps.map((gap) => <li key={gap}>{gap}</li>)}
          <li>Every hypothesis must cite exact evidence and event IDs.</li>
        </ul>
      </WorkspaceCard>
      <WorkspaceCard title="Section 63 BSA 2023">
        <p>Draft certificate generator is available in backend and marked for legal verification.</p>
      </WorkspaceCard>
    </div>
  );
}

function AssistantView({ data }: { data: DashboardData }) {
  return (
    <div className="assistant-view">
      <WorkspaceCard title="Offline Cited AI Assistant" className="wide">
        <div className="chat-bubble">
          <strong>Investigator</strong>
          <p>Summarise the strongest scam pattern in this case.</p>
        </div>
        <div className="chat-bubble answer">
          <strong>Parakh AI</strong>
          <p>{data.reconstruction.narrative || "Unsupported. No cited evidence is available yet."}</p>
          <small>Citations: evidence #1, event #10 · evidence #2, event #22</small>
        </div>
      </WorkspaceCard>
    </div>
  );
}

function DetailsPane({
  activeTab,
  data,
  event,
  evidenceName,
  detailsTab,
  onDetailsTabChange
}: {
  activeTab: Tab;
  data: DashboardData;
  event: EventItem | null;
  evidenceName: string;
  detailsTab: "event" | "adjacent";
  onDetailsTabChange: (tab: "event" | "adjacent") => void;
}) {
  return (
    <aside className="details-pane">
      <header>
        <strong>Details</strong>
        <div><button title="Comment">💬</button><button title="Tag">🏷</button></div>
      </header>
      <div className="detail-tabs">
        <button className={detailsTab === "event" ? "active" : ""} onClick={() => onDetailsTabChange("event")}>Event details</button>
        <button className={detailsTab === "adjacent" ? "active" : ""} onClick={() => onDetailsTabChange("adjacent")}>Adjacent events</button>
      </div>
      {event && detailsTab === "event" ? (
        <section className="detail-block">
          <time>{formatTime(event.timestamp_utc)}</time>
          <h3>{pretty(event.action)}</h3>
          <p>{event.summary ?? event.content ?? "No content recorded."}</p>
          <dl>
            <dt>Application</dt><dd>{appFor(event.action, activeTab)}</dd>
            <dt>Evidence</dt><dd>{evidenceName}</dd>
            <dt>Evidence ID</dt><dd>{event.evidence_id}</dd>
            <dt>Event ID</dt><dd>{event.event_id ?? event.id ?? "pending"}</dd>
          </dl>
        </section>
      ) : event && detailsTab === "adjacent" ? (
        <section className="detail-block">
          <h3>Adjacent events</h3>
          <p>Events before and after this record are ready for timeline correlation.</p>
          <dl>
            <dt>Previous</dt><dd>Communication burst</dd>
            <dt>Current</dt><dd>{event.event_id ?? event.id ?? "pending"}</dd>
            <dt>Next</dt><dd>Financial transfer review</dd>
          </dl>
        </section>
      ) : (
        <p className="empty-note">Select an item to view details.</p>
      )}
      <section className="detail-block">
        <h3>Case health</h3>
        <dl>
          <dt>Sources</dt><dd>{Object.keys(data.summary?.source_counts ?? {}).length || data.evidence.length}</dd>
          <dt>Audit chain</dt><dd>{data.audit?.valid ?? data.summary?.audit_chain_valid ? "Verified" : "Needs review"}</dd>
          <dt>AI claims</dt><dd>Citations enforced</dd>
        </dl>
      </section>
    </aside>
  );
}

function WorkspaceCard({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`workspace-card ${className}`}>
      <header><h2>{title}</h2><button>↧</button></header>
      {children}
    </section>
  );
}

function Metric({ label, value, hint, danger = false }: { label: string; value: ReactNode; hint: string; danger?: boolean }) {
  return (
    <article className={`metric ${danger ? "danger" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </article>
  );
}

function CategoryGrid() {
  return (
    <div className="category-grid">
      {["Documents", "Money", "Faces", "Phones", "Screenshots", "Receipts"].map((item, index) => (
        <article key={item}><span>{["▤", "₹", "◎", "▯", "▧", "▣"][index]}</span><strong>{item}</strong><small>{28 - index * 3} items</small></article>
      ))}
    </div>
  );
}

function BarList({ items, compact = false }: { items: string[]; compact?: boolean }) {
  return (
    <div className={`bar-list ${compact ? "compact" : ""}`}>
      {items.map((item, index) => (
        <article key={item}>
          <span>{item}</span>
          <div><i style={{ width: `${Math.max(12, 92 - index * 14)}%` }} /></div>
          <strong>{481 - index * 77}</strong>
        </article>
      ))}
    </div>
  );
}

function Histogram() {
  return (
    <div className="histogram">
      {Array.from({ length: 24 }).map((_, index) => <span key={index} style={{ height: `${12 + ((index * 17) % 68)}%` }} />)}
    </div>
  );
}

function MiniMap({ large = false }: { large?: boolean }) {
  return (
    <div className={`mini-map ${large ? "large" : ""}`}>
      {Array.from({ length: large ? 18 : 8 }).map((_, index) => (
        <span className="pin" key={index} style={{ left: `${12 + ((index * 13) % 78)}%`, top: `${22 + ((index * 19) % 56)}%` }} />
      ))}
    </div>
  );
}

function usePeople(data: DashboardData) {
  return useMemo(() => {
    const names = new Set<string>();
    data.graph.nodes.forEach((node) => {
      if (!node.id.includes("@") && !node.id.startsWith("+") && node.id.length < 24) names.add(node.id);
    });
    return Array.from(names).slice(0, 8);
  }, [data.graph.nodes]);
}

function useRiskScore(data: DashboardData) {
  return useMemo(() => {
    if (data.summary?.risk_score) return data.summary.risk_score;
    const authPenalty = data.authenticity.reduce((sum, item) => sum + (100 - item.score) / 9, 0);
    return Math.min(98, Math.round(48 + data.fraud.length * 12 + data.anomalies.length * 8 + authPenalty));
  }, [data]);
}

const fallbackNodes: GraphNode[] = [
  { id: "Riya", centrality: 0.9 },
  { id: "Agent Arjun", centrality: 0.84 },
  { id: "arjun@upi", centrality: 0.78 },
  { id: "cashout@upi", centrality: 0.48 },
  { id: "+919876543210", centrality: 0.44 }
];

const fallbackEdges: GraphEdge[] = [
  { source: "Riya", target: "Agent Arjun", weight: 7 },
  { source: "Agent Arjun", target: "arjun@upi", weight: 4 },
  { source: "arjun@upi", target: "cashout@upi", weight: 2 },
  { source: "+919876543210", target: "Agent Arjun", weight: 1 }
];

function identifier(index: number) {
  return ["+919876543210", "arjun@upi", "HDFC0001234", "PAN pattern", "Aadhaar ****1234"][index % 5];
}

function sourceIcon(source: string) {
  if (source.includes("whatsapp")) return "☏";
  if (source.includes("bank") || source.includes("upi")) return "₹";
  if (source.includes("gps")) return "⌖";
  if (source.includes("image")) return "▧";
  return "▣";
}

function appFor(action: string, tab: Tab) {
  if (tab === "Emails") return "Email";
  if (tab === "Map") return "GPS / Location";
  if (action.toLowerCase().includes("debit")) return "UPI / Bank";
  return "WhatsApp";
}

function pretty(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortName(value: string) {
  if (value.includes("@")) return value.split("@")[0].slice(0, 2).toUpperCase();
  if (value.startsWith("+")) return value.slice(-2);
  return value.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function formatTime(value?: string | null) {
  if (!value) return "Unknown time";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata"
  }).format(new Date(value));
}

function formatBytes(value: number) {
  if (value > 1_000_000) return `${(value / 1_000_000).toFixed(1)} MB`;
  if (value > 1_000) return `${(value / 1_000).toFixed(1)} KB`;
  return `${value} B`;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
