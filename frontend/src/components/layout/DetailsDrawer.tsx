import { useEffect, useState, type ReactNode } from "react";
import { X, MessageSquare, Tags } from "lucide-react";
export function DetailsDrawer({
  children,
  onClose,
}: {
  children: ReactNode;
  onClose: () => void;
}) {
  const [overlay, setOverlay] = useState(() => window.innerWidth < 1440);
  useEffect(() => {
    const media = matchMedia("(max-width: 1439px)");
    const update = () => setOverlay(media.matches);
    media.addEventListener("change", update);
    const previous = document.activeElement as HTMLElement | null;
    const closeButton =
      document.querySelector<HTMLButtonElement>(".drawer-close");
    closeButton?.focus();
    const handle = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab" && media.matches) {
        const items = Array.from(
          document.querySelectorAll<HTMLElement>(
            '.drawer button,.drawer input,.drawer [tabindex="0"]',
          ),
        );
        const first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", handle);
    return () => {
      media.removeEventListener("change", update);
      window.removeEventListener("keydown", handle);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <>
      <button
        className="drawer-scrim"
        aria-label="Close details"
        onClick={onClose}
        tabIndex={-1}
      />
      <section
        className="drawer"
        role={overlay ? "dialog" : "complementary"}
        aria-modal={overlay || undefined}
        aria-label="Event details"
      >
        <button
          className="drawer-close"
          aria-label="Close details"
          onClick={onClose}
        >
          <X />
        </button>
        {children}
      </section>
    </>
  );
}

import type { DashboardData } from "../../api";
import type { EventItem } from "../../types";
import { appFor, pretty, formatTime } from "../../format";

export function DetailsPane({
  activeTab,
  data,
  event,
  evidenceName,
  detailsTab,
  onDetailsTabChange,
}: {
  activeTab: string;
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
        <div className="detail-actions">
          <button title="Comment" aria-label="Comment">
            <MessageSquare />
          </button>
          <button title="Tag" aria-label="Tag">
            <Tags />
          </button>
        </div>
      </header>
      <div className="detail-tabs">
        <button
          className={detailsTab === "event" ? "active" : ""}
          onClick={() => onDetailsTabChange("event")}
        >
          Event details
        </button>
        <button
          className={detailsTab === "adjacent" ? "active" : ""}
          onClick={() => onDetailsTabChange("adjacent")}
        >
          Adjacent events
        </button>
      </div>
      {event && detailsTab === "event" ? (
        <section className="detail-block">
          <time>{formatTime(event.timestamp_utc)}</time>
          <h3>{pretty(event.action)}</h3>
          <p>{event.summary ?? event.content ?? "No content recorded."}</p>
          <dl>
            <dt>Application</dt>
            <dd>{appFor(event.action, activeTab)}</dd>
            <dt>Evidence</dt>
            <dd>{evidenceName}</dd>
            <dt>Evidence ID</dt>
            <dd>{event.evidence_id}</dd>
            <dt>Event ID</dt>
            <dd>{event.event_id ?? event.id ?? "pending"}</dd>
          </dl>
        </section>
      ) : event && detailsTab === "adjacent" ? (
        <section className="detail-block">
          <h3>Adjacent events</h3>
          <p>
            Events before and after this record are ready for timeline
            correlation.
          </p>
          <dl>
            <dt>Previous</dt>
            <dd>Communication burst</dd>
            <dt>Current</dt>
            <dd>{event.event_id ?? event.id ?? "pending"}</dd>
            <dt>Next</dt>
            <dd>Financial transfer review</dd>
          </dl>
        </section>
      ) : (
        <p className="empty-note">Select an item to view details.</p>
      )}
      <section className="detail-block">
        <h3>Case health</h3>
        <dl>
          <dt>Sources</dt>
          <dd>
            {Object.keys(data.summary?.source_counts ?? {}).length ||
              data.evidence.length}
          </dd>
          <dt>Audit chain</dt>
          <dd>
            {(data.audit?.valid ?? data.summary?.audit_chain_valid)
              ? "Verified"
              : "Needs review"}
          </dd>
          <dt>AI claims</dt>
          <dd>Citations enforced</dd>
        </dl>
      </section>
    </aside>
  );
}
