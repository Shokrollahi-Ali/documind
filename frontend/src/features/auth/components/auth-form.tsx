"use client";

import { useRef, useState } from "react";
import type { FormEvent } from "react";
import Button from "@/components/button";
import { submitCredentials } from "../api/auth";
import type { User } from "../api/auth";
import styles from "./auth.module.css";

export default function AuthForm({ onSignedIn, notice }: { onSignedIn: (user: User) => Promise<void>; notice: string }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState(notice);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const submitting = useRef(false);

  function changeMode() {
    setMode(mode === "login" ? "register" : "login");
    setPassword("");
    setError("");
    setMessage("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setPending(true);
    setError("");
    setMessage("");
    try {
      const user = await submitCredentials(mode, { email: email.trim(), password });
      setPassword("");
      if (mode === "register") {
        setMode("login");
        setMessage("Account created. Sign in to open your documents.");
      } else {
        await onSignedIn(user);
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : "Please try again.");
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  return (
    <section className={styles.card} aria-labelledby="auth-heading">
      <p className={styles.eyebrow}>Your document workspace</p>
      <h1 id="auth-heading">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <p className={styles.description}>{mode === "login" ? "Sign in to upload and manage your PDFs." : "Keep your documents together in your own workspace."}</p>
      {message && <p role="status" className={styles.notice}>{message}</p>}
      <form onSubmit={handleSubmit} aria-busy={pending}>
        <fieldset disabled={pending} className={styles.fields}>
          <label htmlFor="auth-email">Email</label>
          <input id="auth-email" name="email" type="email" autoComplete="username" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} />
          <label htmlFor="auth-password">Password</label>
          <input id="auth-password" name="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={mode === "register" ? 15 : 1} maxLength={128} aria-describedby={mode === "register" ? "password-help" : undefined} value={password} onChange={(event) => setPassword(event.target.value)} />
          {mode === "register" && <p id="password-help" className={styles.help}>Use 15–128 characters. A long passphrase works well.</p>}
          {error && <p role="alert" className={styles.error}>{error}</p>}
          <Button type="submit" variant="primary">{pending ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</Button>
        </fieldset>
      </form>
      <div className={styles.switchMode}>
        <span>{mode === "login" ? "New to Documind?" : "Already have an account?"}</span>
        <Button onClick={changeMode} disabled={pending}>{mode === "login" ? "Create an account" : "Back to sign in"}</Button>
      </div>
    </section>
  );
}
