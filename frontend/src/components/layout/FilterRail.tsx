import type { ReactNode } from "react";
export function FilterRail({
  children,
  collapsed,
}: {
  children: ReactNode;
  collapsed: boolean;
}) {
  return (
    <div className={`filter-rail ${collapsed ? "filters-collapsed" : ""}`}>
      {children}
    </div>
  );
}

import type { DashboardData } from "../../api";
import { FacetGroup } from "../ui";
import { FileText } from "lucide-react";
import { pretty } from "../../format";

export function FacetPanel({
  data,
  people,
  selectedPerson,
  showFilters,
  onSelectPerson,
  onToggleFilters,
  onQuickReport,
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
        <strong>Faceted filters</strong>
        <button onClick={onToggleFilters}>
          {showFilters ? "Hide" : "Show"}
        </button>
      </div>
      {showFilters && (
        <>
          <FacetGroup
            title="Owners"
            count={people.length || 3}
            items={people.length ? people : ["Victim", "Suspect", "Mule"]}
            selected={selectedPerson}
            onSelect={onSelectPerson}
          />
          <FacetGroup
            title="Data sources"
            count={sources.length || 7}
            items={
              sources.length
                ? sources.map(([name, count]) => `${pretty(name)} ${count}`)
                : ["WhatsApp", "UPI CSV", "GPS", "PDF"]
            }
          />
          <FacetGroup
            title="Types"
            count={7}
            items={[
              "Messages 1,107",
              "Transactions 18",
              "Image files 76",
              "Locations 42",
              "Calls 12",
            ]}
            initiallyOpen
          />
          <FacetGroup
            title="Parties"
            count={62}
            items={[
              "Colin DaCopps 1,099",
              "Riya 576",
              "Agent Arjun 232",
              "Cashout UPI 137",
            ]}
            initiallyOpen
          />
          <FacetGroup
            title="Identifiers"
            count={775}
            items={["+91 phones", "UPI IDs", "PAN patterns", "IFSC codes"]}
          />
          <FacetGroup
            title="Entities"
            count={11}
            items={["People", "Organizations", "Locations", "URLs"]}
          />
        </>
      )}
      {showFilters && (
        <button
          className="facet-clear"
          onClick={() =>
            window.dispatchEvent(new Event("parakh-clear-filters"))
          }
        >
          Clear filters
        </button>
      )}
      <button
        className="report-fab"
        title="Quick report"
        onClick={onQuickReport}
      >
        <FileText /> Quick report
      </button>
    </aside>
  );
}
