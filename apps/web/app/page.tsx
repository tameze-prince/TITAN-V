import Link from "next/link";

import { titanFetch } from "../lib/api";
import type {
  ControlPlaneOverview,
  OperatorSession,
  ProjectSummary,
} from "../lib/types";
import { AuthControls } from "./AuthControls";

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default async function HomePage() {
  try {
    const [overview, projects, session] = await Promise.all([
      titanFetch<ControlPlaneOverview>("/api/v1/control-plane/overview"),
      titanFetch<ProjectSummary[]>("/api/v1/control-plane/projects"),
      titanFetch<OperatorSession>("/api/v1/auth/session"),
    ]);

    return (
      <main className="shell">
        <header className="topbar">
          <div className="brand">
            <div className="brand-mark">TV</div>
            <div>
              <p className="eyebrow">TITAN V.</p>
              <strong>Command Center</strong>
            </div>
          </div>
          <AuthControls session={session} />
        </header>

        <section className="hero">
          <p className="eyebrow">Control plane</p>
          <h1>See what TITAN is doing.</h1>
          <p>
            A durable operator view over projects, workflows, agents, governance,
            artifacts and recovery. Execution remains inside the governed runtime.
          </p>
        </section>

        <section className="grid metrics">
          <Metric label="Projects" value={overview.projects.total} />
          <Metric label="Tasks" value={overview.tasks.total} />
          <Metric label="Workflows" value={overview.workflows.total} />
          <Metric label="Agents" value={overview.agents.total} />
          <Metric label="Artifacts" value={overview.artifacts} />
          <Metric label="Human decisions" value={overview.pending_human_decisions} />
        </section>

        <section className="layout">
          <div className="card">
            <h2>Projects</h2>
            {projects.length === 0 ? (
              <p className="muted">No project has been created yet.</p>
            ) : (
              <div className="project-list">
                {projects.map((project) => (
                  <Link
                    key={project.id}
                    className="project"
                    href={`/projects/${project.id}`}
                  >
                    <div>
                      <div className="project-title">{project.name}</div>
                      <div className="project-meta">
                        <span className="badge">{project.current_phase}</span>
                        <span className="badge">{project.status}</span>
                        <span className="badge">
                          autonomy {project.autonomy_level}/5
                        </span>
                      </div>
                      <p className="muted" style={{ marginTop: 10 }}>
                        {project.objective ?? "No objective defined."}
                      </p>
                    </div>
                    <div className="project-counts">
                      <strong>{project.task_counts.total}</strong>
                      <span className="muted">tasks</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <h2>Runtime status</h2>
            <div className="stack">
              <div className="row">
                <span className="label">Projects active</span>
                <strong>{overview.projects.by_status.ACTIVE ?? 0}</strong>
              </div>
              <div className="row">
                <span className="label">Tasks running</span>
                <strong>{overview.tasks.by_status.RUNNING ?? 0}</strong>
              </div>
              <div className="row">
                <span className="label">Workflows running</span>
                <strong>{overview.workflows.by_status.RUNNING ?? 0}</strong>
              </div>
              <div className="row">
                <span className="label">Agents active</span>
                <strong>{overview.agents.by_status.ACTIVE ?? 0}</strong>
              </div>
              <div className="row">
                <span className="label">Human decisions</span>
                <strong>{overview.pending_human_decisions}</strong>
              </div>
            </div>
          </div>
        </section>
      </main>
    );
  } catch (error) {
    return (
      <main className="shell">
        <div className="topbar">
          <div className="brand">
            <div className="brand-mark">TV</div>
            <div>
              <p className="eyebrow">TITAN V.</p>
              <strong>Command Center</strong>
            </div>
          </div>
          <AuthControls session={null} />
        </div>
        <div className="card error">
          <p className="eyebrow">Operator session required</p>
          <h1>Sign in to access the control plane.</h1>
          <p style={{ marginTop: 10 }}>
            Use the configured OIDC identity to open the governed operator surface.
          </p>
          <p className="muted" style={{ marginTop: 10 }}>
            {error instanceof Error ? error.message : "Authentication required"}
          </p>
        </div>
      </main>
    );
  }
}
