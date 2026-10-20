"use client";

import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import Button from "@/components/button";
import DocumentWorkspace from "@/features/documents/components/document-workspace";
import { getCurrentUser, logout } from "../api/auth";
import type { User } from "../api/auth";
import AuthForm from "./auth-form";
import styles from "./auth.module.css";

function SessionContent() {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const logoutInProgress = useRef(false);
  const [logoutError, setLogoutError] = useState("");
  const session = useQuery({
    queryKey: ["session"],
    queryFn: ({ signal }) => getCurrentUser(signal),
    retry: false,
    staleTime: 0,
  });

  async function setSession(user: User | null) {
    await queryClient.cancelQueries({ queryKey: ["session"] });
    queryClient.setQueryData(["session"], user);
  }

  async function handleSessionExpired() {
    setNotice("Your session has expired. Please sign in again.");
    await setSession(null);
  }

  async function handleLogout() {
    if (logoutInProgress.current) return;
    logoutInProgress.current = true;
    setSigningOut(true);
    setLogoutError("");
    try {
      await logout();
      setNotice("You have signed out.");
      await setSession(null);
    } catch {
      setLogoutError("Sign-out could not be confirmed. Please try again.");
    } finally {
      logoutInProgress.current = false;
      setSigningOut(false);
    }
  }

  if (session.isPending) return <p role="status" className={styles.notice}>Checking your session…</p>;
  if (session.isError) return (
    <section className={styles.card}>
      <h1>Unable to check your session</h1>
      <p role="alert" className={styles.notice}>Check your connection and try again.</p>
      <Button onClick={() => void session.refetch()} disabled={session.isFetching}>Try again</Button>
    </section>
  );
  if (!session.data) return <AuthForm onSignedIn={setSession} notice={notice} />;

  return (
    <>
      <header className={styles.workspaceHeader}>
        <h1>Your documents</h1>
        <div className={styles.account}>
          <span>{session.data.email}</span>
          <Button onClick={() => void handleLogout()} disabled={signingOut}>{signingOut ? "Signing out…" : "Sign out"}</Button>
        </div>
      </header>
      {logoutError && <p role="alert" className={styles.error}>{logoutError}</p>}
      {signingOut ? <p role="status">Signing out…</p> : <DocumentWorkspace key={session.data.id} onSessionExpired={handleSessionExpired} />}
    </>
  );
}

export default function AuthenticatedWorkspace() {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <main className={styles.shell}>
      <p className={styles.brand}>Documind</p>
      <QueryClientProvider client={queryClient}><SessionContent /></QueryClientProvider>
    </main>
  );
}
