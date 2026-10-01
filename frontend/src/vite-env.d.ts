/// <reference types="vite/client" />

declare module "react" {
  export type ReactNode = unknown;
  export type CSSProperties = Record<string, string | number>;
  export type Key = string | number;
  export function useEffect(effect: () => void | (() => void), deps?: unknown[]): void;
  export function useMemo<T>(factory: () => T, deps?: unknown[]): T;
  export function useState<T>(initial: T | (() => T)): [T, (value: T | ((previous: T) => T)) => void];
  export const StrictMode: (props: { children?: ReactNode }) => unknown;
  const React: {
    StrictMode: typeof StrictMode;
  };
  export default React;
}

declare module "react-dom/client" {
  export function createRoot(element: Element): {
    render(node: unknown): void;
  };
}

declare module "react/jsx-runtime" {
  export const Fragment: (props: { children?: unknown }) => unknown;
  export function jsx(type: unknown, props: unknown, key?: unknown): unknown;
  export function jsxs(type: unknown, props: unknown, key?: unknown): unknown;
}

declare namespace JSX {
  type Element = unknown;
  interface ElementChildrenAttribute {
    children: unknown;
  }
  interface IntrinsicAttributes {
    key?: string | number;
  }
  interface IntrinsicElements {
    [elementName: string]: Record<string, unknown>;
  }
}
