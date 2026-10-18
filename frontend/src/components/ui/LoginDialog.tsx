import { useEffect, useRef, useState, type FormEvent } from "react";
import { X } from "lucide-react";
import type { LoginCredentials } from "../../api";
import { Button, Input } from "./index";
import styles from "./UI.module.css";

export function LoginDialog({
  onClose,
  onConnect,
}: {
  onClose: () => void;
  onConnect: (credentials: LoginCredentials) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const element = dialog.current;
    element?.showModal();
    element?.querySelector<HTMLInputElement>('input[name="username"]')?.focus();
    return () => {
      element?.close();
      previous?.focus();
    };
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await onConnect({ username: username.trim(), password });
      onClose();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to connect to the backend.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <dialog
      ref={dialog}
      className={styles.loginDialog}
      aria-labelledby="login-title"
      onCancel={(event) => {
        event.preventDefault();
        if (!pending) onClose();
      }}
    >
      <header>
        <h2 id="login-title">Connect to backend</h2>
        <Button
          variant="ghost"
          aria-label="Close sign-in"
          onClick={onClose}
          disabled={pending}
        >
          <X />
        </Button>
      </header>
      <p>
        Use the account configured for this server. The offline demo stays
        available without signing in.
      </p>
      <form onSubmit={submit}>
        <label>
          Username
          <Input
            autoFocus
            name="username"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            disabled={pending}
          />
        </label>
        <label>
          Password
          <Input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={pending}
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <Button
          variant="primary"
          type="submit"
          disabled={pending || !username.trim() || !password}
        >
          {pending ? "Connecting…" : "Sign in"}
        </Button>
      </form>
    </dialog>
  );
}
