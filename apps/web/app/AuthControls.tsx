"use client";

import { useEffect, useState } from "react";

export type OperatorSession = {
  authenticated: boolean;
  subject: string;
  role: string;
  issuer: string | null;
  auth_method: string;
  user_id: string | null;
  session_id: string | null;
  email?: string | null;
  display_name?: string | null;
  expires_at?: string | null;
};

export function AuthControls({
  session,
}: {
  session: OperatorSession | null;
}) {
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!session) {
      return;
    }
    void fetch("/api/auth/rotate", { method: "POST" });
  }, [session]);

  if (!session) {
    return (
      <a className="button primary" href="/api/auth/login">
        Sign in with OIDC
      </a>
    );
  }

  async function logout() {
    setBusy(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      window.location.reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="row">
      <span className="badge">
        {session.display_name ?? session.subject} · {session.role}
      </span>
      <button
        className="button"
        disabled={busy}
        onClick={() => void logout()}
      >
        {busy ? "Signing out…" : "Sign out"}
      </button>
    </div>
  );
}
