import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { fallbackDashboard, type DashboardData } from "./api";
import {
  caseDashboard,
  getCase,
  getAudit,
  type Audit,
  forgetSession,
  refreshSession,
  signIn,
  signOut,
  subscribeSession,
  type CaseInfo,
  type Session,
} from "./caseApi";
import { SignInPage } from "./components/entry/SignInPage";
import { ActiveCases } from "./components/cases/ActiveCases";
import { EvidenceIntake } from "./components/intake/EvidenceIntake";
import { CaseWorkspace } from "./components/casework/CaseWorkspace";
import "./styles.css";
function App() {
  const [signOutNotice, setSignOutNotice] = useState("");
  const params = new URLSearchParams(window.location.search);
  const [mode, setMode] = useState<"signin" | "demo" | "signed">(
    params.get("mode") === "demo" ? "demo" : "signin",
  );
  const [session, setSession] = useState<Session | null>(null),
    [view, setView] = useState<"cases" | "upload" | "case">("cases"),
    [item, setItem] = useState<CaseInfo | null>(null),
    [caseAudit, setCaseAudit] = useState<Audit | null>(null),
    [data, setData] = useState<DashboardData>(fallbackDashboard),
    [restoring, setRestoring] = useState(params.get("mode") === "investigator");
  useEffect(
    () =>
      subscribeSession((value) => {
        setSession(value);
        if (!value)
          setMode((current) => (current === "signed" ? "signin" : current));
      }),
    [],
  );
  useEffect(() => {
    if (
      new URLSearchParams(window.location.search).get("mode") !== "investigator"
    )
      return;
    let active = true;
    refreshSession()
      .then((value) => {
        if (active) {
          setSession(value);
          setMode("signed");
        }
      })
      .catch(() => {
        if (active) setMode("signin");
      })
      .finally(() => {
        if (active) setRestoring(false);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    document.title =
      mode === "signin"
        ? "Investigator sign-in | Parakh"
        : view === "cases"
          ? "Active Cases | Parakh"
          : view === "upload"
            ? "Upload evidence | Parakh"
            : `${item?.title ?? "Case workspace"} | Parakh`;
  }, [mode, view, item?.title]);
  async function logout() {
    if (mode === "demo") {
      forgetSession();
      setSignOutNotice("");
      setMode("signin");
      setView("cases");
      setItem(null);
      window.history.replaceState(null, "", "./signin.html");
      return;
    }
    try {
      await signOut();
      setSignOutNotice("");
    } catch {
      forgetSession();
      setSignOutNotice(
        "Signed out of this page. The server could not confirm session revocation; sign in again and retry signing out when connected.",
      );
    }
    setMode("signin");
    setView("cases");
    setItem(null);
    window.history.replaceState(null, "", "./signin.html");
  }
  function enter(next: "demo" | "signed") {
    setSignOutNotice("");
    setMode(next);
    setView("cases");
    window.history.replaceState(
      null,
      "",
      `./dashboard.html?mode=${next === "demo" ? "demo" : "investigator"}`,
    );
  }
  async function openCase(selected: CaseInfo) {
    if (mode === "demo") {
      setData(fallbackDashboard);
      setItem(selected);
      setCaseAudit(null);
    } else {
      const [fresh, dashboard, audit] = await Promise.all([
        getCase(selected.id),
        caseDashboard(selected.id),
        getAudit(selected.id),
      ]);
      setItem(fresh);
      setData({ ...dashboard, online: true });
      setCaseAudit(audit);
    }
    setView("case");
  }
  if (restoring)
    return (
      <main style={{ padding: 32 }} role="status">
        Restoring your session…
      </main>
    );
  if (mode === "signin")
    return (
      <SignInPage
        notice={signOutNotice}
        onDemo={() => {
          forgetSession();
          enter("demo");
        }}
        onSignIn={async (credentials) => {
          setSession(await signIn(credentials));
          enter("signed");
        }}
      />
    );
  if (view === "upload" && item && session)
    return (
      <EvidenceIntake
        key={item.id}
        token={session.access_token}
        existingCaseId={item.id}
        initialTitle={item.title}
        backLabel="Back to Active Cases"
        onBack={() => setView("cases")}
        onReview={async () => openCase(item)}
      />
    );
  if (view === "case" && item)
    return (
      <CaseWorkspace
        data={data}
        caseAudit={caseAudit}
        title={item.title}
        token={session?.access_token ?? null}
        caseId={item.id}
        readOnly={mode === "demo" || !item.can_edit}
        onNew={() => setView("cases")}
        onSignOut={logout}
      />
    );
  return (
    <ActiveCases
      key={`${mode}-${view}`}
      user={session?.user ?? null}
      onLogout={logout}
      onOpen={openCase}
      onUpload={(selected) => {
        setItem(selected);
        setView("upload");
      }}
    />
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
