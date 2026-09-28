export type StatusCounts = {
  total: number;
  by_status: Record<string, number>;
};

export type ControlPlaneOverview = {
  projects: StatusCounts;
  tasks: StatusCounts;
  workflows: StatusCounts;
  agents: StatusCounts;
  artifacts: number;
  pending_human_decisions: number;
};

export type ProjectEvent = {
  id: string;
  type: string;
  actor_type: string;
  occurred_at: string;
};

export type ProjectSummary = {
  id: string;
  name: string;
  objective: string | null;
  status: string;
  current_phase: string;
  autonomy_level: number;
  updated_at: string;
  task_counts: StatusCounts;
  workflow_counts: StatusCounts;
};

export type ProjectOverview = {
  project: {
    id: string;
    name: string;
    objective: string | null;
    status: string;
    current_phase: string;
    autonomy_level: number;
  };
  state: {
    phase: string;
    status: string;
    version: number;
    state_json: Record<string, unknown>;
  } | null;
  task_counts: StatusCounts;
  workflow_counts: StatusCounts;
  agents: Array<{
    id: string;
    name: string;
    role: string;
    version: string;
    status: string;
  }>;
  artifacts: Array<{
    id: string;
    title: string;
    type: string;
    status: string;
    version: number;
    media_type: string;
    created_at: string;
  }>;
  recovery_actions: Array<{
    workflow_id: string;
    workflow_name: string;
    workflow_type: string;
    workflow_status: string;
    action: string;
    reason: string;
    current_attempt: number | null;
    failure_category: string | null;
  }>;
  governance_decisions: Array<{
    id: string;
    action: string;
    domain: string;
    allowed: boolean;
    requires_human: boolean;
    reason: string;
    created_at: string;
  }>;
  pending_human_decisions: number;
  pending_task_approvals: number;
  recent_events: ProjectEvent[];
  explainability: Array<{
    occurred_at: string;
    stage: string;
    event_type: string;
    summary: string;
  }>;
  recovery: {
    started: number;
    resolved: number;
    repeated_failures: number;
    escalated: number;
    failed_to_start: number;
    terminal_attempts: number;
    resolved_ratio: number;
    latest_outcome: string | null;
  };
  latest_task_graph: {
    id: string;
    name: string;
    version: number;
    status: string;
    objective: string;
    created_at: string;
  } | null;
};
