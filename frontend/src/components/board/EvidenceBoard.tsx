import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent } from "react";
import { Download, FileText, Link2, Map as MapIcon, Maximize2, Network, Redo2, Save, StickyNote, Trash2, Undo2, ZoomIn, ZoomOut } from "lucide-react";
import {
  analyseBoard,
  createBoardSnapshot,
  exportBoard,
  getBoard,
  getBoardSnapshot,
  getBoardSnapshots,
  saveBoard,
} from "../../caseApi";
import type { RecordEvent, Source } from "../casework/model";
import {
  BOARD_WARNING,
  cloneBoard,
  deleteBoardCards,
  riyaBoard,
  type BoardCard,
  type BoardReceipt,
  type BoardSnapshot,
  type BoardState,
} from "./boardModel";
import styles from "./EvidenceBoard.module.css";

type Props = {
  caseId: number | null;
  token: string | null;
  readOnly: boolean;
  isScenario: boolean;
  sources: Source[];
  records: RecordEvent[];
  onOpenReceipt: (receipt: BoardReceipt) => void;
};
type PersistAction = "card.added" | "card.moved" | "card.deleted" | "card.restored" | "link.drawn" | "link.updated" | "link.deleted" | "zone.added" | "zone.moved" | "zone.deleted" | "selection.changed" | "exhibit.changed" | "board.arranged" | "board.restored";
type Analysis = { nodes?: string[]; links?: string[]; complete?: boolean; status?: string; algorithm?: string; fallback?: string; leads?: GapLead[] };
type GapLead = { id: string; source: string; target: string; confidence: number; model_name: string; model_version: string; top_reasons: string[]; notice: string };

const cardWidth = 190;
const cardHeight = 94;
const palette = ["var(--board-community-1)", "var(--board-community-2)", "var(--board-community-3)", "var(--board-community-4)", "var(--board-community-5)", "var(--board-community-6)"];
const truncate = (value: string, length: number) => value.length > length ? `${value.slice(0, length - 1)}…` : value;
const receiptKey = (receipt?: BoardReceipt | null) => receipt ? `${receipt.evidence_id ?? receipt.file}:${receipt.reference}` : "";

function localPath(state: BoardState, selected: string[]): Analysis {
  if (selected.length < 2) return { nodes: selected, links: [], complete: true, status: "select_two_or_more" };
  const adjacency = new Map<string, { node: string; link: string }[]>();
  state.links.filter((link) => link.status !== "contradicted").forEach((link) => {
    adjacency.set(link.source, [...(adjacency.get(link.source) ?? []), { node: link.target, link: link.id }]);
    adjacency.set(link.target, [...(adjacency.get(link.target) ?? []), { node: link.source, link: link.id }]);
  });
  const nodes = new Set<string>([selected[0]]), links = new Set<string>();
  for (const target of selected.slice(1)) {
    const queue: { node: string; path: string[]; edges: string[] }[] = [{ node: selected[0], path: [selected[0]], edges: [] }];
    const seen = new Set([selected[0]]);
    let match: (typeof queue)[number] | undefined;
    while (queue.length) {
      const item = queue.shift()!;
      if (item.node === target) { match = item; break; }
      for (const edge of (adjacency.get(item.node) ?? []).sort((a, b) => a.node.localeCompare(b.node))) {
        if (!seen.has(edge.node)) { seen.add(edge.node); queue.push({ node: edge.node, path: [...item.path, edge.node], edges: [...item.edges, edge.link] }); }
      }
    }
    match?.path.forEach((item) => nodes.add(item));
    match?.edges.forEach((item) => links.add(item));
  }
  return { nodes: [...nodes], links: [...links], complete: true, status: links.size ? "ready" : "no_path", algorithm: "deterministic shortest-path union" };
}

function demoGaps(state: BoardState): GapLead[] {
  const exists = state.links.some((link) => [link.source, link.target].includes("arjun-phone") && [link.source, link.target].includes("handle"));
  return exists ? [] : [{ id: "gap-arjun-phone-handle", source: "arjun-phone", target: "handle", confidence: .71, model_name: "alias-matcher", model_version: "step4-existing", top_reasons: ["Agent Arjun token appears in both labels", "Calls surround payment requests", "No direct ownership record"], notice: "Suggested missing link; this is a lead, never a finding." }];
}

export function EvidenceBoard({ caseId, token, readOnly, isScenario, sources, records: _records, onOpenReceipt }: Props) {
  const hashes = useMemo(() => Object.fromEntries(sources.map((source) => [source.id, source.sha256])), [sources]);
  const seeded = useMemo(() => riyaBoard(hashes), [hashes]);
  const [state, setState] = useState<BoardState>(() => cloneBoard(seeded));
  const [revision, setRevision] = useState(0);
  const [boardHash, setBoardHash] = useState("local-unsaved");
  const [updatedBy, setUpdatedBy] = useState<string | null>(null);
  const [undo, setUndo] = useState<BoardState[]>([]), [redo, setRedo] = useState<BoardState[]>([]);
  const [selected, setSelected] = useState<string[]>(() => new URLSearchParams(location.search).get("board")?.split(",").filter(Boolean) ?? []);
  const [analysis, setAnalysis] = useState<Analysis | null>(null), [message, setMessage] = useState("");
  const [snapshots, setSnapshots] = useState<BoardSnapshot[]>([]), [compare, setCompare] = useState<number[]>([]);
  const [gapLeads, setGapLeads] = useState<GapLead[]>([]), [timeIndex, setTimeIndex] = useState(100);
  const svg = useRef<SVGSVGElement>(null), drag = useRef<{ id: string; start: BoardState; dx: number; dy: number } | null>(null);
  const pan = useRef<{ x: number; y: number; viewport: BoardState["viewport"] } | null>(null);
  const times = useMemo(() => state.cards.flatMap((card) => card.timestamp ? [Date.parse(card.timestamp)] : []).sort((a, b) => a - b), [state.cards]);
  const cutoff = times.length ? times[Math.min(times.length - 1, Math.floor((timeIndex / 100) * (times.length - 1)))] : Number.POSITIVE_INFINITY;
  const selectedCards = state.cards.filter((card) => selected.includes(card.id));
  const canEdit = !readOnly;

  useEffect(() => {
    if (!token || !caseId) return;
    let active = true;
    Promise.all([getBoard(caseId), getBoardSnapshots(caseId)]).then(([board, saved]) => {
      if (!active) return;
      const loaded = board.state.cards.length || !isScenario ? board.state : seeded;
      setState(cloneBoard(loaded)); setRevision(board.revision); setBoardHash(board.board_hash); setUpdatedBy(board.updated_by); setSnapshots(saved);
    }).catch((error) => setMessage(error instanceof Error ? error.message : "Could not load board"));
    return () => { active = false; };
  }, [caseId, isScenario, seeded, token]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (selected.length) params.set("board", selected.join(",")); else params.delete("board");
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }, [selected]);

  useEffect(() => {
    const receive = (raw: Event) => {
      const detail = (raw as CustomEvent).detail as Partial<BoardCard> & { receipt?: BoardReceipt };
      if (!detail.title || !detail.receipt) return;
      const id = detail.id ?? `pin-${detail.receipt.evidence_id}-${detail.receipt.reference.replace(/\W/g, "-")}`;
      if (state.cards.some((card) => card.id === id)) { setSelected([id]); setMessage("That source is already pinned."); return; }
      const next = cloneBoard(state);
      next.cards.push({ id, kind: detail.kind ?? "event", title: detail.title, body: detail.body ?? "Pinned source record", timestamp: detail.timestamp ?? null,
        source_badge: detail.source_badge ?? detail.receipt.file, receipt: detail.receipt, x: state.viewport.x + 320, y: state.viewport.y + 220,
        locked: false, community: 0, size: 1 });
      void commit(next, "card.added", id, { origin: "pin-from-anywhere" });
      setSelected([id]);
    };
    window.addEventListener("parakh-pin-board", receive);
    return () => window.removeEventListener("parakh-pin-board", receive);
  });

  const persist = useCallback(async (next: BoardState, action: PersistAction, targetId = "", detail: Record<string, unknown> = {}) => {
    if (!token || !caseId) {
      const encoded = JSON.stringify(next);
      const bytes = new TextEncoder().encode(encoded);
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      setBoardHash(Array.from(new Uint8Array(digest)).map((value) => value.toString(16).padStart(2, "0")).join(""));
      localStorage.setItem("parakh-riya-board-v1", encoded);
      setUpdatedBy("Demo investigator (local session)");
      return;
    }
    try {
      const result = await saveBoard(caseId, revision, action, targetId, detail, next);
      setRevision(result.revision); setBoardHash(result.board_hash); setUpdatedBy(result.updated_by); setMessage(`${action.replaceAll(".", " ")} · audited`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Board save failed"); }
  }, [caseId, revision, token]);

  const commit = useCallback(async (next: BoardState, action: PersistAction, targetId = "", detail: Record<string, unknown> = {}) => {
    if (!canEdit) { setMessage("Read-only role: prosecutors cannot edit this board."); return; }
    setUndo((items) => [...items.slice(-49), cloneBoard(state)]); setRedo([]); setState(next);
    await persist(next, action, targetId, detail);
  }, [canEdit, persist, state]);

  const restore = (direction: "undo" | "redo") => {
    const source = direction === "undo" ? undo : redo;
    const target = source[source.length - 1]; if (!target || !canEdit) return;
    if (direction === "undo") { setUndo(source.slice(0, -1)); setRedo((items) => [...items, cloneBoard(state)]); }
    else { setRedo(source.slice(0, -1)); setUndo((items) => [...items, cloneBoard(state)]); }
    setState(cloneBoard(target)); void persist(target, "board.restored", "", { direction });
  };

  useEffect(() => {
    const keys = (event: KeyboardEvent) => {
      const modifier = event.ctrlKey || event.metaKey;
      if (modifier && event.key.toLowerCase() === "z") { event.preventDefault(); restore(event.shiftKey ? "redo" : "undo"); }
      if (modifier && event.key.toLowerCase() === "y") { event.preventDefault(); restore("redo"); }
      if ((event.key === "Delete" || event.key === "Backspace") && selected.length && !["INPUT", "TEXTAREA"].includes((event.target as HTMLElement).tagName)) { event.preventDefault(); removeSelected(); }
      if (event.key === "0" && modifier) { event.preventDefault(); setState((current) => ({ ...current, viewport: { x: 0, y: 0, zoom: 1 } })); }
    };
    window.addEventListener("keydown", keys); return () => window.removeEventListener("keydown", keys);
  });

  function pointerToWorld(event: { clientX: number; clientY: number }) {
    const rect = svg.current!.getBoundingClientRect();
    return { x: state.viewport.x + (event.clientX - rect.left) / state.viewport.zoom, y: state.viewport.y + (event.clientY - rect.top) / state.viewport.zoom };
  }
  function selectCard(id: string, additive: boolean) { setSelected((current) => additive ? (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]) : [id]); }
  function cardDown(event: ReactPointerEvent, card: BoardCard) {
    event.stopPropagation(); selectCard(card.id, event.ctrlKey || event.metaKey || event.shiftKey);
    if (!canEdit || card.locked) return;
    const point = pointerToWorld(event); drag.current = { id: card.id, start: cloneBoard(state), dx: point.x - card.x, dy: point.y - card.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function move(event: ReactPointerEvent<SVGSVGElement>) {
    if (drag.current) {
      const point = pointerToWorld(event), info = drag.current;
      setState((current) => ({ ...current, cards: current.cards.map((card) => card.id === info.id ? { ...card, x: point.x - info.dx, y: point.y - info.dy } : card) }));
    } else if (pan.current) {
      const rect = svg.current!.getBoundingClientRect(), info = pan.current;
      setState((current) => ({ ...current, viewport: { ...current.viewport, x: info.viewport.x - (event.clientX - info.x) / current.viewport.zoom, y: info.viewport.y - (event.clientY - info.y) / current.viewport.zoom } }));
      void rect;
    }
  }
  function up() {
    if (drag.current) {
      const info = drag.current; drag.current = null;
      setUndo((items) => [...items.slice(-49), info.start]); setRedo([]); void persist(state, "card.moved", info.id, { locked: false });
    }
    pan.current = null;
  }
  function backgroundDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.target !== event.currentTarget && !(event.target as Element).classList.contains(styles.background)) return;
    setSelected([]); pan.current = { x: event.clientX, y: event.clientY, viewport: { ...state.viewport } };
  }
  function zoom(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault(); const factor = event.deltaY > 0 ? .88 : 1.14;
    setState((current) => ({ ...current, viewport: { ...current.viewport, zoom: Math.max(.25, Math.min(2.5, current.viewport.zoom * factor)) } }));
  }
  function moveKeyboard(card: BoardCard, dx: number, dy: number) {
    if (!canEdit || card.locked) return;
    const next = cloneBoard(state), target = next.cards.find((item) => item.id === card.id)!; target.x += dx; target.y += dy;
    void commit(next, "card.moved", card.id, { method: "keyboard", dx, dy });
  }
  function removeSelected() {
    if (!selected.length || !canEdit) return;
    const next = deleteBoardCards(state, selected);
    void commit(next, "card.deleted", selected.join(","), { count: selected.length }); setSelected([]);
  }
  function addNote() {
    const title = window.prompt("Sticky note title"); if (!title) return;
    const body = window.prompt("Investigator note (not evidence)", "") ?? ""; const id = `note-${Date.now()}`; const next = cloneBoard(state);
    next.cards.push({ id, kind: "note", title, body, timestamp: null, source_badge: "Investigator note, not evidence", receipt: null, x: state.viewport.x + 280, y: state.viewport.y + 180, locked: false, community: 0, size: 1 });
    void commit(next, "card.added", id, { kind: "note" });
  }
  function drawLink() {
    if (selected.length !== 2) { setMessage("Select exactly two cards to draw a string."); return; }
    const label = window.prompt("String label", "investigator hypothesis"); if (!label) return; const id = `link-${Date.now()}`; const next = cloneBoard(state);
    next.links.push({ id, source: selected[0], target: selected[1], label, type: "investigator hypothesis", status: "not_established", auto: false, support: [], reasons: ["No cited card or note supports this investigator-drawn string"] });
    void commit(next, "link.drawn", id, { status: "not_established" });
  }
  function addZone() {
    const label = window.prompt("Zone label", "New cluster"); if (!label) return; const id = `zone-${Date.now()}`; const next = cloneBoard(state);
    next.zones.push({ id, label, x: state.viewport.x + 100, y: state.viewport.y + 100, width: 500, height: 320, community: next.zones.length % 6 });
    void commit(next, "zone.added", id, { label });
  }
  async function run(operation: string) {
    let result: Analysis;
    if (token && caseId) result = await analyseBoard(caseId, operation, { selected, source: selected[0], target: selected[selected.length - 1], depth: 1, time_limit_ms: 1000 }) as Analysis;
    else if (operation === "find-gaps") result = { leads: demoGaps(state), complete: true };
    else if (operation === "expand-neighbours") {
      const neighbours = new Set(selected); state.links.forEach((link) => { if (neighbours.has(link.source)) neighbours.add(link.target); if (neighbours.has(link.target)) neighbours.add(link.source); });
      result = { nodes: [...neighbours], links: state.links.filter((link) => neighbours.has(link.source) && neighbours.has(link.target)).map((link) => link.id), complete: true };
    } else result = localPath(state, operation === "shortest-path" ? selected.slice(0, 2) : selected);
    if (operation === "find-gaps") setGapLeads(result.leads ?? []); else { setAnalysis(result); setSelected(result.nodes ?? selected); }
    setMessage(`${operation.replaceAll("-", " ")}: ${result.status ?? "ready"}${result.complete === false ? " · incomplete" : ""}`);
  }
  function autoArrange() {
    const next = cloneBoard(state), movable = next.cards.filter((card) => !card.locked).sort((a, b) => a.id.localeCompare(b.id));
    movable.forEach((card, index) => { card.x = 180 + (index % 5) * 290; card.y = 120 + Math.floor(index / 5) * 190; });
    void commit(next, "board.arranged", "", { algorithm: "seeded grid fallback", seed: next.seed, time_limit_ms: 1000, locked: next.cards.filter((card) => card.locked).map((card) => card.id) });
    setMessage("Auto-arranged with fixed seed 51026; locked cards retained.");
  }
  async function saveSnapshot() {
    const name = window.prompt("Snapshot name", `Board ${snapshots.length + 1}`); if (!name) return;
    if (token && caseId) {
      if (revision === 0) await persist(state, "board.restored", "", { initial_save: true });
      const item = await createBoardSnapshot(caseId, name); setSnapshots((items) => [...items, item]);
    } else {
      const item: BoardSnapshot = { id: Date.now(), name, revision, board_hash: boardHash, created_by: "Demo investigator", state: cloneBoard(state), created_at: new Date().toISOString() };
      const items = [...snapshots, item]; setSnapshots(items); localStorage.setItem("parakh-riya-board-snapshots-v1", JSON.stringify(items));
    }
    setMessage(`Snapshot “${name}” saved with the current layout.`);
  }
  async function loadSnapshot(id: number) {
    const item = token && caseId ? await getBoardSnapshot(caseId, id) : snapshots.find((snapshot) => snapshot.id === id);
    if (!item?.state) return; await commit(cloneBoard(item.state), "board.restored", String(id), { snapshot: item.name, board_hash: item.board_hash });
  }
  async function renderPng() {
    const node = svg.current!; const clone = node.cloneNode(true) as SVGSVGElement;
    clone.setAttribute("viewBox", "0 0 1850 650"); clone.setAttribute("width", "1850"); clone.setAttribute("height", "650");
    const encoded = new XMLSerializer().serializeToString(clone), url = URL.createObjectURL(new Blob([encoded], { type: "image/svg+xml" }));
    const image = new Image(); await new Promise<void>((resolve, reject) => { image.onload = () => resolve(); image.onerror = reject; image.src = url; });
    const canvas = document.createElement("canvas"); canvas.width = 1850; canvas.height = 650; const context = canvas.getContext("2d")!; context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--board-canvas"); context.fillRect(0, 0, canvas.width, canvas.height); context.drawImage(image, 0, 0); URL.revokeObjectURL(url); return canvas.toDataURL("image/png");
  }
  async function output(format: "png" | "pdf") {
    const png = await renderPng(), receipts = state.cards.filter((card) => state.exhibit_ids.includes(card.id)).map((card) => receiptKey(card.receipt)).filter(Boolean);
    if (token && caseId) {
      const result = await exportBoard(caseId, format, png, state.caption, receipts); const bytes = Uint8Array.from(atob(result.content_base64), (char) => char.charCodeAt(0));
      const href = URL.createObjectURL(new Blob([bytes], { type: format === "pdf" ? "application/pdf" : "image/png" })); const anchor = document.createElement("a"); anchor.href = href; anchor.download = result.filename; anchor.click(); URL.revokeObjectURL(href); setMessage(`${format.toUpperCase()} exported and audited · ${result.sha256.slice(0, 12)}…`);
    } else if (format === "png") { const anchor = document.createElement("a"); anchor.href = png; anchor.download = "riya-evidence-board.png"; anchor.click(); setMessage("PNG exported locally. Sign in to attach an audited PDF to a report."); }
    else setMessage("Sign in to create the audited report PDF page.");
  }
  function toggleExhibit() {
    const next = cloneBoard(state), ids = new Set(next.exhibit_ids); selected.forEach((id) => ids.has(id) ? ids.delete(id) : ids.add(id)); next.exhibit_ids = [...ids];
    void commit(next, "exhibit.changed", selected.join(","), { selected: next.exhibit_ids });
    selectedCards.forEach((card) => card.receipt && window.dispatchEvent(new CustomEvent("parakh-exhibit", { detail: { file: card.receipt.evidence_id, ref: card.receipt.reference } })));
  }
  const highlightedLinks = new Set(analysis?.links ?? []), highlightedNodes = new Set(analysis?.nodes ?? []);
  const compareSummary = compare.length === 2 ? (() => { const left = snapshots.find((item) => item.id === compare[0]), right = snapshots.find((item) => item.id === compare[1]); return left && right ? `${left.board_hash === right.board_hash ? "Identical" : "Different"} board hash · revisions ${left.revision} → ${right.revision}` : ""; })() : "";

  return <section className={styles.boardShell} aria-label="Evidence relationship board">
    <aside className={styles.banner}>{BOARD_WARNING}</aside>
    <div className={styles.toolbar} role="toolbar" aria-label="Board tools">
      <button onClick={() => restore("undo")} disabled={!undo.length || !canEdit} title="Undo (Ctrl/Cmd+Z)"><Undo2/>Undo</button>
      <button onClick={() => restore("redo")} disabled={!redo.length || !canEdit} title="Redo (Ctrl/Cmd+Y)"><Redo2/>Redo</button>
      <button onClick={addNote} disabled={!canEdit}><StickyNote/>Sticky note</button>
      <button onClick={drawLink} disabled={!canEdit || selected.length !== 2}><Link2/>Draw string</button>
      <button onClick={addZone} disabled={!canEdit}><MapIcon/>Zone</button>
      <button onClick={() => void run("connect")} disabled={selected.length < 2}><Network/>Connect these</button>
      <button onClick={() => void run("shortest-path")} disabled={selected.length !== 2}>Shortest path</button>
      <button onClick={() => void run("expand-neighbours")} disabled={!selected.length}>Expand neighbours</button>
      <button onClick={() => void run("find-gaps")}>Find gaps</button>
      <button onClick={autoArrange} disabled={!canEdit}><Maximize2/>Auto-arrange</button>
      <button onClick={removeSelected} disabled={!selected.length || !canEdit}><Trash2/>Delete</button>
    </div>
    <div className={styles.lens}>
      <label>Time lens <input aria-label="Time lens" type="range" min="0" max="100" value={timeIndex} onChange={(event) => setTimeIndex(Number(event.target.value))}/></label>
      <span>{timeIndex === 100 ? "All times" : new Date(cutoff).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}</span>
      <button onClick={() => setState((current) => ({ ...current, viewport: { ...current.viewport, zoom: Math.min(2.5, current.viewport.zoom * 1.2) } }))}><ZoomIn/>Zoom in</button>
      <button onClick={() => setState((current) => ({ ...current, viewport: { ...current.viewport, zoom: Math.max(.25, current.viewport.zoom / 1.2) } }))}><ZoomOut/>Zoom out</button>
      <small>{state.cards.length} cards · {state.links.length} strings · seed {state.seed}</small>
    </div>
    {message && <p className={styles.message} role="status">{message}</p>}
    <div className={styles.canvasWrap}>
      <svg ref={svg} className={styles.canvas} aria-label="Infinite evidence canvas" onPointerDown={backgroundDown} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onWheel={zoom}
        viewBox={`${state.viewport.x} ${state.viewport.y} ${1850 / state.viewport.zoom} ${650 / state.viewport.zoom}`}>
        <defs><pattern id="board-grid" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="var(--board-grid)"/></pattern><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="var(--board-accent-dark)"/></marker></defs>
        <rect className={styles.background} x="-100000" y="-100000" width="200000" height="200000" fill="url(#board-grid)"/>
        {state.zones.map((zone) => <g key={zone.id}><rect className={styles.zone} x={zone.x} y={zone.y} width={zone.width} height={zone.height} style={{ stroke: palette[zone.community % palette.length] }}/><text className={styles.zoneLabel} x={zone.x + 14} y={zone.y + 24}>{zone.label}</text></g>)}
        {state.links.map((link) => {
          const source = state.cards.find((card) => card.id === link.source), target = state.cards.find((card) => card.id === link.target); if (!source || !target) return null;
          const x1 = source.x + cardWidth / 2, y1 = source.y + cardHeight / 2, x2 = target.x + cardWidth / 2, y2 = target.y + cardHeight / 2;
          return <g key={link.id} className={`${styles.string} ${styles[link.status]} ${highlightedLinks.has(link.id) ? styles.highlight : ""}`}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} markerEnd="url(#arrow)"/><text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6}>{truncate(link.label, 34)}</text><title>{link.type} · {link.status} · {link.reasons.join("; ")}</title>
          </g>;
        })}
        {state.cards.map((card) => {
          const faded = card.timestamp ? Date.parse(card.timestamp) > cutoff : false, active = selected.includes(card.id) || highlightedNodes.has(card.id);
          return <g key={card.id} role="button" tabIndex={0} aria-label={`${card.kind}: ${card.title}. ${card.source_badge}`} aria-pressed={selected.includes(card.id)}
            transform={`translate(${card.x} ${card.y}) scale(${card.size})`} className={`${styles.card} ${active ? styles.selected : ""} ${faded ? styles.faded : ""}`}
            onPointerDown={(event) => cardDown(event, card)} onDoubleClick={() => card.receipt && onOpenReceipt(card.receipt)}
            onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectCard(card.id, event.shiftKey); } if (event.key === "ArrowLeft") moveKeyboard(card, -10, 0); if (event.key === "ArrowRight") moveKeyboard(card, 10, 0); if (event.key === "ArrowUp") moveKeyboard(card, 0, -10); if (event.key === "ArrowDown") moveKeyboard(card, 0, 10); }}>
            <rect width={cardWidth} height={cardHeight} rx="7" style={{ fill: card.kind === "note" ? "var(--board-note)" : palette[card.community % palette.length] }}/>
            <circle cx="95" cy="0" r="7"/><text className={styles.kind} x="12" y="19">{card.kind.toUpperCase()}</text><text className={styles.title} x="12" y="40">{truncate(card.title, 27)}</text>
            <text className={styles.bodyText} x="12" y="58">{truncate(card.body, 31)}</text><text className={styles.source} x="12" y="78">{truncate(card.source_badge, 29)}</text>
            {card.receipt && <g className={styles.receipt} onPointerDown={(event) => event.stopPropagation()} onClick={() => onOpenReceipt(card.receipt!)}><rect x="127" y="64" width="54" height="21" rx="3"/><text x="137" y="78">Receipt</text></g>}
            {card.locked && <text className={styles.locked} x="174" y="18">●</text>}
          </g>;
        })}
      </svg>
      <svg className={styles.minimap} viewBox="0 0 1850 650" aria-label="Board minimap">
        {state.links.map((link) => { const a = state.cards.find((card) => card.id === link.source), b = state.cards.find((card) => card.id === link.target); return a && b ? <line key={link.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y}/> : null; })}
        {state.cards.map((card) => <circle key={card.id} cx={card.x} cy={card.y} r={selected.includes(card.id) ? 18 : 10} fill={palette[card.community % palette.length]}/>)}</svg>
    </div>
    <div className={styles.lowerGrid}>
      <section><h3>Selection</h3><p>{selectedCards.map((card) => card.title).join(" · ") || "Select cards with Ctrl/Cmd or Shift. Arrow keys move an unlocked focused card."}</p>
        <button onClick={toggleExhibit} disabled={!selected.length || !canEdit}><FileText/>Send selected to exhibit tray</button>
        <small>{state.exhibit_ids.length} board item(s) in tray</small>
      </section>
      <section><h3>Snapshots</h3><button onClick={() => void saveSnapshot()} disabled={!canEdit}><Save/>Save named version</button>
        <div className={styles.snapshotList}>{snapshots.map((snapshot) => <label key={snapshot.id}><input type="checkbox" checked={compare.includes(snapshot.id)} onChange={() => setCompare((items) => items.includes(snapshot.id) ? items.filter((id) => id !== snapshot.id) : [...items.slice(-1), snapshot.id])}/><button onClick={() => void loadSnapshot(snapshot.id)}>{snapshot.name}</button><small>{snapshot.board_hash.slice(0, 10)}…</small></label>)}</div>
        {compareSummary && <p>{compareSummary}</p>}
      </section>
      <section><h3>Gap leads</h3>{gapLeads.length ? gapLeads.map((lead) => <article key={lead.id}><strong>{state.cards.find((card) => card.id === lead.source)?.title} ↔ {state.cards.find((card) => card.id === lead.target)?.title}</strong><p>{Math.round(lead.confidence * 100)}% · {lead.model_name} {lead.model_version}</p>{lead.top_reasons.map((reason) => <small key={reason}>{reason}</small>)}<em>{lead.notice}</em></article>) : <p>Run Find gaps. Suggestions remain leads, never findings.</p>}</section>
      <section><h3>Output</h3><label>Caption<input value={state.caption} disabled={!canEdit} onChange={(event) => setState((current) => ({ ...current, caption: event.target.value }))}/></label><button onClick={() => void output("png")}><Download/>PNG</button><button onClick={() => void output("pdf")}><Download/>PDF report page</button><small>Board hash {boardHash.slice(0, 16)}… · updated by {updatedBy ?? "not saved"}</small></section>
    </div>
    <footer>Realtime multi-user editing: <strong>planned [T3]</strong>. Current edits are revision-checked and attributed individually.</footer>
  </section>;
}
