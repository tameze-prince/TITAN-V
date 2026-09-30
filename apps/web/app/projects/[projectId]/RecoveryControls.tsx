"use client";

import { useState } from "react";

type RecoveryAction = {
  workflow_id: string;
  workflow_name: string;
  workflow_type: string;
  workflow_status: string;
  action: string;
  reason: string;
  current_attempt?: number | null;
  failure_category?: string | null;
};

export function RecoveryControls({
  projectId,
  actions,
}: {
  projectId: string;
  actions: RecoveryAction[];
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function callAction(
    action: RecoveryAction,
    endpoint: "decision" | "rollback",
    body: Record<string, unknown>,
  ) {
    setBusy(action.workflow_id + ":" + endpoint);
    setMessage(null);

    try {
      const response = await fetch(
        "/api/titan/projects/" +
          projectId +
          "/workflows/" +
          action.workflow_id +
          "/recovery/" +
          endpoint,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "Action failed with HTTP " + response.status,
        );
      }

      setMessage(
        typeof payload.message === "string"
          ? payload.message
          : "Action completed.",
      );
      window.setTimeout(() => window.location.reload(), 300);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  }

  if (actions.length === 0) {
    return (
      <div className="card">
        <h2>Governed actions</h2>
        <p className="muted">No recovery action currently requires an operator.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Governed actions</h2>
      <div className="stack">
        {actions.map((action) => {
          const key = action.workflow_id + ":" + action.action;

          return (
            <div className="action-card" key={key}>
              <div className="row">
                <div>
                  <strong>{action.workflow_name}</strong>
                  <div className="muted">
                    {action.workflow_status} · {action.action}
                  </div>
                </div>
                {action.failure_category ? (
                  <span className="badge warning">{action.failure_category}</span>
                ) : null}
              </div>

              <p className="muted" style={{ marginTop: 10 }}>
                {action.reason}
              </p>

              {action.action === "APPROVE_OR_REJECT_RECOVERY" ? (
                <div className="action-buttons">
                  <button
                    className="button primary"
                    disabled={busy !== null}
                    onClick={() =>
                      void callAction(action, "decision", {
                        approved: true,
                        reason: "Approved from TITAN Command Center",
                      })
                    }
                  >
                    {busy === key + ":decision" ? "Approving…" : "Approve recovery"}
                  </button>
                  <button
                    className="button danger"
                    disabled={busy !== null}
                    onClick={() =>
                      void callAction(action, "decision", {
                        approved: false,
                        reason: "Rejected from TITAN Command Center",
                      })
                    }
                  >
                    {busy === key + ":decision" ? "Working…" : "Reject"}
                  </button>
                </div>
              ) : null}

              {action.action === "ROLLBACK_RECOVERY" ? (
                <div className="action-buttons">
                  <button
                    className="button danger"
                    disabled={busy !== null}
                    onClick={() =>
                      void callAction(action, "rollback", {
                        reason: "Rollback requested from TITAN Command Center",
                      })
                    }
                  >
                    {busy === key + ":rollback" ? "Rolling back…" : "Rollback recovery"}
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}

        {message ? <p className="muted">{message}</p> : null}
      </div>
    </div>
  );
}
