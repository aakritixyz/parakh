import { useEffect } from "react";
import {
  Menu,
  Search,
  ShieldCheck,
  ShieldAlert,
  UserRound,
} from "lucide-react";
export function Header({
  title,
  online,
  verified,
  onToggle,
  onProfile,
  query,
  onQuery,
  onConnect,
}: {
  title: string;
  online: boolean;
  verified: boolean;
  onToggle: () => void;
  onProfile: () => void;
  query: string;
  onQuery: (query: string) => void;
  onConnect: () => void;
}) {
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        document.querySelector<HTMLInputElement>("#global-search")?.focus();
      }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, []);
  return (
    <header className="suite-topbar">
      <button
        className="hamburger"
        aria-label="Toggle navigation"
        onClick={onToggle}
      >
        <Menu />
      </button>
      <a
        className="product-lockup"
        href="./index.html"
        aria-label="Return to the Parakh landing page"
      >
        <div className="brand-mark">P</div>
        <strong>Parakh</strong>
      </a>
      <div className="case-title">
        <strong title={title}>{title}</strong>
        <small>{online ? "Backend connected" : "Demo data · Offline"}</small>
      </div>
      <label className="global-search">
        <Search />
        <input
          id="global-search"
          type="search"
          placeholder="Search workspace…"
          aria-label="Search workspace"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
        />
        <kbd>⌘K</kbd>
      </label>
      {!online && (
        <button className="connect-button" onClick={onConnect}>
          Connect backend
        </button>
      )}
      <span className={`chain-status ${verified ? "" : "chain-warning"}`}>
        {verified ? <ShieldCheck /> : <ShieldAlert />}
        {verified ? "Chain verified" : "Chain needs review"}
      </span>
      <button
        className="profile-button"
        aria-label="User profile"
        onClick={onProfile}
      >
        <UserRound />
      </button>
    </header>
  );
}
