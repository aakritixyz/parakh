import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  fallbackDashboard,
  authenticate,
  loadCaseDashboard,
  type DashboardData,
} from "./api";
import { SignInPage } from "./components/entry/SignInPage";
import { EvidenceIntake } from "./components/intake/EvidenceIntake";
import { CaseWorkspace } from "./components/casework/CaseWorkspace";
import "./styles.css";
function App() {
  const [data, setData] = useState<DashboardData>(fallbackDashboard);
  const [caseId, setCaseId] = useState<number | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [intake, setIntake] = useState(true);
  const [caseTitle, setCaseTitle] = useState("Sample investigation");
  const [screen, setScreen] = useState<"signin" | "workspace">(() =>
    new URLSearchParams(window.location.search).get("mode") === "demo" &&
    window.location.pathname.endsWith("dashboard.html")
      ? "workspace"
      : "signin",
  );
  useEffect(() => {
    const pop = () =>
      setScreen(
        new URLSearchParams(window.location.search).get("mode") === "demo" &&
          window.location.pathname.endsWith("dashboard.html")
          ? "workspace"
          : "signin",
      );
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);
  function enter(mode: "demo" | "investigator", next: DashboardData) {
    setData(next);
    const params = new URLSearchParams(window.location.search);
    params.set("mode", mode);
    window.history.replaceState(
      null,
      "",
      "./dashboard.html?" + params.toString(),
    );
    document.title =
      mode === "demo"
        ? "Demo workspace | Parakh"
        : "Investigator workspace | Parakh";
    setScreen("workspace");
  }
  if (screen === "signin")
    return (
      <SignInPage
        onDemo={() => {
          setToken(null);
          setIntake(true);
          enter("demo", fallbackDashboard);
        }}
        onSignIn={async (credentials) => {
          setToken(await authenticate(credentials));
          setIntake(true);
          enter("investigator", fallbackDashboard);
        }}
      />
    );
  if (intake)
    return (
      <EvidenceIntake
        token={token}
        onBack={() => {
          setToken(null);
          window.history.pushState(null, "", "./signin.html");
          setScreen("signin");
        }}
        onReview={async (caseId, title) => {
          setData(
            token && caseId
              ? await loadCaseDashboard(caseId, token)
              : fallbackDashboard,
          );
          setCaseId(caseId);
          setCaseTitle(title);
          setIntake(false);
        }}
      />
    );
  return (
    <CaseWorkspace
      data={data}
      title={caseTitle}
      token={token}
      caseId={caseId}
      onNew={() => setIntake(true)}
      onSignOut={() => {
        setToken(null);
        window.history.pushState(null, "", "./signin.html");
        setScreen("signin");
      }}
    />
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
