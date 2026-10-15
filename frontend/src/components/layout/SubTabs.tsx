export function SubTabs({
  tabs,
  active,
  onSelect,
}: {
  tabs: string[];
  active: string;
  onSelect: (tab: string) => void;
}) {
  return (
    <nav className="tab-strip" aria-label="Investigation views">
      {tabs.map((tab) => (
        <button
          key={tab}
          aria-current={active === tab ? "page" : undefined}
          className={active === tab ? "tab-active" : ""}
          onClick={() => onSelect(tab)}
        >
          {tab}
        </button>
      ))}
    </nav>
  );
}
