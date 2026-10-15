import type { ReactNode } from "react";
import styles from "./Layout.module.css";
export function AppShell({ children }: { children: ReactNode }) {
  return <div className={`${styles.root} suite-shell`}>{children}</div>;
}
