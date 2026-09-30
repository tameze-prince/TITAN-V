import Link from "next/link";

import { titanFetch } from "../../../lib/api";
import type { ProjectOverview, StatusCounts } from "../../../lib/types";
import { LiveEvents } from "./LiveEvents";
import { RecoveryControls } from "./RecoveryControls";
import { TaskApprovalControls } from "./TaskApprovalControls";

function Counts({ title, counts }: { title: string; counts: StatusCounts }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      <div className="stack">
        <div className="row">
          <span className="label">Total</span>
          <strong>{counts.total}</strong>
        </div>
        {Object.entries(counts.by_status).map(([status, count]) => (
          <div className="row" key={status}>
            <span className="label">{status}</span>
            <strong>{count}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;

  try {
    const project = await titanFetch<ProjectOverview>(
      "/api/v1/control-plane/projects/" + projectId,
    );

    return (
      <main className="shell">
        <header className="topbar">
          <Link href="/" className="badge">
            ← Projects
          </Link>
          <span className="badge">{project.project.current_phase}</span>
        </header>

        <section className="hero">
          <p className="eyebrow">Project overview</p>
          <h1>{project.project.name}</h1>
          <p>{project.project.objective ?? "No objective defined."}</p>
          <div className="project-meta">
            <span className="badge">{project.project.status}</span>
            <span className="badge">
              autonomy {project.project.autonomy_level}/5
            </span>
            {project.state ? (
              <span className="badge">state v{project.state.version}</span>
            ) : null}
          </div>
        </section>

        <section className="detail-grid">
          <Counts title="Tasks" counts={project.task_counts} />
          <Counts title="Workflows" counts={project.workflow_counts} />

          <div className="card">
            <h2>Governance & approvals</h2>
            <div className="stack">
              <div className="row">
                <span className="label">Human decisions</span>
                <strong>{project.pending_human_decisions}</strong>
              </div>
              <div className="row">
                <span className="label">Task approvals</span>
                <strong>{project.pending_task_approvals}</strong>
              </div>
              <div className="row">
                <span className="label">Latest decisions</span>
                <strong>{project.governance_decisions.length}</strong>
              </div>
            </div>
          </div>

          <div className="card">
            <h2>Recovery</h2>
            <div className="stack">
              <div className="row">
                <span className="label">Started</span>
                <strong>{project.recovery.started}</strong>
              </div>
              <div className="row">
                <span className="label">Resolved</span>
                <strong>{project.recovery.resolved}</strong>
              </div>
              <div className="row">
                <span className="label">Resolution ratio</span>
                <strong>
                  {(project.recovery.resolved_ratio * 100).toFixed(1)}%
                </strong>
              </div>
              <div className="row">
                <span className="label">Latest outcome</span>
                <strong>{project.recovery.latest_outcome ?? "—"}</strong>
              </div>
            </div>
          </div>
        </section>

        <section className="detail-grid">
          <div className="card">
            <h2>Quality gate</h2>
            <div className="stack">
              <div className="row">
                <span className="label">Evaluations</span>
                <strong>{project.quality.evaluation_count}</strong>
              </div>
              <div className="row">
                <span className="label">Passed</span>
                <strong>{project.quality.passed_count}</strong>
              </div>
              <div className="row">
                <span className="label">Failed</span>
                <strong>{project.quality.failed_count}</strong>
              </div>
              <div className="row">
                <span className="label">Evidence</span>
                <strong>{project.quality.evidence_count}</strong>
              </div>
              <div className="row">
                <span className="label">Latest score</span>
                <strong>
                  {project.quality.latest_score === null
                    ? "—"
                    : (project.quality.latest_score * 100).toFixed(0) + "%"}
                </strong>
              </div>
              <div className="row">
                <span className="label">Unread alerts</span>
                <strong>{project.quality.unread_notification_count}</strong>
              </div>
            </div>
          </div>

          <div className="card">
            <h2>Self-repair</h2>
            <div className="stack">
              <div className="row">
                <span className="label">Repair attempts</span>
                <strong>{project.quality.repair_attempt_count}</strong>
              </div>
              <div className="row">
                <span className="label">Latest decision</span>
                <strong>{project.quality.latest_decision ?? "—"}</strong>
              </div>
              <div className="row">
                <span className="label">Latest evaluator</span>
                <strong>{project.evaluations[0]?.evaluator_type ?? "—"}</strong>
              </div>
            </div>
          </div>
        </section>

        <RecoveryControls
          projectId={projectId}
          actions={project.recovery_actions}
        />

        <TaskApprovalControls
          projectId={projectId}
          actions={project.task_approval_actions}
        />

        <section className="layout">
          <div className="card">
            <h2>Agents</h2>
            {project.agents.length === 0 ? (
              <p className="muted">No persisted agent assignments yet.</p>
            ) : (
              <div className="stack">
                {project.agents.map((agent) => (
                  <div className="row" key={agent.id}>
                    <div>
                      <strong>{agent.name}</strong>
                      <div className="muted">{agent.role}</div>
                    </div>
                    <span className="badge">{agent.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <h2>Latest task graph</h2>
            {project.latest_task_graph ? (
              <div className="stack">
                <strong>{project.latest_task_graph.name}</strong>
                <span className="muted">
                  v{project.latest_task_graph.version} ·{" "}
                  {project.latest_task_graph.status}
                </span>
                <span>{project.latest_task_graph.objective}</span>
              </div>
            ) : (
              <p className="muted">No task graph has been persisted yet.</p>
            )}
          </div>
        </section>

        <section className="layout">
          <div className="card">
            <h2>Recent evaluations</h2>
            {project.evaluations.length === 0 ? (
              <p className="muted">No evaluations recorded.</p>
            ) : (
              <div className="stack">
                {project.evaluations.slice(0, 10).map((evaluation) => (
                  <div className="event" key={evaluation.id}>
                    <div className="row">
                      <strong>{evaluation.decision}</strong>
                      <span className="badge">
                        {evaluation.score === null
                          ? "—"
                          : (evaluation.score * 100).toFixed(0) + "%"}
                      </span>
                    </div>
                    <div className="muted">
                      {evaluation.evaluator_type} ·{" "}
                      {evaluation.independent ? "independent" : "producer"} ·{" "}
                      repair {evaluation.repair_attempt}
                    </div>
                    <div className="muted">
                      {Object.entries(evaluation.criteria)
                        .map(([name, passed]) => name + ":" + (passed ? "pass" : "fail"))
                        .join(" · ")}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <h2>Repair loop</h2>
            {project.repair_attempts.length === 0 ? (
              <p className="muted">No repair attempts recorded.</p>
            ) : (
              <div className="stack">
                {project.repair_attempts.slice(0, 10).map((repair) => (
                  <div className="event" key={repair.id}>
                    <div className="row">
                      <strong>
                        attempt {repair.attempt}/{repair.max_attempts}
                      </strong>
                      <span className="badge">{repair.status}</span>
                    </div>
                    <div style={{ marginTop: 6 }}>{repair.diagnosis}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="layout">
          <LiveEvents
            projectId={projectId}
            initialEvents={project.recent_events}
          />

          <div className="card">
            <h2>Explainability</h2>
            <div className="stack">
              {project.explainability.slice(0, 10).map((item, index) => (
                <div className="event" key={item.occurred_at + item.event_type + index}>
                  <div className="row">
                    <strong>{item.stage}</strong>
                    <span className="muted">{item.event_type}</span>
                  </div>
                  <div style={{ marginTop: 6 }}>{item.summary}</div>
                </div>
              ))}
              {project.explainability.length === 0 ? (
                <p className="muted">No explainability entries recorded.</p>
              ) : null}
            </div>
          </div>
        </section>

        <section className="card" style={{ marginTop: 16 }}>
          <h2>Artifacts</h2>
          {project.artifacts.length === 0 ? (
            <p className="muted">No artifacts recorded.</p>
          ) : (
            <div className="project-list">
              {project.artifacts.map((artifact) => (
                <div className="project" key={artifact.id}>
                  <div>
                    <div className="project-title">{artifact.title}</div>
                    <div className="project-meta">
                      <span className="badge">{artifact.type}</span>
                      <span className="badge">{artifact.status}</span>
                      <span className="badge">v{artifact.version}</span>
                    </div>
                  </div>
                  <span className="muted">{artifact.media_type}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    );
  } catch (error) {
    return (
      <main className="shell">
        <div className="card error">
          <Link href="/" className="badge">← Projects</Link>
          <p className="eyebrow" style={{ marginTop: 18 }}>
            Project unavailable
          </p>
          <h1>Cannot load this project.</h1>
          <p className="muted" style={{ marginTop: 10 }}>
            {error instanceof Error ? error.message : "Unknown API error"}
          </p>
        </div>
      </main>
    );
  }
}
