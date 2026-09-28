"use client";

import { useState } from "react";

type TaskApprovalAction = {
  task_id: string;
  workflow_id: string;
  title: string;
  objective: string;
  risk_level: string;
  status: string;
  action: string;
  reason: string;
};

export function TaskApprovalControls({
  projectId,
  actions,
}: {
  projectId: string;
  actions: TaskApprovalAction[];
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function decide(
    action: TaskApprovalAction,
    approved: boolean,
  ) {
    setBusy(action.task_id);
    setMessage(null);

    try {
      const response = await fetch(
        "/api/titan/projects/" +
          projectId +
          "/tasks/" +
          action.task_id +
          "/approval",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            approved,
            reason: approved
              ? "Approved from TITAN Command Center"
              : "Rejected from TITAN Command Center",
          }),
        },
      );

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "Approval action failed with HTTP " + response.status,
        );
      }

      setMessage(
        typeof payload.reason === "string"
          ? payload.reason
          : "Decision recorded.",
      );
      window.setTimeout(() => window.location.reload(), 300);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Approval action failed.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card">
      <div className="row">
        <h2>Human approvals</h2>
        {actions.length ? (
          <span className="badge warning">{actions.length} pending</span>
        ) : (
          <span className="badge success">clear</span>
        )}
      </div>

      {actions.length === 0 ? (
        <p className="muted" style={{ marginTop: 12 }}>
          No task is currently waiting for human approval.
        </p>
      ) : (
        <div className="stack" style={{ marginTop: 12 }}>
          {actions.map((action) => (
            <div className="action-card" key={action.task_id}>
              <div className="row">
                <div>
                  <strong>{action.title}</strong>
                  <div className="muted">
                    {action.status} · risk {action.risk_level}
                  </div>
                </div>
                <span className="badge warning">approval required</span>
              </div>

              <p style={{ marginTop: 10 }}>{action.objective}</p>
              <p className="muted" style={{ marginTop: 6 }}>
                {action.reason}
              </p>

              <div className="action-buttons">
                <button
                  className="button primary"
                  disabled={busy !== null}
                  onClick={() => void decide(action, true)}
                >
                  {busy === action.task_id ? "Working…" : "Approve task"}
                </button>
                <button
                  className="button danger"
                  disabled={busy !== null}
                  onClick={() => void decide(action, false)}
                >
                  {busy === action.task_id ? "Working…" : "Reject task"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {message ? (
        <p className="muted" style={{ marginTop: 12 }}>
          {message}
        </p>
      ) : null}
    </div>
  );
}
