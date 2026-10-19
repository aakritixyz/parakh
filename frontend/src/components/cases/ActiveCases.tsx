import { BrandMark } from "../ui/BrandMark";
import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  FileText,
  Plus,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import {
  createAccount,
  createCase,
  getAccounts,
  getAudit,
  getCases,
  getMembers,
  getCase,
  putMember,
  removeMember,
  type Account,
  type Audit,
  type CaseInfo,
  type CaseInput,
  type Member,
  type Role,
} from "../../caseApi";
import { time } from "../casework/model";
import styles from "./Cases.module.css";
const roles: Role[] = ["investigator", "analyst", "prosecutor"];
const initial: CaseInput = {
  title: "",
  case_number: "",
  jurisdiction: "",
  offence_type: "",
  description: "",
  lead_investigator: "",
  team_members: [],
};
const demoCase: CaseInfo = {
  id: 1,
  title: "Riya: investment scam complaint",
  case_number: "PARAKH-SYN-RIYA-001",
  jurisdiction: "Synthetic demo jurisdiction",
  offence_type: "UPI investment fraud",
  description: "Fictional source pack for investigator training.",
  lead_investigator: "Demo investigator",
  status: "open",
  evidence_count: 15,
  last_activity: "2026-10-18T00:00:00Z",
  created_at: "2026-10-18T00:00:00Z",
  effective_role: "prosecutor",
  can_manage: false,
  can_edit: false,
};
export function ActiveCases({
  user,
  onLogout,
  onOpen,
  onUpload,
}: {
  user: Account | null;
  onLogout: () => void;
  onOpen: (item: CaseInfo) => Promise<void>;
  onUpload: (item: CaseInfo) => void;
}) {
  const dialog = useRef<HTMLElement>(null);
  const demo = !user,
    canCreate = !!user && ["admin", "investigator"].includes(user.role);
  const [cases, setCases] = useState<CaseInfo[]>(demo ? [demoCase] : []),
    [accounts, setAccounts] = useState<Account[]>([]),
    [selected, setSelected] = useState<CaseInfo | null>(null),
    [form, setForm] = useState(false),
    [input, setInput] = useState<CaseInput>({
      ...initial,
      lead_investigator: user?.username ?? "",
    }),
    [members, setMembers] = useState<Member[]>([]),
    [audit, setAudit] = useState<Audit | null>(null),
    [showAudit, setShowAudit] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(!demo);
  const [memberName, setMemberName] = useState(""),
    [memberRole, setMemberRole] = useState<Role>("prosecutor");
  const [accountForm, setAccountForm] = useState(false),
    [newName, setNewName] = useState(""),
    [newPassword, setNewPassword] = useState(""),
    [newRole, setNewRole] = useState<Role>("analyst");
  useEffect(() => {
    if (demo) return;
    let active = true;
    (async () => {
      try {
        const list = await getCases();
        if (active) setCases(list);
        if (canCreate) {
          const people = await getAccounts();
          if (active) setAccounts(people);
        }
      } catch (cause) {
        if (active)
          setError(
            cause instanceof Error ? cause.message : "Could not load cases.",
          );
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [demo, canCreate]);
  useEffect(() => {
    if (!form) return;
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.querySelector<HTMLInputElement>("input")?.focus();
    const keys = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" &&
        !dialog.current?.querySelector<HTMLButtonElement>(
          'button[type="submit"]',
        )?.disabled
      )
        setForm(false);
      if (event.key === "Tab") {
        const nodes = Array.from(
          dialog.current?.querySelectorAll<HTMLElement>(
            "button:not(:disabled),input,select,textarea",
          ) ?? [],
        );
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", keys);
    return () => {
      window.removeEventListener("keydown", keys);
      previous?.focus();
    };
  }, [form]);
  async function inspect(item: CaseInfo) {
    setSelected(item);
    setShowAudit(false);
    setError("");
    if (!demo) {
      try {
        const [team, log] = await Promise.all([
          getMembers(item.id),
          getAudit(item.id),
        ]);
        setMembers(team);
        setAudit(log);
      } catch (cause) {
        setError(
          cause instanceof Error ? cause.message : "Could not open case.",
        );
      }
    }
  }
  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    void perform(async () => {
      const created = await createCase(input);
      setCases(await getCases());
      setForm(false);
      setInput({ ...initial, lead_investigator: user?.username ?? "" });
      await inspect(created);
    });
  }
  async function refreshTeam() {
    if (selected) {
      const [team, log] = await Promise.all([
        getMembers(selected.id),
        getAudit(selected.id),
      ]);
      setMembers(team);
      setAudit(log);
      const fresh = await getCase(selected.id);
      setSelected(fresh);
    }
  }
  const availableRoles = (name: string): Role[] => {
    const role = accounts.find((a) => a.username === name)?.role;
    return role === "prosecutor"
      ? ["prosecutor"]
      : role === "analyst"
        ? ["analyst", "prosecutor"]
        : user?.role === "admin" && role === "admin"
          ? ["admin", ...roles]
          : roles;
  };
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <a href="./index.html">
          <BrandMark /><strong>Parakh</strong>
        </a>
        <div>
          <strong>Investigator workspace</strong>
          <small>
            {demo
              ? "Demo viewer · Read-only"
              : `${user.username} · ${user.role}`}
          </small>
        </div>
        <span>IST · UTC+05:30</span>
        <button onClick={onLogout}>{demo ? "Sign in" : "Sign out"}</button>
      </header>
      <main className={styles.main}>
        {demo && (
          <p className={styles.banner}>
            <ShieldCheck />
            Synthetic demo data · Read-only. No account, case or permission
            changes are made in demo mode.
          </p>
        )}
        <div className={styles.title}>
          <div>
            <p>Cases / Investigator workspace</p>
            <h1>{selected ? selected.title : "Active Cases"}</h1>
          </div>
          {!selected && (
            <div className={styles.actions}>
              {user?.role === "admin" && (
                <button onClick={() => setAccountForm(!accountForm)}>
                  <Users />
                  Provision team account
                </button>
              )}
              <button
                className={styles.primary}
                onClick={() => setForm(true)}
                disabled={!canCreate || busy}
              >
                <Plus />
                New case
              </button>
            </div>
          )}
        </div>
        {error && (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        )}
        {accountForm && user?.role === "admin" && (
          <section className={styles.panel}>
            <h2>Provision an account</h2>
            <p>
              System roles set the maximum access. A case membership is also
              required for non-admin users.
            </p>
            <form
              className={styles.fields}
              onSubmit={(e) => {
                e.preventDefault();
                void perform(async () => {
                  await createAccount(newName, newPassword, newRole);
                  setNewPassword("");
                  setNewName("");
                  setAccounts(await getAccounts());
                  setAccountForm(false);
                });
              }}
            >
              <label>
                Account username
                <input
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  autoComplete="off"
                />
              </label>
              <label>
                Initial password
                <input
                  required
                  type="password"
                  value={newPassword}
                  minLength={12}
                  maxLength={72}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </label>
              <label>
                System role
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as Role)}
                >
                  {["admin", ...roles].map((r) => (
                    <option key={r}>{r}</option>
                  ))}
                </select>
              </label>
              <button disabled={busy}>Create account</button>
            </form>
          </section>
        )}
        {!selected ? (
          <section className={styles.panel}>
            <div className={styles.sectionTitle}>
              <h2>Your active cases</h2>
              <span>
                Only cases permitted by your account and membership are listed.
              </span>
            </div>
            {loading ? (
              <p role="status">Loading cases…</p>
            ) : cases.length ? (
              <div className={styles.tableWrap}>
                <table>
                  <thead>
                    <tr>
                      <th>Case / FIR number</th>
                      <th>Status</th>
                      <th>Evidence</th>
                      <th>Last activity · IST</th>
                      <th>Your case role</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <button
                            className={styles.caseLink}
                            onClick={() => inspect(c)}
                          >
                            {c.title}
                          </button>
                          <small>
                            {c.case_number || "Case number not supplied"}
                          </small>
                        </td>
                        <td>
                          <span className={styles.status}>{c.status}</span>
                        </td>
                        <td>
                          <button onClick={() => inspect(c)}>
                            {c.evidence_count} files
                          </button>
                        </td>
                        <td>
                          <button
                            onClick={() => {
                              void inspect(c);
                              setShowAudit(true);
                            }}
                          >
                            {time(c.last_activity)}
                          </button>
                        </td>
                        <td>{demo ? "Read-only demo" : c.effective_role}</td>
                        <td>
                          <button
                            aria-label={`Open case ${c.title}`}
                            onClick={() =>
                              demo
                                ? void perform(() => onOpen(c))
                                : void inspect(c)
                            }
                          >
                            Open case
                            <ArrowRight />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className={styles.empty}>
                <FolderIcon />
                <h2>No active cases yet.</h2>
                <p>
                  {canCreate
                    ? "Create a case, then upload the logical evidence exports."
                    : "Ask a case investigator or admin to add you as a member."}
                </p>
              </div>
            )}
          </section>
        ) : (
          <>
            <button
              className={styles.back}
              onClick={() => {
                setSelected(null);
                setAudit(null);
                setMembers([]);
                setShowAudit(false);
              }}
            >
              <ArrowLeft />
              Active Cases
            </button>
            <div className={styles.grid}>
              <section className={styles.panel}>
                <h2>Case record</h2>
                <dl>
                  {[
                    ["FIR / case number", selected.case_number],
                    ["Police station / jurisdiction", selected.jurisdiction],
                    ["Offence type", selected.offence_type],
                    ["Lead investigator", selected.lead_investigator],
                    ["Status", selected.status],
                    [
                      "Your case role",
                      demo ? "Read-only demo" : selected.effective_role,
                    ],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value || "Not supplied"}</dd>
                    </div>
                  ))}
                </dl>
                <p>{selected.description}</p>
                <p className={styles.note}>
                  Case details are administrative records, not evidentiary
                  findings. Changes are linked to the audit log.
                </p>
              </section>
              <section className={styles.panel}>
                <h2>Evidence</h2>
                {selected.evidence_count === 0 ? (
                  <>
                    <p>No evidence yet. Add your first file.</p>
                    <p className={styles.note}>
                      Logical exports only. Original uploaded bytes are
                      preserved.
                    </p>
                  </>
                ) : (
                  <p>{selected.evidence_count} source files in this case.</p>
                )}
                <div className={styles.actions}>
                  <button
                    disabled={demo || !selected.can_edit || busy}
                    onClick={() => onUpload(selected)}
                  >
                    Upload evidence
                  </button>
                  <button
                    className={styles.primary}
                    disabled={!selected.evidence_count || busy}
                    onClick={() => perform(() => onOpen(selected))}
                  >
                    Open case workspace
                    <ArrowRight />
                  </button>
                </div>
                {!selected.can_edit && (
                  <p className={styles.note}>
                    Read-only access: uploads, case editing and membership
                    changes are unavailable.
                  </p>
                )}
              </section>
            </div>
            {!demo && (
              <section className={styles.panel}>
                <div className={styles.sectionTitle}>
                  <h2>Case access</h2>
                  <span>
                    Account role and case role both apply. Prosecutors are
                    always read-only.
                  </span>
                </div>
                <ul className={styles.members}>
                  {members.map((m) => (
                    <li key={m.user_id}>
                      <strong>{m.username}</strong>
                      <span>
                        {m.role} · system: {m.system_role}
                      </span>
                      {selected.can_manage &&
                        m.username !== selected.lead_investigator && (
                          <button
                            disabled={busy}
                            onClick={() =>
                              perform(async () => {
                                await removeMember(selected.id, m.user_id);
                                await refreshTeam();
                              })
                            }
                          >
                            Remove access
                          </button>
                        )}
                    </li>
                  ))}
                </ul>
                {selected.can_manage && (
                  <form
                    className={styles.inlineForm}
                    onSubmit={(e) => {
                      e.preventDefault();
                      void perform(async () => {
                        await putMember(selected.id, memberName, memberRole);
                        await refreshTeam();
                        setMemberName("");
                      });
                    }}
                  >
                    <label>
                      Team account
                      <select
                        required
                        value={memberName}
                        onChange={(e) => {
                          setMemberName(e.target.value);
                          setMemberRole(availableRoles(e.target.value)[0]);
                        }}
                      >
                        <option value="">Choose an existing account</option>
                        {accounts
                          .filter(
                            (a) => a.username !== selected.lead_investigator,
                          )
                          .map((a) => (
                            <option key={a.id} value={a.username}>
                              {a.username} ({a.role})
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Case role
                      <select
                        value={memberRole}
                        onChange={(e) => setMemberRole(e.target.value as Role)}
                      >
                        {availableRoles(memberName).map((r) => (
                          <option key={r}>{r}</option>
                        ))}
                      </select>
                    </label>
                    <button disabled={!memberName || busy}>
                      Add / update member
                    </button>
                  </form>
                )}
              </section>
            )}
            {!demo && (
              <section className={styles.panel}>
                <div className={styles.sectionTitle}>
                  <h2>
                    <ShieldCheck />
                    Audit log
                  </h2>
                  <button
                    onClick={() => setShowAudit(!showAudit)}
                    aria-expanded={showAudit}
                  >
                    {showAudit ? "Hide audit log" : "Show audit log"}
                  </button>
                </div>
                {audit && (
                  <p
                    className={
                      audit.chain_verified ? styles.verified : styles.error
                    }
                  >
                    {audit.chain_verified ? "Chain verified" : "Chain broken"} ·{" "}
                    {audit.scope}
                  </p>
                )}
                {showAudit &&
                  audit?.entries.map((a) => (
                    <article className={styles.audit} key={a.id}>
                      <strong>{a.action}</strong>
                      <p>
                        {a.actor} · {time(a.created_at)}
                      </p>
                      <pre>{JSON.stringify(a.payload, null, 2)}</pre>
                      <code>Previous: {a.previous_hash}</code>
                      <code>Entry: {a.entry_hash}</code>
                    </article>
                  ))}
              </section>
            )}
          </>
        )}
        {form && (
          <div className={styles.backdrop}>
            <section
              ref={dialog}
              className={styles.dialog}
              role="dialog"
              aria-modal="true"
              aria-label="New case"
            >
              <div className={styles.sectionTitle}>
                <h2>New case</h2>
                <button
                  aria-label="Close new case"
                  onClick={() => setForm(false)}
                  disabled={busy}
                >
                  <X />
                </button>
              </div>
              <p>
                Name the case and define who may access it. Upload evidence
                after creating the case.
              </p>
              <form onSubmit={submit}>
                <div className={styles.fields}>
                  {[
                    ["title", "Case title"],
                    ["case_number", "FIR / case number"],
                    ["jurisdiction", "Police station / jurisdiction"],
                    ["offence_type", "Offence type"],
                  ].map(([key, label]) => (
                    <label key={key}>
                      {label}
                      <input
                        required={key === "title"}
                        maxLength={
                          key === "title"
                            ? 200
                            : key === "jurisdiction"
                              ? 200
                              : 120
                        }
                        value={String(input[key as keyof CaseInput])}
                        onChange={(e) =>
                          setInput((value) => ({
                            ...value,
                            [key]: e.target.value,
                          }))
                        }
                      />
                    </label>
                  ))}
                  <label>
                    Description
                    <textarea
                      value={input.description}
                      onChange={(e) =>
                        setInput((value) => ({
                          ...value,
                          description: e.target.value,
                        }))
                      }
                      maxLength={10000}
                    />
                  </label>
                  <label>
                    Lead investigator
                    <select
                      required
                      value={input.lead_investigator}
                      onChange={(e) =>
                        setInput((value) => ({
                          ...value,
                          lead_investigator: e.target.value,
                        }))
                      }
                    >
                      <option value="">Select a lead</option>
                      {accounts
                        .filter((a) =>
                          ["admin", "investigator"].includes(a.role),
                        )
                        .map((a) => (
                          <option key={a.id} value={a.username}>
                            {a.username}
                          </option>
                        ))}
                    </select>
                  </label>
                </div>
                <h3>Team members and case roles</h3>
                <p className={styles.note}>
                  Accounts must be provisioned by an admin first. The case
                  creator and lead receive investigator access automatically.
                </p>
                {input.team_members.map((m, i) => (
                  <div className={styles.inlineForm} key={i}>
                    <label>
                      Team member {i + 1}
                      <select
                        required
                        value={m.username}
                        onChange={(e) =>
                          setInput((value) => ({
                            ...value,
                            team_members: value.team_members.map(
                              (row, index) =>
                                index === i
                                  ? {
                                      username: e.target.value,
                                      role: availableRoles(e.target.value)[0],
                                    }
                                  : row,
                            ),
                          }))
                        }
                      >
                        <option value="">Choose an account</option>
                        {accounts
                          .filter(
                            (a) =>
                              a.username !== input.lead_investigator &&
                              a.username !== user?.username,
                          )
                          .map((a) => (
                            <option key={a.id} value={a.username}>
                              {a.username} ({a.role})
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Member role {i + 1}
                      <select
                        value={m.role}
                        onChange={(e) =>
                          setInput((value) => ({
                            ...value,
                            team_members: value.team_members.map(
                              (row, index) =>
                                index === i
                                  ? { ...row, role: e.target.value as Role }
                                  : row,
                            ),
                          }))
                        }
                      >
                        {availableRoles(m.username).map((r) => (
                          <option key={r}>{r}</option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        setInput((value) => ({
                          ...value,
                          team_members: value.team_members.filter(
                            (_, index) => i !== index,
                          ),
                        }))
                      }
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <div className={styles.actions}>
                  <button
                    type="button"
                    onClick={() =>
                      setInput((value) => ({
                        ...value,
                        team_members: [
                          ...value.team_members,
                          { username: "", role: "prosecutor" },
                        ],
                      }))
                    }
                  >
                    <Plus />
                    Add team member
                  </button>
                  <button
                    className={styles.primary}
                    type="submit"
                    disabled={busy}
                  >
                    {busy ? "Creating…" : "Create case"}
                    <ArrowRight />
                  </button>
                </div>
                {error && (
                  <p className={styles.error} role="alert">
                    {error}
                  </p>
                )}
              </form>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
function FolderIcon() {
  return <FileText />;
}
