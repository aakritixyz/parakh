import { useRef, type ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import styles from "./UI.module.css";

/** Keep ordinary lists native; measure variable-height event rows once a case exceeds 500 records. */
export function VirtualList<T>({
  items,
  children,
}: {
  items: T[];
  children: (item: T, index: number) => ReactNode;
}) {
  const scrollElement = useRef<HTMLDivElement>(null);
  const virtual = items.length > 500;
  const rows = useVirtualizer({
    count: virtual ? items.length : 0,
    getScrollElement: () => scrollElement.current,
    estimateSize: () => 56,
    overscan: 8,
  });
  return (
    <div
      ref={scrollElement}
      className={`event-list ${virtual ? styles.virtualList : ""}`}
    >
      {virtual ? (
        <div
          className={styles.virtualSpace}
          style={{ height: rows.getTotalSize() }}
        >
          {rows.getVirtualItems().map((row) => (
            <div
              key={row.key}
              ref={rows.measureElement}
              data-index={row.index}
              className={styles.virtualRow}
              style={{ transform: `translateY(${row.start}px)` }}
            >
              {children(items[row.index], row.index)}
            </div>
          ))}
        </div>
      ) : (
        items.map((item, index) => (
          <div key={index}>{children(item, index)}</div>
        ))
      )}
    </div>
  );
}
