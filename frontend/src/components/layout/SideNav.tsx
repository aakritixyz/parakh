import {
  FolderOpen,
  Archive,
  FileText,
  LockKeyhole,
  ListChecks,
  ScanSearch,
  Files,
  Settings,
  PanelLeftClose,
  ShieldCheck,
} from "lucide-react";
const icons = [
  FolderOpen,
  Archive,
  FileText,
  LockKeyhole,
  ListChecks,
  ScanSearch,
  Files,
  Settings,
];
export function SideNav({
  items,
  active,
  onNavigate,
  collapsed,
  onToggle,
}: {
  items: string[];
  active: string;
  onNavigate: (item: string) => void;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <aside className={`case-rail ${collapsed ? "collapsed" : ""}`}>
      <button
        className="nav-toggle"
        onClick={onToggle}
        aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
        aria-expanded={!collapsed}
      >
        <PanelLeftClose />
        <span>Workspace</span>
      </button>
      <nav aria-label="Workspace">
        {items.map((item, index) => {
          const Icon = icons[index];
          return (
            <button
              key={item}
              title={item}
              aria-label={item}
              aria-current={item === active ? "page" : undefined}
              className={item === active ? "rail-active" : ""}
              onClick={() => onNavigate(item)}
            >
              <Icon />
              <span>{item}</span>
            </button>
          );
        })}
      </nav>
      <div className="nav-footer">
        <ShieldCheck />
        <span>Evidence integrity first</span>
      </div>
    </aside>
  );
}
