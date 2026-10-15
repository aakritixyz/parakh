import {
  useEffect,
  useState,
  type ReactNode,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
} from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Inbox } from "lucide-react";
import styles from "./UI.module.css";
export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
}) {
  return (
    <button
      className={`${styles.button} ${styles[variant]} ${styles[size]} ${className}`}
      {...props}
    />
  );
}
export function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`workspace-card ${className}`}>
      {title && (
        <header>
          <h2>{title}</h2>
        </header>
      )}
      {children}
    </section>
  );
}
export function Badge({ children }: { children: ReactNode }) {
  return <span className={styles.badge}>{children}</span>;
}
export const Chip = Badge;
export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} />;
}
export function Checkbox(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input type="checkbox" {...props} />;
}
export function Tooltip({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return <span title={label}>{children}</span>;
}
export function Skeleton() {
  return <span className={styles.skeleton} aria-hidden="true" />;
}
export function EmptyState({
  children,
  action,
}: {
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className={styles.empty}>
      <Inbox />
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Tabs({
  items,
  active,
  onChange,
}: {
  items: string[];
  active: string;
  onChange: (item: string) => void;
}) {
  return (
    <div className={styles.tabs} role="group">
      {items.map((item) => (
        <button
          key={item}
          aria-pressed={active === item}
          onClick={() => onChange(item)}
        >
          {item}
        </button>
      ))}
    </div>
  );
}
export const SegmentedControl = Tabs;
export function KpiCard({
  label,
  value,
  hint,
  danger = false,
}: {
  label: string;
  value: ReactNode;
  hint: string;
  danger?: boolean;
}) {
  return (
    <article className={`metric ${danger ? "danger" : ""}`}>
      <span>{label}</span>
      <strong>
        {danger && <AlertTriangle aria-label="Risk" />}
        {value}
      </strong>
      <small>{hint}</small>
    </article>
  );
}
export function FacetGroup({
  title,
  count,
  items,
  initiallyOpen = false,
  selected,
  onSelect,
}: {
  title: string;
  count: number;
  items: string[];
  initiallyOpen?: boolean;
  selected?: string;
  onSelect?: (item: string) => void;
}) {
  const [open, setOpen] = useState(initiallyOpen),
    [all, setAll] = useState(false);
  const [checked, setChecked] = useState(() => new Set(items.slice(0, 2)));
  useEffect(() => {
    const clear = () => setChecked(new Set());
    window.addEventListener("parakh-clear-filters", clear);
    return () => window.removeEventListener("parakh-clear-filters", clear);
  }, []);
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
      <header
        role="button"
        aria-expanded={open}
        tabIndex={0}
        onClick={() => setOpen(!open)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setOpen(!open);
          }
        }}
      >
        <span>
          {open ? <ChevronDown /> : <ChevronRight />} {title}
        </span>
        <strong>{count}</strong>
      </header>
      {open && (
        <div className="facet-items">
          <label>
            <Checkbox
              checked={checked.size === items.length}
              onChange={(event) =>
                setChecked(event.target.checked ? new Set(items) : new Set())
              }
            />
            All
          </label>
          {(all ? items : items.slice(0, 5)).map((item) => {
            const match = item.match(/^(.*?)\s+(\d[\d,]*)$/);
            return (
              <label
                className={
                  selected && item.startsWith(selected) ? "selected-filter" : ""
                }
                key={item}
              >
                <Checkbox
                  checked={checked.has(item)}
                  onChange={() => toggleItem(item)}
                />
                <span>{match ? match[1] : item}</span>
                {match && <span className="facet-count">{match[2]}</span>}
              </label>
            );
          })}
          {items.length > 5 && (
            <Button variant="ghost" size="sm" onClick={() => setAll(!all)}>
              {all ? "Show less" : "Show all"}
            </Button>
          )}
        </div>
      )}
    </section>
  );
}
export function DataTable({ children }: { children: ReactNode }) {
  return (
    <div className={styles.table}>
      <table>{children}</table>
    </div>
  );
}
export { DetailsDrawer as Drawer } from "../layout/DetailsDrawer";
export { VirtualList } from "./VirtualList";
