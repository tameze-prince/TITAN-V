"use client";

import { type FormEvent, useMemo, useState } from "react";

import type {
  EvaluationProfile,
  OperatorNotification,
  OperatorSession,
} from "../../lib/types";

const DEFAULT_CRITERIA = [
  {
    key: "correctness",
    description: "The result directly addresses the task objective.",
    kind: "PRESENCE",
    weight: 1,
    required: true,
    position: 0,
  },
  {
    key: "evidence",
    description: "The artifact contains concrete supporting evidence.",
    kind: "PRESENCE",
    weight: 1,
    required: true,
    position: 1,
  },
];

export function GovernanceConsole({
  initialProfiles,
  initialNotifications,
  session,
  notificationsScoped,
}: {
  initialProfiles: EvaluationProfile[];
  initialNotifications: OperatorNotification[];
  session: OperatorSession;
  notificationsScoped: boolean;
}) {
  const [profiles, setProfiles] = useState(initialProfiles);
  const [notifications, setNotifications] = useState(initialNotifications);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const canAdmin = session.role === "admin";
  const unreadCount = useMemo(
    () => notifications.filter((item) => item.status === "UNREAD").length,
    [notifications],
  );

  async function activate(profile: EvaluationProfile) {
    setBusy(profile.id);
    setMessage(null);
    try {
      const response = await fetch(
        "/api/titan/evaluator-profiles/" + profile.id + "/activate",
        { method: "POST" },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Activation failed.");
      }

      setProfiles((current) =>
        current.map((item) =>
          item.name === payload.name
            ? {
                ...item,
                status: item.id === payload.id ? "ACTIVE" : "SUPERSEDED",
                activated_at:
                  item.id === payload.id ? payload.activated_at : item.activated_at,
              }
            : item,
        ),
      );
      setMessage("Activated " + payload.name + " v" + payload.version + ".");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Activation failed.");
    } finally {
      setBusy(null);
    }
  }

  async function acknowledge(notificationId: string) {
    setBusy(notificationId);
    setMessage(null);
    try {
      const response = await fetch(
        "/api/titan/notifications/" + notificationId + "/acknowledge",
        { method: "POST" },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Acknowledgement failed.");
      }

      setNotifications((current) =>
        current.map((item) =>
          item.id === notificationId ? { ...item, ...payload } : item,
        ),
      );
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Acknowledgement failed.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function createProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canAdmin) return;

    const form = new FormData(event.currentTarget);
    const criteriaText = String(form.get("criteria_json") ?? "").trim();

    let criteria = DEFAULT_CRITERIA;
    if (criteriaText) {
      try {
        const parsed = JSON.parse(criteriaText);
        if (!Array.isArray(parsed) || parsed.length === 0) {
          throw new Error("criteria must be a non-empty array");
        }
        criteria = parsed;
      } catch (error) {
        setMessage(
          error instanceof Error
            ? "Invalid criteria JSON: " + error.message
            : "Criteria JSON is invalid.",
        );
        return;
      }
    }

    setBusy("create-profile");
    setMessage(null);

    try {
      const response = await fetch("/api/titan/evaluator-profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: String(form.get("name") ?? ""),
          scope_type: String(form.get("scope_type") ?? "GLOBAL"),
          scope_id: String(form.get("scope_id") ?? "").trim() || null,
          evaluator_kind: String(form.get("evaluator_kind") ?? "RULE_BASED"),
          evaluator_model:
            String(form.get("evaluator_model") ?? "").trim() || null,
          min_score: Number(form.get("min_score") ?? 1),
          min_confidence: Number(form.get("min_confidence") ?? 0.75),
          system_prompt:
            String(form.get("system_prompt") ?? "").trim() || null,
          criteria,
          activate: form.get("activate") === "on",
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Profile creation failed.");
      }

      setProfiles((current) =>
        payload.status === "ACTIVE"
          ? [
              payload,
              ...current.map((item) =>
                item.name === payload.name
                  ? { ...item, status: "SUPERSEDED" }
                  : item,
              ),
            ]
          : [payload, ...current],
      );
      event.currentTarget.reset();
      setMessage("Created " + payload.name + " v" + payload.version + ".");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Profile creation failed.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="stack governance-console">
      <section className="layout">
        <div className="card">
          <div className="row">
            <div>
              <h2>Evaluator profiles</h2>
              <p className="muted" style={{ marginTop: 6 }}>
                {profiles.length} versions · {canAdmin ? "admin controls enabled" : "read only"}
              </p>
            </div>
            <span className="badge">
              active {profiles.filter((item) => item.status === "ACTIVE").length}
            </span>
          </div>

          <div className="project-list" style={{ marginTop: 16 }}>
            {profiles.length === 0 ? (
              <p className="muted">No evaluator profiles are available.</p>
            ) : (
              profiles.map((profile) => (
                <article className="project" key={profile.id}>
                  <div>
                    <div className="project-title">
                      {profile.name} · v{profile.version}
                    </div>
                    <div className="project-meta">
                      <span
                        className={
                          "badge " +
                          (profile.status === "ACTIVE"
                            ? "success"
                            : profile.status === "DRAFT"
                              ? "warning"
                              : "")
                        }
                      >
                        {profile.status}
                      </span>
                      <span className="badge">{profile.scope_type}</span>
                      <span className="badge">{profile.evaluator_kind}</span>
                      <span className="badge">
                        score ≥ {(profile.min_score * 100).toFixed(0)}%
                      </span>
                      <span className="badge">
                        confidence ≥ {(profile.min_confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    {profile.evaluator_model ? (
                      <p className="muted" style={{ marginTop: 8 }}>
                        judge model: {profile.evaluator_model}
                      </p>
                    ) : null}

                    <div className="stack" style={{ marginTop: 12 }}>
                      {profile.criteria.map((criterion) => (
                        <div className="row" key={criterion.id}>
                          <div>
                            <strong>{criterion.key}</strong>
                            <div className="muted">{criterion.description}</div>
                          </div>
                          <span className="badge">
                            {criterion.required ? "required" : "optional"} ·{" "}
                            {criterion.weight}×
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {canAdmin && profile.status !== "ACTIVE" ? (
                    <button
                      className="button primary"
                      disabled={busy !== null}
                      onClick={() => void activate(profile)}
                    >
                      {busy === profile.id ? "Activating…" : "Activate"}
                    </button>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </div>

        <div className="card">
          <h2>Create profile version</h2>
          <p className="muted" style={{ marginBottom: 14 }}>
            Creating a profile always creates a new immutable version.
          </p>

          {canAdmin ? (
            <form className="stack" onSubmit={(event) => void createProfile(event)}>
              <label className="field">
                <span className="label">Profile name</span>
                <input name="name" required placeholder="strict-quality" />
              </label>

              <div className="form-grid">
                <label className="field">
                  <span className="label">Scope</span>
                  <select name="scope_type" defaultValue="GLOBAL">
                    <option value="GLOBAL">Global</option>
                    <option value="PROJECT">Project</option>
                  </select>
                </label>

                <label className="field">
                  <span className="label">Project ID</span>
                  <input name="scope_id" placeholder="required for PROJECT" />
                </label>
              </div>

              <div className="form-grid">
                <label className="field">
                  <span className="label">Evaluator</span>
                  <select name="evaluator_kind" defaultValue="RULE_BASED">
                    <option value="RULE_BASED">Rule based</option>
                    <option value="MODEL">Independent model</option>
                  </select>
                </label>

                <label className="field">
                  <span className="label">Evaluator model</span>
                  <input name="evaluator_model" placeholder="openai:gpt-5" />
                </label>
              </div>

              <div className="form-grid">
                <label className="field">
                  <span className="label">Minimum score</span>
                  <input
                    name="min_score"
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    defaultValue="1"
                  />
                </label>

                <label className="field">
                  <span className="label">Minimum confidence</span>
                  <input
                    name="min_confidence"
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    defaultValue="0.75"
                  />
                </label>
              </div>

              <label className="field">
                <span className="label">System prompt</span>
                <textarea
                  name="system_prompt"
                  rows={5}
                  placeholder="Used only by MODEL evaluator profiles."
                />
              </label>

              <label className="field">
                <span className="label">Criteria JSON</span>
                <textarea
                  name="criteria_json"
                  rows={9}
                  defaultValue={JSON.stringify(DEFAULT_CRITERIA, null, 2)}
                />
              </label>

              <label className="checkbox">
                <input name="activate" type="checkbox" defaultChecked />
                <span>Activate immediately</span>
              </label>

              <button className="button primary" disabled={busy !== null}>
                {busy === "create-profile"
                  ? "Creating…"
                  : "Create profile version"}
              </button>
            </form>
          ) : (
            <p className="muted">
              Your role can inspect governance but cannot create policy.
            </p>
          )}
          </div>
        )}
      </section>

      <section className="card">
        <div className="row">
          <div>
            <h2>Operator notifications</h2>
            <p className="muted" style={{ marginTop: 6 }}>
              Alerts requiring human review stay persisted until acknowledged.
            </p>
          </div>
          <span className={"badge " + (unreadCount ? "warning" : "success")}>
            {unreadCount} unread
          </span>
        </div>

        {!notificationsScoped ? (
          <p className="muted" style={{ marginTop: 16 }}>
            Notifications are project-scoped for your current authorization. Open
            the relevant project in the Command Center to review its alerts.
          </p>
        ) : (
          <div className="project-list" style={{ marginTop: 16 }}>
          {notifications.length === 0 ? (
            <p className="muted">No operator escalation is recorded.</p>
          ) : (
            notifications.map((notification) => (
              <article className="action-card" key={notification.id}>
                <div className="row">
                  <div>
                    <strong>{notification.title}</strong>
                    <div className="project-meta">
                      <span
                        className={
                          "badge " +
                          (notification.severity === "CRITICAL"
                            ? "danger"
                            : "warning")
                        }
                      >
                        {notification.severity}
                      </span>
                      <span className="badge">
                        {notification.notification_type}
                      </span>
                      <span className="badge">{notification.status}</span>
                    </div>
                  </div>

                  {notification.status === "UNREAD" ? (
                    <button
                      className="button"
                      disabled={busy !== null}
                      onClick={() => void acknowledge(notification.id)}
                    >
                      {busy === notification.id ? "Saving…" : "Acknowledge"}
                    </button>
                  ) : null}
                </div>

                <p style={{ marginTop: 10 }}>{notification.body}</p>
                <p className="muted" style={{ marginTop: 6 }}>
                  {new Date(notification.created_at).toLocaleString()}
                </p>
              </article>
            ))
          )}
        </div>
      </section>

      {message ? <p className="muted">{message}</p> : null}
    </div>
  );
}
