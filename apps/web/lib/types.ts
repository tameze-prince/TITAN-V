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
  actor_subject: string | null;
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
  task_approval_actions: Array<{
    task_id: string;
    workflow_id: string;
    title: string;
    objective: string;
    risk_level: string;
    status: string;
    approval_quorum: number;
    approval_count: number;
    action: string;
    reason: string;
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
  evaluations: Array<{
    id: string;
    task_id: string | null;
    run_id: string | null;
    artifact_id: string | null;
    evaluator_type: string;
    evaluator_version: string;
    producer_agent: string | null;
    independent: boolean;
    decision: string;
    status: string;
    score: number | null;
    confidence: number;
    repair_attempt: number;
    criteria: Record<string, boolean>;
    created_at: string;
    completed_at: string | null;
  }>;
  repair_attempts: Array<{
    id: string;
    evaluation_id: string;
    task_id: string | null;
    attempt: number;
    max_attempts: number;
    diagnosis: string;
    corrective_action: string;
    status: string;
    created_at: string;
    started_at: string | null;
    completed_at: string | null;
  }>;
  quality: {
    evaluation_count: number;
    passed_count: number;
    failed_count: number;
    evidence_count: number;
    repair_attempt_count: number;
    unread_notification_count: number;
    latest_score: number | null;
    latest_decision: string | null;
  };
};


export type EvaluationCriterion = {
  id: string;
  profile_id: string;
  key: string;
  description: string;
  kind: string;
  weight: number;
  required: boolean;
  position: number;
  status: string;
};

export type EvaluationProfile = {
  id: string;
  name: string;
  scope_type: string;
  scope_id: string | null;
  version: number;
  status: string;
  evaluator_kind: string;
  evaluator_model: string | null;
  min_score: number;
  min_confidence: number;
  created_by: string;
  activated_at: string | null;
  criteria: EvaluationCriterion[];
};

export type OperatorNotification = {
  id: string;
  project_id: string;
  evaluation_id: string | null;
  task_id: string | null;
  severity: string;
  notification_type: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
};
