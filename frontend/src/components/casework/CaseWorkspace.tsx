import {
  confirmAlias,
  getIdentities,
  searchCaseEvents,
  unmergeAlias,
  verifyLiveIntegrity,
  type Audit,
  type IdentityOverview,
  type SearchResult,
} from "../../caseApi";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  ArrowRight,
  Check,
  ChevronRight,
  Download,
  FileText,
  FolderOpen,
  Menu,
  Pause,
  Play,
  Search,
  ShieldCheck,
  ShieldX,
  Sparkles,
  X,
} from "lucide-react";
import type { DashboardData } from "../../api";
import {
  demo,
  findings,
  time,
  verifyChain,
  sha256,
  download,
  type Citation,
  type Source,
  type RecordEvent,
  type Finding,
  type FindingStatus,
} from "./model";
import styles from "./Casework.module.css";
import { VirtualList } from "../ui/VirtualList";

const views = [
  "Overview",
  "Evidence",
  "Explore",
  "Comms",
  "Money",
  "Authenticity",
  "Graph",
  "Map",
  "Timeline",
  "Findings",
  "Reports",
] as const;
type View = (typeof views)[number];
type Detail = {
  citation?: Citation;
  event?: RecordEvent;
  title?: string;
  text?: string;
  citations?: Citation[];
};
type Props = {
  caseAudit?: Audit | null;
  readOnly?: boolean;
  data: DashboardData;
  title: string;
  token: string | null;
  caseId: number | null;
  onNew: () => void;
  onSignOut: () => void;
};
function identity(token: string | null) {
  if (!token) return { name: "Demo viewer", role: "Read-only demo" };
  try {
    const claims = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    );
    return {
      name: String(claims.sub ?? "Signed-in user"),
      role: String(claims.role ?? "Role unavailable"),
    };
  } catch {
    return { name: "Signed-in user", role: "Role unavailable" };
  }
}
const localDay = (value: string) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
const money = (value: string | number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(value));
const short = (file: string) => file.replace(/^\d+_/, "").replaceAll("_", " ");
const statusClass = (status: FindingStatus) =>
  status === "Established"
    ? styles.established
    : status === "Possible"
      ? styles.possible
      : status === "Contradicted"
        ? styles.contradicted
        : styles.unknown;

export function CaseWorkspace({
  data,
  title,
  token,
  caseId,
  onNew,
  onSignOut,
  readOnly = false,
  caseAudit,
}: Props) {
  const isDemo = !token;
  const isScenario =
    isDemo ||
    (data.evidence.length === demo.files.length &&
      demo.files.every((f) =>
        data.evidence.some((e) => e.sha256 === f.sha256),
      ));
  const sources: Source[] = useMemo(
    () =>
      isScenario
        ? demo.files
        : data.evidence.map((e) => ({
            id: e.id,
            file: e.filename,
            owner: "Not supplied",
            source: e.source_type,
            note: "Source-row provenance is not included in this dashboard response.",
            sha256: e.sha256,
            bytes: e.size_bytes,
            parser: "Not supplied",
            records: data.timeline.filter((t) => t.evidence_id === e.id).length,
            rows: [],
          })),
    [data, isScenario],
  );
  const sourceRecords: RecordEvent[] = useMemo(
    () =>
      isScenario
        ? demo.events
        : data.timeline.map((e, i) => ({
            id: String(e.event_id ?? e.id ?? i),
            file:
              sources.find((s) => s.id === e.evidence_id)?.file ??
              "Unknown source",
            evidence_id: e.evidence_id,
            timestamp_utc: e.timestamp_utc ?? null,
            original_timestamp: null,
            action: e.action,
            content: e.content ?? e.summary ?? "",
            raw_ref: "Not supplied",
            confidence: 0,
            actor_entities: [],
          })),
    [data, isScenario, sources],
  );
  const initialFilters = new URLSearchParams(window.location.search);
  const [view, setView] = useState<View>("Overview"),
    [nav, setNav] = useState(false),
    [query, setQuery] = useState(initialFilters.get("q") ?? "");
  const [owner, setOwner] = useState(initialFilters.get("owner") ?? "All"),
    [kind, setKind] = useState(initialFilters.get("type") ?? "All"),
    [sourceId, setSourceId] = useState(initialFilters.get("source") ?? "All"),
    [day, setDay] = useState(initialFilters.get("day") ?? "All"),
    [identifier, setIdentifier] = useState(initialFilters.get("identifier") ?? "All"),
    [app, setApp] = useState(initialFilters.get("app") ?? "All"),
    [device, setDevice] = useState(initialFilters.get("device") ?? "All"),
    [party, setParty] = useState(initialFilters.get("party") ?? "All"),
    [tag, setTag] = useState(initialFilters.get("tag") ?? "All"),
    [deleted, setDeleted] = useState(initialFilters.get("deleted") ?? "all"),
    [regex, setRegex] = useState(initialFilters.get("regex") ?? "");
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null),
    [searchError, setSearchError] = useState("");
  const [identityData, setIdentityData] = useState<IdentityOverview | null>(null);
  const records: RecordEvent[] = useMemo(
    () =>
      searchResult
        ? searchResult.items.map((event) => ({
            id: String(event.event_id),
            file: event.source.filename,
            evidence_id: event.evidence_id,
            timestamp_utc: event.timestamp_utc,
            original_timestamp: event.original_timestamp,
            action: event.type === "transaction" ? "payment" : event.action,
            content: event.content,
            raw_ref: event.raw_ref,
            confidence: event.confidence,
            actor_entities: event.parties,
            identifiers: event.identifiers,
            owner: event.owner,
            device: event.device,
            app: event.app,
            tags: event.tags,
          }))
        : sourceRecords,
    [searchResult, sourceRecords],
  );
  const [detail, setDetail] = useState<Detail | null>(null),
    [custody, setCustody] = useState(false),
    [assistant, setAssistant] = useState(false);
  const [chain, setChain] = useState<boolean | null>(
    isDemo
      ? null
      : (caseAudit?.chain_verified ??
          data.audit?.valid ??
          data.summary?.audit_chain_valid ??
          null),
  );
  const [checks, setChecks] = useState<Record<number, string>>({}),
    [english, setEnglish] = useState(false),
    [merged, setMerged] = useState(false);
  const [findingStatuses, setFindingStatuses] = useState<
      Record<string, FindingStatus>
    >({}),
    [exhibits, setExhibits] = useState<string[]>([]);
  const [sourceExhibits, setSourceExhibits] = useState<Citation[]>([]);
  const [question, setQuestion] = useState(""),
    [answer, setAnswer] = useState<Finding | null>(null),
    [refusal, setRefusal] = useState(false);
  const [replay, setReplay] = useState(0),
    [playing, setPlaying] = useState(false),
    [notice, setNotice] = useState("");
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0 });
  }, [view]);
  const search = useRef<HTMLInputElement>(null);
  const person = identity(token);
  useEffect(() => {
    if (!token || !caseId) return;
    const timer = window.setTimeout(() => {
      const selectedSource =
        sourceId === "All" ? "" : sources.find((item) => String(item.id) === sourceId)?.file ?? "";
      const params = new URLSearchParams(window.location.search);
      const values = { q: query, owner, type: kind, source: sourceId, day, identifier, app, device, party, tag, deleted, regex };
      Object.entries(values).forEach(([key, value]) => {
        if (!value || value === "All") params.delete(key);
        else params.set(key, value);
      });
      window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
      void searchCaseEvents(caseId, {
        q: query,
        regex,
        facets: {
          ...(owner !== "All" ? { owner } : {}),
          ...(kind !== "All" ? { type: kind } : {}),
          ...(identifier !== "All" ? { identifier } : {}),
          ...(selectedSource ? { source: selectedSource } : {}),
          ...(app !== "All" ? { app } : {}),
          ...(device !== "All" ? { device } : {}),
          ...(party !== "All" ? { party } : {}),
          ...(tag !== "All" ? { tag } : {}),
          ...(deleted !== "all" ? { deleted: deleted === "recovered" } : {}),
        },
        time: day !== "All" ? { start: `${day}T00:00:00+05:30`, end: `${day}T23:59:59+05:30` } : {},
        page: { limit: 100000 },
      })
        .then((result) => {
          setSearchResult(result);
          setSearchError("");
        })
        .catch((cause) => setSearchError(cause instanceof Error ? cause.message : "Search failed."));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [app, caseId, day, deleted, device, identifier, kind, owner, party, query, regex, sourceId, sources, tag, token]);
  useEffect(() => {
    if (!token || !caseId || view !== "Graph") return;
    void getIdentities(caseId).then(setIdentityData);
  }, [caseId, token, view]);
  useEffect(() => {
    if (isDemo) {
      let active = true;
      verifyChain(demo.audit).then((valid) => {
        if (active) setChain(valid);
      });
      return () => {
        active = false;
      };
    }
  }, [isDemo]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        search.current?.focus();
      }
      if (e.key === "Escape") {
        setDetail(null);
        setCustody(false);
        setAssistant(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  const dated = useMemo(
    () =>
      records
        .filter((e) => e.timestamp_utc)
        .sort((a, b) => a.timestamp_utc!.localeCompare(b.timestamp_utc!)),
    [records],
  );
  useEffect(() => {
    if (!playing) return;
    const tick = window.setInterval(
      () =>
        setReplay((i) => {
          if (i >= dated.length - 1) {
            setPlaying(false);
            return i;
          }
          return i + 1;
        }),
      900,
    );
    return () => window.clearInterval(tick);
  }, [playing, dated.length]);
  const open = useCallback(
    (citation: Citation, event?: RecordEvent) => setDetail({ citation, event }),
    [],
  );
  const cite = (c: Citation) => (
    <button
      className={styles.citation}
      key={`${c.file}-${c.ref}-${c.label}`}
      onClick={() => open(c)}
    >
      <FileText />
      {c.label ?? `${String(c.file).padStart(2, "0")} · ${c.ref ?? "source"}`}
    </button>
  );
  const cites = (cs: Citation[]) => (
    <div className={styles.citations}>{cs.map(cite)}</div>
  );
  const go = (next: View) => {
    setView(next);
    setNav(false);
    setNotice("");
  };
  const filtered = searchResult
    ? records
    : records.filter(
        (e) =>
          (!query ||
            `${e.content} ${e.file} ${e.actor_entities.join(" ")}`
              .toLowerCase()
              .includes(query.toLowerCase())) &&
          (owner === "All" || e.owner === owner || e.actor_entities.includes(owner)) &&
          (kind === "All" || e.action === kind) &&
          (identifier === "All" || e.identifiers?.includes(identifier)) &&
          (sourceId === "All" || String(e.evidence_id) === sourceId) &&
          (day === "All" ||
            (e.timestamp_utc ? localDay(e.timestamp_utc) : null) === day),
      );
  const actors = Array.from(
    new Set(records.flatMap((e) => e.actor_entities)),
  ).sort();
  const actions = Array.from(new Set(records.map((e) => e.action))).sort();
  const identifiers = Array.from(
    new Set(records.flatMap((e) => e.identifiers ?? [])),
  ).sort();
  const dates = Array.from(
    new Set(
      records.flatMap((e) =>
        e.timestamp_utc ? [localDay(e.timestamp_utc)] : [],
      ),
    ),
  ).sort();
  const recordButton = (e: RecordEvent) => (
    <button
      className={styles.eventButton}
      onClick={() => open({ file: e.evidence_id, ref: e.raw_ref }, e)}
    >
      <span>{time(e.timestamp_utc)}</span>
      <strong>{e.content}</strong>
      <small>
        {short(e.file)} · {e.raw_ref}
      </small>
    </button>
  );
  const source = (id: number) => sources.find((f) => f.id === id);
  async function verifyFile(f: Source) {
    setChecks((c) => ({ ...c, [f.id]: "Checking…" }));
    try {
      if (isDemo) {
        const response = await fetch(
          `./demo-evidence/${encodeURIComponent(f.file)}`,
        );
        if (!response.ok) throw Error();
        const valid = (await sha256(await response.arrayBuffer())) === f.sha256;
        setChecks((c) => ({
          ...c,
          [f.id]: valid ? "Hash matches" : "HASH MISMATCH",
        }));
      } else {
        const result = await verifyLiveIntegrity(
          data.evidence.find((e) => e.sha256 === f.sha256)?.id ?? f.id,
        );
        setChecks((c) => ({
          ...c,
          [f.id]: result.valid ? "Hash matches" : "HASH MISMATCH",
        }));
      }
    } catch {
      setChecks((c) => ({ ...c, [f.id]: "Verification unavailable" }));
    }
  }
  function questionCard(f: Finding) {
    return (
      <article className={styles.questionCard} key={f.id}>
        <div className={styles.cardTitle}>
          <h2>{f.question}</h2>
          <span
            className={`${styles.status} ${statusClass(findingStatuses[f.id] ?? f.status)}`}
          >
            {findingStatuses[f.id] ?? f.status}
          </span>
        </div>
        <button
          className={styles.claim}
          onClick={() =>
            setDetail({
              title: f.question,
              text: f.answer + "\n\n" + f.limits,
              citations: f.citations,
            })
          }
        >
          {f.answer}
          <ChevronRight />
        </button>
        {cites(f.citations)}
        <p className={styles.limit}>{f.limits}</p>
      </article>
    );
  }
  const eventList = (items: RecordEvent[]) =>
    items.length ? (
      <div className={styles.eventList}>
        {items.map((e) => (
          <div key={e.id}>{recordButton(e)}</div>
        ))}
      </div>
    ) : (
      <p className={styles.empty}>
        No matching records in the supplied sources.
      </p>
    );
  const scenarioGuard = (children: ReactNode) =>
    isScenario ? (
      children
    ) : (
      <section className={styles.panel}>
        <h2>Source-linked view planned for this case</h2>
        <p>
          Scenario-specific analysis is available only for the synthetic
          evidence pack. Your uploaded records are available in Evidence and
          Explore; no demo findings are applied to this case.
        </p>
        <button onClick={() => go("Explore")}>
          Explore uploaded records <ArrowRight />
        </button>
      </section>
    );
  const activeEvent = dated[replay];
  function mapView(atTime?: string | null) {
    const gps = records.filter(
      (e) =>
        e.evidence_id === 7 &&
        e.location?.lat !== undefined &&
        (!atTime ||
          !e.timestamp_utc ||
          new Date(e.timestamp_utc).getTime() <= new Date(atTime).getTime()),
    );
    const allGps = records.filter(
      (e) => e.evidence_id === 7 && e.location?.lat !== undefined,
    );
    const lats = allGps.map((e) => Number(e.location?.lat)),
      lons = allGps.map((e) => Number(e.location?.lon));
    const minLat = Math.min(...lats),
      maxLat = Math.max(...lats),
      minLon = Math.min(...lons),
      maxLon = Math.max(...lons);
    const points = gps.map((e) => ({
      event: e,
      x:
        35 +
        ((Number(e.location?.lon) - minLon) /
          Math.max(0.0001, maxLon - minLon)) *
          340,
      y:
        240 -
        ((Number(e.location?.lat) - minLat) /
          Math.max(0.0001, maxLat - minLat)) *
          200,
    }));
    return (
      <>
        <p className={styles.note}>
          Schematic GPS plot · synthetic coordinates · no external map or
          inferred suspect location.
        </p>
        <svg
          className={styles.map}
          viewBox="0 0 420 280"
          role="img"
          aria-label="Complainant GPS trail"
        >
          <path
            d={points.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" ")}
            fill="none"
            className={styles.path}
          />
          {points.map((p, i) => (
            <g
              key={p.event.id}
              role="button"
              tabIndex={0}
              aria-label={`GPS record ${i + 1}: ${time(p.event.timestamp_utc)}`}
              onClick={() => open({ file: 7, ref: p.event.raw_ref }, p.event)}
              onKeyDown={(e) => {
                if (e.key === "Enter")
                  open({ file: 7, ref: p.event.raw_ref }, p.event);
              }}
            >
              <circle cx={p.x} cy={p.y} r="7" />
              <text x={p.x + 10} y={p.y - 8}>
                {i + 1}
              </text>
            </g>
          ))}
        </svg>
      </>
    );
  }
  function flow(atTime?: string | null) {
    const rows = source(5)?.table ?? [];
    const visible = atTime
      ? rows.filter(
          (r) => new Date(r.timestamp).getTime() <= new Date(atTime).getTime(),
        )
      : rows;
    const victimRows =
      source(3)?.table?.filter(
        (r) =>
          r.counterparty === "arjun.collect@demo" &&
          (!atTime ||
            new Date(r.timestamp).getTime() <= new Date(atTime).getTime()),
      ) ?? [];
    const victimTotal = victimRows.reduce((n, r) => n + Number(r.amount), 0);
    if (atTime && victimTotal === 0)
      return (
        <p className={styles.note}>
          No matching case payment recorded at the replay cursor yet.
        </p>
      );
    return (
      <div className={styles.flow}>
        <button onClick={() => open({ file: 3, ref: "line:4" })}>
          Riya’s statement
          <br />
          <strong>
            {money(victimTotal)} in {victimRows.length} debits
          </strong>
        </button>
        <ArrowRight />
        <button onClick={() => open({ file: 5, ref: "line:2" })}>
          Collection account
          <br />
          <strong>DEMO-ACCT-COLLECT-009</strong>
        </button>
        <div className={styles.flowBranches}>
          {visible
            .filter((r) => r.type === "debit")
            .map((r) => (
              <button
                key={r.utr}
                onClick={() =>
                  open({ file: 5, ref: `line:${rows.indexOf(r) + 2}` })
                }
              >
                {r.counterparty}
                <strong>{money(r.amount)}</strong>
                <small>{time(r.timestamp)}</small>
              </button>
            ))}
        </div>
      </div>
    );
  }
  function bankTable(id: number) {
    const f = source(id);
    return (
      <section className={styles.panel}>
        <h2>{id === 3 ? "Complainant statement" : "Collection statement"}</h2>
        <div className={styles.tableWrap}>
          <table>
            <thead>
              <tr>
                <th>Time · IST</th>
                <th>Direction</th>
                <th>Counterparty</th>
                <th>Amount</th>
                <th>Balance</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {f?.table?.map((r, i) => (
                <tr key={r.utr}>
                  <td>
                    <button
                      onClick={() => open({ file: id, ref: `line:${i + 2}` })}
                    >
                      {time(r.timestamp)}
                    </button>
                  </td>
                  <td>{r.type}</td>
                  <td>
                    <button
                      onClick={() => open({ file: id, ref: `line:${i + 2}` })}
                    >
                      {r.counterparty}
                    </button>
                  </td>
                  <td>
                    <button
                      onClick={() => open({ file: id, ref: `line:${i + 2}` })}
                    >
                      {money(r.amount)}
                    </button>
                  </td>
                  <td>
                    <button
                      onClick={() => open({ file: id, ref: `line:${i + 2}` })}
                    >
                      {money(r.balance)}
                    </button>
                  </td>
                  <td>{cite({ file: id, ref: `line:${i + 2}` })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    );
  }
  function exportReport() {
    const bundle = {
      format: "parakh-review-bundle-v1",
      synthetic: isDemo,
      case_title: isScenario ? "Riya: investment scam complaint" : title,
      created_at: new Date().toISOString(),
      notice:
        "Investigator review draft. No legal attestation. Local finding statuses and exhibit selection are not persisted to the backend.",
      evidence: sources.map(({ rows: _, table: _table, ...f }) => f),
      findings: isScenario
        ? findings.map((f) => ({
            ...f,
            status: findingStatuses[f.id] ?? f.status,
          }))
        : [],
      exhibits,
      source_exhibits: sourceExhibits,
      custody: isDemo ? demo.audit : [],
      custody_notice: isDemo
        ? demo.notice
        : "Backend custody entries are not included in this dashboard response.",
      events: records,
    };
    download("parakh-review-bundle.json", JSON.stringify(bundle, null, 2));
    setNotice(
      "Review bundle exported. Original files are separate; export audit logging is planned.",
    );
  }
  function exportVerifier() {
    download(
      "verify_parakh.py",
      `"""Verify source bytes and, when present, the explicitly simulated demo chain.\nNo signatures or acquisition truth are certified.\nUsage: python3 verify_parakh.py parakh-review-bundle.json /path/to/evidence\n"""\nimport sys,json,hashlib\nfrom pathlib import Path\nreport=json.loads(Path(sys.argv[1]).read_text())\nfolder=Path(sys.argv[2]); failures=[]\nfor item in report['evidence']:\n p=folder/Path(item['file']).name\n if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']: failures.append(item['file'])\nprevious='0'*64\nfor entry in report.get('custody',[]):\n data={k:v for k,v in entry.items() if k!='entry_hash'}\n digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()\n if data['previous_hash']!=previous or digest!=entry['entry_hash']: failures.append('demo custody entry '+str(entry['sequence']))\n previous=entry['entry_hash']\nif failures: print('FAIL:', ', '.join(failures)); sys.exit(1)\nprint('PASS: original file hashes match the exported manifest.')\nprint('Demo chain entries checked:',len(report.get('custody',[])))\nprint('No legal attestation, signatures, or acquisition truth verified.')\n`,
      "text/x-python",
    );
  }
  const drawerSource = detail?.citation
    ? sources.find((f) => f.id === detail.citation!.file)
    : undefined;
  const selectedRaw = drawerSource?.rows.find(
    (r) =>
      r.ref === detail?.citation?.ref ||
      r.ref === detail?.citation?.ref?.replace("row:", "line:"),
  );
  const selectedEvent =
    detail?.event ??
    records.find(
      (e) =>
        e.evidence_id === detail?.citation?.file &&
        (e.raw_ref === detail?.citation?.ref ||
          e.raw_ref === detail?.citation?.ref?.replace("line:", "row:")),
    );
  const adjacent = selectedEvent
    ? dated.filter((e) => e.file === selectedEvent.file)
    : [];
  const adjacentIndex = adjacent.findIndex((e) => e.id === selectedEvent?.id);
  return (
    <div className={styles.workspace}>
      <header className={styles.header}>
        <button
          className={styles.iconButton}
          aria-label="Toggle navigation"
          onClick={() => setNav(!nav)}
        >
          <Menu />
        </button>
        <a href="./index.html" className={styles.brand}>
          P <span>Parakh</span>
        </a>
        <div className={styles.caseName} title={`Case ${caseId ?? "DEMO"}`}>
          <strong>
            {isScenario ? "Riya: investment scam complaint" : title}
          </strong>
          <small>
            {isDemo
              ? "Synthetic demo data"
              : isScenario
                ? "Synthetic evidence pack · signed in"
                : "Investigation workspace"}
          </small>
        </div>
        <button
          onClick={() => setCustody(true)}
          className={`${styles.integrity} ${chain === false ? styles.broken : chain === true ? styles.verified : styles.unchecked}`}
        >
          {chain === false ? <ShieldX /> : <ShieldCheck />}
          {chain === true
            ? "Chain verified"
            : chain === false
              ? "Chain broken"
              : "Chain not verified"}
        </button>
        <label className={styles.search}>
          <Search />
          <input
            ref={search}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              go("Explore");
            }}
            placeholder="Search all records…"
            aria-label="Global search"
          />
          <kbd>⌘K</kbd>
        </label>
        <span className={styles.zone}>IST · UTC+05:30</span>
        <button
          className={styles.user}
          onClick={onSignOut}
          title="Return to sign-in"
        >
          <strong>{person.name}</strong>
          <small>{person.role}</small>
        </button>
        <button
          className={styles.assistantToggle}
          onClick={() => setAssistant(!assistant)}
          aria-expanded={assistant}
        >
          <Sparkles />
          Assistant
        </button>
      </header>
      <div className={styles.body}>
        <nav
          className={`${styles.nav} ${nav ? styles.navOpen : ""}`}
          aria-label="Case navigation"
        >
          <p>Investigator workspace</p>
          {views.map((v, i) => (
            <button
              key={v}
              aria-current={view === v ? "page" : undefined}
              onClick={() => go(v)}
            >
              <span>{String(i + 1).padStart(2, "0")}</span>
              {v}
            </button>
          ))}
          <button className={styles.newCase} onClick={onNew}>
            <FolderOpen />
            Active Cases
          </button>
          <small>
            Upload → Review → Investigate
            <br />
            {isDemo
              ? "Local demo review session"
              : "Authenticated case session"}
          </small>
        </nav>
        <main className={styles.main}>
          <div className={styles.viewHeader}>
            <div>
              <p>
                {isScenario
                  ? "Source-linked investigation"
                  : "Uploaded case records"}{" "}
                / {view}
              </p>
              <h1>
                {view === "Evidence"
                  ? "Evidence & custody"
                  : view === "Map"
                    ? "Map & telecom"
                    : view === "Timeline"
                      ? "Timeline & Replay"
                      : view === "Authenticity"
                        ? "Authenticity & contradictions"
                        : view}
              </h1>
            </div>
            <span className={styles.viewLabel}>
              {isDemo
                ? "Synthetic demo"
                : isScenario
                  ? "Synthetic case review"
                  : "Live case"}
            </span>
          </div>
          {notice && (
            <p className={styles.notice} role="status">
              {notice}
            </p>
          )}
          {view === "Overview" && (
            <>
              <p className={styles.intro}>
                Four questions. Answers tied to the supplied records. Open any
                answer or source chip to inspect its receipt.
              </p>
              {isScenario ? (
                <div className={styles.questionGrid}>
                  {findings.slice(0, 4).map(questionCard)}
                </div>
              ) : (
                <section className={styles.panel}>
                  <h2>No scenario findings applied</h2>
                  <p>
                    Review uploaded sources before recording a conclusion.
                    Automatic question answering for arbitrary cases is planned.
                  </p>
                  <button onClick={() => go("Explore")}>Open Explore</button>
                </section>
              )}
              <div className={styles.metrics}>
                <button onClick={() => go("Evidence")}>
                  <strong>{sources.length}</strong>
                  <span>Evidence files</span>
                </button>
                <button onClick={() => go("Explore")}>
                  <strong>{records.length}</strong>
                  <span>Parsed source records · includes notices</span>
                </button>
                <button onClick={() => go("Findings")}>
                  <strong>{isScenario ? findings.length : 0}</strong>
                  <span>Review findings {isScenario && "· curated demo"}</span>
                </button>
                <button onClick={() => setCustody(true)}>
                  <strong>
                    {chain === true
                      ? "Verified"
                      : chain === false
                        ? "Broken"
                        : "Unchecked"}
                  </strong>
                  <span>
                    {isDemo ? "Simulated demo chain" : "Backend chain status"}
                  </span>
                </button>
              </div>
              <section className={styles.panel}>
                <h2>Source coverage</h2>
                <p className={styles.note}>
                  Counts include provenance notes and duplicate document
                  representations. They are not independent corroboration.
                </p>
                <div className={styles.coverage}>
                  {sources.map((f) => (
                    <button
                      key={f.id}
                      onClick={() => {
                        setSourceId(String(f.id));
                        go("Explore");
                      }}
                    >
                      <span>{short(f.file)}</span>
                      <strong>
                        {records.filter((e) => e.evidence_id === f.id).length}{" "}
                        records
                      </strong>
                    </button>
                  ))}
                </div>
              </section>
              {isScenario && (
                <section className={`${styles.panel} ${styles.warning}`}>
                  <h2>Data-quality decisions remain visible</h2>
                  <button
                    className={styles.claim}
                    onClick={() => open({ file: 13, ref: "line:9" })}
                  >
                    Tablet clock observed 30 minutes slow. Historical correction
                    assumes a constant offset.
                  </button>
                  {cites([
                    { file: 2, ref: "line:1" },
                    { file: 13, ref: "line:9" },
                  ])}
                  <button
                    className={styles.claim}
                    onClick={() => open({ file: 14, ref: "line:1" })}
                  >
                    The tablet is a selected excerpt; gaps do not demonstrate
                    deleted messages. Statement CSV and PDF duplicate one
                    source.
                  </button>
                  {cites([
                    { file: 14, ref: "line:1" },
                    { file: 3, ref: "line:1" },
                    { file: 4, ref: "page:1" },
                  ])}
                  <p>
                    Untimed records remain untimed. Day-first WhatsApp dates and
                    IST are parser assumptions for this fixture; an ambiguous
                    date-resolution workflow is planned.
                  </p>
                </section>
              )}
            </>
          )}
          {view === "Evidence" && (
            <>
              <p className={styles.intro}>
                A matching hash proves the file is unchanged, not that it’s
                true.
              </p>
              <div className={styles.toolbar}>
                <button onClick={() => setCustody(true)}>
                  <ShieldCheck />
                  Open custody log
                </button>
                <button
                  onClick={() => {
                    void Promise.all(sources.map(verifyFile));
                  }}
                >
                  Verify all file hashes
                </button>
                <button onClick={onNew}>Back to Active Cases</button>
              </div>
              <section className={styles.panel}>
                <div className={styles.tableWrap}>
                  <table>
                    <thead>
                      <tr>
                        <th>Original file / SHA-256</th>
                        <th>Source / owner</th>
                        <th>Parser / status</th>
                        <th>Records</th>
                        <th>Integrity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sources.map((f) => (
                        <tr key={f.id}>
                          <td>
                            <button
                              className={styles.fileLink}
                              onClick={() => open({ file: f.id })}
                            >
                              {f.file}
                            </button>
                            <button
                              className={styles.hash}
                              onClick={() => open({ file: f.id })}
                            >
                              {f.sha256}
                            </button>
                          </td>
                          <td>
                            {f.source}
                            <small>{f.owner}</small>
                          </td>
                          <td>
                            {f.parser}
                            <small>
                              {isScenario
                                ? "Parsed · review assumptions"
                                : "Parser metadata unavailable"}
                            </small>
                          </td>
                          <td>
                            <button
                              onClick={() => {
                                setSourceId(String(f.id));
                                go("Explore");
                              }}
                            >
                              {
                                records.filter((e) => e.evidence_id === f.id)
                                  .length
                              }
                            </button>
                          </td>
                          <td>
                            <button onClick={() => verifyFile(f)}>
                              Verify
                            </button>
                            <small
                              className={
                                checks[f.id] === "HASH MISMATCH"
                                  ? styles.danger
                                  : styles.note
                              }
                            >
                              {checks[f.id] ?? "Not checked this session"}
                            </small>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <p className={styles.note}>
                Demo originals are locally bundled copies of the synthetic pack.
                Signed-in verification requests the backend vault integrity
                check for the matching evidence hash. Re-import and editable
                owner/device assignments are planned.
              </p>
            </>
          )}
          {view === "Explore" && (
            <>
              <div className={styles.filters}>
                <label>
                  Owner
                  <select
                    value={owner}
                    onChange={(e) => setOwner(e.target.value)}
                  >
                    <option>All</option>
                    {actors.map((a) => (
                      <option key={a}>{a}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Type
                  <select
                    value={kind}
                    onChange={(e) => setKind(e.target.value)}
                  >
                    <option>All</option>
                    {actions.map((a) => (
                      <option key={a}>{a}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Source
                  <select
                    value={sourceId}
                    onChange={(e) => setSourceId(e.target.value)}
                  >
                    <option>All</option>
                    {sources.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.file}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  IST day
                  <select value={day} onChange={(e) => setDay(e.target.value)}>
                    <option>All</option>
                    {dates.map((d) => (
                      <option key={d}>{d}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Identifier
                  <select
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                  >
                    <option>All</option>
                    {identifiers.map((value) => (
                      <option key={value}>{value}</option>
                    ))}
                  </select>
                </label>
                <label>
                  App
                  <select value={app} onChange={(e) => setApp(e.target.value)}>
                    <option>All</option>
                    {(searchResult?.facets.apps ?? []).map((item) => (
                      <option key={item.value} value={item.value}>{item.value} ({item.count})</option>
                    ))}
                  </select>
                </label>
                <label>
                  Device
                  <select value={device} onChange={(e) => setDevice(e.target.value)}>
                    <option>All</option>
                    {(searchResult?.facets.devices ?? []).map((item) => (
                      <option key={item.value} value={item.value}>{item.value} ({item.count})</option>
                    ))}
                  </select>
                </label>
                <label>
                  Party
                  <select value={party} onChange={(e) => setParty(e.target.value)}>
                    <option>All</option>
                    {(searchResult?.facets.parties ?? []).map((item) => (
                      <option key={item.value} value={item.value}>{item.value} ({item.count})</option>
                    ))}
                  </select>
                </label>
                <label>
                  Tag
                  <select value={tag} onChange={(e) => setTag(e.target.value)}>
                    <option>All</option>
                    {(searchResult?.facets.tags ?? []).map((item) => (
                      <option key={item.value} value={item.value}>{item.value} ({item.count})</option>
                    ))}
                  </select>
                </label>
                <label>
                  Deleted / recovered
                  <select value={deleted} onChange={(e) => setDeleted(e.target.value)}>
                    <option value="all">All</option>
                    <option value="recovered">Recovered only</option>
                    <option value="current">Current only</option>
                  </select>
                </label>
                <label>
                  Regex <span className={styles.note}>(guarded)</span>
                  <input
                    value={regex}
                    onChange={(e) => setRegex(e.target.value)}
                    placeholder="Optional pattern"
                  />
                </label>
                <button
                  onClick={() => {
                    setOwner("All");
                    setKind("All");
                    setSourceId("All");
                    setDay("All");
                    setIdentifier("All");
                    setApp("All");
                    setDevice("All");
                    setParty("All");
                    setTag("All");
                    setDeleted("all");
                    setRegex("");
                    setQuery("");
                  }}
                >
                  Clear filters
                </button>
              </div>
              {searchError && <p role="alert" className={styles.warning}>{searchError}</p>}
              {searchResult && (
                <p className={styles.note}>
                  {searchResult.search_engine} · Shared filters are saved in the URL. Multilingual embeddings: {searchResult.semantic_search.status.replaceAll("_", " ")}.
                </p>
              )}
              <section className={styles.panel}>
                <div className={styles.cardTitle}>
                  <h2>Time histogram</h2>
                  <button
                    onClick={() =>
                      setDetail({
                        title: "Filtered record count",
                        text: `${filtered.length} records match the current filters. Includes untimed provenance records and repeated representations.`,
                        citations: Array.from(
                          new Set(filtered.map((e) => e.evidence_id)),
                        ).map((file) => ({ file })),
                      })
                    }
                  >
                    {filtered.length} matching records
                  </button>
                </div>
                <div className={styles.histogram}>
                  {dates.map((d) => {
                    const count = filtered.filter(
                      (e) =>
                        (e.timestamp_utc ? localDay(e.timestamp_utc) : null) ===
                        d,
                    ).length;
                    return (
                      <button
                        key={d}
                        onClick={() => setDay(day === d ? "All" : d)}
                      >
                        <span
                          style={{
                            height: Math.max(
                              4,
                              (count / Math.max(1, filtered.length)) * 90,
                            ),
                          }}
                        />
                        <strong>{count}</strong>
                        <small>{d}</small>
                      </button>
                    );
                  })}
                </div>
                <p className={styles.note}>
                  Buckets and displayed times use IST. Untimed records have no
                  invented timestamp.
                </p>
              </section>
              <section className={styles.panel}>
                <h2>Event table</h2>
                {filtered.length > 500 ? (
                  <VirtualList items={filtered}>
                    {(event) => recordButton(event)}
                  </VirtualList>
                ) : (
                <div className={`${styles.tableWrap} ${styles.tableScroll}`}>
                  <table aria-label="Filtered source events">
                    <thead>
                      <tr>
                        <th>Time · IST</th>
                        <th>Type</th>
                        <th>Record</th>
                        <th>Source reference</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((e) => (
                        <tr key={e.id}>
                          <td>
                            <button
                              onClick={() =>
                                open({ file: e.evidence_id, ref: e.raw_ref }, e)
                              }
                            >
                              {time(e.timestamp_utc)}
                            </button>
                          </td>
                          <td>{e.action}</td>
                          <td>
                            <button
                              className={styles.claim}
                              onClick={() =>
                                open({ file: e.evidence_id, ref: e.raw_ref }, e)
                              }
                            >
                              {e.content}
                            </button>
                          </td>
                          <td>
                            <button
                              onClick={() =>
                                open({ file: e.evidence_id, ref: e.raw_ref }, e)
                              }
                            >
                              {e.file} · {e.raw_ref}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!filtered.length && (
                    <p className={styles.empty}>No matching records.</p>
                  )}
                </div>
                )}
              </section>
            </>
          )}
          {view === "Comms" &&
            scenarioGuard(
              <>
                <div className={styles.toolbar}>
                  <button
                    aria-pressed={english}
                    onClick={() => setEnglish(!english)}
                  >
                    {english
                      ? "Show original Hinglish"
                      : "English assistance · demo"}
                  </button>
                  <span className={styles.note}>
                    Curated phrase translations only; original text remains in
                    the source drawer.
                  </span>
                </div>
                <div className={styles.twoColumns}>
                  <section className={styles.panel}>
                    <h2>Primary WhatsApp thread</h2>
                    <p className={styles.note}>
                      Highlighted phrases are review cues, not a fraud verdict.
                    </p>
                    <div className={styles.thread}>
                      {records
                        .filter(
                          (e) => e.evidence_id === 1 && e.actor_entities.length,
                        )
                        .map((e) => (
                          <button
                            key={e.id}
                            onClick={() => open({ file: 1, ref: e.raw_ref }, e)}
                          >
                            <small>
                              {e.actor_entities.join(", ")} ·{" "}
                              {time(e.timestamp_utc)}
                            </small>
                            <span>
                              {(english
                                ? e.content.replace(
                                    "OTP bhejo, jaldi.",
                                    "Send the OTP, quickly. [curated translation]",
                                  )
                                : e.content
                              )
                                .split(
                                  /(guaranteed|OTP|urgent|release fee|do not contact|limited slots)/gi,
                                )
                                .map((s, i) =>
                                  /^(guaranteed|OTP|urgent|release fee|do not contact|limited slots)$/i.test(
                                    s,
                                  ) ? (
                                    <mark key={i}>{s}</mark>
                                  ) : (
                                    s
                                  ),
                                )}
                            </span>
                            <small>{e.raw_ref}</small>
                          </button>
                        ))}
                    </div>
                  </section>
                  <section className={styles.panel}>
                    <h2>Linked-device excerpt</h2>
                    <p className={styles.warning}>
                      Raw timestamps are preserved. Matched text is 30 minutes
                      earlier on the tablet. Missing messages are outside the
                      selected excerpt, not proven deletions.
                    </p>
                    {records
                      .filter(
                        (e) => e.evidence_id === 2 && e.actor_entities.length,
                      )
                      .map((e) => {
                        const match = records.find(
                          (a) => a.evidence_id === 1 && a.content === e.content,
                        );
                        return (
                          <article className={styles.comparison} key={e.id}>
                            {recordButton(e)}
                            <span>
                              Android match:{" "}
                              {match ? (
                                <button
                                  onClick={() =>
                                    open({ file: 1, ref: match.raw_ref }, match)
                                  }
                                >
                                  {time(match.timestamp_utc)}
                                </button>
                              ) : (
                                "No exact body match"
                              )}
                            </span>
                            <small>
                              Correction under constant-offset assumption: +30
                              minutes.
                            </small>
                          </article>
                        );
                      })}
                    {cites([{ file: 13, ref: "line:9" }])}
                  </section>
                </div>
                <section className={styles.panel}>
                  <h2>Emails & browser history</h2>
                  {eventList(
                    records.filter((e) => [10, 11, 12].includes(e.evidence_id)),
                  )}
                </section>
              </>,
            )}
          {view === "Money" &&
            scenarioGuard(
              <>
                <section className={styles.panel}>
                  <h2>Recorded account flow</h2>
                  {flow()}
                  <p className={styles.note}>
                    Account-level statement flow. Edges do not establish legal
                    ownership or unique per-rupee attribution.
                  </p>
                  {cites(findings[1].citations)}
                </section>
                <div className={styles.threeColumns}>
                  {[
                    {
                      title: "Directly shown",
                      text: "Two complainant debits, matching collection credits, and onward collection outflows are recorded.",
                      cs: findings[1].citations,
                    },
                    {
                      title: "Possible under stated assumptions",
                      text: "With zero opening balance and complete coverage, onward outflows depend collectively on these inflows. No unique allocation of either ₹25,000 payment is established.",
                      cs: findings[4].citations,
                    },
                    {
                      title: "Unexplained",
                      text: "Legal control of the accounts, the final recipients and recovery are not established by the supplied statements.",
                      cs: [{ file: 5, ref: "line:1" }],
                    },
                  ].map((g) => (
                    <section className={styles.panel} key={g.title}>
                      <h2>{g.title}</h2>
                      <button
                        className={styles.claim}
                        onClick={() =>
                          setDetail({
                            title: g.title,
                            text: g.text,
                            citations: g.cs,
                          })
                        }
                      >
                        {g.text}
                      </button>
                      {cites(g.cs)}
                    </section>
                  ))}
                </div>
                {bankTable(3)}
                {bankTable(5)}
                <section className={styles.panel}>
                  <h2>Same statement, second representation</h2>
                  <p>
                    The PDF repeats the complainant statement; do not count it
                    as independent corroboration.
                  </p>
                  {cites([
                    { file: 3, ref: "line:1" },
                    { file: 4, ref: "page:1" },
                  ])}
                </section>
              </>,
            )}
          {view === "Authenticity" &&
            scenarioGuard(
              <>
                <div className={styles.twoColumns}>
                  <section className={styles.panel}>
                    <h2>Claimed refund receipt</h2>
                    <button
                      className={styles.claim}
                      onClick={() => open({ file: 6, ref: "page:1" })}
                    >
                      {source(6)?.rows[0]?.text}
                    </button>
                    {cites([{ file: 6, ref: "page:1" }])}
                  </section>
                  <section className={styles.panel}>
                    <h2>Bank record with the same reference</h2>
                    <button
                      className={styles.claim}
                      onClick={() => open({ file: 3, ref: "line:4" })}
                    >
                      {source(3)?.rows.find((r) => r.ref === "line:4")?.text}
                    </button>
                    <span className={`${styles.status} ${styles.contradicted}`}>
                      Contradiction
                    </span>
                    <p>
                      No matching refund credit within the supplied statement
                      window. The receipt’s creator and intent are not
                      established by the mismatch alone.
                    </p>
                    {cites(findings[2].citations)}
                  </section>
                </div>
                <section className={styles.panel}>
                  <h2>Signals with reasons</h2>
                  {[
                    {
                      t: "Amount and direction",
                      b: "Receipt: ₹50,000 incoming refund. Same reference in bank: ₹25,000 outgoing debit.",
                      cs: [
                        { file: 6, ref: "page:1" },
                        { file: 3, ref: "line:4" },
                      ],
                    },
                    {
                      t: "Timing",
                      b: "Receipt claims 09:42 IST; bank debit is 09:25 IST. Changing a clock would not resolve the amount or direction.",
                      cs: [
                        { file: 6, ref: "page:1" },
                        { file: 3, ref: "line:4" },
                      ],
                    },
                    {
                      t: "Clock reconciliation · demo calculation",
                      b: "Ten exact message-body matches show the tablet 30 minutes earlier. Adding 30 minutes aligns those matched records if the observed offset remained constant. Raw timestamps remain unchanged.",
                      cs: [
                        { file: 1, ref: "line:2" },
                        { file: 2, ref: "line:2" },
                        { file: 13, ref: "line:9" },
                      ],
                    },
                  ].map((s) => (
                    <article className={styles.signal} key={s.t}>
                      <h3>{s.t}</h3>
                      <button
                        className={styles.claim}
                        onClick={() =>
                          setDetail({ title: s.t, text: s.b, citations: s.cs })
                        }
                      >
                        {s.b}
                      </button>
                      {cites(s.cs)}
                    </article>
                  ))}
                </section>
                <section className={styles.panel}>
                  <h2>Alternative explanations reviewed · curated demo</h2>
                  <div className={styles.tableWrap}>
                    <table>
                      <thead>
                        <tr>
                          <th>Alternative</th>
                          <th>What the supplied evidence supports</th>
                          <th>Receipt</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          [
                            "Altered or incorrect receipt",
                            "Consistent with a content mismatch; no independent document-forensics proof of editing.",
                            6,
                          ],
                          [
                            "Wrong device clock",
                            "Supported for tablet excerpt under a fixed-offset assumption. Does not fix payment amount/direction.",
                            13,
                          ],
                          [
                            "Different time zone",
                            "Source offsets are explicit in the bank records; time-zone conversion does not turn a debit into a credit.",
                            3,
                          ],
                          [
                            "Different transaction",
                            "Possible outside coverage; within this statement, the repeated reference identifies the earlier debit.",
                            3,
                          ],
                        ].map(([a, b, c]) => (
                          <tr key={String(a)}>
                            <td>{a}</td>
                            <td>
                              <button
                                onClick={() =>
                                  open({
                                    file: Number(c),
                                    ref: Number(c) === 6 ? "page:1" : "line:1",
                                  })
                                }
                              >
                                {b}
                              </button>
                            </td>
                            <td>
                              {cite({
                                file: Number(c),
                                ref: Number(c) === 6 ? "page:1" : "line:1",
                              })}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className={styles.note}>
                    No probability score, fake EXIF result or claim of an
                    automated forensic test is attached to these editorial
                    comparisons.
                  </p>
                </section>
              </>,
            )}
          {view === "Graph" &&
            scenarioGuard(
              <>
                <section className={styles.panel}>
                  <h2>Source-backed relationships</h2>
                  {flow()}
                  <div
                    className={`${styles.relationships} ${merged ? styles.grouped : ""}`}
                    role="group"
                    aria-label={
                      merged
                        ? "Locally grouped display name and payment identifier"
                        : "Separate source identities"
                    }
                  >
                    <button onClick={() => open({ file: 1, ref: "line:3" })}>
                      Agent Arjun · WhatsApp display name
                    </button>
                    <ArrowRight />
                    <button onClick={() => open({ file: 1, ref: "line:10" })}>
                      arjun.collect@demo · payment request
                    </button>
                    <ArrowRight />
                    <button onClick={() => open({ file: 3, ref: "line:4" })}>
                      Complainant statement counterparty
                    </button>
                  </div>
                  {cites([
                    { file: 1, ref: "line:10" },
                    { file: 3, ref: "line:4" },
                  ])}
                </section>
                <section className={styles.panel}>
                  <h2>Alias suggestions</h2>
                  {isDemo ? (
                    <>
                      <p>“Agent Arjun” and the payment identifier share a name token and occur in the payment request.</p>
                      <button disabled={readOnly} aria-pressed={merged} onClick={() => setMerged(!merged)}>
                        {merged ? "Undo local grouping" : "Group in this demo view"}
                      </button>
                    </>
                  ) : identityData ? (
                    <>
                      <p className={styles.note}>
                        {identityData.matcher.kind} v{identityData.matcher.version} · ML {identityData.matcher.ml_status.replaceAll("_", " ")} · {identityData.matcher.labels_recorded} investigator labels. {identityData.matcher.limits}
                      </p>
                      <div className={styles.aliasList}>
                        {identityData.suggestions.slice(0, 12).map((suggestion) => (
                          <article key={suggestion.id}>
                            <div>
                              <strong>{suggestion.party} ↔ {suggestion.identifier}</strong>
                              <span>{Math.round(suggestion.confidence * 100)}% heuristic confidence · {suggestion.status}</span>
                              <small>{suggestion.reasons.join(" · ")}</small>
                              {suggestion.feedback_bonus > 0 && <small>Ranking feedback bonus +{Math.round(suggestion.feedback_bonus * 100)}%</small>}
                            </div>
                            <button
                              disabled={readOnly}
                              onClick={async () => {
                                if (!caseId) return;
                                if (suggestion.status === "confirmed") await unmergeAlias(caseId, suggestion.id);
                                else await confirmAlias(caseId, suggestion.id);
                                setIdentityData(await getIdentities(caseId));
                              }}
                            >
                              {suggestion.status === "confirmed" ? "Unmerge" : "Confirm merge"}
                            </button>
                          </article>
                        ))}
                      </div>
                    </>
                  ) : <p role="status">Preparing identity suggestions…</p>}
                </section>
              </>,
            )}
          {view === "Map" &&
            scenarioGuard(
              <>
                <section className={styles.panel}>
                  <h2>Complainant GPS trail</h2>
                  {mapView()}
                  {cites([{ file: 7, ref: "line:1" }])}
                  <p className={styles.warning}>
                    Being near each other does not prove co-location. This pack
                    contains no suspect GPS or suspect subscriber-location
                    disclosure.
                  </p>
                </section>
                <div className={styles.twoColumns}>
                  <section className={styles.panel}>
                    <h2>Call records</h2>
                    {eventList(records.filter((e) => e.evidence_id === 8))}
                    <p className={styles.note}>
                      Call metadata is not a transcript. Conversation contents
                      are not established.
                    </p>
                  </section>
                  <section className={styles.panel}>
                    <h2>Tower context</h2>
                    {eventList(records.filter((e) => e.evidence_id === 9))}
                    <p className={styles.note}>
                      Tower context is approximate and synthetic. A geographic
                      tower-radius overlay is planned.
                    </p>
                    {cites([
                      { file: 9, ref: "line:1" },
                      { file: 14, ref: "line:1" },
                    ])}
                  </section>
                </div>
              </>,
            )}
          {view === "Timeline" && (
            <>
              <section className={styles.panel}>
                <h2>Cited sequence</h2>
                <p className={styles.note}>
                  Raw source-time order in IST. Tablet timestamps are not
                  silently corrected. Untimed records remain available in
                  Explore.
                </p>
                <div className={styles.replayControls}>
                  <button
                    aria-label={playing ? "Pause replay" : "Play replay"}
                    onClick={() => setPlaying(!playing)}
                    disabled={!dated.length}
                  >
                    {playing ? <Pause /> : <Play />}
                  </button>
                  <input
                    type="range"
                    aria-label="Replay position"
                    min={0}
                    max={Math.max(0, dated.length - 1)}
                    value={replay}
                    onChange={(e) => {
                      setPlaying(false);
                      setReplay(Number(e.target.value));
                    }}
                  />
                  <button
                    onClick={() =>
                      activeEvent &&
                      open(
                        {
                          file: activeEvent.evidence_id,
                          ref: activeEvent.raw_ref,
                        },
                        activeEvent,
                      )
                    }
                  >
                    {time(activeEvent?.timestamp_utc)}
                  </button>
                  <span className={styles.viewLabel}>
                    Demo replay · source-time sync
                  </span>
                </div>
                {activeEvent && recordButton(activeEvent)}
              </section>
              {scenarioGuard(
                <div className={styles.threeColumns}>
                  <section className={styles.panel}>
                    <h2>Latest chat at cursor</h2>
                    {eventList(
                      dated
                        .filter(
                          (e) =>
                            e.evidence_id === 1 &&
                            new Date(e.timestamp_utc ?? 0).getTime() <=
                              new Date(
                                activeEvent?.timestamp_utc ?? 0,
                              ).getTime(),
                        )
                        .slice(-1),
                    )}
                  </section>
                  <section className={styles.panel}>
                    <h2>Recorded money at cursor</h2>
                    {flow(activeEvent?.timestamp_utc)}
                  </section>
                  <section className={styles.panel}>
                    <h2>GPS at cursor</h2>
                    {mapView(activeEvent?.timestamp_utc)}
                  </section>
                </div>,
              )}
              <section className={styles.panel}>
                <h2>Source events</h2>
                {eventList(dated)}
              </section>
            </>
          )}
          {view === "Findings" &&
            scenarioGuard(
              <>
                <p className={styles.intro}>
                  Curated demo findings for review. Status changes and exhibit
                  selection are local to this session; collaboration and
                  persisted review are planned.
                </p>
                {findings.map((f) => (
                  <section className={styles.finding} key={f.id}>
                    {questionCard(f)}
                    <div className={styles.findingActions}>
                      <label>
                        Review status
                        <select
                          disabled={readOnly}
                          aria-label={`Review status for ${f.id}`}
                          value={findingStatuses[f.id] ?? f.status}
                          onChange={(e) =>
                            setFindingStatuses((s) => ({
                              ...s,
                              [f.id]: e.target.value as FindingStatus,
                            }))
                          }
                        >
                          {[
                            "Established",
                            "Possible",
                            "Not established",
                            "Contradicted",
                          ].map((s) => (
                            <option key={s}>{s}</option>
                          ))}
                        </select>
                      </label>
                      <button
                        aria-pressed={exhibits.includes(f.id)}
                        onClick={() =>
                          setExhibits((cs) =>
                            cs.includes(f.id)
                              ? cs.filter((x) => x !== f.id)
                              : [...cs, f.id],
                          )
                        }
                      >
                        {exhibits.includes(f.id) ? <Check /> : <FileText />}
                        {exhibits.includes(f.id)
                          ? "Remove from exhibit tray"
                          : "Add to exhibit tray"}
                      </button>
                    </div>
                  </section>
                ))}
              </>,
            )}
          {view === "Reports" && (
            <>
              <section className={styles.panel}>
                <h2>Exhibit tray</h2>
                {exhibits.length ? (
                  exhibits.map((id) => {
                    const f = findings.find((f) => f.id === id)!;
                    return (
                      <article key={id}>
                        <button
                          className={styles.claim}
                          onClick={() =>
                            setDetail({
                              title: f.question,
                              text: f.answer,
                              citations: f.citations,
                            })
                          }
                        >
                          {f.id} · {f.question}
                        </button>
                        {cites(f.citations)}
                      </article>
                    );
                  })
                ) : (
                  <p>
                    No findings selected. Add findings or individual source
                    references to the tray before exporting your review.
                  </p>
                )}
                {sourceExhibits.map((c, i) => (
                  <div
                    className={styles.sourceExhibit}
                    key={`${c.file}-${c.ref}`}
                  >
                    {cite({
                      ...c,
                      label: `Source exhibit · ${source(c.file)?.file} · ${c.ref ?? "full file"}`,
                    })}
                    <button
                      aria-label={`Remove source exhibit ${i + 1}`}
                      onClick={() =>
                        setSourceExhibits((current) =>
                          current.filter((_, index) => index !== i),
                        )
                      }
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <button onClick={() => go("Findings")}>
                  Review findings <ArrowRight />
                </button>
              </section>
              <section className={styles.panel}>
                <h2>Export & independent verification</h2>
                <p>
                  Download a JSON review bundle with sources, hashes, cited
                  findings and selected exhibits. The Python verifier checks
                  original file hashes and any included simulated demo-chain
                  entries without Parakh.
                </p>
                <div className={styles.toolbar}>
                  <button onClick={exportReport}>
                    <Download />
                    Export review bundle
                  </button>
                  <button onClick={exportVerifier}>
                    <Download />
                    Download offline verifier
                  </button>
                </div>
                <code className={styles.code}>
                  python3 verify_parakh.py parakh-review-bundle.json
                  /path/to/evidence
                </code>
                <p className={styles.warning}>
                  Demo custody entries are explicitly simulated. Signed audit
                  entries, backend export audit logging, a zipped evidence
                  bundle and formatted court reports are planned.
                </p>
              </section>
              <section className={styles.panel}>
                <h2>
                  Section 63 draft{" "}
                  <span className={styles.viewLabel}>
                    Planned · verify with counsel
                  </span>
                </h2>
                <p>
                  Legal certificate generation is not implemented. A
                  counsel-reviewed workflow must establish the applicable
                  requirements, acquisition facts, responsible signatory and
                  supporting records before any certificate is issued.
                </p>
                <button disabled>Certificate draft · planned</button>
              </section>
            </>
          )}
        </main>
      </div>
      {assistant && (
        <aside
          className={styles.assistant}
          aria-label="Investigation assistant"
        >
          <div className={styles.cardTitle}>
            <h2>
              <Sparkles />
              Investigation assistant
            </h2>
            <button
              onClick={() => setAssistant(false)}
              aria-label="Close assistant"
            >
              <X />
            </button>
          </div>
          <span className={styles.viewLabel}>
            Curated demo answers · no language model
          </span>
          <p>
            Answers are limited to the supplied synthetic sources. A
            source-backed refusal is valid.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const q = question.toLowerCase();
              const result =
                !isScenario ||
                /legal|controll|recover|what.*call|said.*call/.test(q)
                  ? undefined
                  : /refund|receipt/.test(q)
                    ? findings[2]
                    : /where.*arjun|location|co.location/.test(q)
                      ? findings[5]
                      : /delet|tablet|clock/.test(q)
                        ? findings[6]
                        : /money|25000|25,000|transfer|payment/.test(q)
                          ? findings[1]
                          : /contact|who/.test(q)
                            ? findings[0]
                            : undefined;
              setAnswer(result ?? null);
              setRefusal(!result);
            }}
          >
            <label htmlFor="assistant-question">Ask about the evidence</label>
            <textarea
              id="assistant-question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              required
              placeholder="Does the receipt match the bank record?"
            />
            <button type="submit">
              Ask <ArrowRight />
            </button>
          </form>
          {answer && (
            <div className={styles.answer}>
              <span
                className={`${styles.status} ${statusClass(answer.status)}`}
              >
                {answer.status}
              </span>
              <button
                className={styles.claim}
                onClick={() =>
                  setDetail({
                    title: answer.question,
                    text: answer.answer,
                    citations: answer.citations,
                  })
                }
              >
                {answer.answer}
              </button>
              {cites(answer.citations)}
              <p className={styles.limit}>{answer.limits}</p>
            </div>
          )}
          {refusal && (
            <p role="status" className={styles.warning}>
              No supporting evidence found in this curated answer set. No answer
              is inferred from missing data. Open Explore to inspect the
              supplied records.
            </p>
          )}
        </aside>
      )}
      {detail && (
        <SourceDrawer
          detail={detail}
          source={drawerSource}
          raw={selectedRaw?.text}
          records={records}
          adjacent={
            adjacentIndex < 0
              ? []
              : adjacent.slice(
                  Math.max(0, adjacentIndex - 1),
                  adjacentIndex + 2,
                )
          }
          close={() => setDetail(null)}
          open={open}
          cites={cites}
          isScenario={isScenario}
          onExhibit={() => {
            if (detail.citation) {
              const selection = detail.citation;
              setSourceExhibits((current) =>
                current.some(
                  (c) => c.file === selection.file && c.ref === selection.ref,
                )
                  ? current
                  : [...current, selection],
              );
              setNotice("Source reference added to the exhibit tray.");
              setDetail(null);
            }
          }}
        />
      )}
      {custody && (
        <div className={styles.modalBackdrop} onClick={() => setCustody(false)}>
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Custody log"
            className={styles.custody}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.cardTitle}>
              <h2>Custody log</h2>
              <button
                onClick={() => setCustody(false)}
                aria-label="Close custody log"
              >
                <X />
              </button>
            </div>
            <p className={styles.warning}>
              {isDemo
                ? demo.notice
                : "Chain status comes from the backend dashboard. Full custody entries are not supplied by this endpoint; authenticated custody-log integration is planned."}
            </p>
            <p>
              Signed entries and acquisition attestations are planned. An
              unchanged file may still contain a false claim.
            </p>
            {!isDemo && caseAudit && (
              <div className={styles.auditList}>
                {caseAudit.entries.map((a) => (
                  <article key={a.id}>
                    <h3>{a.action}</h3>
                    <p>
                      {a.actor} · {time(a.created_at)}
                    </p>
                    <pre className={styles.raw}>
                      {JSON.stringify(a.payload, null, 2)}
                    </pre>
                    <code>Previous: {a.previous_hash}</code>
                    <code>Entry: {a.entry_hash}</code>
                  </article>
                ))}
              </div>
            )}
            {isDemo && (
              <>
                <button
                  onClick={async () => setChain(await verifyChain(demo.audit))}
                >
                  Re-check simulated chain
                </button>
                <div className={styles.auditList}>
                  {demo.audit.map((a) => (
                    <article key={a.sequence}>
                      <button
                        onClick={() => {
                          setCustody(false);
                          open({ file: a.sequence });
                        }}
                      >
                        {a.sequence}. {a.filename}
                      </button>
                      <p>
                        {a.action} · {a.actor} · {time(a.timestamp)}
                      </p>
                      <code>Previous: {a.previous_hash}</code>
                      <code>Entry: {a.entry_hash}</code>
                    </article>
                  ))}
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function SourceDrawer({
  detail,
  source,
  raw,
  records,
  adjacent,
  close,
  open,
  cites,
  isScenario,
  onExhibit,
}: {
  detail: Detail;
  source?: Source;
  raw?: string;
  records: RecordEvent[];
  adjacent: RecordEvent[];
  close: () => void;
  open: (c: Citation, e?: RecordEvent) => void;
  cites: (cs: Citation[]) => ReactNode;
  isScenario: boolean;
  onExhibit: () => void;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => previous?.focus();
  }, []);
  const [tab, setTab] = useState<"source" | "adjacent">("source");
  const event =
    detail.event ??
    records.find(
      (e) =>
        e.evidence_id === source?.id &&
        (e.raw_ref === detail.citation?.ref ||
          e.raw_ref === detail.citation?.ref?.replace("line:", "row:")),
    );
  return (
    <>
      <button
        className={styles.drawerBackdrop}
        onClick={close}
        aria-label="Close source details"
        tabIndex={-1}
      />
      <aside
        ref={ref}
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-label="Source receipt"
        onKeyDown={(e) => {
          if (e.key === "Tab") {
            const nodes = Array.from(
              ref.current?.querySelectorAll<HTMLElement>(
                'button,a,[tabindex="0"]',
              ) ?? [],
            );
            const first = nodes[0],
              last = nodes[nodes.length - 1];
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last?.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <div className={styles.cardTitle}>
          <h2>Source receipt</h2>
          <button onClick={close} aria-label="Close source details">
            <X />
          </button>
        </div>
        {detail.title && (
          <>
            <h3>{detail.title}</h3>
            <p className={styles.preserve}>{detail.text}</p>
            {cites(detail.citations ?? [])}
          </>
        )}
        {source && (
          <>
            <h3>{source.file}</h3>
            <dl>
              <dt>Reference</dt>
              <dd>{detail.citation?.ref ?? "Complete original source"}</dd>
              <dt>Source timestamp</dt>
              <dd>{time(event?.timestamp_utc)}</dd>
              <dt>Raw timestamp</dt>
              <dd>
                {event?.original_timestamp ?? "Not supplied for this selection"}
              </dd>
              <dt>Owner / source</dt>
              <dd>
                {source.owner} · {source.source}
              </dd>
              <dt>Parser</dt>
              <dd>{source.parser}</dd>
              <dt>SHA-256</dt>
              <dd className={styles.hash}>{source.sha256}</dd>
            </dl>
            <div className={styles.toolbar}>
              <button
                onClick={() => setTab("source")}
                aria-pressed={tab === "source"}
              >
                Original record
              </button>
              <button
                onClick={() => setTab("adjacent")}
                aria-pressed={tab === "adjacent"}
              >
                Adjacent events
              </button>
            </div>
            {tab === "source" ? (
              <>
                <pre className={styles.raw}>
                  {raw ??
                    event?.content ??
                    source.rows.map((r) => `${r.ref}  ${r.text}`).join("\n") ??
                    "Original source text is not provided by this endpoint."}
                </pre>
                <p className={styles.note}>{source.note}</p>
                {isScenario && (
                  <a
                    className={styles.original}
                    href={`./demo-evidence/${encodeURIComponent(source.file)}`}
                    download={source.file}
                  >
                    <Download />
                    Download original synthetic source
                  </a>
                )}
                <button onClick={onExhibit}>Add source to exhibit tray</button>
              </>
            ) : adjacent.length ? (
              <div className={styles.eventList}>
                {adjacent.map((e) => (
                  <button
                    key={e.id}
                    onClick={() =>
                      open({ file: e.evidence_id, ref: e.raw_ref }, e)
                    }
                  >
                    {time(e.timestamp_utc)} · {e.content}
                  </button>
                ))}
              </div>
            ) : (
              <p>
                No adjacent events for this selection. Select an event in
                Explore to inspect its neighbours.
              </p>
            )}
          </>
        )}
        <p className={styles.warning}>
          A matching hash proves byte consistency, not that the source’s claim
          is true.
        </p>
      </aside>
    </>
  );
}
