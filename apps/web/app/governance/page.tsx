import Link from "next/link";

import { titanFetch } from "../../lib/api";
import type {
  EvaluationProfile,
  OperatorNotification,
  OperatorSession,
} from "../../lib/types";
import { GovernanceConsole } from "./GovernanceConsole";

export default async function GovernancePage() {
  try {
    const [profiles, notifications, session] = await Promise.all([
      titanFetch<EvaluationProfile[]>("/api/v1/control-plane/evaluator-profiles"),
      titanFetch<OperatorNotification[]>(
        "/api/v1/control-plane/notifications?limit=100",
      ),
      titanFetch<OperatorSession>("/api/v1/auth/session"),
    ]);

    return (
      <main className="shell">
        <header className="topbar">
          <Link href="/" className="badge">
            ← Command Center
          </Link>
          <span className="badge">Governance</span>
        </header>

        <section className="hero">
          <p className="eyebrow">Operator governance</p>
          <h1>Evaluation profiles & alerts.</h1>
          <p>
            Version the quality rules TITAN uses to judge outputs, activate them
            deliberately, and acknowledge human-escalation alerts.
          </p>
        </section>

        <GovernanceConsole
          initialProfiles={profiles}
          initialNotifications={notifications}
          session={session}
        />
      </main>
    );
  } catch (error) {
    return (
      <main className="shell">
        <div className="card error">
          <Link href="/" className="badge">
            ← Command Center
          </Link>
          <p className="eyebrow" style={{ marginTop: 18 }}>
            Governance unavailable
          </p>
          <h1>Cannot load governance controls.</h1>
          <p className="muted" style={{ marginTop: 10 }}>
            {error instanceof Error ? error.message : "Unknown API error"}
          </p>
        </div>
      </main>
    );
  }
}
