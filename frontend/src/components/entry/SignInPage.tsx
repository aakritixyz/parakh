import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Eye,
  EyeOff,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type { LoginCredentials } from "../../api";
import styles from "./Entry.module.css";

export function SignInPage({
  onSignIn,
  onDemo,
}: {
  onSignIn: (credentials: LoginCredentials) => Promise<void>;
  onDemo: () => void;
}) {
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [visible, setVisible] = useState(false),
    [pending, setPending] = useState(false),
    [error, setError] = useState("");
  const usernameInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    usernameInput.current?.focus();
    document.title = "Investigator sign-in | Parakh";
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await onSignIn({ username: username.trim(), password });
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to sign in. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <div className={styles.entry}>
      <header className={styles.header}>
        <a className={styles.brand} href="./index.html">
          <span className={styles.mark}>P</span>Parakh
          <span className={styles.brandMeta}>Digital investigations</span>
        </a>
        <a className={styles.backLink} href="./index.html">
          <ArrowLeft /> Back to home
        </a>
      </header>
      <main className={styles.authMain}>
        <div className={styles.authFormColumn}>
          <span className={styles.authIcon}>
            <UserRound />
          </span>
          <span className={styles.eyebrow}>Investigator workspace</span>
          <h1>Welcome to Parakh.</h1>
          <p className={styles.authIntro}>
            Sign in to your investigation server, or take a look around with the
            sample case.
          </p>
          <form
            onSubmit={submit}
            className={styles.authForm}
            aria-label="Investigator sign-in"
            aria-busy={pending}
          >
            <label htmlFor="investigator-username">Username</label>
            <input
              ref={usernameInput}
              id="investigator-username"
              name="username"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={pending}
              placeholder="Enter your username"
            />
            <label htmlFor="investigator-password">Password</label>
            <div className={styles.passwordField}>
              <input
                id="investigator-password"
                name="password"
                type={visible ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={pending}
                placeholder="Enter your password"
              />
              <button
                type="button"
                aria-label={visible ? "Hide password" : "Show password"}
                aria-pressed={visible}
                onClick={() => setVisible(!visible)}
                disabled={pending}
              >
                {visible ? <EyeOff /> : <Eye />}
              </button>
            </div>
            {error && (
              <p role="alert" className={styles.authError}>
                {error}
              </p>
            )}
            <button
              className={styles.primary}
              type="submit"
              disabled={pending || !username.trim() || !password}
            >
              {pending ? "Signing in…" : "Sign in"}
              <ArrowRight />
            </button>
          </form>
          <div className={styles.orDivider}>
            <span />
            or explore first
            <span />
          </div>
          <button
            className={styles.demoButton}
            onClick={onDemo}
            disabled={pending}
          >
            View demo without signing in <ArrowRight />
          </button>
          <p className={styles.demoNote}>
            No account needed. Explore fictional evidence in the offline sample
            workspace.
          </p>
          <p className={styles.accountHelp}>
            Need access? Ask the person who manages your Parakh server for an
            investigator account.
          </p>
        </div>
        <aside className={styles.authStory}>
          <img
            src="./images/evidence-review.jpg"
            alt="Documents being reviewed at a desk beside laptops"
          />
          <div className={styles.authStoryCopy}>
            <span className={styles.eyebrow}>
              One place to see the whole picture
            </span>
            <h2>
              Follow the evidence.
              <br />
              Keep the context.
            </h2>
            <p>
              Move between records, timelines and connections in one
              investigator workspace.
            </p>
            <div>
              <ShieldCheck />
              <span>
                Self-hosted · Source-focused · Built for careful review
              </span>
            </div>
          </div>
        </aside>
      </main>
      <footer className={styles.authFooter}>
        <span>Parakh · Investigator access</span>
        <a href="./image-credits.html">Photo credits</a>
      </footer>
    </div>
  );
}
