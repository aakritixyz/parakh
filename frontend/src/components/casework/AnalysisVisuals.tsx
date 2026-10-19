import { useId } from "react";
import type { CorrelationResult } from "../../caseApi";
import styles from "./Casework.module.css";

const colours = ["var(--chart-blue)", "var(--chart-teal)", "var(--chart-violet)", "var(--chart-amber)", "var(--chart-cyan)", "var(--chart-slate)"];

type SourceCount = { name: string; count: number; onSelect: () => void };
export function EvidenceComposition({ sources }: { sources: SourceCount[] }) {
  const total = sources.reduce((sum, item) => sum + item.count, 0);
  let offset = 0;
  const ranked = [...sources].sort((a, b) => b.count - a.count);
  return <section className={`${styles.panel} ${styles.analyticsPanel}`}>
    <div className={styles.cardTitle}><div><span className={styles.eyebrow}>EVIDENCE INTELLIGENCE</span><h2>Source distribution</h2></div><span className={styles.viewLabel}>Source-linked records</span></div>
    <div className={styles.compositionLayout}>
      <div className={styles.donutWrap}>
        <svg viewBox="0 0 220 220" role="img" aria-label={`${total} loaded records across ${sources.length} evidence files`}>
          <circle cx="110" cy="110" r="78" fill="none" stroke="var(--line)" strokeWidth="22" />
          {ranked.map((item, i) => {
            const fraction = total ? item.count / total : 0;
            const start = offset; offset += fraction * 100;
            return <circle key={item.name} cx="110" cy="110" r="78" pathLength="100" fill="none" stroke={colours[i % colours.length]} strokeWidth="22" strokeDasharray={`${fraction * 100} ${100 - fraction * 100}`} strokeDashoffset={-start} transform="rotate(-90 110 110)"><title>{item.name}: {item.count} records</title></circle>;
          })}
          <text x="110" y="108" textAnchor="middle" className={styles.donutValue}>{total.toLocaleString()}</text>
          <text x="110" y="132" textAnchor="middle" className={styles.donutLabel}>LOADED RECORDS</text>
        </svg>
      </div>
      <div className={styles.distributionBars}>{ranked.slice(0, 6).map((item, i) => <button key={item.name} onClick={item.onSelect}>
        <span className={styles.distributionName}>{item.name}</span><strong>{item.count}</strong>
        <span className={styles.distributionTrack}><span style={{ width: `${total ? item.count / total * 100 : 0}%`, background: colours[i % colours.length] }} /></span>
      </button>)}</div>
    </div>
    <p className={styles.note}>Counts reflect loaded records, including repeated representations. Select a source to inspect its evidence.</p>
  </section>;
}

type Node = CorrelationResult["graph"]["nodes"][number];
export function RelationshipGraph({ nodes, edges, path = [], onSelect, onSource }: {
  nodes: Node[]; edges: CorrelationResult["graph"]["edges"]; path?: string[];
  onSelect: (node: Node) => void; onSource: (evidenceId: number, reference: string) => void;
}) {
  const marker = useId().replaceAll(":", "");
  const ordered = [...nodes].sort((a, b) => b.importance - a.importance || a.id.localeCompare(b.id));
  const rings = Math.max(1, Math.ceil((ordered.length - 1) / 12));
  const height = Math.max(440, rings * 210 + 180);
  const centre = {x:490,y:height/2};
  const positions = new Map(ordered.map((node,index) => {
    if(index===0)return [node.id,centre] as const;
    const ring=Math.floor((index-1)/12);
    const count=Math.min(12,ordered.length-1-ring*12);
    const angle=((index-1)%12/count)*Math.PI*2-Math.PI/2;
    return [node.id,{x:centre.x+Math.cos(angle)*(240+ring*95),y:centre.y+Math.sin(angle)*(145+ring*105)}] as const;
  }));
  return <div className={styles.networkCanvas}>
    <div className={styles.networkToolbar}><span><i /> RELATIONSHIP ANALYSIS</span><span>Node size: relative importance · edge width: record count</span></div>
    {!nodes.length ? <p>No relationships are established by the current evidence selection.</p> : <svg viewBox={`0 0 980 ${height}`} role="group" aria-label="Evidence relationship network">
      <defs><pattern id={`${marker}-grid`} width="28" height="28" patternUnits="userSpaceOnUse"><path d="M 28 0 L 0 0 0 28" fill="none" stroke="var(--graph-grid)" strokeWidth="0.7"/></pattern><marker id={marker} viewBox="0 0 10 10" refX="23" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="var(--chart-slate)" /></marker></defs>
      <rect width="980" height={height} fill={`url(#${marker}-grid)`} />
      {edges.map((edge, i) => {
        const a = positions.get(edge.source), b = positions.get(edge.target);
        if (!a || !b) return null;
        const highlighted = path.some((id, index) => id === edge.source && path[index + 1] === edge.target);
        const open = () => { const source = edge.support[0]; if (source) onSource(source.evidence_id, source.reference); };
        return <g key={`${edge.source}-${edge.target}-${i}`} role={edge.support.length ? "button" : undefined} tabIndex={edge.support.length ? 0 : undefined} aria-label={`${edge.source} to ${edge.target}: ${edge.count} ${edge.relation} records`} onClick={open} onKeyDown={event => {if (event.key === "Enter" || event.key === " ") {event.preventDefault(); open();}}}>
          <path d={`M ${a.x} ${a.y} Q ${(a.x+b.x)/2} ${(a.y+b.y)/2-25} ${b.x} ${b.y}`} fill="none" stroke={highlighted ? "var(--chart-teal)" : "var(--graph-edge)"} strokeWidth={Math.min(7, 1.5 + Math.log2(1 + edge.count))} markerEnd={`url(#${marker})`} />
          <title>{edge.relation} · {edge.count} source records; select to inspect</title>
        </g>;
      })}
      {ordered.map(node => {
        const point = positions.get(node.id)!;
        const radius = Math.min(29, 16 + Math.sqrt(Math.max(0, node.importance)) * 13);
        const colour = colours[Math.abs(node.community) % colours.length];
        return <g key={node.id} role="button" tabIndex={0} aria-label={`${node.label}, ${node.type}, ${node.edge_count} links`} onClick={() => onSelect(node)} onKeyDown={event => {if (event.key === "Enter" || event.key === " ") {event.preventDefault(); onSelect(node);}}} className={styles.networkNode}>
          <circle cx={point.x} cy={point.y} r={radius+7} fill="var(--graph-halo)" stroke={colour} strokeOpacity="0.22" />
          <circle cx={point.x} cy={point.y} r={radius} fill={colour} stroke="var(--surface)" strokeWidth="2" />
          <text x={point.x} y={point.y+4} textAnchor="middle" className={styles.nodeGlyph}>{node.type === "account" ? "₹" : node.type === "party" ? "P" : "ID"}</text>
          <text x={point.x} y={point.y+radius+25} textAnchor="middle" className={styles.nodeLabel}>{node.label.length > 25 ? node.label.slice(0,22)+"…" : node.label}</text>
          <text x={point.x} y={point.y+radius+41} textAnchor="middle" className={styles.nodeMeta}>{node.type.toUpperCase()} · {node.edge_count} LINKS</text>
          <title>{node.label} · importance {node.importance} · select to expand and filter</title>
        </g>;
      })}
    </svg>}
    <div className={styles.networkLegend}>{Array.from(new Set(nodes.map(node => node.community))).sort((a,b)=>a-b).map(community => <span key={community}><i style={{background:colours[Math.abs(community)%colours.length]}} />Community {community+1}</span>)}</div>
  </div>;
}

export function MoneyNetwork({ edges, onSource }: {
  edges: {source: string; target: string; amount: number; reference: string; evidenceId: number; rawRef: string}[];
  onSource: (file: number, ref: string) => void;
}) {
  const amounts = new Map<string, number>();
  edges.forEach(edge => { amounts.set(edge.source, (amounts.get(edge.source) ?? 0)+1); amounts.set(edge.target, (amounts.get(edge.target) ?? 0)+1); });
  const nodes = [...amounts].map(([id, count], index) => ({id, label:id, type:"account", edge_count:count, importance:count/Math.max(1, edges.length), betweenness:0, size:20, community:index%6}));
  return <><RelationshipGraph nodes={nodes} edges={edges.map(edge => ({source:edge.source,target:edge.target,count:1,relation:`INR ${edge.amount.toLocaleString("en-IN")} · ${edge.reference}`,support:[{evidence_id:edge.evidenceId,file:"Bank statement",event_id:0,reference:edge.rawRef}]}))} onSelect={node => {const edge=edges.find(edge=>edge.source===node.id||edge.target===node.id);if(edge)onSource(edge.evidenceId,edge.rawRef);}} onSource={onSource} />
    <div className={styles.transferLegend}>{edges.map((edge,index)=><button key={`${edge.reference}-${index}`} onClick={()=>onSource(edge.evidenceId,edge.rawRef)}><span>{edge.source} → {edge.target}</span><strong>₹{edge.amount.toLocaleString("en-IN")}</strong><small>{edge.reference} · {edge.rawRef}</small></button>)}</div>
    <p className={styles.note}>Each edge is a recorded transaction. Connected transfers do not establish that the same funds moved onward; allocations remain in the tracing panel.</p></>;
}

export function ActivityChart({ events, onDay }: {events:{timestamp_utc:string|null;action:string}[];onDay:(day:string)=>void}) {
  const format = new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Kolkata"});
  const groups = new Map<string,{messages:number;payments:number;other:number}>();
  events.forEach(event=>{if(!event.timestamp_utc)return;const day=format.format(new Date(event.timestamp_utc));const value=groups.get(day)??{messages:0,payments:0,other:0};if(/payment|transaction|debit|credit/i.test(event.action))value.payments++;else if(/message|chat|call/i.test(event.action))value.messages++;else value.other++;groups.set(day,value);});
  const days=[...groups].sort(([a],[b])=>a.localeCompare(b));
  const maximum=Math.max(1,...days.map(([,value])=>value.messages+value.payments+value.other));
  return <section className={`${styles.panel} ${styles.activityPanel}`}><div className={styles.cardTitle}><div><span className={styles.eyebrow}>TEMPORAL ANALYSIS · IST</span><h2>Activity across sources</h2></div><span className={styles.viewLabel}>Loaded records</span></div>
    <div className={styles.activityChart} aria-label="Daily activity; select a day to filter the evidence">{days.map(([day,value])=><button key={day} onClick={()=>onDay(day)} aria-label={`${day}: ${value.messages} communications, ${value.payments} transactions, ${value.other} other records`}><span className={styles.activityTotal}>{value.messages+value.payments+value.other}</span><span className={styles.activityColumn}>{([{value:value.other,colour:"var(--chart-slate)"},{value:value.payments,colour:"var(--chart-teal)"},{value:value.messages,colour:"var(--chart-blue)"}]).map((part,i)=><span key={i} style={{height:`${part.value/maximum*140}px`,background:part.colour}}/>)}</span><small>{day.slice(5)}</small></button>)}</div>
    {!days.length && <p>No timestamped records are available.</p>}
    <div className={styles.chartLegend}><span><i style={{background:"var(--chart-blue)"}}/>Communications</span><span><i style={{background:"var(--chart-teal)"}}/>Transactions</span><span><i style={{background:"var(--chart-slate)"}}/>Other</span></div><p className={styles.note}>Select a day to inspect exact records. Proximity in time does not establish causation.</p></section>;
}
