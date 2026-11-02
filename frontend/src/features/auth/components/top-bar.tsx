import Button from "@/components/button";
import type { User } from "../api/auth";
import styles from "./auth.module.css";

export default function TopBar({ user, isSigningOut, onSignOut }: {
  user?: User;
  isSigningOut: boolean;
  onSignOut: () => void;
}) {
  return (
    <header className={styles.topBar}>
      <p className={styles.brand}>Documind</p>
      {user && (
        <div className={styles.account}>
          <span>{user.email}</span>
          <Button variant="ghost" size="sm" onClick={onSignOut} disabled={isSigningOut}>
            {isSigningOut ? "Signing out…" : "Sign out"}
          </Button>
        </div>
      )}
    </header>
  );
}
